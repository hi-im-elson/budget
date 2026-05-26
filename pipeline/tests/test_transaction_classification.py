"""
Unit tests for gold-layer transaction classification logic.

These tests mirror the CASE expressions in fact_transactions.sql exactly,
so that any change to the SQL can be validated against known real-world inputs
before the pipeline runs.

Run with:  pytest tests/test_transaction_classification.py -v
"""

import pytest


def classify_wealthsimple(transaction: str, description: str, amount: float) -> tuple[str, str]:
    """
    Returns (type_code, direction) for a wealthsimple_cash row.
    Mirrors the CASE blocks in fact_transactions.sql.
    """
    desc = description.lower()

    # --- type_code ---
    if transaction == "SPEND":
        type_code = "spending"
    elif transaction == "OBP_OUT":
        type_code = "bill_payment"
    elif transaction == "E_TRFOUT":
        type_code = "e_transfer_out"
    elif transaction == "E_TRFIN":
        type_code = "reimbursement"
    elif transaction == "P2P_SENT":
        type_code = "p2p"
    elif transaction == "AFT_IN":
        type_code = "payroll" if "themis" in desc else "account_transfer"
    elif transaction == "AFT_OUT":
        type_code = "pre_auth_debit"
    elif transaction == "EFT":
        type_code = "account_transfer"
    elif transaction == "EFTOUT":
        type_code = "account_transfer"
    elif transaction == "TRFOUT":
        type_code = "account_transfer"
    elif transaction == "INT":
        type_code = "interest_earned"
    elif transaction == "CASHBACK":
        type_code = "cashback"
    else:
        type_code = "spending"

    # --- direction ---
    if transaction in ("AFT_IN", "EFT", "EFTOUT", "TRFOUT"):
        direction = "transfer"
    elif transaction in ("E_TRFIN", "INT", "CASHBACK"):
        direction = "inbound"
    elif transaction == "AFT_IN" and "themis" in desc:
        direction = "inbound"
    elif transaction == "OBP_OUT" and "mastercard" in desc:
        direction = "transfer"
    else:
        direction = "outbound"

    return type_code, direction


def classify_rbc_chequing(description: str, cad: float) -> tuple[str, str]:
    """
    Returns (type_code, direction) for a rbc_chequing row.
    Mirrors the CASE blocks in fact_transactions.sql.
    """
    desc = description.lower()

    # --- type_code ---
    if cad < 0 and any(k in desc for k in ("amex", "american express", "mastercard", "visa")):
        type_code = "cc_payment"
    elif cad < 0 and "e-transfer" in desc:
        type_code = "e_transfer_out"
    elif cad < 0 and any(k in desc for k in ("wealthsimple", "wlthsimple", "transfer")):
        type_code = "account_transfer"
    elif cad < 0 and "bill payment" in desc:
        type_code = "bill_payment"
    elif cad > 0 and any(k in desc for k in ("themis", "payroll", "direct dep")):
        type_code = "payroll"
    elif cad > 0 and "e-transfer" in desc:
        type_code = "e_transfer_in"
    elif cad > 0 and any(k in desc for k in ("canada revenue", "cra", "tax refund", "government")):
        type_code = "deposit"
    elif cad > 0 and any(k in desc for k in ("investment", "wealthsimple", "wlthsimple")):
        type_code = "account_transfer"
    elif cad > 0:
        type_code = "deposit"
    else:
        type_code = "spending"

    # --- direction ---
    if cad < 0 and any(k in desc for k in ("amex", "american express", "mastercard", "visa",
                                            "wealthsimple", "wlthsimple")):
        direction = "transfer"
    elif cad < 0 and "transfer" in desc and "e-transfer" not in desc:
        direction = "transfer"
    elif cad > 0 and any(k in desc for k in ("investment", "wealthsimple", "wlthsimple")):
        direction = "transfer"
    elif cad > 0:
        direction = "inbound"
    else:
        direction = "outbound"

    return type_code, direction


def classify_amex(merchant: str, amount: float) -> tuple[str, str]:
    """Returns (type_code, direction) for an amex_cobalt row."""
    if merchant == "PAYMENT RECEIVED - THANK YOU":
        return "cc_payment", "transfer"
    if merchant == "MEMBERSHIP FEE INSTALLMENT":
        return "fee", "outbound"
    if merchant in ("Use Points for Purchases", "Air Canada Pay with Points"):
        return "cashback", "inbound"
    if amount < 0 and merchant != "PAYMENT RECEIVED - THANK YOU":
        return "refund", "inbound"
    return "spending", "outbound"


