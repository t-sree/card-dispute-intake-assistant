# Data

## Complaint narratives (real customer language)

Source: the [CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/), public domain.

As of October 2026 the CFPB API and bulk CSV no longer include the consumer narrative column, only the structured fields. Narratives are still available in a CC0 snapshot of the database on Hugging Face ([BEE-spoke-data/consumer-finance-complaints](https://huggingface.co/datasets/BEE-spoke-data/consumer-finance-complaints), `has-text` config). We query it through the Hugging Face datasets-server filter API instead of downloading all 1.7M rows.

Filter: product is `Credit card` or `Credit card or prepaid card`, and issue is `Problem with a purchase shown on your statement` (about 29k complaints).

```bash
uv run python -m card_dispute_intake.data.complaints --limit 3000
```

Output goes to `data/raw/complaints.jsonl` (git-ignored). Narratives are already redacted by the CFPB (`XXXX`).

### Tagging

`data/tagging.py` assigns a likely dispute type with keyword rules. It is only used to choose a balanced sample for conversation simulation. It is noisy on purpose: for example, "fraudulent recurring charge" gets tagged as a cancelled subscription. Evaluation uses hand labels, not these tags.

Distribution on the first 3,000 complaints:

| Tag | Count |
|---|---|
| unauthorized | 851 |
| not_received | 556 |
| credit_not_processed | 274 |
| cancelled_recurring | 37 |
| untagged | 1,282 |

## Account data (synthetic)

`data/accounts.py` generates seeded card accounts: 2–4 monthly subscriptions billed on a fixed day plus about one everyday purchase a day, over a 90-day window. Merchant names are made up. The same seed always gives the same account.
