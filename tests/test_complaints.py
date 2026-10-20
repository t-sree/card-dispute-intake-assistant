from pathlib import Path
from typing import Any

import httpx

from card_dispute_intake.data.complaints import (
    Complaint,
    fetch_complaints,
    load_jsonl,
    save_jsonl,
)


def make_row(complaint_id: int) -> dict[str, Any]:
    return {
        "Complaint ID": complaint_id,
        "Date received": "2024-01-30",
        "Product": "Credit card",
        "Issue": "Problem with a purchase shown on your statement",
        "Sub-issue": "Card was charged for something you did not purchase with the card",
        "Company": "Example Bank",
        "Consumer complaint narrative": "  I never made this purchase.  ",
    }


def fake_client(total_rows: int, fail_first: bool = False) -> httpx.Client:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if fail_first and calls["count"] == 1:
            return httpx.Response(500, json={"error": "index loading"})
        offset = int(request.url.params["offset"])
        length = int(request.url.params["length"])
        ids = range(offset, min(offset + length, total_rows))
        return httpx.Response(200, json={"rows": [{"row": make_row(i)} for i in ids]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_from_row_maps_fields_and_strips_narrative() -> None:
    complaint = Complaint.from_row(make_row(42))
    assert complaint.complaint_id == "42"
    assert complaint.narrative == "I never made this purchase."


def test_fetch_pages_until_limit() -> None:
    complaints = list(fetch_complaints(limit=250, client=fake_client(total_rows=1000)))
    assert len(complaints) == 250
    assert complaints[-1].complaint_id == "249"


def test_fetch_stops_when_data_runs_out() -> None:
    complaints = list(fetch_complaints(limit=500, client=fake_client(total_rows=120)))
    assert len(complaints) == 120


def test_fetch_retries_server_errors(monkeypatch: Any) -> None:
    monkeypatch.setattr("card_dispute_intake.data.complaints.time.sleep", lambda _: None)
    complaints = list(fetch_complaints(limit=5, client=fake_client(10, fail_first=True)))
    assert len(complaints) == 5


def test_jsonl_round_trip(tmp_path: Path) -> None:
    original = [Complaint.from_row(make_row(i)) for i in range(3)]
    path = tmp_path / "complaints.jsonl"

    assert save_jsonl(iter(original), path) == 3
    assert load_jsonl(path) == original
