"""Deterministic input hygiene. Runs before any model sees customer text.

Blocking reasons are logged internally and never echoed back: telling an attacker which
pattern matched tells them what to try next.
"""

import re
import unicodedata
from dataclasses import dataclass

_ZERO_WIDTH = re.compile("[" + chr(0x200B) + "-" + chr(0x200F) + chr(0x2060) + chr(0xFEFF) + "]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ROLE_MARKERS = re.compile(
    r"<\|?/?\s*(?:im_start|im_end|system|assistant|user|developer)\s*\|?>"
    r"|^\s*(?:system|assistant|human|developer)\s*:",
    re.IGNORECASE | re.MULTILINE,
)
_INJECTION_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        # Instruction-like targets only: "ignore my previous message" is a normal correction.
        r"\b(?:ignore|disregard|forget)\b.{0,20}\b(?:previous|prior|above|earlier|system|your)\b"
        r".{0,20}\b(?:instructions?|prompts?|rules|guidelines|directives?)\b",
        r"\b(?:reveal|show|print|repeat|output)\b.{0,20}\b(?:system prompt|your instructions"
        r"|your prompt|hidden instructions)\b",
        r"\byou are now\b.{0,30}\b(?:developer mode|jailbroken|dan|unrestricted)\b",
        r"\b(?:approve|issue|process|force)\b.{0,30}\brefund\b.{0,30}\b(?:without|skip|bypass)\b"
        r".{0,20}\b(?:approval|review|policy|checks?)\b",
        r"</?\s*(?:documents?|system|instructions?|policy)\s*>",
    )
)
_EXCESS_WHITESPACE = re.compile(r"[ \t]{3,}|\n{3,}")


@dataclass(frozen=True)
class SanitizedInput:
    text: str
    truncated: bool
    stripped_role_markers: bool
    injection_suspected: bool

    @property
    def is_empty(self) -> bool:
        return not self.text


def sanitize(raw: str, max_chars: int) -> SanitizedInput:
    text = unicodedata.normalize("NFKC", raw)
    text = _CONTROL.sub("", _ZERO_WIDTH.sub("", text))
    injection_suspected = any(p.search(text) for p in _INJECTION_PATTERNS)

    without_markers = _ROLE_MARKERS.sub(" ", text)
    stripped = without_markers != text
    text = _EXCESS_WHITESPACE.sub(lambda m: "\n\n" if "\n" in m.group() else " ", without_markers)
    text = text.strip()

    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars].rstrip()
    return SanitizedInput(
        text=text,
        truncated=truncated,
        stripped_role_markers=stripped,
        injection_suspected=injection_suspected,
    )


# Retrieved help-center text is untrusted too: it reaches the model inside the prompt, so an
# article that was tampered with (or ingested from a poisoned source) is an injection channel
# just like a customer message. These patterns look for text that talks TO the model.
_DOCUMENT_INJECTION_PATTERNS = _INJECTION_PATTERNS + tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:ignore|disregard|forget|override|bypass)\b.{0,30}"
        r"\b(?:instructions?|rules|guidelines|polic(?:y|ies)|approval)\b",
        r"\bnew (?:instructions?|rules|policy)\b.{0,10}:",
        r"\b(?:system|developer) (?:prompt|message|override)\b",
        r"\b(?:you|assistant) (?:must|should|will|shall)\b.{0,40}"
        r"\b(?:approve|reveal|ignore|disregard|obey|comply|pretend)\b",
        r"\bdo not (?:tell|mention|inform|reveal|show)\b.{0,30}\b(?:customer|user)\b",
        r"\b(?:approve|grant|issue)\b.{0,20}\b(?:all|every|any)\b.{0,20}\brefunds?\b",
        r"</?\s*(?:document|documents|system|assistant|user|instructions?|policy)\b[^>]*>",
    )
)


@dataclass(frozen=True)
class SanitizedDocument:
    text: str
    # True when the passage reads like an instruction aimed at the model. It is dropped, and the
    # reason is logged internally only.
    quarantined: bool


def _normalize(text: str) -> str:
    return _CONTROL.sub("", _ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", text)))


def sanitize_document(content: str, *context: str) -> SanitizedDocument:
    """Clean one retrieved passage before it enters a prompt.

    `content` is the body that will be cleaned and returned. `context` (the title and heading)
    is only checked, because those also end up in the prompt.
    """
    body = _normalize(content)
    scanned = "\n".join([body, *(_normalize(part) for part in context)])
    quarantined = any(p.search(scanned) for p in _DOCUMENT_INJECTION_PATTERNS)
    body = _ROLE_MARKERS.sub(" ", body)
    body = _EXCESS_WHITESPACE.sub(lambda m: "\n\n" if "\n" in m.group() else " ", body).strip()
    return SanitizedDocument(text=body, quarantined=quarantined)


BOOKING_REFERENCE = re.compile(r"\bBK-?(\d{4,8})\b", re.IGNORECASE)


def extract_booking_reference(text: str) -> str | None:
    """Deterministic first: a regex beats asking a model to copy an ID."""
    match = BOOKING_REFERENCE.search(text)
    return f"BK-{match.group(1)}" if match else None
