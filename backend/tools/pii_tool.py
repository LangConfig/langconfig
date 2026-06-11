"""
PII Detection & Redaction Tool
===============================

Workflow-callable tool wrapping LangChain v1.0's official PIIMiddleware.

Each PII type is detected by a CALLABLE detector function (not just a regex
string) so detection can be context-aware. This handles ASR output where
numbers come out as continuous digit runs ("my SSN is 555121234") and
symbols are spoken as words ("email me at foo at bar dot com").

Detectors are registered with `PIIMiddleware(pii_type, detector=callable)`
per LangChain's official API.

Covered types:
  email, phone, ssn, credit_card, name, api_key, ip, mac_address, url
"""

import logging
import re
from typing import Optional, List, Tuple, Dict, Any, Callable

from langchain_core.tools import tool
from langchain.agents.middleware import PIIMiddleware
from langchain.agents.middleware.pii import PIIMatch

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers
# =============================================================================

# Context-anchored detection window size (in characters after the trigger phrase).
# Catches cases like "my SSN is ... uh ... 555 12 1234" without being so large
# it picks up unrelated numbers later in the sentence.
DEFAULT_WINDOW = 80


def _digits_only(s: str) -> str:
    return re.sub(r"\D", "", s)


def _luhn_valid(digits: str) -> bool:
    """Luhn algorithm for credit card validation."""
    if not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# =============================================================================
# Context-aware detectors
# =============================================================================


def detect_ssn(text: str) -> List[PIIMatch]:
    """
    Detect SSN via context phrases + nearby 9-digit run (dashes optional),
    plus formatted SSN anywhere in the text.
    """
    matches: List[PIIMatch] = []
    seen = set()

    # Context-primed: phrase triggers then 9-digit run within window
    context_re = re.compile(
        r"\b(?:social\s+security(?:\s+number)?|\bssn\b|social\s+is|my\s+social)\b",
        re.IGNORECASE,
    )
    # 9 digits, optionally grouped 3-2-4 with spaces/dashes
    value_re = re.compile(r"\b\d{3}[\s-]?\d{2}[\s-]?\d{4}\b")

    for ctx in context_re.finditer(text):
        window_end = min(len(text), ctx.end() + DEFAULT_WINDOW)
        window = text[ctx.end():window_end]
        m = value_re.search(window)
        if m:
            start = ctx.end() + m.start()
            end = ctx.end() + m.end()
            key = (start, end)
            if key not in seen:
                seen.add(key)
                matches.append({"type": "ssn", "value": text[start:end], "start": start, "end": end})

    # Formatted SSN anywhere (for typed input)
    formatted_re = re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
    for m in formatted_re.finditer(text):
        key = (m.start(), m.end())
        if key not in seen:
            seen.add(key)
            matches.append({"type": "ssn", "value": m.group(), "start": m.start(), "end": m.end()})

    return matches


def detect_phone(text: str) -> List[PIIMatch]:
    """Detect phone via context phrases + nearby 10-digit run, plus formatted patterns."""
    matches: List[PIIMatch] = []
    seen = set()

    context_re = re.compile(
        r"\b(?:call\s+me(?:\s+at)?|my\s+(?:cell|mobile|phone)(?:\s+number)?(?:\s+is)?"
        r"|phone\s+number(?:\s+is)?|reach\s+me\s+at|my\s+number\s+is|contact\s+me\s+at"
        r"|dial)\b",
        re.IGNORECASE,
    )
    # 10 digits with optional separators; also country-code prefixed
    value_re = re.compile(
        r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
    )

    for ctx in context_re.finditer(text):
        window_end = min(len(text), ctx.end() + DEFAULT_WINDOW)
        window = text[ctx.end():window_end]
        m = value_re.search(window)
        if m:
            start = ctx.end() + m.start()
            end = ctx.end() + m.end()
            key = (start, end)
            if key not in seen:
                seen.add(key)
                matches.append({"type": "phone", "value": text[start:end], "start": start, "end": end})

    # Formatted phone anywhere (NNN-NNN-NNNN, (NNN) NNN-NNNN, etc.)
    # Area code first digit 2-9 (real NANP), but exchange code first digit
    # is any digit so test numbers like 555-123-4567 still match.
    formatted_re = re.compile(
        r"\b(?:\+?1[\s.-]?)?\(?[2-9]\d{2}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"
    )
    for m in formatted_re.finditer(text):
        key = (m.start(), m.end())
        if key not in seen:
            seen.add(key)
            matches.append({"type": "phone", "value": m.group(), "start": m.start(), "end": m.end()})

    return matches


