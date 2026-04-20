"""Synthetic messy warehouse data generator.

Populates the `messy_warehouse` Postgres database with deliberately
misaligned sales, accounting, bank, forecast, finance, product, and
legacy data across 4 schemas and 15 tables.

Running this script wipes existing data and repopulates with a fixed seed.
Output is deterministic — two runs produce identical rows.

Usage (from project root):
    backend/.venv/Scripts/python synthetic_data/generate.py

The deliberate mismatches are defined in docs/decisions/0002-synthetic-warehouse-design.md
and summarized in MISMATCH_MANIFEST below.
"""

from __future__ import annotations

import json
import os
import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

import psycopg
from faker import Faker

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

WAREHOUSE_URL = os.environ.get(
    "MESSY_WAREHOUSE_URL",
    "postgresql://datum:datum_dev_password@localhost:5432/messy_warehouse",
)

SEED = 42  # Fixed for reproducibility

fake = Faker()
Faker.seed(SEED)
random.seed(SEED)


# ----------------------------------------------------------------------
# Mismatch manifest — explicit declaration of the intentional mess.
# Each entry corresponds to a mismatch described in ADR 0002 or 0009.
# ----------------------------------------------------------------------

MISMATCH_MANIFEST = {
    # Original 8 (ADR 0002)
    "spelling_variants": "3+ customers appear with different spellings across sales, accounting, bank, GL, and product systems",
    "uninvoiced_deals": "2 Closed Won opportunities never generate an invoice",
    "split_payments": "3 invoices are paid in 2 partial bank transactions each",
    "wrong_payment_and_credit": "1 customer pays the wrong amount, credit issued later",
    "forecast_miss": "Q1 forecast is ~15% higher than actual closed revenue",
    "unattributed_refund": "1 bank refund (negative) with no matching invoice",
    "null_contract_fields": "~12% of opportunities have NULL contract_months or arr_committed",
    "orphan_segment_dimension": "segment (Enterprise/Mid-Market/SMB) exists only in forecast",
    # New 10 (ADR 0009 / 11b)
    "gl_missing_invoices": "~15% of sales_cloud invoices have no GL counterpart in finance_mart.invoices_gl",
    "gl_adjustments": "~15% of GL invoices have non-zero adjustment_amount (write-offs)",
    "gl_fourth_spelling": "finance_mart.invoices_gl uses a 4th customer spelling variant",
    "revenue_plan_drift": "finance_mart.revenue_plan is ~5-10% off from sales_cloud.revenue_forecast (different teams, different assumptions)",
    "orphan_page_view_users": "~3% of product_analytics.page_views have user_ids that don't match any app_user",
    "product_fifth_spelling": "~15 product_analytics.app_users have company_name matching sales accounts via a 5th spelling variant",
    "feature_flag_text_json": "product_analytics.feature_flags stores JSON in a TEXT column, not JSONB — schema smell",
    "legacy_status_inconsistency": "legacy_erp.customers.status uses 6 strings for 3 states; doesn't match legacy_erp.status_codes",
    "dead_legacy_tables": "legacy_erp.customers_old and legacy_erp.orders_v1 are empty — dead tables nobody deleted",
    "frozen_legacy_invoices": "legacy_erp.invoices_2019 contains only 2019 data — stale temporal scope",
}


# ----------------------------------------------------------------------
# Customer pool — the shared universe of fictional accounts.
# 5 spelling variants used inconsistently across systems:
#   0 = sales (CRM), 1 = accounting, 2 = bank description,
#   3 = GL (finance_mart), 4 = product (app_users company_name)
# ----------------------------------------------------------------------

@dataclass
class Customer:
    canonical: str
    variants: list[str]
    segment: str          # used only by forecast (orphan dimension)


