"""Synthetic messy warehouse data generator.

Populates the `messy_warehouse` Postgres database with deliberately
misaligned sales, accounting, bank, and forecast data.

Running this script wipes existing data and repopulates with a fixed seed.
Output is deterministic — two runs produce identical rows.

Usage (from project root):
    backend/.venv/Scripts/python synthetic_data/generate.py

The deliberate mismatches are defined in docs/decisions/0002-synthetic-warehouse-design.md
and summarized in MISMATCH_MANIFEST below.
"""

from __future__ import annotations

import os
import random
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
# Each entry corresponds to a mismatch described in ADR 0002.
# ----------------------------------------------------------------------

MISMATCH_MANIFEST = {
    "spelling_variants": "3 customers appear with 3 spellings each across systems",
    "uninvoiced_deals": "2 Closed Won opportunities never generate an invoice",
    "split_payments": "3 invoices are paid in 2 partial bank transactions each",
    "wrong_payment_and_credit": "1 customer pays the wrong amount, credit issued later",
    "forecast_miss": "Q1 forecast is ~15% higher than actual closed revenue",
    "unattributed_refund": "1 bank refund (negative) with no matching invoice",
    "null_contract_fields": "~12% of opportunities have NULL contract_months or arr_committed",
    "orphan_segment_dimension": "segment (Enterprise/Mid-Market/SMB) exists only in forecast",
}


# ----------------------------------------------------------------------
# Customer pool — the shared universe of fictional accounts.
# Each entry has 3 spelling variants used inconsistently across systems.
# ----------------------------------------------------------------------

@dataclass
class Customer:
    canonical: str
    variants: list[str]   # index 0 = sales, 1 = accounting, 2 = bank description
    segment: str          # used only by forecast (orphan dimension)


