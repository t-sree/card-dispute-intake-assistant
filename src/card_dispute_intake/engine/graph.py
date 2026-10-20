"""LangGraph flow that runs after every customer message.

    extract -> match -> assess

- extract: the only LLM step. Re-reads the whole transcript and rebuilds the cases.
- match:   finds each case's disputed charge on the account (unless the agent confirmed one).
- assess:  runs the checklist and signal rules and produces suggestions for the agent.

State is checkpointed per conversation (thread_id), so each turn builds on the last one and
agent edits can be applied between turns. When the agent changes something by hand, the
session resumes the graph after `extract`, so no LLM call is needed.
"""

import operator
from datetime import date
from enum import StrEnum
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from card_dispute_intake import models
from card_dispute_intake.data.accounts import Account
from card_dispute_intake.engine.extraction import charge_details, extract, merge_cases
from card_dispute_intake.engine.matching import match_transaction
from card_dispute_intake.llm import LLMClient
from card_dispute_intake.models import DisputeCase, Message
from card_dispute_intake.rules.checker import check_case
from card_dispute_intake.rules.checklists import TRANSACTION
from card_dispute_intake.rules.signals import Signal, detect_signals

EXTRACT, MATCH, ASSESS = "extract", "match", "assess"


class SuggestionKind(StrEnum):
    PICK_TRANSACTION = "pick_transaction"
    SIGNAL = "signal"
    ASK = "ask"
    COMPLETE = "complete"


class Suggestion(BaseModel):
    case_id: str
    kind: SuggestionKind
    text: str
    field_name: str | None = None


class IntakeState(TypedDict, total=False):
    messages: Annotated[list[Message], operator.add]
    cases: list[DisputeCase]
    candidates: dict[str, list[str]]  # case_id -> transaction ids to pick from
    signals: dict[str, list[Signal]]  # case_id -> signals
    suggestions: list[Suggestion]


def _suggest(case: DisputeCase, candidates: list[str], signals: list[Signal]) -> list[Suggestion]:
    suggestions = [
        Suggestion(case_id=case.case_id, kind=SuggestionKind.SIGNAL, text=s.question)
        for s in signals
    ]
    result = check_case(case)
    if result.is_complete:
        text = "All required information collected. Review and submit the case."
        return [
            *suggestions,
            Suggestion(case_id=case.case_id, kind=SuggestionKind.COMPLETE, text=text),
        ]

    next_field = result.next_field
    assert next_field is not None
    if next_field is TRANSACTION and candidates:
        text = f"Confirm which of {len(candidates)} possible charges the customer means."
        suggestions.append(
            Suggestion(case_id=case.case_id, kind=SuggestionKind.PICK_TRANSACTION, text=text)
        )
        # Keep the conversation moving while the agent checks the charge.
        later = [f for f in result.missing if f is not TRANSACTION]
        next_field = later[0] if later else None
    if next_field is not None:
        suggestions.append(
            Suggestion(
                case_id=case.case_id,
                kind=SuggestionKind.ASK,
                text=next_field.question,
                field_name=next_field.name,
            )
        )
    return suggestions


def build_graph(
    llm: LLMClient,
    account: Account,
    today: date,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[IntakeState, None, IntakeState, IntakeState]:
    def extract_node(state: IntakeState) -> IntakeState:
        extraction = extract(llm, state["messages"], today)
        return {"cases": merge_cases(state.get("cases", []), extraction)}

    def match_node(state: IntakeState) -> IntakeState:
        cases, candidates = [], {}
        for case in state.get("cases", []):
            case = case.model_copy(deep=True)
            if not case.transaction_confirmed:
                merchant, amount, charge_date = charge_details(case)
                result = match_transaction(account, merchant, amount, charge_date)
                case.transaction_id = (
                    result.transaction.transaction_id if result.transaction else None
                )
                if result.transaction is None:
                    candidates[case.case_id] = [t.transaction_id for t in result.candidates]
            cases.append(case)
        return {"cases": cases, "candidates": candidates}

    def assess_node(state: IntakeState) -> IntakeState:
        signals: dict[str, list[Signal]] = {}
        suggestions: list[Suggestion] = []
        candidates = state.get("candidates", {})
        for case in state.get("cases", []):
            transaction = account.find(case.transaction_id) if case.transaction_id else None
            case_signals = detect_signals(case, transaction, account.transactions)
            signals[case.case_id] = case_signals
            suggestions += _suggest(case, candidates.get(case.case_id, []), case_signals)
        return {"signals": signals, "suggestions": suggestions}

    graph = StateGraph(IntakeState)
    graph.add_node(EXTRACT, extract_node)
    graph.add_node(MATCH, match_node)
    graph.add_node(ASSESS, assess_node)
    graph.add_edge(START, EXTRACT)
    graph.add_edge(EXTRACT, MATCH)
    graph.add_edge(MATCH, ASSESS)
    graph.add_edge(ASSESS, END)
    return graph.compile(checkpointer=checkpointer or new_checkpointer())


_STATE_TYPES = [
    models.CardNetwork,
    models.DisputeCase,
    models.DisputeType,
    models.Fact,
    models.FactSource,
    models.Message,
    models.Speaker,
    Signal,
    Suggestion,
    SuggestionKind,
]


def new_checkpointer() -> InMemorySaver:
    """In-memory checkpoints, with our state types explicitly allowed for deserialization."""
    allowed = [(t.__module__, t.__name__) for t in _STATE_TYPES]
    return InMemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=allowed))