def detect_credit_card(text: str) -> List[PIIMatch]:
    """Detect credit card via context + nearby 13-19 digit run (Luhn-validated when possible)."""
    matches: List[PIIMatch] = []
    seen = set()

    context_re = re.compile(
        r"\b(?:credit\s+card(?:\s+number)?|card\s+number|cc\s+(?:is|number)"
        r"|my\s+card|pink\s+cut\s+number)\b",
        re.IGNORECASE,
    )
    # 13-19 digits, optionally grouped in 4s with spaces or dashes
    value_re = re.compile(r"(?:\d[\s-]?){12,18}\d")

    # Fallback for ASR-truncated or short digit runs when context is strong
    short_re = re.compile(r"\b\d{9,}\b")

    for ctx in context_re.finditer(text):
        window_end = min(len(text), ctx.end() + DEFAULT_WINDOW)
        window = text[ctx.end():window_end]

        # Try full-length credit card first
        m = value_re.search(window)
        if m:
            digits = _digits_only(m.group())
            if 13 <= len(digits) <= 19:
                start = ctx.end() + m.start()
                end = ctx.end() + m.end()
                key = (start, end)
                if key not in seen:
                    seen.add(key)
                    matches.append({
                        "type": "credit_card",
                        "value": text[start:end],
                        "start": start,
                        "end": end,
                    })
                    continue

        # Fall back to any 9+ digit run (ASR often drops digits or merges them)
        m2 = short_re.search(window)
        if m2:
            start = ctx.end() + m2.start()
            end = ctx.end() + m2.end()
            key = (start, end)
            if key not in seen:
                seen.add(key)
                matches.append({
                    "type": "credit_card",
                    "value": text[start:end],
                    "start": start,
                    "end": end,
                })

    # Formatted credit card anywhere (Luhn-validated)
    formatted_re = re.compile(r"\b(?:\d[\s-]?){12,18}\d\b")
    for m in formatted_re.finditer(text):
        digits = _digits_only(m.group())
        if 13 <= len(digits) <= 19 and _luhn_valid(digits):
            key = (m.start(), m.end())
            if key not in seen:
                seen.add(key)
                matches.append({
                    "type": "credit_card",
                    "value": m.group(),
                    "start": m.start(),
                    "end": m.end(),
                })

    return matches


