from __future__ import annotations
from dataclasses import dataclass, field


from typing import Protocol, runtime_checkable


@dataclass
class ClassificationResult:
    type_code: str               # e.g. 'spending', 'cc_payment', 'payroll'
    category_id: int
    category_name: str
    matched_by: str              # 'structural' | 'user_rule' | 'system_rule' | 'llm_cache' | 'llm' | 'pending_review'
    direction: str = "outbound"  # 'inbound' | 'outbound' | 'transfer'
    confidence: float = 1.0
    rule_id: int | None = None


@dataclass
class TransactionRow:
    id: str                  # SHA256 key from pipeline.utils.hash
    date: str                # ISO date string, e.g. '2024-03-15'
    description: str         # Raw description from source
    amount: float            # Always positive; direction encodes sign
    direction: str           # 'inbound' | 'outbound' | 'transfer'
    source: str              # Source key, e.g. 'amex-cobalt'
    raw: dict = field(default_factory=dict)  # Full silver row for adapter-specific field access


@runtime_checkable
class SourceAdapter(Protocol):
    """
    Interface for Step 1 of the classification chain: structural rules only.
    Steps 2–6 (user rules, system rules, LLM cache, LLM, pending review)
    are handled by classification/chain.py.
    """
    source_key: str  # Must match the 'source' column value in silver/gold tables

    def classify_structural(self, row: TransactionRow) -> ClassificationResult | None:
        """
        Apply hard-coded, always-correct rules for this source.
        Return None if no structural rule matches — the chain will continue.
        """
        ...