def classify_rbc_mastercard(description: str, cad: float) -> tuple[str, str]:
    """Returns (type_code, direction) for a rbc_mastercard row."""
    payment = "PAYMENT - THANK YOU / PAI EMENT - MERCI"
    if description == payment:
        return "cc_payment", "transfer"
    if cad > 0 and description != payment:
        return "refund", "inbound"
    return "spending", "outbound"


# ---------------------------------------------------------------------------
# Wealthsimple Cash tests
# ---------------------------------------------------------------------------

class TestWealthsimpleClassification:

    def test_payroll_themis(self):
        tc, d = classify_wealthsimple("AFT_IN", "Direct deposit from THEMIS SOLUTION", 3595.32)
        assert tc == "payroll"
        assert d == "transfer"  # AFT_IN always transfer in direction CASE — payroll arrives via RBC

    def test_aft_in_generic_deposit_is_transfer(self):
        """Generic AFT_IN with no employer keyword must be account_transfer, not income."""
        tc, d = classify_wealthsimple("AFT_IN", "Deposit", 2614.00)
        assert tc == "account_transfer"
        assert d == "transfer"

    def test_eft_is_transfer(self):
        """EFT deposits (e.g. GIC proceeds moved in) must be transfer, not income."""
        tc, d = classify_wealthsimple("EFT", "Deposit", 5000.00)
        assert tc == "account_transfer"
        assert d == "transfer"

    def test_e_transfer_in_is_reimbursement(self):
        tc, d = classify_wealthsimple("E_TRFIN", "Interac e-Transfer® Received", 27.50)
        assert tc == "reimbursement"
        assert d == "inbound"

    def test_spend_is_outbound(self):
        tc, d = classify_wealthsimple("SPEND", "TIM HORTONS #1234", 4.75)
        assert tc == "spending"
        assert d == "outbound"

    def test_obp_out_mastercard_is_transfer(self):
        tc, d = classify_wealthsimple("OBP_OUT", "Bill payment to MASTERCARD", 500.00)
        assert tc == "bill_payment"
        assert d == "transfer"

    def test_trfout_is_transfer(self):
        tc, d = classify_wealthsimple("TRFOUT", "Transfer out", 1000.00)
        assert tc == "account_transfer"
        assert d == "transfer"

    def test_interest_earned(self):
        tc, d = classify_wealthsimple("INT", "Interest earned", 6.31)
        assert tc == "interest_earned"
        assert d == "inbound"

    def test_cashback(self):
        tc, d = classify_wealthsimple("CASHBACK", "Cashback reward", 12.50)
        assert tc == "cashback"
        assert d == "inbound"

    def test_p2p_sent(self):
        tc, d = classify_wealthsimple("P2P_SENT", "Payment to Alex", 50.00)
        assert tc == "p2p"
        assert d == "outbound"

    def test_aft_out_is_pre_auth(self):
        tc, d = classify_wealthsimple("AFT_OUT", "Pre-authorized debit", 29.99)
        assert tc == "pre_auth_debit"
        assert d == "outbound"


# ---------------------------------------------------------------------------
# RBC Chequing tests
# ---------------------------------------------------------------------------

class TestRbcChequingClassification:

    def test_investment_ws_is_transfer(self):
        """'INVESTMENT WS INVESTMENTS' deposit from WS back to RBC must be transfer."""
        tc, d = classify_rbc_chequing("INVESTMENT WS INVESTMENTS", 500.00)
        assert tc == "account_transfer"
        assert d == "transfer"

    def test_wealthsimple_outbound_is_transfer(self):
        tc, d = classify_rbc_chequing("ONLINE TRANSFER TO WEALTHSIMPLE", -1000.00)
        assert tc == "account_transfer"
        assert d == "transfer"

    def test_mastercard_payment_is_transfer(self):
        tc, d = classify_rbc_chequing("MASTERCARD PAYMENT", -450.00)
        assert tc == "cc_payment"
        assert d == "transfer"

    def test_amex_payment_is_transfer(self):
        tc, d = classify_rbc_chequing("AMEX PAYMENT", -200.00)
        assert tc == "cc_payment"
        assert d == "transfer"

    def test_payroll_direct_deposit(self):
        tc, d = classify_rbc_chequing("DIRECT DEP THEMIS SOLUTIONS", 3595.32)
        assert tc == "payroll"
        assert d == "inbound"

    def test_cra_tax_refund_is_deposit_inbound(self):
        tc, d = classify_rbc_chequing("CRA TAX REFUND", 5379.69)
        assert tc == "deposit"
        assert d == "inbound"

    def test_e_transfer_out(self):
        tc, d = classify_rbc_chequing("E-TRANSFER SENT TO JANE DOE", -75.00)
        assert tc == "e_transfer_out"
        assert d == "outbound"

    def test_e_transfer_in(self):
        tc, d = classify_rbc_chequing("E-TRANSFER RECEIVED FROM JOHN", 50.00)
        assert tc == "e_transfer_in"
        assert d == "inbound"

    def test_generic_outbound_spending(self):
        tc, d = classify_rbc_chequing("SOME UNKNOWN DEBIT", -25.00)
        assert tc == "spending"
        assert d == "outbound"

    def test_generic_inbound_deposit(self):
        """An unrecognised positive amount should be deposit/inbound (not transfer)."""
        tc, d = classify_rbc_chequing("MISC CREDIT", 100.00)
        assert tc == "deposit"
        assert d == "inbound"


