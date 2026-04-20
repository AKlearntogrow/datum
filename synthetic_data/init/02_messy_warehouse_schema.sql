-- Schema for the messy_warehouse database.
-- This file runs as part of Postgres container initialization.
-- Deliberately contains NO column comments — the semantic layer must infer meaning.

\connect messy_warehouse

-- ==============================================================
-- Create schemas
-- ==============================================================
CREATE SCHEMA sales_cloud;
CREATE SCHEMA finance_mart;
CREATE SCHEMA product_analytics;
CREATE SCHEMA legacy_erp;

-- ==============================================================
-- sales_cloud (4 tables) — CRM, accounting, bank, FP&A
-- ==============================================================
CREATE TABLE sales_cloud.sales_opportunities (
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

CREATE TABLE sales_cloud.invoices (
    inv_num    VARCHAR(30) PRIMARY KEY,
    customer   VARCHAR(200) NOT NULL,
    inv_date   DATE NOT NULL,
    due_date   DATE,
    subtotal   NUMERIC(12, 2) NOT NULL,
    tax        NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total      NUMERIC(12, 2) NOT NULL,
    status     VARCHAR(20) NOT NULL
);

CREATE TABLE sales_cloud.bank_transactions (
    txn_id       VARCHAR(30) PRIMARY KEY,
    posted_date  DATE NOT NULL,
    description  VARCHAR(500),
    amount       NUMERIC(12, 2) NOT NULL,
    type         VARCHAR(20) NOT NULL
);

CREATE TABLE sales_cloud.revenue_forecast (
    forecast_month        DATE NOT NULL,
    segment               VARCHAR(50) NOT NULL,
    forecasted_amount     NUMERIC(14, 2) NOT NULL,
    ltv_estimate          NUMERIC(14, 2),
    expected_churn_rate   NUMERIC(5, 4),
    owner                 VARCHAR(100),
    notes                 VARCHAR(500),
    PRIMARY KEY (forecast_month, segment)
);

-- ==============================================================
-- finance_mart (3 tables) — GL invoices, revenue plan, FX rates
-- ==============================================================
CREATE TABLE finance_mart.invoices_gl (
    gl_invoice_id     VARCHAR(30) PRIMARY KEY,
    inv_number        VARCHAR(30) NOT NULL,
    gl_customer       VARCHAR(200) NOT NULL,
    gl_date           DATE NOT NULL,
    gl_amount         NUMERIC(14, 2) NOT NULL,
    adjustment_amount NUMERIC(14, 2) DEFAULT 0,
    gl_notes          TEXT
);

CREATE TABLE finance_mart.revenue_plan (
    plan_quarter    VARCHAR(7) NOT NULL,
    business_unit   VARCHAR(50) NOT NULL,
    planned_revenue NUMERIC(14, 2) NOT NULL,
    plan_version    INTEGER NOT NULL,
    PRIMARY KEY (plan_quarter, business_unit, plan_version)
);

CREATE TABLE finance_mart.fx_rates (
    currency_code VARCHAR(3) NOT NULL,
    rate_date     DATE NOT NULL,
    rate_to_usd   NUMERIC(10, 6) NOT NULL,
    PRIMARY KEY (currency_code, rate_date)
);

-- ==============================================================
-- product_analytics (3 tables) — page views, users, feature flags
-- ==============================================================
CREATE TABLE product_analytics.page_views (
    event_time  TIMESTAMP NOT NULL,
    user_id     VARCHAR(40),
    page_path   VARCHAR(500),
    session_id  VARCHAR(40),
    user_agent  VARCHAR(500)
);
CREATE INDEX idx_page_views_event_time ON product_analytics.page_views (event_time);

CREATE TABLE product_analytics.app_users (
    app_user_id  VARCHAR(40) PRIMARY KEY,
    email        VARCHAR(200) NOT NULL,
    company_name VARCHAR(200),
    signup_date  DATE NOT NULL,
    plan_tier    VARCHAR(20)
);

CREATE TABLE product_analytics.feature_flags (
    flag_id     VARCHAR(40) PRIMARY KEY,
    flag_name   VARCHAR(100) NOT NULL,
    config_json TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL
);

-- ==============================================================
-- legacy_erp (5 tables) — old ERP system, partially dead
-- ==============================================================
CREATE TABLE legacy_erp.customers (
    cust_id      INTEGER PRIMARY KEY,
    cust_name    VARCHAR(200) NOT NULL,
    status       VARCHAR(20),
    created_date DATE
);

CREATE TABLE legacy_erp.customers_old (
    cust_id      INTEGER PRIMARY KEY,
    cust_name    VARCHAR(200) NOT NULL,
    status       VARCHAR(20),
    created_date DATE
);

CREATE TABLE legacy_erp.orders_v1 (
    order_id     INTEGER PRIMARY KEY,
    cust_id      INTEGER,
    order_amount NUMERIC(10, 2),
    order_date   DATE
);

CREATE TABLE legacy_erp.invoices_2019 (
    inv_id     INTEGER PRIMARY KEY,
    cust_id    INTEGER,
    inv_amount NUMERIC(10, 2) NOT NULL,
    inv_date   DATE NOT NULL
);

CREATE TABLE legacy_erp.status_codes (
    code        VARCHAR(10) PRIMARY KEY,
    description VARCHAR(100) NOT NULL
);