CUSTOMERS: list[Customer] = [
    Customer("Acme Corporation",   ["Acme Corporation", "Acme Corp.", "ACME CORP", "Acme Corp Ltd", "acme corporation"], "Enterprise"),
    Customer("Globex Industries",  ["Globex Industries", "globex industries", "GLOBEX IND", "Globex Industries LLC", "Globex Ind."], "Enterprise"),
    Customer("Initech LLC",        ["Initech LLC", "Initech", "INITECH LLC", "Initech Limited", "initech"], "Mid-Market"),
    Customer("Umbrella Holdings",  ["Umbrella Holdings", "Umbrella Hldgs", "UMBRELLA HOLD", "Umbrella Holdings Inc", "Umbrella Corp"], "Enterprise"),
    Customer("Soylent Group",      ["Soylent Group", "Soylent Grp", "SOYLENT GRP", "Soylent Group PLC", "soylent group"], "Mid-Market"),
    Customer("Hooli Inc",          ["Hooli Inc", "Hooli, Inc.", "HOOLI INC", "Hooli Incorporated", "Hooli"], "Enterprise"),
    Customer("Pied Piper",         ["Pied Piper", "Pied Piper Co", "PIED PIPER CO", "Pied Piper LLC", "piedpiper"], "SMB"),
    Customer("Stark Industries",   ["Stark Industries", "Stark Ind.", "STARK INDUSTRIES", "Stark Industries Corp", "Stark Ind"], "Enterprise"),
    Customer("Wayne Enterprises",  ["Wayne Enterprises", "Wayne Ent", "WAYNE ENT", "Wayne Enterprises Ltd", "Wayne Ent."], "Enterprise"),
    Customer("Vandelay Imports",   ["Vandelay Imports", "Vandelay", "VANDELAY IMPORTS", "Vandelay Import Co", "vandelay imports"], "SMB"),
    Customer("Cyberdyne Systems",  ["Cyberdyne Systems", "Cyberdyne Sys", "CYBERDYNE SYS", "Cyberdyne Systems Inc", "cyberdyne"], "Mid-Market"),
    Customer("Tyrell Corporation", ["Tyrell Corporation", "Tyrell Corp", "TYRELL CORP", "Tyrell Corp.", "tyrell corp"], "Mid-Market"),
]

# Sales reps
SALES_REPS = [
    "alice.chen@example.com",
    "bob.martinez@example.com",
    "carol.nguyen@example.com",
    "david.okafor@example.com",
]

STAGES = ["Prospecting", "Qualification", "Proposal", "Closed Won", "Closed Lost"]
STAGE_WEIGHTS = [0.15, 0.15, 0.10, 0.45, 0.15]  # bias toward Closed Won for interesting data


# ----------------------------------------------------------------------
# sales_cloud generators (existing 4 tables, unchanged logic)
# ----------------------------------------------------------------------

@dataclass
class GeneratedOpp:
    opp_id: str
    customer: Customer
    stage: str
    amount: Decimal
    contract_months: int | None
    arr_committed: Decimal | None
    close_date: date
    created_at: datetime
    row: tuple


def generate_opportunities() -> list[GeneratedOpp]:
    opps: list[GeneratedOpp] = []
    for i in range(40):
        customer = random.choice(CUSTOMERS)
        stage = random.choices(STAGES, weights=STAGE_WEIGHTS)[0]
        amount = Decimal(random.choice([25_000, 50_000, 75_000, 120_000, 240_000, 500_000]))
        contract_months: int | None = random.choice([12, 12, 24, 24, 36, 1])
        if random.random() < 0.12:
            contract_months = None
        arr_committed: Decimal | None
        roll = random.random()
        if roll < 0.12:
            arr_committed = None
        elif roll < 0.50 and contract_months:
            arr_committed = (amount * Decimal(12) / Decimal(contract_months)).quantize(Decimal("0.01"))
        else:
            if contract_months:
                base = amount * Decimal(12) / Decimal(contract_months)
            else:
                base = amount
            fudge = Decimal(str(random.uniform(0.8, 1.2)))
            arr_committed = (base * fudge).quantize(Decimal("0.01"))
        close_date = fake.date_between(start_date="-12M", end_date="+2M")
        created_at = datetime.combine(
            close_date - timedelta(days=random.randint(20, 120)),
            datetime.min.time(),
        )
        opp_id = f"OPP-{i + 1:05d}"
        row = (opp_id, customer.variants[0], random.choice(SALES_REPS), stage,
               amount, contract_months, arr_committed, close_date, created_at)
        opps.append(GeneratedOpp(opp_id=opp_id, customer=customer, stage=stage,
                                 amount=amount, contract_months=contract_months,
                                 arr_committed=arr_committed, close_date=close_date,
                                 created_at=created_at, row=row))
    return opps


