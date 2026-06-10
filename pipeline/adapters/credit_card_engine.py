"""
Credit card engine — fully structural, no chain deferrals.

Evaluation order per row:
  1. exact_matches on merchant_field (case-sensitive, matches SQL exactly)
  2. sign_rules on amount_field (negative / positive)
"""
from __future__ import annotations
from pipeline.adapters.base import ClassificationResult, TransactionRow


def classify(row: TransactionRow, config: dict, category_map: dict[str, int]) -> ClassificationResult:
    amount_field   = config["amount_field"]
    merchant_field = config["merchant_field"]

    merchant = str(row.raw.get(merchant_field, "") or "")
    amount   = float(row.raw.get(amount_field, 0) or 0)

    # 1. Exact merchant matches
    for rule in config.get("exact_matches", []):
        if merchant == rule["merchant"]:
            type_code = rule["type_code"]
            return ClassificationResult(
                category_id=category_map[type_code],
                category_name=type_code,
                matched_by="structural",
            )

    # 2. Amount-sign fallback rules
    for rule in config.get("sign_rules", []):
        if rule["condition"] == "negative" and amount < 0:
            type_code = rule["type_code"]
            return ClassificationResult(
                category_id=category_map[type_code],
                category_name=type_code,
                matched_by="structural",
            )
        if rule["condition"] == "positive" and amount >= 0:
            type_code = rule["type_code"]
            return ClassificationResult(
                category_id=category_map[type_code],
                category_name=type_code,
                matched_by="structural",
            )

    # Should never reach here if config has a fallback sign_rule, but be safe
    return ClassificationResult(
        category_id=category_map["spending"],
        category_name="spending",
        matched_by="structural",
    )