def detect_email(text: str) -> List[PIIMatch]:
    """
    Detect email via:
      - Standard form: user@domain.tld
      - ASR form: "user at domain dot tld" (spoken)
      - Context-primed: "email is X", "email me at X" — accepts `word.word.tld`
        form even without @ or "at", since Whisper sometimes drops those tokens
        (e.g. "Cade at example.xyz" -> "kade.example.xyz").
    """
    matches: List[PIIMatch] = []
    seen = set()

    # Standard written email
    written_re = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    for m in written_re.finditer(text):
        key = (m.start(), m.end())
        if key not in seen:
            seen.add(key)
            matches.append({"type": "email", "value": m.group(), "start": m.start(), "end": m.end()})

    # ASR form: word "at" word "dot" word
    token = r"[A-Za-z0-9][A-Za-z0-9._+-]*"
    asr_re = re.compile(
        rf"\b{token}\s+(?:at|@)\s+{token}(?:\s+(?:dot|\.)\s+{token})+\b",
        re.IGNORECASE,
    )
    for m in asr_re.finditer(text):
        key = (m.start(), m.end())
        if key not in seen:
            seen.add(key)
            matches.append({"type": "email", "value": m.group(), "start": m.start(), "end": m.end()})

    # Context-primed — tries several fallback value shapes after "email is" triggers
    context_re = re.compile(
        r"\b(?:email(?:\s+(?:is|address))?(?:\s+is)?|email\s+me\s+at|my\s+email\s+is)\b",
        re.IGNORECASE,
    )
    # Common TLD list for the no-@ fallback — keeps false positives down
    tld = r"(?:com|net|org|edu|gov|io|co|xyz|ai|app|tech|dev|me|us|uk|ca|cloud)"
    primed_patterns = [
        # ASR form with "at" and "dot"
        re.compile(rf"{token}\s+(?:at|@)\s+{token}(?:\s+(?:dot|\.)\s+{token})*", re.IGNORECASE),
        # Standard @ form
        re.compile(rf"{token}@{token}(?:\.{token})+", re.IGNORECASE),
        # No-@ fallback: word.word.tld (catches Whisper collapses like kade.example.xyz)
        re.compile(rf"\b{token}\.{token}\.{tld}\b", re.IGNORECASE),
        # No-@ fallback with subdomain: word.word.word.tld
        re.compile(rf"\b{token}\.{token}\.{token}\.{tld}\b", re.IGNORECASE),
    ]
    for ctx in context_re.finditer(text):
        window_end = min(len(text), ctx.end() + DEFAULT_WINDOW)
        window = text[ctx.end():window_end]
        for pat in primed_patterns:
            m = pat.search(window)
            if m:
                start = ctx.end() + m.start()
                end = ctx.end() + m.end()
                key = (start, end)
                if key not in seen:
                    seen.add(key)
                    matches.append({
                        "type": "email",
                        "value": text[start:end],
                        "start": start,
                        "end": end,
                    })
                break  # one match per trigger

    return matches


# =============================================================================
# Banking & finance detectors (hedge fund / investor compliance)
# =============================================================================


def _context_digit_detector(
    pii_type: str,
    context_pattern: str,
    value_pattern: str,
    text: str,
    seen: set,
) -> List[PIIMatch]:
    """Helper: context-anchored digit/token detector."""
    matches: List[PIIMatch] = []
    context_re = re.compile(context_pattern, re.IGNORECASE)
    value_re = re.compile(value_pattern)
    for ctx in context_re.finditer(text):
        window_end = min(len(text), ctx.end() + DEFAULT_WINDOW)
        window = text[ctx.end():window_end]
        m = value_re.search(window)
        if m:
            start = ctx.end() + m.start()
            end = ctx.end() + m.end()
            key = (start, end)
            if key not in seen:
                seen.add(key)
                matches.append({
                    "type": pii_type,
                    "value": text[start:end],
                    "start": start,
                    "end": end,
                })
    return matches


def detect_bank_account(text: str) -> List[PIIMatch]:
    """Bank account numbers — context-triggered, 8-17 digit run."""
    seen = set()
    return _context_digit_detector(
        "bank_account",
        r"\b(?:bank\s+account(?:\s+number)?|account\s+number|checking\s+account|savings\s+account|bank\s+cut(?:\s+number)?|account\s+cut)\b",
        r"\b\d{8,17}\b",
        text,
        seen,
    )


def detect_routing_number(text: str) -> List[PIIMatch]:
    """ABA routing numbers — exactly 9 digits, context-anchored."""
    seen = set()
    return _context_digit_detector(
        "routing_number",
        r"\b(?:routing\s+(?:number|code)?|ABA(?:\s+(?:number|routing))?|wire\s+routing)\b",
        r"\b\d{9}\b",
        text,
        seen,
    )


def detect_iban(text: str) -> List[PIIMatch]:
    """IBAN — 2 country letters + 2 check digits + 11-30 alphanumeric (15-34 chars total)."""
    matches: List[PIIMatch] = []
    # IBANs are 15-34 chars; use overall length bound rather than rigid 4-char groups
    # (real IBANs from different countries have different lengths)
    pattern = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
    for m in pattern.finditer(text):
        # Exclude 12-char matches — those are ISIN, caught by detect_isin
        if len(m.group()) > 12:
            matches.append({"type": "iban", "value": m.group(), "start": m.start(), "end": m.end()})
    return matches


