"""Verify the Phase 1 polling loop iterates over tenants.

The real polling code calls into SNMP/web scraping, which we mock here so
the test can assert tenant fan-out without touching any network.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


@pytest.mark.asyncio
async def test_poll_all_tenants_calls_poll_all_olts_per_tenant():
    """poll_all_tenants must invoke poll_all_olts once for each active
    tenant, passing that tenant's id."""
    import main

    # Two fake tenants
    t1 = MagicMock(id="tenant-a", name="Acme", status="active", deleted_at=None)
    t2 = MagicMock(id="tenant-b", name="Globex", status="active", deleted_at=None)

    # Fake session factory whose query(Tenant) chain returns [t1, t2].
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.filter.return_value.all.return_value = [t1, t2]
    factory = MagicMock(return_value=fake_db)

    with patch.object(main, "poll_all_olts", new=AsyncMock()) as mock_poll:
        await main.poll_all_tenants(factory)

        assert mock_poll.await_count == 2
        called_tenants = {call.kwargs.get("tenant_id") for call in mock_poll.await_args_list}
        assert called_tenants == {"tenant-a", "tenant-b"}


@pytest.mark.asyncio
async def test_poll_all_tenants_falls_back_to_legacy_when_tenants_table_missing():
    """If the tenants table doesn't exist (e.g. legacy SQLite single-tenant
    binary running pre-Phase-1 schema), poll_all_tenants must fall through
    to a single legacy poll with tenant_id=None."""
    import main

    fake_db = MagicMock()
    # Simulate "no such table: tenants"
    fake_db.query.side_effect = Exception("no such table: tenants")
    factory = MagicMock(return_value=fake_db)

    with patch.object(main, "poll_all_olts", new=AsyncMock()) as mock_poll:
        await main.poll_all_tenants(factory)

        assert mock_poll.await_count == 1
        assert mock_poll.await_args.kwargs.get("tenant_id") is None


@pytest.mark.asyncio
async def test_one_failing_tenant_does_not_block_others():
    """If polling tenant A raises, tenant B must still be polled."""
    import main

    t1 = MagicMock(id="tenant-a", name="Acme", status="active", deleted_at=None)
    t2 = MagicMock(id="tenant-b", name="Globex", status="active", deleted_at=None)

    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.filter.return_value.all.return_value = [t1, t2]
    factory = MagicMock(return_value=fake_db)

    async def flaky(factory, use_snmp=True, tenant_id=None):
        if tenant_id == "tenant-a":
            raise RuntimeError("SNMP timeout")

    with patch.object(main, "poll_all_olts", new=AsyncMock(side_effect=flaky)) as mock_poll:
        await main.poll_all_tenants(factory)
        # Both tenants attempted; failure of A did not abort B.
        assert mock_poll.await_count == 2
