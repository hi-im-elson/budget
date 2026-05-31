CREATE OR REPLACE TABLE gold.dim_type_category (
    "type_code"           VARCHAR(50) NOT NULL PRIMARY KEY,
    "default_category_id" INTEGER
);

DELETE FROM gold.dim_type_category;

INSERT OR IGNORE INTO gold.dim_type_category (type_code, default_category_id)
SELECT t.type_code, c.id
FROM (VALUES
    ('spending',         'Uncategorised'),
    ('bill_payment',     'Bills & Utilities'),
    ('fee',              'Fees & Charges'),
    ('interest_charge',  'Fees & Charges'),
    ('e_transfer_out',   'Transfers'),
    ('p2p',              'Transfers'),
    ('pre_auth_debit',   'Bills & Utilities'),
    ('payroll',          'Income'),
    ('reimbursement',    'Income'),
    ('e_transfer_in',    'Income'),
    ('deposit',          'Income'),
    ('interest_earned',  'Investment Income'),
    ('cashback',         'Investment Income'),
    ('refund',           'Refunds'),
    ('cc_payment',       'Transfers'),
    ('account_transfer', 'Transfers'),
    ('investment',       'Transfers')
) AS t(type_code, category_name)
LEFT JOIN mappings.categories c ON c.category = t.category_name;

-- external_transfer has no meaningful default category; must be set via merchant or etransfer_recipients overrides
INSERT OR IGNORE INTO gold.dim_type_category (type_code, default_category_id) VALUES ('external_transfer', NULL);