def detect_swift_bic(text: str) -> List[PIIMatch]:
    """SWIFT/BIC codes — context-anchored to reduce false positives."""
    seen = set()
    return _context_digit_detector(
        "swift_bic",
        r"\b(?:SWIFT(?:\s+code)?|BIC(?:\s+code)?)\b",
        r"\b[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b",
        text,
        seen,
    )


def detect_brokerage_account(text: str) -> List[PIIMatch]:
    """Brokerage / trading / custody account numbers."""
    seen = set()
    return _context_digit_detector(
        "brokerage_account",
        r"\b(?:brokerage(?:\s+account)?|trading\s+account|custody\s+account|custodian\s+account|investment\s+account|portfolio\s+account)\b",
        r"\b[A-Z0-9]{6,15}\b",
        text,
        seen,
    )


def detect_tax_id(text: str) -> List[PIIMatch]:
    """EIN / TIN — XX-XXXXXXX or 9 digits with context."""
    matches: List[PIIMatch] = []
    seen = set()

    # Formatted EIN anywhere: XX-XXXXXXX
    formatted_re = re.compile(r"\b\d{2}-\d{7}\b")
    for m in formatted_re.finditer(text):
        key = (m.start(), m.end())
        if key not in seen:
            seen.add(key)
            matches.append({"type": "tax_id", "value": m.group(), "start": m.start(), "end": m.end()})

    # Context-primed 9-digit run
    matches.extend(_context_digit_detector(
        "tax_id",
        r"\b(?:EIN|tax\s+ID(?:\s+number)?|employer\s+identification(?:\s+number)?|TIN|taxpayer\s+ID)\b",
        r"\b\d{9}\b",
        text,
        seen,
    ))
    return matches


def detect_date_of_birth(text: str) -> List[PIIMatch]:
    """DOB — context-anchored date in common formats."""
    seen = set()
    # Matches: M/D/YYYY, MM/DD/YYYY, M-D-YYYY, YYYY-MM-DD, "Month D YYYY", "Month D, YYYY"
    value_pattern = (
        r"(?:"
        r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"  # 4/15/1987 or 04-15-1987
        r"|\d{4}-\d{1,2}-\d{1,2}"  # 1987-04-15
        r"|(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{2,4}"
        r")"
    )
    return _context_digit_detector(
        "date_of_birth",
        r"\b(?:date\s+of\s+birth|DOB|born\s+on|birthday|birthdate)\b",
        value_pattern,
        text,
        seen,
    )


