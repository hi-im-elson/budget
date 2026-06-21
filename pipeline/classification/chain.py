"""
ClassificationChain — orchestrates the 6-step classification pipeline.

Phase 2 implements steps 1–3 (structural → user rules → system rules).
Steps 4–6 (LLM cache, LLM, pending review) are stubs returning None.

All Postgres I/O happens once in __init__. classify() is pure in-memory.
"""
from __future__ import annotations

from pipeline.adapters.adapter import ConfigurableAdapter, build_registry
from pipeline.adapters.base import ClassificationResult, TransactionRow
from pipeline.classification.rules import CompiledRule, apply_rules, load_category_map, load_rules
from pipeline.utils.logger import get_logger

logger = get_logger(__name__)


class ClassificationChain:
    """
    Instantiate once per pipeline run, then call classify() per transaction.
    __init__ makes all Postgres calls; classify() is pure in-memory.
    """

    def __init__(self) -> None:
        category_map = load_category_map()
        self._registry: dict[str, ConfigurableAdapter] = build_registry(category_map)
        self._rules: list[CompiledRule] = load_rules()
        logger.info("ClassificationChain ready: %d adapters, %d rules", len(self._registry), len(self._rules))

    def classify(self, row: TransactionRow) -> ClassificationResult:
        """Run the chain. Always returns a result — never raises."""
        result = (
            self._step_structural(row)
            or self._step_rules(row)
            or self._step_chain_fallback(row)
            or self._step_llm_cache(row)
            or self._step_llm(row)
            or self._step_pending_review(row)
            or self._fallback(row)
        )
        logger.debug(
            "[%s] '%s' → %s (%s / %s)",
            row.source, row.description[:40], result.type_code, result.matched_by, result.direction,
        )
        return result

    def _step_structural(self, row: TransactionRow) -> ClassificationResult | None:
        adapter = self._registry.get(row.source)
        if not adapter:
            logger.warning("No adapter registered for source: %s", row.source)
            return None
        return adapter.classify_structural(row)

    def _step_rules(self, row: TransactionRow) -> ClassificationResult | None:
        return apply_rules(row, self._rules)

    def _step_chain_fallback(self, row: TransactionRow) -> ClassificationResult | None:
        adapter = self._registry.get(row.source)
        if not adapter:
            return None
        return adapter.classify_chain_fallback(row)

    def _step_llm_cache(self, row: TransactionRow) -> ClassificationResult | None:
        return None  # Phase 3

    def _step_llm(self, row: TransactionRow) -> ClassificationResult | None:
        return None  # Phase 3

    def _step_pending_review(self, row: TransactionRow) -> ClassificationResult | None:
        return None  # Phase 3

    def _fallback(self, row: TransactionRow) -> ClassificationResult:
        logger.warning("No classification for [%s] '%s' — marking unclassified", row.source, row.description)
        return ClassificationResult(
            type_code="unclassified",
            category_id=-1,
            category_name="unclassified",
            matched_by="fallback",
            direction="outbound",
            confidence=0.0,
        )
