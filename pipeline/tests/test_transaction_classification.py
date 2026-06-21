"""
Unit tests for structural classification via ConfigurableAdapter.

Tests call classify_structural() directly — no SQL mirror functions.
A fake category_map is used so tests have no Postgres dependency.

Run with:  pytest tests/test_transaction_classification.py -v
"""
from __future__ import annotations
from pathlib import Path

import pytest

from pipeline.adapters.adapter import ConfigurableAdapter, build_registry, _extract_type_codes
from pipeline.adapters.base import ClassificationResult, SourceAdapter, TransactionRow
import yaml


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RULES_PATH = Path(__file__).parent.parent / "adapters" / "adapter_rules.yml"


def _load_rules() -> dict:
    with open(RULES_PATH) as f:
        return yaml.safe_load(f)


def _fake_category_map() -> dict[str, int]:
    """Assign sequential IDs to every type_code in adapter_rules.yml."""
    codes = _extract_type_codes(_load_rules())
    return {code: i + 1 for i, code in enumerate(sorted(codes))}


def _make_adapter(source_key: str) -> ConfigurableAdapter:
    rules = _load_rules()
    config = rules["sources"][source_key]
    return ConfigurableAdapter(source_key, config, _fake_category_map())


def _row(source: str, description: str, amount: float, raw: dict) -> TransactionRow:
    return TransactionRow(
        id="test",
        date="2024-01-01",
        description=description,
        amount=abs(amount),
        direction="outbound" if amount > 0 else "inbound",
        source=source,
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Protocol / registry checks
# ---------------------------------------------------------------------------

class TestRegistry:

    def test_all_adapters_satisfy_source_adapter_protocol(self):
        registry = build_registry(_fake_category_map(), rules_path=RULES_PATH)
        for source_key, adapter in registry.items():
            assert isinstance(adapter, SourceAdapter), f"{source_key} does not satisfy SourceAdapter"

    def test_all_four_sources_in_registry(self):
        registry = build_registry(_fake_category_map(), rules_path=RULES_PATH)
        assert set(registry.keys()) == {"amex-cobalt", "rbc-mastercard", "rbc-chequing", "wealthsimple-cash"}

    def test_adapter_accessible_by_source_key(self):
        registry = build_registry(_fake_category_map(), rules_path=RULES_PATH)
        adapter = registry["amex-cobalt"]
        assert adapter.source_key == "amex-cobalt"

    def test_validate_category_map_raises_on_missing_type_code(self):
        from pipeline.classification.rules import validate_category_map
        with pytest.raises(ValueError, match="missing type_codes"):
            validate_category_map({"spending": 1}, {"spending", "cc_payment"})

    def test_validate_category_map_passes_when_complete(self):
        from pipeline.classification.rules import validate_category_map
        cat_map = _fake_category_map()
        required = _extract_type_codes(_load_rules())
        validate_category_map(cat_map, required)  # must not raise


# ---------------------------------------------------------------------------
# Amex Cobalt
# ---------------------------------------------------------------------------

class TestAmexCobaltAdapter:

    def _adapter(self) -> ConfigurableAdapter:
        return _make_adapter("amex-cobalt")

    def _row(self, merchant: str, amount: float) -> TransactionRow:
        return _row("amex-cobalt", merchant, amount, {"merchant": merchant, "amount": amount})

    def test_payment_received(self):
        result = self._adapter().classify_structural(self._row("PAYMENT RECEIVED - THANK YOU", 500.0))
        assert result is not None
        assert result.category_name == "cc_payment"
        assert result.matched_by == "structural"

    def test_membership_fee(self):
        result = self._adapter().classify_structural(self._row("MEMBERSHIP FEE INSTALLMENT", 15.99))
        assert result is not None
        assert result.category_name == "fee"

    def test_use_points(self):
        result = self._adapter().classify_structural(self._row("Use Points for Purchases", 29.00))
        assert result is not None
        assert result.category_name == "cashback"

    def test_air_canada_points(self):
        result = self._adapter().classify_structural(self._row("Air Canada Pay with Points", 120.00))
        assert result is not None
        assert result.category_name == "cashback"

    def test_negative_amount_is_refund(self):
        result = self._adapter().classify_structural(self._row("SOME MERCHANT", -45.00))
        assert result is not None
        assert result.category_name == "refund"

    def test_regular_spend(self):
        result = self._adapter().classify_structural(self._row("LOBLAWS #1234", 87.32))
        assert result is not None
        assert result.category_name == "spending"

    def test_no_match_returns_result_not_none(self):
        # credit_card engine always returns a result (sign_rule fallback) — never None
        result = self._adapter().classify_structural(self._row("UNKNOWN MERCHANT", 10.00))
        assert result is not None


# ---------------------------------------------------------------------------
# RBC Mastercard
# ---------------------------------------------------------------------------

class TestRbcMastercardAdapter:

    def _adapter(self) -> ConfigurableAdapter:
        return _make_adapter("rbc-mastercard")

    def _row(self, description: str, cad: float) -> TransactionRow:
        return _row("rbc-mastercard", description, cad, {"description": description, "cad": cad})

    def test_payment_is_cc_payment(self):
        result = self._adapter().classify_structural(
            self._row("PAYMENT - THANK YOU / PAI EMENT - MERCI", 600.00)
        )
        assert result is not None
        assert result.category_name == "cc_payment"

    def test_positive_cad_is_refund(self):
        result = self._adapter().classify_structural(self._row("AMAZON REFUND", 39.99))
        assert result is not None
        assert result.category_name == "refund"

    def test_negative_cad_is_spending(self):
        result = self._adapter().classify_structural(self._row("SHELL #4567", -62.00))
        assert result is not None
        assert result.category_name == "spending"


# ---------------------------------------------------------------------------
# RBC Chequing
# ---------------------------------------------------------------------------

class TestRbcChequingAdapter:

    def _adapter(self) -> ConfigurableAdapter:
        return _make_adapter("rbc-chequing")

    def _row(self, description: str, cad: float) -> TransactionRow:
        return _row("rbc-chequing", description, cad, {"description": description, "cad": cad})

    def test_mastercard_payment_outbound(self):
        result = self._adapter().classify_structural(self._row("MASTERCARD PAYMENT", -450.00))
        assert result is not None
        assert result.category_name == "cc_payment"

    def test_amex_payment_outbound(self):
        result = self._adapter().classify_structural(self._row("AMEX PAYMENT", -200.00))
        assert result is not None
        assert result.category_name == "cc_payment"

    def test_e_transfer_out(self):
        result = self._adapter().classify_structural(self._row("E-TRANSFER SENT TO JANE DOE", -75.00))
        assert result is not None
        assert result.category_name == "e_transfer_out"

    def test_wealthsimple_outbound_is_account_transfer(self):
        result = self._adapter().classify_structural(self._row("ONLINE TRANSFER TO WEALTHSIMPLE", -1000.00))
        assert result is not None
        assert result.category_name == "account_transfer"

    def test_wealthsimple_inbound_is_account_transfer(self):
        result = self._adapter().classify_structural(self._row("INVESTMENT WS INVESTMENTS", 500.00))
        assert result is not None
        assert result.category_name == "account_transfer"

    def test_inbound_no_structural_match_returns_none(self):
        # Generic inbound with no wealthsimple keyword → defers to chain (step 2)
        result = self._adapter().classify_structural(self._row("MISC CREDIT", 100.00))
        assert result is None

    def test_generic_outbound_spending(self):
        result = self._adapter().classify_structural(self._row("SOME UNKNOWN DEBIT", -25.00))
        assert result is not None
        assert result.category_name == "spending"

    def test_e_transfer_not_matched_by_transfer_rule(self):
        # "e-transfer" must not fall through to the bare 'transfer' keyword rule
        result = self._adapter().classify_structural(self._row("E-TRANSFER OUT", -50.00))
        assert result is not None
        assert result.category_name == "e_transfer_out"

    def test_bill_payment(self):
        result = self._adapter().classify_structural(self._row("BILL PAYMENT TO ROGERS", -120.00))
        assert result is not None
        assert result.category_name == "bill_payment"


# ---------------------------------------------------------------------------
# Wealthsimple Cash
# ---------------------------------------------------------------------------

class TestWealthsimpleCashAdapter:

    def _adapter(self) -> ConfigurableAdapter:
        return _make_adapter("wealthsimple-cash")

    def _row(self, transaction: str, description: str, amount: float) -> TransactionRow:
        return _row(
            "wealthsimple-cash", description, amount,
            {"transaction": transaction, "description": description, "amount": amount},
        )

    def test_spend_is_spending(self):
        result = self._adapter().classify_structural(self._row("SPEND", "TIM HORTONS #1234", 4.75))
        assert result is not None
        assert result.category_name == "spending"

    def test_obp_out_is_bill_payment(self):
        result = self._adapter().classify_structural(self._row("OBP_OUT", "Bill payment to ROGERS", 120.00))
        assert result is not None
        assert result.category_name == "bill_payment"

    def test_aft_out_is_pre_auth_debit(self):
        result = self._adapter().classify_structural(self._row("AFT_OUT", "Pre-authorized debit", 29.99))
        assert result is not None
        assert result.category_name == "pre_auth_debit"

    def test_int_is_interest_earned(self):
        result = self._adapter().classify_structural(self._row("INT", "Interest earned", 6.31))
        assert result is not None
        assert result.category_name == "interest_earned"

    def test_cashback(self):
        result = self._adapter().classify_structural(self._row("CASHBACK", "Cashback reward", 12.50))
        assert result is not None
        assert result.category_name == "cashback"

    def test_eft_is_account_transfer(self):
        result = self._adapter().classify_structural(self._row("EFT", "Deposit", 5000.00))
        assert result is not None
        assert result.category_name == "account_transfer"

    def test_trfout_is_account_transfer(self):
        result = self._adapter().classify_structural(self._row("TRFOUT", "Transfer out", 1000.00))
        assert result is not None
        assert result.category_name == "account_transfer"

    def test_aft_in_defers_to_chain(self):
        # AFT_IN with no keyword match → None (chain step 2 resolves payroll/insurance)
        result = self._adapter().classify_structural(self._row("AFT_IN", "Deposit", 2614.00))
        assert result is None

    def test_e_trfin_defers_to_chain(self):
        result = self._adapter().classify_structural(
            self._row("E_TRFIN", "Interac e-Transfer Received", 27.50)
        )
        assert result is None

    def test_e_trfout_defers_to_chain(self):
        result = self._adapter().classify_structural(self._row("E_TRFOUT", "Payment to Alex", 50.00))
        assert result is None

    def test_p2p_sent_defers_to_chain(self):
        # P2P_SENT defers — type_code resolved to e_transfer_out by chain fallback, not structural
        result = self._adapter().classify_structural(self._row("P2P_SENT", "Payment to Alex", 50.00))
        assert result is None


# ---------------------------------------------------------------------------
# Transfer reconciliation edge cases (intent tests)
# ---------------------------------------------------------------------------

class TestTransferEdgeCases:

    def test_rbc_chequing_wealthsimple_inflow_is_transfer(self):
        adapter = _make_adapter("rbc-chequing")
        row = _row("rbc-chequing", "INVESTMENT WS INVESTMENTS", 500.00,
                   {"description": "INVESTMENT WS INVESTMENTS", "cad": 500.00})
        result = adapter.classify_structural(row)
        assert result is not None
        assert result.category_name == "account_transfer"

    def test_ws_aft_in_generic_deposit_defers(self):
        """Generic AFT_IN must defer — not classified as income by structural rules."""
        adapter = _make_adapter("wealthsimple-cash")
        row = _row("wealthsimple-cash", "Deposit", 2614.00,
                   {"transaction": "AFT_IN", "description": "Deposit", "amount": 2614.00})
        result = adapter.classify_structural(row)
        assert result is None, "AFT_IN must defer to chain; structural rules must not classify it as income"

    def test_ws_e_transfer_in_defers(self):
        adapter = _make_adapter("wealthsimple-cash")
        row = _row("wealthsimple-cash", "Interac e-Transfer Received", 27.50,
                   {"transaction": "E_TRFIN", "description": "Interac e-Transfer Received", "amount": 27.50})
        result = adapter.classify_structural(row)
        assert result is None
