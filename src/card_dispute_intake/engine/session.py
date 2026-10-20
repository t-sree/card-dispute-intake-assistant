"""One agent-customer conversation. This is what the UI talks to."""

from datetime import date
from uuid import uuid4

from langchain_core.runnables import RunnableConfig

from card_dispute_intake.data.accounts import Account
from card_dispute_intake.engine.graph import ASSESS, EXTRACT, IntakeState, build_graph
from card_dispute_intake.engine.summary import CaseSummary, summarize
from card_dispute_intake.llm import LLMClient
from card_dispute_intake.models import DisputeCase, FactSource, Message, Speaker
from card_dispute_intake.rules.checklists import TRANSACTION, checklist_for


class IntakeSession:
    def __init__(self, llm: LLMClient, account: Account, today: date) -> None:
        self.account = account
        self.today = today
        self._graph = build_graph(llm, account, today)
        self._config: RunnableConfig = {"configurable": {"thread_id": uuid4().hex}}
        self._graph.update_state(self._config, {"messages": [], "cases": []}, as_node=ASSESS)

    @property
    def state(self) -> IntakeState:
        values: IntakeState = self._graph.get_state(self._config).values  # type: ignore[assignment]
        return values

    @property
    def messages(self) -> list[Message]:
        return self.state.get("messages", [])

    @property
    def cases(self) -> list[DisputeCase]:
        return self.state.get("cases", [])

    def agent_says(self, text: str) -> None:
        """Agent turns are context for the next extraction; they don't trigger one."""
        message = Message(speaker=Speaker.AGENT, text=text)
        self._graph.update_state(self._config, {"messages": [message]}, as_node=ASSESS)

    def customer_says(self, text: str) -> IntakeState:
        message = Message(speaker=Speaker.CUSTOMER, text=text)
        self._graph.invoke({"messages": [message]}, self._config)
        return self.state

    def confirm_transaction(self, case_id: str, transaction_id: str) -> IntakeState:
        if self.account.find(transaction_id) is None:
            raise ValueError(f"{transaction_id} is not on account {self.account.account_id}")
        case = self._case(case_id)
        case.transaction_id = transaction_id
        case.transaction_confirmed = True
        return self._rerun_rules(case)

    def set_fact(self, case_id: str, name: str, raw_value: str) -> IntakeState:
        """Agent enters or corrects a fact by hand. Agent facts are never overwritten."""
        case = self._case(case_id)
        assert case.dispute_type is not None
        field = next(
            (
                f
                for f in checklist_for(case.dispute_type)
                if f.name == name and f is not TRANSACTION
            ),
            None,
        )
        if field is None:
            raise ValueError(f"{name} is not a field for {case.dispute_type} disputes")
        value = field.parse(raw_value)
        if value is None:
            raise ValueError(f"{raw_value!r} is not a valid value for {name}")
        case.set_fact(name, value, FactSource.AGENT)
        return self._rerun_rules(case)

    def summaries(self) -> list[CaseSummary]:
        return [s for c in self.cases if (s := summarize(c, self.account, self.today))]

    def _case(self, case_id: str) -> DisputeCase:
        for case in self.cases:
            if case.case_id == case_id:
                return case.model_copy(deep=True)
        raise KeyError(case_id)

    def _rerun_rules(self, changed: DisputeCase) -> IntakeState:
        """Write the edited case back and resume after `extract`, skipping the LLM."""
        cases = [changed if c.case_id == changed.case_id else c for c in self.cases]
        self._graph.update_state(self._config, {"cases": cases}, as_node=EXTRACT)
        self._graph.invoke(None, self._config)
        return self.state