@dataclass
class GeneratedInvoice:
    inv_num: str
    customer: Customer
    inv_date: date
    total: Decimal
    status: str
    row: tuple


def generate_invoices(opps: list[GeneratedOpp]) -> list[GeneratedInvoice]:
    invoices: list[GeneratedInvoice] = []
    closed_won = [o for o in opps if o.stage == "Closed Won"]
    skip_ids = set(random.sample([o.opp_id for o in closed_won], k=min(2, len(closed_won))))
    inv_counter = 1
    for opp in closed_won:
        if opp.opp_id in skip_ids:
            continue
        variance = Decimal(str(random.choice([1.0, 1.0, 1.0, 0.95, 1.05])))
        subtotal = (opp.amount * variance).quantize(Decimal("0.01"))
        tax = (subtotal * Decimal("0.08")).quantize(Decimal("0.01"))
        total = subtotal + tax
        inv_date = opp.close_date + timedelta(days=random.randint(0, 14))
        due_date = inv_date + timedelta(days=30)
        age_days = (date.today() - inv_date).days
        if age_days < 15:
            status = random.choice(["Draft", "Sent", "Sent"])
        elif age_days < 45:
            status = random.choice(["Sent", "Paid", "Paid"])
        else:
            status = random.choices(["Paid", "Overdue"], weights=[0.8, 0.2])[0]
        inv_num = f"INV-{inv_date.year}-{inv_counter:04d}"
        inv_counter += 1
        acct_variant = opp.customer.variants[1]
        row = (inv_num, acct_variant, inv_date, due_date, subtotal, tax, total, status)
        invoices.append(GeneratedInvoice(inv_num=inv_num, customer=opp.customer,
                                         inv_date=inv_date, total=total, status=status, row=row))
    return invoices


def generate_bank_transactions(invoices: list[GeneratedInvoice]) -> list[tuple]:
    rows: list[tuple] = []
    paid = [i for i in invoices if i.status == "Paid"]
    split_invs = set(random.sample([i.inv_num for i in paid], k=min(3, len(paid))))
    wrong_amount_inv: GeneratedInvoice | None = None
    remaining = [i for i in paid if i.inv_num not in split_invs]
    if remaining:
        wrong_amount_inv = random.choice(remaining)
    txn_counter = 1

    def make_txn_id() -> str:
        nonlocal txn_counter
        tid = f"TXN-{txn_counter:06d}"
        txn_counter += 1
        return tid

    for inv in paid:
        posted = inv.inv_date + timedelta(days=random.randint(5, 40))
        bank_variant = inv.customer.variants[2]
        if inv.inv_num in split_invs:
            first = (inv.total * Decimal("0.6")).quantize(Decimal("0.01"))
            second = inv.total - first
            rows.append((make_txn_id(), posted,
                         f"ACH PAYMENT {bank_variant} PARTIAL REF {inv.inv_num}", first, "ACH"))
            rows.append((make_txn_id(), posted + timedelta(days=random.randint(5, 20)),
                         f"ACH PAYMENT {bank_variant} FINAL REF {inv.inv_num}", second, "ACH"))
        elif wrong_amount_inv and inv.inv_num == wrong_amount_inv.inv_num:
            wrong = (inv.total + Decimal("500.00")).quantize(Decimal("0.01"))
            credit = Decimal("-500.00")
            rows.append((make_txn_id(), posted,
                         f"WIRE PAYMENT {bank_variant} REF {inv.inv_num}", wrong, "Wire"))
            rows.append((make_txn_id(), posted + timedelta(days=5),
                         f"CREDIT REFUND {bank_variant} REF {inv.inv_num}", credit, "ACH"))
        else:
            txn_type = random.choice(["ACH", "ACH", "Wire", "Check"])
            rows.append((make_txn_id(), posted,
                         f"{txn_type.upper()} PAYMENT {bank_variant} REF {inv.inv_num}", inv.total, txn_type))
    rows.append((make_txn_id(), fake.date_between(start_date="-6M", end_date="today"),
                 "REFUND - UNMATCHED", Decimal("-1250.00"), "ACH"))
    for _ in range(5):
        rows.append((make_txn_id(), fake.date_between(start_date="-12M", end_date="today"),
                     f"{random.choice(['AWS', 'GOOGLE CLOUD', 'OFFICE RENT', 'PAYROLL'])} EXPENSE",
                     Decimal(str(-random.randint(500, 15000))), random.choice(["ACH", "Wire"])))
    return rows


