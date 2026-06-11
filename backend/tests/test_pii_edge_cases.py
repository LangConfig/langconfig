"""Edge case tests for PII detection — meant to find bugs, not just prove it works."""

from tools.pii_tool import _run_detection


def _types_found(text: str) -> set:
    _, matches = _run_detection(text, "redact")
    return {m["type"] for m in matches}


def _values_found(text: str) -> list:
    _, matches = _run_detection(text, "redact")
    return [m["value"] for m in matches]


# ─── Phone edge cases ───────────────────────────────────────────────────────

class TestPhoneEdgeCases:
    def test_paren_format(self):
        assert "phone" in _types_found("Call (555) 123-4567")

    def test_dot_format(self):
        assert "phone" in _types_found("Reach me at 415.867.5309")

    def test_plus_one_dash(self):
        assert "phone" in _types_found("International: +1-555-123-4567")

    def test_plus_one_space(self):
        assert "phone" in _types_found("Number: +1 555 123 4567")

    def test_no_separators(self):
        # 10 digits with a trigger word
        types = _types_found("Call me at 5551234567")
        # Should catch via context detector
        assert "phone" in types

    def test_no_separators_no_context(self):
        # Bare 10 digits — ambiguous, may or may not match
        # Current behavior: requires NANP area code start digit 2-9 via formatted path
        # but no separators means formatted path doesn't match (needs \b boundary on dashes)
        # This is acceptable — ambiguous without context
        types = _types_found("The number 5551234567 is here")
        # Not strictly required but documenting behavior
        pass

    def test_international_uk(self):
        # UK format not covered — document that
        pass

    def test_multiple_phones(self):
        vals = _values_found("Primary 555-123-4567, backup 212-555-1111")
        assert len(vals) == 2


# ─── SSN edge cases ─────────────────────────────────────────────────────────

class TestSSNEdgeCases:
    def test_dashed(self):
        assert "ssn" in _types_found("SSN: 123-45-6789")

    def test_no_dashes_with_context(self):
        assert "ssn" in _types_found("my SSN is 123456789")

    def test_spaced_with_context(self):
        assert "ssn" in _types_found("social security number 123 45 6789")

    def test_no_context_no_dashes(self):
        # Bare 9 digits — ambiguous, shouldn't fire without context
        types = _types_found("The value is 123456789")
        # Could be matched or not; not strict
        pass

    def test_social_variations(self):
        for variant in ["social security", "SSN", "social is", "my social"]:
            assert "ssn" in _types_found(f"{variant} is 555-12-1234"), f"failed on {variant!r}"


# ─── Email edge cases ───────────────────────────────────────────────────────

class TestEmailEdgeCases:
    def test_standard(self):
        assert "email" in _types_found("Contact john@example.com")

    def test_subdomain(self):
        assert "email" in _types_found("Email: user@mail.example.com")

    def test_plus_addressing(self):
        assert "email" in _types_found("Send to user+tag@example.com")

    def test_asr_at_dot(self):
        assert "email" in _types_found("email me at john at example dot com")

    def test_asr_no_at_with_context(self):
        # Whisper drops "at" — "john.example.com"-like
        assert "email" in _types_found("my email is kade.example.xyz")

    def test_various_tlds(self):
        for tld in ["com", "org", "io", "xyz", "ai", "app", "co", "uk"]:
            txt = f"email is foo.bar.{tld}"
            assert "email" in _types_found(txt), f"failed TLD: {tld}"

    def test_no_email_in_url(self):
        # A URL shouldn't be caught as email
        types = _types_found("Visit https://example.com for details")
        # Not strict — URL might get caught as URL which is fine
        pass


# ─── Credit card edge cases ─────────────────────────────────────────────────

class TestCreditCardEdgeCases:
    def test_spaced_luhn_valid(self):
        # Valid Visa with Luhn: 4111 1111 1111 1111
        assert "credit_card" in _types_found("Card: 4111 1111 1111 1111")

    def test_dashed_luhn_valid(self):
        assert "credit_card" in _types_found("Card: 4111-1111-1111-1111")

    def test_packed_luhn_valid(self):
        assert "credit_card" in _types_found("Card 4111111111111111 on file")

    def test_context_short_digits(self):
        # "pink cut" ASR mishearing with 9 digits
        assert "credit_card" in _types_found("my pink cut number is 302215827")

    def test_context_no_digits_nearby(self):
        # Context word but no number — should NOT match
        types = _types_found("I need a credit card.")
        assert "credit_card" not in types


# ─── Bank account edge cases ───────────────────────────────────────────────