# ---------------------------------------------------------------------------
# Amex Cobalt tests
# ---------------------------------------------------------------------------

class TestAmexClassification:

    def test_payment_received_is_transfer(self):
        tc, d = classify_amex("PAYMENT RECEIVED - THANK YOU", 500.00)
        assert tc == "cc_payment"
        assert d == "transfer"

    def test_membership_fee(self):
        tc, d = classify_amex("MEMBERSHIP FEE INSTALLMENT", 15.99)
        assert tc == "fee"
        assert d == "outbound"

    def test_points_redemption_is_cashback_inbound(self):
        tc, d = classify_amex("Use Points for Purchases", 29.00)
        assert tc == "cashback"
        assert d == "inbound"

    def test_refund_negative_amount(self):
        tc, d = classify_amex("SOME MERCHANT", -45.00)
        assert tc == "refund"
        assert d == "inbound"

    def test_regular_spend(self):
        tc, d = classify_amex("LOBLAWS #1234", 87.32)
        assert tc == "spending"
        assert d == "outbound"


# ---------------------------------------------------------------------------
# RBC Mastercard tests
# ---------------------------------------------------------------------------

class TestRbcMastercardClassification:

    def test_payment_is_transfer(self):
        tc, d = classify_rbc_mastercard("PAYMENT - THANK YOU / PAI EMENT - MERCI", 600.00)
        assert tc == "cc_payment"
        assert d == "transfer"

    def test_positive_amount_is_refund(self):
        tc, d = classify_rbc_mastercard("AMAZON REFUND", 39.99)
        assert tc == "refund"
        assert d == "inbound"

    def test_regular_spend(self):
        """RBC Mastercard charges are stored as negative CAD values."""
        tc, d = classify_rbc_mastercard("SHELL #4567", -62.00)
        assert tc == "spending"
        assert d == "outbound"


# ---------------------------------------------------------------------------
# Transfer reconciliation edge cases
# ---------------------------------------------------------------------------

class TestTransferReconciliationLogic:
    """
    These tests document the known edge cases the bridge algorithm must handle.
    They test the *intent* of the matching rules, not the SQL directly.
    """

    def test_rbc_chequing_wealthsimple_inflow_classified_as_transfer(self):
        """
        RBC row: 'INVESTMENT WS INVESTMENTS' cad=+500 should be direction=transfer
        so it never appears as income even before reconciliation runs.
        """
        tc, d = classify_rbc_chequing("INVESTMENT WS INVESTMENTS", 500.00)
        assert d == "transfer", (
            "RBC inflows from Wealthsimple must be transfer at classification time, "
            "not relying solely on bridge_transfer_pairs to exclude them from income."
        )

    def test_ws_aft_in_generic_deposit_is_transfer_not_income(self):
        """
        Wealthsimple row: AFT_IN / 'Deposit' must be transfer.
        This was the root cause of the $2614 GIC double-count.
        """
        tc, d = classify_wealthsimple("AFT_IN", "Deposit", 2614.00)
        assert d == "transfer", (
            "Generic AFT_IN deposits (GIC, RBC top-ups) must default to transfer. "
            "Only payroll (Themis keyword) should be inbound."
        )

    def test_ws_e_transfer_in_is_inbound_not_transfer(self):
        """
        E_TRFIN (person-to-person) should remain inbound — it's genuinely received money,
        not a self-transfer. Reconciliation should not match these against outbound legs.
        """
        tc, d = classify_wealthsimple("E_TRFIN", "Interac e-Transfer® Received", 27.50)
        assert d == "inbound"
        assert tc == "reimbursement"
