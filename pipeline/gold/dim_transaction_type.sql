CREATE OR REPLACE TABLE gold.dim_transaction_type (
    "type_code"   VARCHAR(50)  NOT NULL PRIMARY KEY,
    "direction"   VARCHAR(20)  NOT NULL,
    "type_name"   VARCHAR(100) NOT NULL,
    "description" VARCHAR(255)
);

-- ── Outbound ─────────────────────────────────────────────────────────────────
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('spending',              'outbound', 'Spending',              'Regular purchases');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('bill_payment',          'outbound', 'Bill Payment',          'Online bill payments (credit cards, utilities)');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('fee',                   'outbound', 'Fee',                   'Card membership or service fees');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('interest_charge',       'outbound', 'Interest Charge',       'Interest charges on accounts');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('e_transfer_out',        'outbound', 'E-Transfer Sent',       'Interac e-Transfer sent to another person');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('p2p',                   'outbound', 'P2P Sent',              'Wealthsimple peer-to-peer payment');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('pre_auth_debit',        'outbound', 'Pre-authorized Debit',  'Recurring pre-authorized debits (utilities, subscriptions, insurance)');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('rent',                  'outbound', 'Rent',                  'Monthly rent payment via e-transfer');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('parking',               'outbound', 'Parking',               'Recurring parking payment via e-transfer');

-- ── Inbound / Income ─────────────────────────────────────────────────────────
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('payroll',               'inbound',  'Payroll',               'Direct deposit from employer');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('insurance_reimbursement','inbound', 'Insurance Reimbursement','Reimbursement from insurer (e.g. Canada Life, Sun Life)');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('reimbursement',         'inbound',  'Reimbursement',         'E-Transfer received as reimbursement from another person');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('e_transfer_in',         'inbound',  'E-Transfer Received',   'Interac e-Transfer received — unclassified');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('deposit',               'inbound',  'Deposit',               'EFT deposit — one-off inflows not matching other rules');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('government_deposit',    'inbound',  'Government Deposit',    'CRA tax refund, CERB, EI, or other government payments');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('interest_earned',       'inbound',  'Interest Earned',       'Interest earned on chequing or savings');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('cashback',              'inbound',  'Cashback',              'Card cashback rewards');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('refund',                'inbound',  'Refund',                'Merchant refunds — not true income');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('external_transfer',     'inbound',  'External Transfer',     'Money received from an external party (not own accounts)');

-- ── Transfer (internal moves, excluded from income/spending) ─────────────────
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('cc_payment',            'transfer', 'Credit Card Payment',   'Payment to a credit card from chequing');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('account_transfer',      'transfer', 'Account Transfer',      'Transfer between own accounts');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('investment',            'transfer', 'Investment',            'Transfer to/from investment or brokerage accounts');