def detect_address(text: str) -> List[PIIMatch]:
    """Street addresses — number + words + street suffix."""
    matches: List[PIIMatch] = []
    seen = set()
    # Number + 1-5 words + common street suffix
    suffix = r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl|Way|Circle|Cir|Parkway|Pkwy|Highway|Hwy)"
    pattern = re.compile(
        rf"\b\d{{1,6}}\s+(?:[A-Z][a-zA-Z]*\s+){{1,5}}{suffix}\b\.?",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        key = (m.start(), m.end())
        if key not in seen:
            seen.add(key)
            matches.append({"type": "address", "value": m.group(), "start": m.start(), "end": m.end()})
    return matches


def detect_passport(text: str) -> List[PIIMatch]:
    """Passport number — context-anchored."""
    seen = set()
    # US: letter + 8 digits, International: 9 alphanumeric
    return _context_digit_detector(
        "passport",
        r"\bpassport(?:\s+(?:number|no|#))?\b",
        r"\b[A-Z]\d{8}\b|\b[A-Z0-9]{9}\b",
        text,
        seen,
    )


def detect_drivers_license(text: str) -> List[PIIMatch]:
    """Driver's license number — context-anchored."""
    seen = set()
    return _context_digit_detector(
        "drivers_license",
        r"\b(?:driver[''`]?s?\s+license|DL(?:\s+number)?|license\s+number)\b",
        r"\b[A-Z0-9]{7,13}\b",
        text,
        seen,
    )


def detect_cusip(text: str) -> List[PIIMatch]:
    """CUSIP — 9-character security identifier. Context-anchored."""
    seen = set()
    return _context_digit_detector(
        "cusip",
        r"\bCUSIP(?:\s+(?:number|code))?\b",
        r"\b[A-Z0-9]{9}\b",
        text,
        seen,
    )


def detect_isin(text: str) -> List[PIIMatch]:
    """ISIN — 12-character international security identifier. Standalone."""
    matches: List[PIIMatch] = []
    # ISIN: 2 country letters + 9 alphanumeric + 1 check digit
    pattern = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b")
    for m in pattern.finditer(text):
        matches.append({"type": "isin", "value": m.group(), "start": m.start(), "end": m.end()})
    return matches


def detect_name(text: str) -> List[PIIMatch]:
    """
    Detect names via context phrases. Captures the next 1-3 word tokens.
    Excludes common stop-words and role nouns from the capture.
    """
    matches: List[PIIMatch] = []
    seen = set()

    # Trigger phrases — after these, the next words are likely a name
    context_re = re.compile(
        r"\b(?:this\s+is|my\s+name(?:\s+is)?|i\s*['`]?\s*m(?:\s+called)?"
        r"|i\s+am|speaking\s+with|introducing|name['`]?s)\b[\s,:]+",
        re.IGNORECASE,
    )

    # Words we should not capture even if they follow a trigger.
    # Includes conjunctions that would otherwise get glued to the name.
    stop = {
        "a", "an", "the", "here", "there", "ready", "done", "going", "trying",
        "not", "just", "really", "very", "so", "actually", "looking", "working",
        "excited", "happy", "sorry", "thinking", "wondering", "from", "with",
        "calling", "reaching", "following", "hello", "hi", "hey", "okay", "ok",
        "yes", "no", "yeah", "yep", "sure", "fine", "good", "great",
        "your", "our", "their", "his", "her", "my",
        "and", "or", "but", "because", "since", "while", "when", "who", "that",
        "which", "at", "in", "on", "for", "to", "of", "by",
    }

    # Token: capitalized word OR any word (ASR may not capitalize)
    # We bias toward capitalized when available, but fall back to lowercase
    # if the trigger is strong.
    word_re = re.compile(r"[A-Za-z][A-Za-z'-]{1,30}")

    for ctx in context_re.finditer(text):
        after_start = ctx.end()
        window_end = min(len(text), after_start + 60)
        window = text[after_start:window_end]
        # Pull up to 3 consecutive name tokens
        tokens = []
        pos = 0
        for wm in word_re.finditer(window):
            if wm.start() > pos + 2:  # stop at punctuation gap
                break
            lower = wm.group().lower()
            if lower in stop:
                break
            tokens.append((wm.start(), wm.end(), wm.group()))
            pos = wm.end()
            if len(tokens) >= 3:
                break
        if tokens:
            first_start = after_start + tokens[0][0]
            last_end = after_start + tokens[-1][1]
            # Don't capture a fragment that's clearly not a name (too short, all-lower single letter, etc.)
            if last_end - first_start >= 2:
                key = (first_start, last_end)
                if key not in seen:
                    seen.add(key)
                    matches.append({
                        "type": "name",
                        "value": text[first_start:last_end],
                        "start": first_start,
                        "end": last_end,
                    })

    return matches


def detect_api_key(text: str) -> List[PIIMatch]:
    """API keys — prefixed and long alphanumeric."""
    matches: List[PIIMatch] = []
    pattern = re.compile(r"\b(?:sk|pk|api)[_-][A-Za-z0-9]{20,}\b")
    for m in pattern.finditer(text):
        matches.append({"type": "api_key", "value": m.group(), "start": m.start(), "end": m.end()})
    return matches


# =============================================================================
# Registry
# =============================================================================

# Types that use LangChain's built-in detection (regex-based, for written text)
BUILTIN_PII_TYPES = ["ip", "mac_address", "url"]

# Types that use our context-aware callable detectors (handle ASR + written)
CALLABLE_DETECTORS: Dict[str, Callable[[str], List[PIIMatch]]] = {
    # Identity
    "ssn": detect_ssn,
    "phone": detect_phone,
    "email": detect_email,
    "name": detect_name,
    "date_of_birth": detect_date_of_birth,
    "address": detect_address,
    "passport": detect_passport,
    "drivers_license": detect_drivers_license,
    # Financial — personal
    "credit_card": detect_credit_card,
    "bank_account": detect_bank_account,
    "routing_number": detect_routing_number,
    "iban": detect_iban,
    "swift_bic": detect_swift_bic,
    "tax_id": detect_tax_id,
    # Financial — investment (hedge fund / investor compliance)
    "brokerage_account": detect_brokerage_account,
    "cusip": detect_cusip,
    "isin": detect_isin,
    # Technical
    "api_key": detect_api_key,
}

ALL_PII_TYPES = BUILTIN_PII_TYPES + list(CALLABLE_DETECTORS.keys())


# Cache PIIMiddleware instances per (type, strategy)
_middleware_cache: Dict[str, PIIMiddleware] = {}


def _get_middleware(pii_type: str, strategy: str = "redact") -> PIIMiddleware:
    """Get or create a cached PIIMiddleware instance."""
    key = f"{pii_type}:{strategy}"
    if key not in _middleware_cache:
        kwargs: Dict[str, Any] = {"pii_type": pii_type, "strategy": strategy}
        if pii_type in CALLABLE_DETECTORS:
            kwargs["detector"] = CALLABLE_DETECTORS[pii_type]
        _middleware_cache[key] = PIIMiddleware(**kwargs)
    return _middleware_cache[key]


def _run_detection(
    text: str,
    strategy: str = "redact",
    pii_types: Optional[List[str]] = None,
) -> Tuple[str, List[PIIMatch]]:
    """Run detection + redaction across multiple PII types."""
    types_to_check = pii_types or ALL_PII_TYPES
    all_matches: List[PIIMatch] = []
    processed = text

    for pii_type in types_to_check:
        if pii_type not in ALL_PII_TYPES:
            logger.warning(f"Unknown PII type: {pii_type}, skipping")
            continue
        mw = _get_middleware(pii_type, strategy)
        processed, matches = mw._process_content(processed)
        all_matches.extend(matches)

    return processed, all_matches


def _make_custom_type_detector(custom_type: Dict[str, Any]) -> Callable[[str], List[PIIMatch]]:
    """Build a context-aware detector from a profile's custom_type spec.

    custom_type shape: {"name": str, "trigger_phrases": [str], "value_regex": str}
    """
    name = custom_type["name"]
    triggers = custom_type.get("trigger_phrases") or []
    value_regex = custom_type.get("value_regex") or ""

    if not value_regex:
        # No pattern to match — no-op detector
        return lambda text: []

    # If triggers exist, anchor detection to them; otherwise match anywhere
    if triggers:
        trigger_pattern = "|".join(re.escape(t) for t in triggers)
        context_re = re.compile(rf"\b(?:{trigger_pattern})\b", re.IGNORECASE)
        value_re = re.compile(value_regex)

        def detector(text: str) -> List[PIIMatch]:
            matches: List[PIIMatch] = []
            seen = set()
            for ctx in context_re.finditer(text):
                window_end = min(len(text), ctx.end() + DEFAULT_WINDOW)
                window = text[ctx.end():window_end]
                m = value_re.search(window)
                if m:
                    start = ctx.end() + m.start()
                    end = ctx.end() + m.end()
                    key = (start, end)
                    if key not in seen:
                        seen.add(key)
                        matches.append({
                            "type": name,
                            "value": text[start:end],
                            "start": start,
                            "end": end,
                        })
            return matches
        return detector
    else:
        # No context triggers — match regex anywhere
        value_re = re.compile(value_regex)

        def detector(text: str) -> List[PIIMatch]:
            return [
                {"type": name, "value": m.group(), "start": m.start(), "end": m.end()}
                for m in value_re.finditer(text)
            ]
        return detector


def _run_detection_with_profile(
    text: str,
    strategy: str,
    profile: Dict[str, Any],
) -> Tuple[str, List[PIIMatch]]:
    """Run detection using a profile's rules layered on top of built-ins.

    Order of operations:
      1. Blocklist terms redacted as [REDACTED_CUSTOM] (literal match)
      2. Custom types from profile (context-aware from triggers)
      3. Built-in types (subset if enabled_builtin_types is non-empty, else all)
      4. Allowlist terms are restored — their positions are protected from
         redaction by marking and un-redacting.
    """
    blocklist = profile.get("blocklist") or []
    allowlist = profile.get("allowlist") or []
    custom_types = profile.get("custom_types") or []
    enabled_builtin = profile.get("enabled_builtin_types") or []

    all_matches: List[PIIMatch] = []
    processed = text

    # Allowlist spans must be recomputed against the CURRENT text before each
    # detection pass: every redaction replaces a substring with a placeholder
    # of different length, shifting all subsequent offsets, so spans captured
    # against an earlier text version would protect the wrong ranges.
    def _allowed_spans_in(current: str) -> List[Tuple[int, int]]:
        spans: List[Tuple[int, int]] = []
        for term in allowlist:
            if not term:
                continue
            for m in re.finditer(re.escape(term), current, re.IGNORECASE):
                spans.append((m.start(), m.end()))
        return spans

    allowed_spans = _allowed_spans_in(processed)

    def is_allowed(start: int, end: int) -> bool:
        return any(a <= start and end <= b for a, b in allowed_spans)

    # 1. Blocklist — literal match redaction
    for term in blocklist:
        if not term:
            continue
        for m in re.finditer(re.escape(term), processed, re.IGNORECASE):
            if is_allowed(m.start(), m.end()):
                continue
            all_matches.append({
                "type": "custom",
                "value": m.group(),
                "start": m.start(),
                "end": m.end(),
            })
    # Redact blocklist matches
    for match in sorted(
        [m for m in all_matches if m["type"] == "custom"],
        key=lambda m: m["start"],
        reverse=True,
    ):
        processed = processed[:match["start"]] + "[REDACTED_CUSTOM]" + processed[match["end"]:]

    # 2. Custom types
    for ct in custom_types:
        detector = _make_custom_type_detector(ct)
        ct_matches = detector(processed)
        # Filter out allowlisted matches — recompute spans against the text
        # version these match offsets refer to (earlier redactions shifted it)
        allowed_spans = _allowed_spans_in(processed)
        ct_matches = [m for m in ct_matches if not is_allowed(m["start"], m["end"])]
        if ct_matches:
            # Apply replacements in reverse so positions stay valid
            for match in sorted(ct_matches, key=lambda m: m["start"], reverse=True):
                placeholder = f"[REDACTED_{ct['name'].upper()}]"
                processed = processed[:match["start"]] + placeholder + processed[match["end"]:]
            all_matches.extend(ct_matches)

    # 3. Built-in types
    builtin_subset = enabled_builtin if enabled_builtin else ALL_PII_TYPES
    for pii_type in builtin_subset:
        if pii_type not in ALL_PII_TYPES:
            continue
        mw = _get_middleware(pii_type, strategy)
        new_processed, matches = mw._process_content(processed)
        # Filter out allowlisted matches. Match offsets refer to the current
        # `processed` text, so recompute allowlist spans against it first.
        allowed_spans = _allowed_spans_in(processed)
        if matches:
            # Keep matches that are NOT inside allowed spans
            safe_matches = [m for m in matches if not is_allowed(m["start"], m["end"])]
            if len(safe_matches) == len(matches):
                # No allowlist conflicts — use the redacted output
                processed = new_processed
                all_matches.extend(matches)
            else:
                # Some matches were in allowed spans — selectively re-redact
                # just the safe ones on the original text
                for m in sorted(safe_matches, key=lambda x: x["start"], reverse=True):
                    label = f"[REDACTED_{m['type'].upper()}]"
                    processed = processed[:m["start"]] + label + processed[m["end"]:]
                all_matches.extend(safe_matches)

    return processed, all_matches


def _format_summary(matches: List[PIIMatch]) -> str:
    """Format a human-readable detection summary."""
    if not matches:
        return "No PII detected."
    counts: Dict[str, int] = {}
    for m in matches:
        counts[m["type"]] = counts.get(m["type"], 0) + 1
    parts = [f"{count} {pii_type}" for pii_type, count in counts.items()]
    return f"Detected: {', '.join(parts)}"


# =============================================================================
# Tools (LangChain @tool)
# =============================================================================


@tool
async def pii_redact(
    text: str,
    strategy: str = "redact",
    pii_types: Optional[str] = None,
    profile_id: Optional[int] = None,
) -> str:
    """
    Detect and redact personally identifiable information (PII) in text.

    Context-aware detection handles both written text and ASR output
    (e.g. "my SSN is 555121234" or "email me at foo at bar dot com").

    Args:
        text: The text to scan and redact.
        strategy: How to handle detected PII. One of:
            - 'redact' (default): Replace with [REDACTED_TYPE]
            - 'mask': Partially mask values
            - 'hash': Replace with deterministic hash
        pii_types: Comma-separated PII types to detect. If omitted, checks all.
            Ignored if profile_id is provided.
        profile_id: Optional PII profile ID. When set, applies that profile's
            blocklist, allowlist, custom types, and enabled built-in types.

    Returns:
        The redacted text followed by a detection summary.
    """
    if strategy not in ("redact", "mask", "hash"):
        return f"Error: strategy must be 'redact', 'mask', or 'hash'. Got '{strategy}'."

    # Profile path — overrides pii_types
    if profile_id:
        try:
            from db.database import AsyncSessionLocal
            from models.pii_profile import PIIProfile
            from sqlalchemy import select

            async with AsyncSessionLocal() as db:
                result = await db.execute(select(PIIProfile).where(PIIProfile.id == profile_id))
                profile = result.scalar_one_or_none()
                if not profile:
                    return f"Error: PII profile {profile_id} not found."

                processed, matches = _run_detection_with_profile(
                    text=text,
                    strategy=strategy,
                    profile={
                        "blocklist": profile.blocklist or [],
                        "allowlist": profile.allowlist or [],
                        "custom_types": profile.custom_types or [],
                        "enabled_builtin_types": profile.enabled_builtin_types or [],
                    },
                )
                summary = _format_summary(matches)
                if not matches:
                    return f"{text}\n\n{summary}"
                return f"{processed}\n\n{summary}"
        except Exception as e:
            logger.error(f"Failed to apply profile {profile_id}: {e}", exc_info=True)
            return f"Error applying profile {profile_id}: {e}"

    # Standard path — built-in detectors only
    types_list = [t.strip() for t in pii_types.split(",")] if pii_types else None
    processed, matches = _run_detection(text, strategy, types_list)
    summary = _format_summary(matches)

    if not matches:
        return f"{text}\n\n{summary}"
    return f"{processed}\n\n{summary}"


@tool
async def pii_detect(
    text: str,
    pii_types: Optional[str] = None,
) -> str:
    """
    Scan text for PII and report findings WITHOUT modifying the text.

    Args:
        text: The text to scan.
        pii_types: Comma-separated PII types to check. If omitted, checks all.

    Returns:
        A structured report of detected PII with types, values, and positions.
    """
    types_list = [t.strip() for t in pii_types.split(",")] if pii_types else None

    _, matches = _run_detection(text, "redact", types_list)

    if not matches:
        return "No PII detected in the provided text."

    lines = [f"Found {len(matches)} PII item(s):\n"]
    for i, m in enumerate(matches, 1):
        lines.append(
            f"  {i}. [{m['type'].upper()}] \"{m['value']}\" "
            f"(position {m['start']}-{m['end']})"
        )

    counts: Dict[str, int] = {}
    for m in matches:
        counts[m["type"]] = counts.get(m["type"], 0) + 1
    lines.append(f"\nSummary: {', '.join(f'{c} {t}' for t, c in counts.items())}")

    return "\n".join(lines)
