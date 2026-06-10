"""
Cash account engine — bi-directional amounts.

Two sub-strategies depending on whether the source has a transaction_field:

  Wealthsimple (has transaction_field):
    1. Look up transaction code in transaction_code_rules
       - defer=false → return ClassificationResult immediately
       - defer=true  → return None (chain steps 2/3 resolve; fallback in chain_fallbacks)
    2. Apply direction_overrides on top of the resolved type_code

  RBC Chequing (no transaction_field, uses amount sign + keyword matching):
    Outbound (amount < 0):
      Iterate outbound_keyword_rules in order; first keyword hit wins.
      exclude_keywords prevents a rule from matching when a keyword is present.
      Last rule may be a bare fallback.
    Inbound (amount > 0):
      Check inbound_structural_rules first.
      No match → return None (chain step 2 resolves via classification_rules).
      Chain orchestrator applies inbound_chain_fallbacks after all chain steps miss.
"""
from __future__ import annotations
from pipeline.adapters.base import ClassificationResult, TransactionRow


def _keyword_match(desc: str, keywords: list[str], exclude: list[str] | None = None) -> bool:
    if any(kw in desc for kw in keywords):
        if exclude and any(ex in desc for ex in exclude):
            return False
        return True
    return False


def _apply_keyword_rules(
    desc: str,
    rules: list[dict],
    category_map: dict[str, int],
) -> ClassificationResult | None:
    for rule in rules:
        if "fallback" in rule:
            type_code = rule["type_code"]
            return ClassificationResult(
                category_id=category_map[type_code],
                category_name=type_code,
                matched_by="structural",
            )
        if _keyword_match(desc, rule["keywords"], rule.get("exclude_keywords")):
            type_code = rule["type_code"]
            return ClassificationResult(
                category_id=category_map[type_code],
                category_name=type_code,
                matched_by="structural",
            )
    return None


def classify(
    row: TransactionRow,
    config: dict,
    category_map: dict[str, int],
) -> ClassificationResult | None:
    amount_field      = config["amount_field"]
    transaction_field = config.get("transaction_field")
    amount            = float(row.raw.get(amount_field, 0) or 0)

    # Wealthsimple-style: transaction code drives classification
    if transaction_field:
        txn_code = str(row.raw.get(transaction_field, "") or "")
        desc     = str(row.raw.get(config["merchant_field"], "") or "").lower()

        for rule in config.get("transaction_code_rules", []):
            if txn_code not in rule["codes"]:
                continue

            if rule.get("defer"):
                return None   # hand off to chain steps 2/3

            type_code = rule["type_code"]
            direction = rule["direction"]

            # Apply any direction overrides (e.g. OBP_OUT + CC keyword → transfer)
            for override in config.get("direction_overrides", []):
                if override["code"] == txn_code and any(kw in desc for kw in override["keywords"]):
                    direction = override["direction"]
                    break

            return ClassificationResult(
                category_id=category_map[type_code],
                category_name=type_code,
                matched_by="structural",
            )

        # Unknown transaction code — safe fallback
        return ClassificationResult(
            category_id=category_map["spending"],
            category_name="spending",
            matched_by="structural",
        )

    # RBC-style: amount sign + keyword matching
    desc = str(row.raw.get(config["merchant_field"], "") or "").lower()

    if amount < 0:
        return _apply_keyword_rules(desc, config.get("outbound_keyword_rules", []), category_map)

    if amount > 0:
        result = _apply_keyword_rules(desc, config.get("inbound_structural_rules", []), category_map)
        if result is not None:
            return result
        return None   # defer to chain step 2 (classification_rules)

    return None