def generate_forecast(opps: list[GeneratedOpp]) -> list[tuple]:
    rows: list[tuple] = []
    today = date.today()
    start = date(today.year, 1, 1)
    segments = ["Enterprise", "Mid-Market", "SMB"]
    segment_base = {"Enterprise": 350_000, "Mid-Market": 150_000, "SMB": 50_000}
    segment_churn = {"Enterprise": 0.05, "Mid-Market": 0.08, "SMB": 0.15}
    analysts = ["emma.park", "frank.singh", "grace.li"]
    for month_idx in range(12):
        forecast_month = date(start.year, month_idx + 1, 1)
        is_q1 = month_idx < 3
        for segment in segments:
            base = Decimal(segment_base[segment])
            churn = Decimal(str(segment_churn[segment]))
            noise = Decimal(str(random.uniform(0.9, 1.1)))
            q1_bump = Decimal("1.15") if is_q1 else Decimal("1.0")
            forecasted = (base * noise * q1_bump).quantize(Decimal("0.01"))
            ltv = (forecasted * 12 / churn).quantize(Decimal("0.01"))
            notes = random.choice(["Tracking well", "Pipeline softening", "New logo heavy",
                                   "Renewal risk flagged", ""])
            rows.append((forecast_month, segment, forecasted, ltv, churn,
                         random.choice(analysts), notes))
    return rows


# ----------------------------------------------------------------------
# finance_mart generators (3 tables)
# ----------------------------------------------------------------------

def generate_gl_invoices(invoices: list[GeneratedInvoice]) -> list[tuple]:
    """GL copies of ~85% of sales_cloud invoices, with 4th spelling variant."""
    rows: list[tuple] = []
    gl_counter = 1
    for inv in invoices:
        if random.random() < 0.15:
            continue  # ~15% not yet processed into GL
        gl_customer = inv.customer.variants[3]
        gl_amount = inv.total
        adjustment = Decimal("0.00")
        if random.random() < 0.15:
            adjustment = Decimal(str(-random.randint(50, 500))).quantize(Decimal("0.01"))
        gl_notes = random.choice(["", "Auto-posted", "Manual review", "Adjustment applied", ""])
        rows.append((
            f"GL-{gl_counter:05d}",
            inv.inv_num,
            gl_customer,
            inv.inv_date,
            gl_amount,
            adjustment,
            gl_notes if gl_notes else None,
        ))
        gl_counter += 1
    return rows


def generate_revenue_plan() -> list[tuple]:
    """Quarterly plan × 3 business units. ~5-10% off from monthly forecast."""
    rows: list[tuple] = []
    today = date.today()
    year = today.year
    units = ["Enterprise", "Mid-Market", "SMB"]
    unit_quarterly_base = {"Enterprise": 1_050_000, "Mid-Market": 450_000, "SMB": 150_000}
    for q in range(1, 5):
        quarter_label = f"{year}-Q{q}"
        for unit in units:
            base = Decimal(unit_quarterly_base[unit])
            drift = Decimal(str(random.uniform(0.92, 1.08)))
            planned = (base * drift).quantize(Decimal("0.01"))
            rows.append((quarter_label, unit, planned, 1))
    return rows


