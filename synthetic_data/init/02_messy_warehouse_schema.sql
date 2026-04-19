-- Schema for the messy_warehouse database.
-- This file runs as part of Postgres container initialization.
-- Deliberately contains NO column comments — the semantic layer must infer meaning.

\connect messy_warehouse

-- ==============================================================
-- Table 1: sales_opportunities (CRM-like)
-- ==============================================================
CREATE TABLE sales_opportunities (
    opp_id           VARCHAR(20) PRIMARY KEY,
    account_name     VARCHAR(200) NOT NULL,
    owner_email      VARCHAR(200),
    stage            VARCHAR(50) NOT NULL,
    amount           NUMERIC(12, 2),
    contract_months  INTEGER,
    arr_committed    NUMERIC(12, 2),
    close_date       DATE,
    created_at       TIMESTAMP NOT NULL
);

-- ==============================================================
-- Table 2: invoices (Accounting-like)
-- ==============================================================
CREATE TABLE invoices (
    inv_num    VARCHAR(30) PRIMARY KEY,
    customer   VARCHAR(200) NOT NULL,
    inv_date   DATE NOT NULL,
    due_date   DATE,
    subtotal   NUMERIC(12, 2) NOT NULL,
    tax        NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total      NUMERIC(12, 2) NOT NULL,
    status     VARCHAR(20) NOT NULL
);

-- ==============================================================
-- Table 3: bank_transactions (bank feed)
-- ==============================================================
CREATE TABLE bank_transactions (
    txn_id       VARCHAR(30) PRIMARY KEY,
    posted_date  DATE NOT NULL,
    description  VARCHAR(500),
    amount       NUMERIC(12, 2) NOT NULL,
    type         VARCHAR(20) NOT NULL
);

-- ==============================================================
-- Table 4: revenue_forecast (FP&A)
-- ==============================================================
CREATE TABLE revenue_forecast (
    forecast_month        DATE NOT NULL,
    segment               VARCHAR(50) NOT NULL,
    forecasted_amount     NUMERIC(14, 2) NOT NULL,
    ltv_estimate          NUMERIC(14, 2),
    expected_churn_rate   NUMERIC(5, 4),
    owner                 VARCHAR(100),
    notes                 VARCHAR(500),
    PRIMARY KEY (forecast_month, segment)
);
