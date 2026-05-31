CREATE OR REPLACE TABLE gold.dim_type_category (
    "type_code"           VARCHAR(50) NOT NULL PRIMARY KEY,
    "default_category_id" INTEGER
);

DELETE FROM gold.dim_type_category;

-- ---------------------------------------------------------------------------
-- Map each type_code to a default category.
-- The category_name here must exactly match a row in mappings.categories.
-- Subcategory differentiation (e.g. Income > Payroll vs Income > Reimbursements)
-- is handled by the categories table having (category, subcategory) pairs —
-- we look up by category here and the subcategory travels with the dim_category row.
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO gold.dim_type_category (type_code, default_category_id)
SELECT t.type_code, c.id
FROM (VALUES
    -- Spending
    ('spending',                 'Uncategorised'),
    ('pre_auth_debit',           'Bills & Utilities'),
    ('bill_payment',             'Bills & Utilities'),
    ('fee',                      'Fees & Charges'),
    ('interest_charge',          'Fees & Charges'),

    -- Outbound transfers / payments
    ('e_transfer_out',           'Transfers'),
    ('p2p',                      'Transfers'),
    ('rent',                     'Housing'),
    ('parking',                  'Transportation'),

    -- Income
    ('payroll',                  'Income'),
    ('insurance_reimbursement',  'Income'),
    ('reimbursement',            'Income'),
    ('e_transfer_in',            'Income'),
    ('deposit',                  'Income'),
    ('government_deposit',       'Income'),

    -- Investment income
    ('interest_earned',          'Investment Income'),
    ('cashback',                 'Investment Income'),

    -- Not income
    ('refund',                   'Refunds'),

    -- Internal transfers (excluded from income/spending totals)
    ('cc_payment',               'Transfers'),
    ('account_transfer',         'Transfers'),
    ('investment',               'Transfers')
) AS t(type_code, category_name)
LEFT JOIN mappings.categories c ON c.category = t.category_name;

-- external_transfer: direction=inbound but not own-account income.
-- No default category — must be resolved via etransfer_rules or etransfer_recipients.
INSERT OR IGNORE INTO gold.dim_type_category (type_code, default_category_id) VALUES ('external_transfer', NULL);
