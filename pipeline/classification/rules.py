from __future__ import annotations
import logging
from dataclasses import dataclass

from pipeline.utils.postgres import fetchall
from pipeline.adapters.base import ClassificationResult, TransactionRow

logger = logging.getLogger(__name__)


@dataclass
class CompiledRule:
    """A rule loaded from Postgres, ready to match against a TransactionRow."""
    id: int
    rule_type: str
    match_value: str
    source: str | None
    category_id: int
    category_name: str
    priority: int
    origin: str  # 'user_rule' | 'system_rule'


def load_category_map() -> dict[str, int]:
    """
    Build {type_code: category_id} by joining the canonical type_code→category_name
    mapping against the live categories table in Postgres.

    Grounded in Postgres — survives re-seeds without hardcoded IDs.
    Call once at chain startup and pass the result to build_registry() and apply_rules().
    """
    rows = fetchall("""
        SELECT dtc.type_code, c.id AS category_id
        FROM (VALUES
            ('spending',                'Miscellaneous'),
            ('pre_auth_debit',          'Utilities'),
            ('bill_payment',            'Utilities'),
            ('fee',                     'Fees'),
            ('interest_charge',         'Fees'),
            ('e_transfer_out',          'Transfers'),
            ('p2p',                     'Transfers'),
            ('rent',                    'Rent'),
            ('parking',                 'Transportation'),
            ('payroll',                 'Income'),
            ('insurance_reimbursement', 'Income'),
            ('reimbursement',           'Income'),
            ('e_transfer_in',           'Income'),
            ('deposit',                 'Income'),
            ('government_deposit',      'Income'),
            ('interest_earned',         'Income'),
            ('cashback',                'Income'),
            ('refund',                  'Income'),
            ('cc_payment',              'Transfers'),
            ('account_transfer',        'Transfers'),
            ('investment',              'Transfers')
        ) AS dtc(type_code, category_name)
        JOIN categories c ON c.name = dtc.category_name
    """)
    return {r["type_code"]: r["category_id"] for r in rows}


def validate_category_map(category_map: dict[str, int], required_type_codes: set[str]) -> None:
    """
    Fail fast at startup if any adapter type_code has no matching Postgres category.
    Call after load_category_map(), before build_registry() instantiates adapters.
    """
    missing = required_type_codes - category_map.keys()
    if missing:
        raise ValueError(
            f"category_map is missing type_codes: {sorted(missing)}. "
            "Check that categories table is seeded and load_category_map() VALUES are complete."
        )


def load_rules() -> list[CompiledRule]:
    """Load all active rules from Postgres ordered by priority DESC. Call once at startup."""
    rows = fetchall("""
        SELECT
            ur.id,
            ur.rule_type,
            ur.match_value,
            ur.source,
            ur.category_id,
            c.name AS category_name,
            ur.priority,
            'user_rule' AS origin
        FROM user_rules ur
        JOIN categories c ON c.id = ur.category_id

        UNION ALL

        SELECT
            sr.id,
            sr.rule_type,
            sr.keyword AS match_value,
            sr.source,
            sr.category_id,
            c.name AS category_name,
            sr.priority,
            'system_rule' AS origin
        FROM system_rules sr
        JOIN categories c ON c.id = sr.category_id
        WHERE sr.category_id IS NOT NULL

        ORDER BY priority DESC
    """)
    return [CompiledRule(**r) for r in rows]


def apply_rules(row: TransactionRow, rules: list[CompiledRule]) -> ClassificationResult | None:
    """
    Apply rules in priority order. Return the first match, or None.
    Steps 2 (user_rules) and 3 (system_rules) share this — priority ordering handles precedence.

    Rules don't carry a type_code, so type_code is set to category_name as a stable identifier.
    Direction is left as the default ('outbound') — _resolve_direction in fact_transactions
    derives the correct value from the signed amount for rule-matched rows.
    """
    for rule in rules:
        if rule.source and rule.source != row.source:
            continue
        if _matches(rule, row):
            return ClassificationResult(
                type_code=rule.category_name,  # best proxy available from rule data
                category_id=rule.category_id,
                category_name=rule.category_name,
                matched_by=rule.origin,
                confidence=1.0,
                rule_id=rule.id,
            )
    return None


def _matches(rule: CompiledRule, row: TransactionRow) -> bool:
    desc = row.description.upper()
    val = rule.match_value.upper()
    match rule.rule_type:
        case "merchant_exact":
            return desc == val
        case (
            "description_contains"
            | "keyword_classification"
            | "keyword_subscription"
            | "etransfer_pattern"
            | "etransfer_recipient"
            | "merchant_parent"
        ):
            return val in desc
        case _:
            logger.warning("Unknown rule_type %r — skipping rule id=%s", rule.rule_type, rule.id)
            return False
