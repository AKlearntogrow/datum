"""Top-level pytest fixtures for the Datum backend test suite."""

from __future__ import annotations

import os

import psycopg
import pytest

MESSY_WAREHOUSE_URL = os.environ.get(
    "MESSY_WAREHOUSE_URL",
    "postgresql://datum:datum_dev_password@localhost:5432/messy_warehouse",
)


def _warehouse_reachable(url: str) -> bool:
    """Cheap check: can we connect at all?"""
    try:
        with psycopg.connect(url, connect_timeout=2):
            return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def messy_warehouse_url() -> str:
    """The URL for the demo messy_warehouse database.

    Tests using this fixture are skipped if the warehouse is not reachable.
    """
    if not _warehouse_reachable(MESSY_WAREHOUSE_URL):
        pytest.skip(
            f"messy_warehouse not reachable at {MESSY_WAREHOUSE_URL}. "
            f"Is docker compose up? Has synthetic_data/generate.py been run?"
        )
    return MESSY_WAREHOUSE_URL
