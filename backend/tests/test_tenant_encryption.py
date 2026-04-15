"""Tests for per-tenant Data Encryption Keys (Phase 1.8).

These tests are pure-Python — no database, no Postgres — so they run in
the existing pytest suite without any extra setup.
"""
from __future__ import annotations

import pytest

from config import (
    decrypt_for_tenant,
    encrypt_for_tenant,
    generate_tenant_dek,
    unwrap_tenant_dek,
    wrap_tenant_dek,
)


def test_tenant_dek_is_32_bytes():
    dek = generate_tenant_dek()
    assert isinstance(dek, bytes)
    assert len(dek) == 32


def test_two_tenants_get_distinct_deks():
    a = generate_tenant_dek()
    b = generate_tenant_dek()
    assert a != b


def test_wrap_then_unwrap_round_trips():
    dek = generate_tenant_dek()
    wrapped = wrap_tenant_dek(dek)
    assert wrapped.startswith("KEK:")
    unwrapped = unwrap_tenant_dek(wrapped)
    assert unwrapped == dek


def test_encrypt_then_decrypt_round_trips_with_raw_dek():
    dek = generate_tenant_dek()
    secret = "super-secret-olt-password"
    ct = encrypt_for_tenant(dek, secret)
    assert ct.startswith("ENC:")
    assert decrypt_for_tenant(dek, ct) == secret


def test_encrypt_then_decrypt_round_trips_with_wrapped_dek():
    """The same encrypt/decrypt API also accepts the KEK-wrapped form, so
    callers can store wrapped DEKs in the DB and pass them straight through.
    """
    dek = generate_tenant_dek()
    wrapped = wrap_tenant_dek(dek)
    secret = "another-secret"
    ct = encrypt_for_tenant(wrapped, secret)
    assert decrypt_for_tenant(wrapped, ct) == secret


def test_tenant_a_cannot_decrypt_tenant_b_data():
    """The whole point of per-tenant DEKs: a leaked tenant A key must not
    be able to read tenant B's ciphertext."""
    dek_a = generate_tenant_dek()
    dek_b = generate_tenant_dek()
    secret = "tenant-b-only"
    ct_b = encrypt_for_tenant(dek_b, secret)

    with pytest.raises(ValueError):
        decrypt_for_tenant(dek_a, ct_b)


def test_empty_string_pass_through():
    """Encrypt/decrypt of empty string is a no-op (matches legacy contract)."""
    dek = generate_tenant_dek()
    assert encrypt_for_tenant(dek, "") == ""
    assert decrypt_for_tenant(dek, "") == ""