def generate_fx_rates() -> list[tuple]:
    """Monthly FX snapshots for 3 currency pairs over 12 months."""
    rows: list[tuple] = []
    today = date.today()
    currencies = {
        "EUR": (0.88, 0.94),
        "GBP": (0.76, 0.82),
        "CAD": (1.32, 1.40),
    }
    for month_offset in range(12):
        rate_date = date(today.year, 12 - month_offset, 1) if (12 - month_offset) >= 1 else date(today.year - 1, 12 - month_offset + 12, 1)
        # Simpler: just go back from month 12
        m = 12 - month_offset
        if m < 1:
            continue
        rate_date = date(today.year, m, 1)
        for code, (lo, hi) in currencies.items():
            rate = Decimal(str(random.uniform(lo, hi))).quantize(Decimal("0.000001"))
            rows.append((code, rate_date, rate))
    return rows


# ----------------------------------------------------------------------
# product_analytics generators (3 tables)
# ----------------------------------------------------------------------

def generate_app_users() -> list[tuple]:
    """~50 product users. ~15 have company_name matching a sales account (5th variant)."""
    rows: list[tuple] = []
    # First ~15 users tied to known customers
    matched_customers = random.sample(CUSTOMERS, k=min(15, len(CUSTOMERS)))
    for i, cust in enumerate(matched_customers):
        app_user_id = str(uuid.UUID(int=random.getrandbits(128), version=4))
        email = f"user{i+1}@{cust.canonical.lower().replace(' ', '').replace(',', '')[:10]}.com"
        rows.append((
            app_user_id,
            email,
            cust.variants[4],  # 5th spelling variant
            fake.date_between(start_date="-24M", end_date="-1M"),
            random.choice(["free", "starter", "pro", "enterprise"]),
        ))
    # Remaining ~35 users with no sales counterpart
    for i in range(35):
        app_user_id = str(uuid.UUID(int=random.getrandbits(128), version=4))
        rows.append((
            app_user_id,
            fake.email(),
            fake.company() if random.random() < 0.7 else None,
            fake.date_between(start_date="-24M", end_date="-1M"),
            random.choice(["free", "free", "starter", "pro"]),
        ))
    return rows


def generate_page_views(app_users: list[tuple]) -> list[tuple]:
    """~100k page views. ~3% have orphan user_ids not in app_users."""
    rows: list[tuple] = []
    user_ids = [u[0] for u in app_users]
    pages = ["/dashboard", "/settings", "/reports", "/billing", "/onboarding",
             "/docs", "/api-keys", "/integrations", "/team", "/profile"]
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/120.0",
    ]
    batch_size = 10_000
    for batch in range(10):
        batch_rows: list[tuple] = []
        for _ in range(batch_size):
            event_time = fake.date_time_between(start_date="-6M", end_date="now")
            if random.random() < 0.03:
                uid = str(uuid.UUID(int=random.getrandbits(128), version=4))  # orphan
            else:
                uid = random.choice(user_ids)
            batch_rows.append((
                event_time,
                uid,
                random.choice(pages),
                str(uuid.UUID(int=random.getrandbits(128), version=4)),
                random.choice(user_agents),
            ))
        rows.extend(batch_rows)
    return rows


def generate_feature_flags() -> list[tuple]:
    """~8 feature flags with JSON-in-TEXT (deliberate schema smell)."""
    flags = [
        ("dark-mode", '{"rollout_percent": 100, "enabled_for": ["all"]}'),
        ("new-dashboard", '{"rollout_percent": 50, "enabled_for": ["beta"], "expires_at": "2026-06-01"}'),
        ("ai-suggestions", '{"rollout_percent": 10, "enabled_for": ["enterprise"], "model": "claude-sonnet-4-5"}'),
        ("export-csv", '{"enabled": true}'),
        ("multi-tenant", '{"rollout_percent": 0, "blocked_reason": "pending security review"}'),
        ("sso-login", '{"rollout_percent": 25, "enabled_for": ["enterprise", "pro"]}'),
        ("webhook-v2", '{"rollout_percent": 75, "schema_version": 2, "deprecated_v1_at": "2026-03-01"}'),
        ("usage-analytics", '{"rollout_percent": 100, "sampling_rate": 0.1}'),
    ]
    rows: list[tuple] = []
    for i, (name, config) in enumerate(flags):
        flag_id = f"flag-{i+1:03d}"
        created_at = fake.date_time_between(start_date="-12M", end_date="-1M")
        rows.append((flag_id, name, config, created_at))
    return rows


