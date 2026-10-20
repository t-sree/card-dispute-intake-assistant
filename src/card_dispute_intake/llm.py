"""Thin LLM interface so the engine never depends on a specific provider.

The only thing we ask an LLM for is structured output: a prompt in, a validated pydantic
object out. Tests use FakeLLM; the app uses OpenAIClient.
"""

import os
from collections import deque
from typing import Protocol, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "gpt-5.4-mini"


class LLMClient(Protocol):
    def parse(self, system: str, user: str, schema: type[T]) -> T: ...


class OpenAIClient:
    def __init__(self, model: str | None = None, client: OpenAI | None = None) -> None:
        load_dotenv()
        self.model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self._client = client or OpenAI()

    def parse(self, system: str, user: str, schema: type[T]) -> T:
        response = self._client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text_format=schema,
        )
        if response.output_parsed is None:
            raise RuntimeError(f"{self.model} returned no parsable output for {schema.__name__}")
        return response.output_parsed


class FakeLLM:
    """Returns queued responses in order and records the prompts it was given."""

    def __init__(self, *responses: BaseModel) -> None:
        self._responses = deque(responses)
        self.calls: list[tuple[str, str]] = []

    def parse(self, system: str, user: str, schema: type[T]) -> T:
        self.calls.append((system, user))
        if not self._responses:
            raise AssertionError("FakeLLM ran out of queued responses")
        response = self._responses.popleft()
        if not isinstance(response, schema):
            raise AssertionError(f"queued {type(response).__name__}, expected {schema.__name__}")
        return response
