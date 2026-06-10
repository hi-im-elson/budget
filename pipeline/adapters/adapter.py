"""
ConfigurableAdapter — single adapter class that works for all sources.

Loaded once per source from adapter_rules.yml via build_registry().
The source_type field in config selects the correct engine.
"""
from __future__ import annotations
from pathlib import Path
import yaml

from pipeline.adapters.base import ClassificationResult, SourceAdapter, TransactionRow  # noqa: F401
from pipeline.adapters.engines import credit_card, cash_account


_ENGINE_MAP = {
    "credit_card":  credit_card.classify,
    "cash_account": cash_account.classify,
}


class ConfigurableAdapter:
    def __init__(self, source_key: str, config: dict, category_map: dict[str, int]) -> None:
        self.source_key  = source_key
        self._config     = config
        self._cat        = category_map
        self._engine     = _ENGINE_MAP[config["source_type"]]

    def classify_structural(self, row: TransactionRow) -> ClassificationResult | None:
        return self._engine(row, self._config, self._cat)


def build_registry(
    category_map: dict[str, int],
    rules_path: str | Path | None = None,
) -> dict[str, ConfigurableAdapter]:
    """
    Load adapter_rules.yml and instantiate one ConfigurableAdapter per source.
    Call at chain startup after the category_map has been fetched from Postgres.

    Returns:
        {source_key: ConfigurableAdapter}
    """
    if rules_path is None:
        rules_path = Path(__file__).parent.parent.parent / "resources" / "adapter_rules.yml"

    with open(rules_path) as f:
        rules = yaml.safe_load(f)

    registry: dict[str, ConfigurableAdapter] = {}
    for source_key, config in rules["sources"].items():
        if config["source_type"] not in _ENGINE_MAP:
            raise ValueError(f"Unknown source_type '{config['source_type']}' for source '{source_key}'")
        registry[source_key] = ConfigurableAdapter(source_key, config, category_map)

    return registry