# ----------------------------------------------------------------------
# legacy_erp generators (5 tables, 2 deliberately empty)
# ----------------------------------------------------------------------

def generate_legacy_customers() -> list[tuple]:
    """~30 customers with inconsistent status values."""
    rows: list[tuple] = []
    statuses = ["Active", "ACTIVE", "A", "Inactive", "INACTIVE", "I"]
    for i in range(30):
        cust_name = fake.company() if i >= len(CUSTOMERS) else CUSTOMERS[i].canonical
        rows.append((
            i + 1,
            cust_name,
            random.choice(statuses),
            fake.date_between(start_date="-5y", end_date="-6M"),
        ))
    return rows


def generate_legacy_invoices_2019() -> list[tuple]:
    """~20 invoices all dated in 2019 — frozen historical data."""
    rows: list[tuple] = []
    for i in range(20):
        rows.append((
            i + 1,
            random.randint(1, 30),
            Decimal(str(random.randint(1000, 50000))).quantize(Decimal("0.01")),
            date(2019, random.randint(1, 12), random.randint(1, 28)),
        ))
    return rows


def generate_status_codes() -> list[tuple]:
    """The 'official' 3 status codes — ironically not used consistently by legacy_erp.customers."""
    return [
        ("A", "Active"),
        ("I", "Inactive"),
        ("P", "Pending"),
    ]


# ----------------------------------------------------------------------
# Main — wire it all together
# ----------------------------------------------------------------------

