"""Tests for PII detection and redaction tool."""

import pytest
import asyncio

from tools.pii_tool import pii_redact, pii_detect, _run_detection, ALL_PII_TYPES


# ── Helper to run async tool functions ───────────────────────────────────────

def run(coro):
    return asyncio.run(coro)


# ── pii_redact tests ────────────────────────────────────────────────────────

class TestPiiRedact:
    def test_redact_email(self):
        result = run(pii_redact.ainvoke({"text": "Contact john@example.com please"}))
        assert "john@example.com" not in result
        assert "REDACTED" in result or "email" in result.lower()

    def test_redact_phone(self):
        result = run(pii_redact.ainvoke({"text": "Call me at 555-123-4567"}))
        assert "555-123-4567" not in result

    def test_redact_ssn(self):
        result = run(pii_redact.ainvoke({"text": "SSN is 123-45-6789"}))
        assert "123-45-6789" not in result

    def test_redact_credit_card(self):
        result = run(pii_redact.ainvoke({"text": "Card: 4111111111111111"}))
        assert "4111111111111111" not in result

    def test_redact_ip(self):
        result = run(pii_redact.ainvoke({"text": "Server at 192.168.1.100"}))
        assert "192.168.1.100" not in result

    def test_redact_mixed(self):
        text = "John's email is john@test.com, phone 555-987-6543, SSN 234-56-7890"
        result = run(pii_redact.ainvoke({"text": text}))
        assert "john@test.com" not in result
        assert "555-987-6543" not in result
        assert "234-56-7890" not in result

    def test_no_pii(self):
        text = "Hello world, nothing sensitive here"
        result = run(pii_redact.ainvoke({"text": text}))
        assert "No PII detected" in result

    def test_mask_strategy(self):
        result = run(pii_redact.ainvoke({
            "text": "Email: john@example.com",
            "strategy": "mask",
        }))
        # Mask strategy should partially obscure, not fully replace
        assert "john@example.com" not in result
        assert "REDACTED" not in result  # mask uses asterisks, not REDACTED

    def test_hash_strategy(self):
        result = run(pii_redact.ainvoke({
            "text": "Email: john@example.com",
            "strategy": "hash",
        }))
        assert "john@example.com" not in result
        assert "hash" in result.lower() or "email" in result.lower()

    def test_invalid_strategy(self):
        result = run(pii_redact.ainvoke({
            "text": "test",
            "strategy": "invalid",
        }))
        assert "Error" in result

    def test_specific_pii_types(self):
        text = "Email: a@b.com, Phone: 555-111-2222"
        result = run(pii_redact.ainvoke({
            "text": text,
            "pii_types": "email",
        }))
        # Email should be redacted, phone should remain
        assert "a@b.com" not in result
        assert "555-111-2222" in result


# ── pii_detect tests ────────────────────────────────────────────────────────

class TestPiiDetect:
    def test_detect_email(self):
        result = run(pii_detect.ainvoke({"text": "Contact user@domain.com"}))
        assert "EMAIL" in result.upper()
        assert "user@domain.com" in result

    def test_detect_no_pii(self):
        result = run(pii_detect.ainvoke({"text": "Just a normal sentence"}))
        assert "No PII detected" in result

    def test_detect_multiple(self):
        text = "Email: x@y.com, Phone: 555-000-1111"
        result = run(pii_detect.ainvoke({"text": text}))
        assert "EMAIL" in result.upper()
        assert "PHONE" in result.upper()

    def test_detect_specific_types(self):
        text = "Email: x@y.com, Phone: 555-000-1111"
        result = run(pii_detect.ainvoke({
            "text": text,
            "pii_types": "phone",
        }))
        assert "PHONE" in result.upper()
        # Should not report email when only phone requested
        assert "x@y.com" not in result


# ── _run_detection internals ────────────────────────────────────────────────

class TestRunDetection:
    def test_returns_processed_and_matches(self):
        processed, matches = _run_detection("test@mail.com", "redact")
        assert "test@mail.com" not in processed
        assert len(matches) >= 1
        assert matches[0]["type"] == "email"

    def test_unknown_type_skipped(self):
        processed, matches = _run_detection("hello", "redact", ["nonexistent_type"])
        assert processed == "hello"
        assert len(matches) == 0

    def test_all_types_constant(self):
        # Ensure all types are registered
        assert "email" in ALL_PII_TYPES
        assert "phone" in ALL_PII_TYPES
        assert "ssn" in ALL_PII_TYPES
        assert "credit_card" in ALL_PII_TYPES
        assert "api_key" in ALL_PII_TYPES
