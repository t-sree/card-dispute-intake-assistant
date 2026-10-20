import pytest
from pydantic import BaseModel

from card_dispute_intake.llm import FakeLLM


class Greeting(BaseModel):
    text: str


class Other(BaseModel):
    value: int


def test_fake_returns_queued_responses_in_order() -> None:
    llm = FakeLLM(Greeting(text="hi"), Greeting(text="bye"))

    assert llm.parse("sys", "first", Greeting).text == "hi"
    assert llm.parse("sys", "second", Greeting).text == "bye"
    assert llm.calls == [("sys", "first"), ("sys", "second")]


def test_fake_fails_when_empty() -> None:
    with pytest.raises(AssertionError, match="ran out"):
        FakeLLM().parse("sys", "user", Greeting)


def test_fake_checks_schema() -> None:
    with pytest.raises(AssertionError, match="expected Greeting"):
        FakeLLM(Other(value=1)).parse("sys", "user", Greeting)
