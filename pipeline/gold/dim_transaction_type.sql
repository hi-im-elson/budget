CREATE TABLE IF NOT EXISTS gold.dim_transaction_type (
    "type_code"   VARCHAR(50) NOT NULL PRIMARY KEY,
    "direction"   VARCHAR(20) NOT NULL,
    "type_name"   VARCHAR(100) NOT NULL,
    "description" VARCHAR(255)
);

INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('spending',        'outbound',  'Spending',           'Regular purchases');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('bill_payment',    'outbound',  'Bill Payment',       'Online bill payments (credit cards, utilities)');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('fee',             'outbound',  'Fee',                'Card membership or service fees');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('interest_charge', 'outbound',  'Interest Charge',    'Interest charges on accounts');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('e_transfer_out',  'outbound',  'E-Transfer Sent',    'Interac e-Transfer sent');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('p2p',             'outbound',  'P2P Sent',           'Wealthsimple peer-to-peer payment');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('pre_auth_debit',  'outbound',  'Pre-authorized Debit','Recurring pre-authorized debits');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('e_transfer_in',   'inbound',   'E-Transfer Received','Interac e-Transfer received');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('payroll',         'inbound',   'Payroll',            'Direct deposit from employer');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('deposit',         'inbound',   'Deposit',            'EFT deposit');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('interest_earned', 'inbound',   'Interest Earned',    'Interest earned on chequing');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('cashback',        'inbound',   'Cashback',           'Card cashback rewards');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('refund',          'inbound',   'Refund',             'Merchant refunds');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('cc_payment',      'transfer',  'Credit Card Payment','Payment received on a credit card');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('account_transfer','transfer',  'Account Transfer',   'Transfer between own accounts');
INSERT OR IGNORE INTO gold.dim_transaction_type VALUES ('investment',      'transfer',  'Investment',         'Transfer to/from investment accounts');