CUSTOMERS: list[Customer] = [
    Customer("Acme Corporation", ["Acme Corporation", "Acme Corp.", "ACME CORP"], "Enterprise"),
    Customer("Globex Industries", ["Globex Industries", "globex industries", "GLOBEX IND"], "Enterprise"),
    Customer("Initech LLC", ["Initech LLC", "Initech", "INITECH LLC"], "Mid-Market"),
    Customer("Umbrella Holdings", ["Umbrella Holdings", "Umbrella Hldgs", "UMBRELLA HOLD"], "Enterprise"),
    Customer("Soylent Group", ["Soylent Group", "Soylent Grp", "SOYLENT GRP"], "Mid-Market"),
    Customer("Hooli Inc", ["Hooli Inc", "Hooli, Inc.", "HOOLI INC"], "Enterprise"),
    Customer("Pied Piper", ["Pied Piper", "Pied Piper Co", "PIED PIPER CO"], "SMB"),
    Customer("Stark Industries", ["Stark Industries", "Stark Ind.", "STARK INDUSTRIES"], "Enterprise"),
    Customer("Wayne Enterprises", ["Wayne Enterprises", "Wayne Ent", "WAYNE ENT"], "Enterprise"),
    Customer("Vandelay Imports", ["Vandelay Imports", "Vandelay", "VANDELAY IMPORTS"], "SMB"),
    Customer("Cyberdyne Systems", ["Cyberdyne Systems", "Cyberdyne Sys", "CYBERDYNE SYS"], "Mid-Market"),
    Customer("Tyrell Corporation", ["Tyrell Corporation", "Tyrell Corp", "TYRELL CORP"], "Mid-Market"),
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
# Generators — one function per table.
# Each returns a list of tuples ready for executemany().
# ----------------------------------------------------------------------

@dataclass
class GeneratedOpp:
    """Internal record: captures what we generated so downstream
    generators (invoices, bank) can reference the same deals."""
    opp_id: str
    customer: Customer
    stage: str
    amount: Decimal
    contract_months: int | None
    arr_committed: Decimal | None
    close_date: date
    created_at: datetime
    row: tuple  # ready for INSERT


def generate_opportunities() -> list[GeneratedOpp]:
    """Generate ~40 opportunities. Return both the insert rows and internal records."""
    opps: list[GeneratedOpp] = []

    for i in range(40):
        customer = random.choice(CUSTOMERS)
        stage = random.choices(STAGES, weights=STAGE_WEIGHTS)[0]
        amount = Decimal(random.choice([25_000, 50_000, 75_000, 120_000, 240_000, 500_000]))

        # Contract length — occasionally NULL (rep forgot)
        contract_months: int | None = random.choice([12, 12, 24, 24, 36, 1])
        if random.random() < 0.12:
            contract_months = None

        # ARR committed — deliberately inconsistent with amount / contract_months × 12
        # Sometimes matches cleanly, sometimes rep declared a different number, sometimes NULL
        arr_committed: Decimal | None
        roll = random.random()
        if roll < 0.12:
            arr_committed = None
        elif roll < 0.50 and contract_months:
            # Clean annualization
            arr_committed = (amount * Decimal(12) / Decimal(contract_months)).quantize(Decimal("0.01"))
        else:
            # Rep entered their own number — within ±20% of the "correct" answer
            if contract_months:
                base = amount * Decimal(12) / Decimal(contract_months)
            else:
                base = amount
            fudge = Decimal(str(random.uniform(0.8, 1.2)))
            arr_committed = (base * fudge).quantize(Decimal("0.01"))

        # Close date — spread across last 12 months
        close_date = fake.date_between(start_date="-12M", end_date="+2M")
        created_at = datetime.combine(
            close_date - timedelta(days=random.randint(20, 120)),
            datetime.min.time(),
        )

        opp_id = f"OPP-{i + 1:05d}"
        sales_variant = customer.variants[0]
        owner = random.choice(SALES_REPS)

        row = (
            opp_id,
            sales_variant,
            owner,
            stage,
            amount,
            contract_months,
            arr_committed,
            close_date,
            created_at,
        )

        opps.append(GeneratedOpp(
            opp_id=opp_id,
            customer=customer,
            stage=stage,
            amount=amount,
            contract_months=contract_months,
            arr_committed=arr_committed,
            close_date=close_date,
            created_at=created_at,
            row=row,
        ))

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
    """Invoices mostly follow Closed Won opps — but not all.
    2 Closed Won deals deliberately never get invoiced.
    """
    invoices: list[GeneratedInvoice] = []
    closed_won = [o for o in opps if o.stage == "Closed Won"]

    # Pick 2 to deliberately skip
    skip_ids = set(random.sample([o.opp_id for o in closed_won], k=min(2, len(closed_won))))

    inv_counter = 1
    for opp in closed_won:
        if opp.opp_id in skip_ids:
            continue

        # Mostly invoice the opportunity amount, occasionally with small rounding or discount
        variance = Decimal(str(random.choice([1.0, 1.0, 1.0, 0.95, 1.05])))
        subtotal = (opp.amount * variance).quantize(Decimal("0.01"))
        tax = (subtotal * Decimal("0.08")).quantize(Decimal("0.01"))
        total = subtotal + tax

        inv_date = opp.close_date + timedelta(days=random.randint(0, 14))
        due_date = inv_date + timedelta(days=30)

        # Status weighted toward Paid for older invoices
        age_days = (date.today() - inv_date).days
        if age_days < 15:
            status = random.choice(["Draft", "Sent", "Sent"])
        elif age_days < 45:
            status = random.choice(["Sent", "Paid", "Paid"])
        else:
            status = random.choices(["Paid", "Overdue"], weights=[0.8, 0.2])[0]

        inv_num = f"INV-{inv_date.year}-{inv_counter:04d}"
        inv_counter += 1

        # Accounting uses a different spelling variant than sales
        acct_variant = opp.customer.variants[1]

        row = (inv_num, acct_variant, inv_date, due_date, subtotal, tax, total, status)

        invoices.append(GeneratedInvoice(
            inv_num=inv_num,
            customer=opp.customer,
            inv_date=inv_date,
            total=total,
            status=status,
            row=row,
        ))

    return invoices


def generate_bank_transactions(invoices: list[GeneratedInvoice]) -> list[tuple]:
    """Bank transactions mostly reflect Paid invoices, with realistic mess:
    - 3 invoices paid in 2 partial transactions each
    - 1 customer pays wrong amount, credit issued separately
    - 1 refund with no matching invoice
    - Some outgoing transactions (expenses)
    """
    rows: list[tuple] = []
    paid = [i for i in invoices if i.status == "Paid"]

    # Pick 3 for split payments
    split_invs = set(random.sample([i.inv_num for i in paid], k=min(3, len(paid))))
    # Pick 1 for wrong-amount-then-credit
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
            # Two partial payments
            first = (inv.total * Decimal("0.6")).quantize(Decimal("0.01"))
            second = inv.total - first
            rows.append((
                make_txn_id(), posted,
                f"ACH PAYMENT {bank_variant} PARTIAL REF {inv.inv_num}",
                first, "ACH",
            ))
            rows.append((
                make_txn_id(), posted + timedelta(days=random.randint(5, 20)),
                f"ACH PAYMENT {bank_variant} FINAL REF {inv.inv_num}",
                second, "ACH",
            ))
        elif wrong_amount_inv and inv.inv_num == wrong_amount_inv.inv_num:
            # Customer paid the wrong amount, then a credit was issued
            wrong = (inv.total + Decimal("500.00")).quantize(Decimal("0.01"))
            credit = Decimal("-500.00")
            rows.append((
                make_txn_id(), posted,
                f"WIRE PAYMENT {bank_variant} REF {inv.inv_num}",
                wrong, "Wire",
            ))
            rows.append((
                make_txn_id(), posted + timedelta(days=5),
                f"CREDIT REFUND {bank_variant} REF {inv.inv_num}",
                credit, "ACH",
            ))
        else:
            # Clean single payment
            txn_type = random.choice(["ACH", "ACH", "Wire", "Check"])
            rows.append((
                make_txn_id(), posted,
                f"{txn_type.upper()} PAYMENT {bank_variant} REF {inv.inv_num}",
                inv.total, txn_type,
            ))

    # 1 unattributed refund
    rows.append((
        make_txn_id(),
        fake.date_between(start_date="-6M", end_date="today"),
        "REFUND - UNMATCHED",
        Decimal("-1250.00"),
        "ACH",
    ))

    # A few expense transactions (outgoing) for realism
    for _ in range(5):
        rows.append((
            make_txn_id(),
            fake.date_between(start_date="-12M", end_date="today"),
            f"{random.choice(['AWS', 'GOOGLE CLOUD', 'OFFICE RENT', 'PAYROLL'])} EXPENSE",
            Decimal(str(-random.randint(500, 15000))),
            random.choice(["ACH", "Wire"]),
        ))

    return rows


def generate_forecast(opps: list[GeneratedOpp]) -> list[tuple]:
    """Monthly forecast × 3 segments. Q1 deliberately overstated ~15%."""
    rows: list[tuple] = []
    today = date.today()
    start = date(today.year, 1, 1)

    segments = ["Enterprise", "Mid-Market", "SMB"]
    segment_base = {"Enterprise": 350_000, "Mid-Market": 150_000, "SMB": 50_000}
    segment_churn = {"Enterprise": 0.05, "Mid-Market": 0.08, "SMB": 0.15}
    analysts = ["emma.park", "frank.singh", "grace.li"]

    for month_idx in range(12):
        forecast_month = date(start.year, month_idx + 1, 1)
        is_q1 = month_idx < 3  # Jan/Feb/Mar — deliberately overstated

        for segment in segments:
            base = Decimal(segment_base[segment])
            churn = Decimal(str(segment_churn[segment]))
            # ±10% noise, plus Q1 overstatement
            noise = Decimal(str(random.uniform(0.9, 1.1)))
            q1_bump = Decimal("1.15") if is_q1 else Decimal("1.0")
            forecasted = (base * noise * q1_bump).quantize(Decimal("0.01"))

            # LTV = ARR × (1 / churn_rate) — the FP&A definition
            ltv = (forecasted * 12 / churn).quantize(Decimal("0.01"))

            notes = random.choice([
                "Tracking well",
                "Pipeline softening",
                "New logo heavy",
                "Renewal risk flagged",
                "",
            ])

            rows.append((
                forecast_month,
                segment,
                forecasted,
                ltv,
                churn,
                random.choice(analysts),
                notes,
            ))

    return rows


# ----------------------------------------------------------------------
# Main — wire it all together
# ----------------------------------------------------------------------

def main() -> None:
    print(f"Connecting to {WAREHOUSE_URL}")
    with psycopg.connect(WAREHOUSE_URL) as conn:
        with conn.cursor() as cur:
            print("Wiping existing data...")
            cur.execute("TRUNCATE sales_opportunities, invoices, bank_transactions, revenue_forecast")

            print("Generating opportunities...")
            opps = generate_opportunities()
            cur.executemany(
                """
                INSERT INTO sales_opportunities
                    (opp_id, account_name, owner_email, stage, amount, contract_months, arr_committed, close_date, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [o.row for o in opps],
            )
            print(f"  inserted {len(opps)} opportunities")

            print("Generating invoices...")
            invs = generate_invoices(opps)
            cur.executemany(
                """
                INSERT INTO invoices
                    (inv_num, customer, inv_date, due_date, subtotal, tax, total, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [i.row for i in invs],
            )
            print(f"  inserted {len(invs)} invoices")

            print("Generating bank transactions...")
            bank_rows = generate_bank_transactions(invs)
            cur.executemany(
                """
                INSERT INTO bank_transactions
                    (txn_id, posted_date, description, amount, type)
                VALUES (%s, %s, %s, %s, %s)
                """,
                bank_rows,
            )
            print(f"  inserted {len(bank_rows)} bank transactions")

            print("Generating forecast...")
            forecast_rows = generate_forecast(opps)
            cur.executemany(
                """
                INSERT INTO revenue_forecast
                    (forecast_month, segment, forecasted_amount, ltv_estimate, expected_churn_rate, owner, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                forecast_rows,
            )
            print(f"  inserted {len(forecast_rows)} forecast rows")

        conn.commit()

    print()
    print("=" * 60)
    print("Mismatch manifest (intentional):")
    for key, desc in MISMATCH_MANIFEST.items():
        print(f"  • {key}: {desc}")
    print("=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