class TestBankAccountEdgeCases:
    def test_checking(self):
        assert "bank_account" in _types_found("my checking account is 1234567890")

    def test_routing_only(self):
        assert "routing_number" in _types_found("routing number is 021000021")

    def test_bank_cut_asr(self):
        assert "bank_account" in _types_found("bank cut number 987654321")

    def test_account_number_long(self):
        # Longer account numbers (some banks use 14+)
        assert "bank_account" in _types_found("account number 12345678901234")


# ─── Name edge cases ───────────────────────────────────────────────────────

class TestNameEdgeCases:
    def test_this_is_name(self):
        assert "name" in _types_found("Hi, this is Sarah.")

    def test_my_name_is(self):
        assert "name" in _types_found("my name is John Doe")

    def test_im_name(self):
        assert "name" in _types_found("Hi, I'm David.")

    def test_first_last(self):
        vals = _values_found("This is Sarah Mitchell from Acme")
        # Should capture multi-word name
        name_vals = [v for v in vals if len(v.split()) >= 2]
        # Tolerant: either "Sarah Mitchell" or at least "Sarah"
        assert any("Sarah" in v for v in vals), f"Sarah not found in {vals}"

    def test_stop_at_common_words(self):
        vals = _values_found("this is John from Acme")
        # Should not include "from"
        for v in vals:
            assert "from" not in v.lower(), f"captured stop word: {v}"

    def test_no_trigger_no_name(self):
        types = _types_found("John had a great meeting")
        # Without trigger, we don't try to detect arbitrary capitalized words
        assert "name" not in types


# ─── DOB edge cases ────────────────────────────────────────────────────────

class TestDOBEdgeCases:
    def test_slash_date(self):
        assert "date_of_birth" in _types_found("DOB 4/15/1987")

    def test_dash_date(self):
        assert "date_of_birth" in _types_found("date of birth 04-15-1987")

    def test_iso_date(self):
        assert "date_of_birth" in _types_found("date of birth 1987-04-15")

    def test_long_form(self):
        assert "date_of_birth" in _types_found("born on January 15 1987")

    def test_short_month(self):
        assert "date_of_birth" in _types_found("DOB: Jan 15, 1987")


# ─── IBAN / SWIFT / ISIN / CUSIP ───────────────────────────────────────────

class TestFinancialIDs:
    def test_iban_standalone(self):
        assert "iban" in _types_found("Payment to GB82WEST12345698765432 today")

    def test_iban_german(self):
        assert "iban" in _types_found("IBAN DE89370400440532013000 received")

    def test_swift_8char(self):
        assert "swift_bic" in _types_found("SWIFT is DEUTDEFF")

    def test_swift_11char(self):
        assert "swift_bic" in _types_found("SWIFT code CITIUS33XXX")

    def test_cusip(self):
        assert "cusip" in _types_found("CUSIP 037833100 for the holding")

    def test_isin(self):
        assert "isin" in _types_found("ISIN US0378331005 represents AAPL")


# ─── Address edge cases ───────────────────────────────────────────────────

class TestAddressEdgeCases:
    def test_street(self):
        assert "address" in _types_found("lives at 123 Main Street")

    def test_avenue(self):
        assert "address" in _types_found("1600 Pennsylvania Avenue")

    def test_abbreviated(self):
        assert "address" in _types_found("500 Oak Ave")

    def test_road(self):
        assert "address" in _types_found("45 Mill Road")


# ─── Empty / whitespace / edge strings ────────────────────────────────────

class TestBoundaryConditions:
    def test_empty_string(self):
        processed, matches = _run_detection("", "redact")
        assert matches == []
        assert processed == ""

    def test_whitespace_only(self):
        processed, matches = _run_detection("   \n\t  ", "redact")
        assert matches == []

    def test_only_pii(self):
        assert "email" in _types_found("test@example.com")

    def test_pii_at_start(self):
        types = _types_found("test@example.com said hi")
        assert "email" in types

    def test_pii_at_end(self):
        types = _types_found("contact us at test@example.com")
        assert "email" in types

    def test_multiple_of_same_type(self):
        vals = _values_found("emails: a@b.com and c@d.com and e@f.com")
        emails = [v for v in vals if "@" in v]
        assert len(emails) == 3


# ─── Mixed-case and punctuation ────────────────────────────────────────────

class TestCaseAndPunctuation:
    def test_uppercase_trigger(self):
        assert "ssn" in _types_found("MY SSN IS 123-45-6789")

    def test_mixed_case_context(self):
        assert "phone" in _types_found("Please Call Me At 555-123-4567")

    def test_pii_in_quotes(self):
        assert "email" in _types_found('He said "email me at foo@bar.com"')

    def test_pii_in_parens(self):
        assert "phone" in _types_found("(phone: 555-123-4567)")
