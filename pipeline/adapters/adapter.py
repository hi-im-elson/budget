"""
ConfigurableAdapter — single adapter class that works for all sources.

Loaded once per source from adapter_rules.yml via build_registry().
The source_type field in config selects the correct engine.
"""
from __future__ import annotations
from pathlib import Path
import yaml

from pipeline.adapters.base import ClassificationResult, TransactionRow
from pipeline.adapters.engines import credit_card, cash_account


_ENGINE_MAP = {
    "credit_card":  credit_card.classify,
    "cash_account": cash_account.classify,
}


class ConfigurableAdapter:
    def __init__(self, source_key: str, config: dict, category_map: dict[str, int]) -> None:
        self.source_key = source_key
        self._config    = config
        self._cat       = category_map
        self._engine    = _ENGINE_MAP[config["source_type"]]

    def classify_structural(self, row: TransactionRow) -> ClassificationResult | None:
        return self._engine(row, self._config, self._cat)

    def classify_chain_fallback(self, row: TransactionRow) -> ClassificationResult | None:
        """
        Source-specific fallbacks applied after steps 2/3 (user/system rules) miss.

        Wealthsimple: keyed by transaction code (chain_fallbacks in config).
        RBC Chequing: keyword rules for inbound amounts (inbound_chain_fallbacks).
        """
        config    = self._config
        cat       = self._cat

        transaction_field = config.get("transaction_field")

        if transaction_field:
            txn_code = str(row.raw.get(transaction_field, "") or "")
            for fallback in config.get("chain_fallbacks", []):
                if fallback.get("code") == txn_code:
                    type_code = fallback["type_code"]
                    return ClassificationResult(
                        type_code=type_code,
                        category_id=cat[type_code],
                        category_name=type_code,
                        matched_by="structural",
                        direction=fallback.get("direction", "outbound"),
                    )
            return None

        # RBC-style: inbound_chain_fallbacks after classification_rules miss
        amount_field = config.get("amount_field")
        amount = float(row.raw.get(amount_field, 0) or 0) if amount_field else 0
        if amount > 0:
            desc = str(row.raw.get(config.get("merchant_field", "description"), "") or "").lower()
            return cash_account.apply_keyword_rules(desc, config.get("inbound_chain_fallbacks", []), cat)

        return None


def _extract_type_codes(rules: dict) -> set[str]:
    """Walk adapter_rules.yml and collect every type_code referenced across all sources."""
    codes: set[str] = set()
    for config in rules.get("sources", {}).values():
        for section_key in (
            "exact_matches", "sign_rules", "outbound_keyword_rules",
            "inbound_structural_rules", "inbound_chain_fallbacks",
            "transaction_code_rules", "chain_fallbacks",
        ):
            for rule in config.get(section_key, []):
                if tc := rule.get("type_code"):
                    codes.add(tc)
    return codes


def build_registry(
    category_map: dict[str, int] | None = None,
    rules_path: str | Path | None = None,
) -> dict[str, ConfigurableAdapter]:
    """
    Load adapter_rules.yml and instantiate one ConfigurableAdapter per source.
    Call at chain startup; category_map is loaded from Postgres if not provided.
    """
    if rules_path is None:
        rules_path = Path(__file__).parent / "adapter_rules.yml"

    with open(rules_path) as f:
        rules = yaml.safe_load(f)

    if category_map is None:
        from pipeline.classification.rules import load_category_map
        category_map = load_category_map()

    from pipeline.classification.rules import validate_category_map
    validate_category_map(category_map, _extract_type_codes(rules))

    registry: dict[str, ConfigurableAdapter] = {}
    for source_key, config in rules["sources"].items():
        if config["source_type"] not in _ENGINE_MAP:
            raise ValueError(f"Unknown source_type '{config['source_type']}' for source '{source_key}'")
        registry[source_key] = ConfigurableAdapter(source_key, config, category_map)

    return registry
