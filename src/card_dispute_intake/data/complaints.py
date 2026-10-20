"""Fetch credit card dispute complaints with consumer narratives.

The CFPB no longer serves narratives through its own API or bulk CSV, so we read a CC0
snapshot of the database hosted on Hugging Face, through the datasets-server filter API.
This avoids downloading the full 1.7M-row dataset. See docs/data.md.

Usage:
    uv run python -m card_dispute_intake.data.complaints --limit 500
"""

import argparse
import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

FILTER_URL = "https://datasets-server.huggingface.co/filter"
DATASET = "BEE-spoke-data/consumer-finance-complaints"
CONFIG = "has-text"
PAGE_SIZE = 100  # max the API allows

DISPUTE_FILTER = (
    "(\"Product\"='Credit card' OR \"Product\"='Credit card or prepaid card') "
    "AND \"Issue\"='Problem with a purchase shown on your statement'"
)

DEFAULT_OUTPUT = Path("data/raw/complaints.jsonl")


class Complaint(BaseModel):
    complaint_id: str
    date_received: str
    product: str
    issue: str
    sub_issue: str | None
    company: str
    narrative: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Complaint":
        return cls(
            complaint_id=str(row["Complaint ID"]),
            date_received=row["Date received"],
            product=row["Product"],
            issue=row["Issue"],
            sub_issue=row.get("Sub-issue"),
            company=row["Company"],
            narrative=row["Consumer complaint narrative"].strip(),
        )


def _get_page(client: httpx.Client, offset: int, length: int) -> dict[str, Any]:
    params: dict[str, str | int] = {
        "dataset": DATASET,
        "config": CONFIG,
        "split": "train",
        "where": DISPUTE_FILTER,
        "offset": offset,
        "length": length,
    }
    for attempt in range(5):
        response = client.get(FILTER_URL, params=params)
        # The server returns 5xx while it (re)builds its index; back off and retry.
        if response.status_code < 500:
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data
        time.sleep(2**attempt)
    response.raise_for_status()
    raise RuntimeError("unreachable")


def fetch_complaints(limit: int, client: httpx.Client | None = None) -> Iterator[Complaint]:
    owns_client = client is None
    client = client or httpx.Client(timeout=60)
    try:
        offset = 0
        while offset < limit:
            page = _get_page(client, offset, min(PAGE_SIZE, limit - offset))
            rows = page["rows"]
            if not rows:
                return
            for item in rows:
                yield Complaint.from_row(item["row"])
            offset += len(rows)
    finally:
        if owns_client:
            client.close()


def save_jsonl(complaints: Iterator[Complaint], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for complaint in complaints:
            f.write(complaint.model_dump_json() + "\n")
            count += 1
    return count


def load_jsonl(path: Path) -> list[Complaint]:
    with path.open(encoding="utf-8") as f:
        return [Complaint.model_validate(json.loads(line)) for line in f if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    count = save_jsonl(fetch_complaints(args.limit), args.output)
    print(f"Saved {count} complaints to {args.output}")


if __name__ == "__main__":
    main()