def main() -> None:
    print(f"Connecting to {WAREHOUSE_URL}")
    with psycopg.connect(WAREHOUSE_URL) as conn:
        with conn.cursor() as cur:
            print("Wiping existing data...")
            cur.execute("""
                TRUNCATE
                    sales_cloud.sales_opportunities,
                    sales_cloud.invoices,
                    sales_cloud.bank_transactions,
                    sales_cloud.revenue_forecast,
                    finance_mart.invoices_gl,
                    finance_mart.revenue_plan,
                    finance_mart.fx_rates,
                    product_analytics.page_views,
                    product_analytics.app_users,
                    product_analytics.feature_flags,
                    legacy_erp.customers,
                    legacy_erp.customers_old,
                    legacy_erp.orders_v1,
                    legacy_erp.invoices_2019,
                    legacy_erp.status_codes
            """)

            # --- sales_cloud ---
            print("Generating sales_cloud.sales_opportunities...")
            opps = generate_opportunities()
            cur.executemany(
                "INSERT INTO sales_cloud.sales_opportunities (opp_id, account_name, owner_email, stage, amount, contract_months, arr_committed, close_date, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [o.row for o in opps])
            print(f"  inserted {len(opps)} opportunities")

            print("Generating sales_cloud.invoices...")
            invs = generate_invoices(opps)
            cur.executemany(
                "INSERT INTO sales_cloud.invoices (inv_num, customer, inv_date, due_date, subtotal, tax, total, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                [i.row for i in invs])
            print(f"  inserted {len(invs)} invoices")

            print("Generating sales_cloud.bank_transactions...")
            bank_rows = generate_bank_transactions(invs)
            cur.executemany(
                "INSERT INTO sales_cloud.bank_transactions (txn_id, posted_date, description, amount, type) VALUES (%s, %s, %s, %s, %s)",
                bank_rows)
            print(f"  inserted {len(bank_rows)} bank transactions")

            print("Generating sales_cloud.revenue_forecast...")
            forecast_rows = generate_forecast(opps)
            cur.executemany(
                "INSERT INTO sales_cloud.revenue_forecast (forecast_month, segment, forecasted_amount, ltv_estimate, expected_churn_rate, owner, notes) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                forecast_rows)
            print(f"  inserted {len(forecast_rows)} forecast rows")

            # --- finance_mart ---
            print("Generating finance_mart.invoices_gl...")
            gl_rows = generate_gl_invoices(invs)
            cur.executemany(
                "INSERT INTO finance_mart.invoices_gl (gl_invoice_id, inv_number, gl_customer, gl_date, gl_amount, adjustment_amount, gl_notes) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                gl_rows)
            print(f"  inserted {len(gl_rows)} GL invoices")

            print("Generating finance_mart.revenue_plan...")
            plan_rows = generate_revenue_plan()
            cur.executemany(
                "INSERT INTO finance_mart.revenue_plan (plan_quarter, business_unit, planned_revenue, plan_version) VALUES (%s, %s, %s, %s)",
                plan_rows)
            print(f"  inserted {len(plan_rows)} revenue plan rows")

            print("Generating finance_mart.fx_rates...")
            fx_rows = generate_fx_rates()
            cur.executemany(
                "INSERT INTO finance_mart.fx_rates (currency_code, rate_date, rate_to_usd) VALUES (%s, %s, %s)",
                fx_rows)
            print(f"  inserted {len(fx_rows)} FX rate rows")

            # --- product_analytics ---
            print("Generating product_analytics.app_users...")
            user_rows = generate_app_users()
            cur.executemany(
                "INSERT INTO product_analytics.app_users (app_user_id, email, company_name, signup_date, plan_tier) VALUES (%s, %s, %s, %s, %s)",
                user_rows)
            print(f"  inserted {len(user_rows)} app users")

            print("Generating product_analytics.page_views (100k rows)...")
            pv_rows = generate_page_views(user_rows)
            # Batch insert for performance
            batch_size = 10_000
            for i in range(0, len(pv_rows), batch_size):
                batch = pv_rows[i:i + batch_size]
                cur.executemany(
                    "INSERT INTO product_analytics.page_views (event_time, user_id, page_path, session_id, user_agent) VALUES (%s, %s, %s, %s, %s)",
                    batch)
            print(f"  inserted {len(pv_rows)} page views")

            print("Generating product_analytics.feature_flags...")
            flag_rows = generate_feature_flags()
            cur.executemany(
                "INSERT INTO product_analytics.feature_flags (flag_id, flag_name, config_json, created_at) VALUES (%s, %s, %s, %s)",
                flag_rows)
            print(f"  inserted {len(flag_rows)} feature flags")

            # --- legacy_erp ---
            print("Generating legacy_erp.customers...")
            legacy_cust_rows = generate_legacy_customers()
            cur.executemany(
                "INSERT INTO legacy_erp.customers (cust_id, cust_name, status, created_date) VALUES (%s, %s, %s, %s)",
                legacy_cust_rows)
            print(f"  inserted {len(legacy_cust_rows)} legacy customers")

            # customers_old and orders_v1 stay empty (dead tables)
            print("  legacy_erp.customers_old: 0 rows (dead table)")
            print("  legacy_erp.orders_v1: 0 rows (dead table)")

            print("Generating legacy_erp.invoices_2019...")
            legacy_inv_rows = generate_legacy_invoices_2019()
            cur.executemany(
                "INSERT INTO legacy_erp.invoices_2019 (inv_id, cust_id, inv_amount, inv_date) VALUES (%s, %s, %s, %s)",
                legacy_inv_rows)
            print(f"  inserted {len(legacy_inv_rows)} legacy 2019 invoices")

            print("Generating legacy_erp.status_codes...")
            status_rows = generate_status_codes()
            cur.executemany(
                "INSERT INTO legacy_erp.status_codes (code, description) VALUES (%s, %s)",
                status_rows)
            print(f"  inserted {len(status_rows)} status codes")

        conn.commit()

    print()
    print("=" * 60)
    print(f"Mismatch manifest ({len(MISMATCH_MANIFEST)} intentional mismatches):")
    for key, desc in MISMATCH_MANIFEST.items():
        print(f"  • {key}: {desc}")
    print("=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
