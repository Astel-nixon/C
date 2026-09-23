"""Evidence extraction from text -- the first slice of the NLP layer.

The schema below is the actual point of this module: notice what's
missing from it. No expected_return, no price_target, no probability --
nothing that looks like a number an optimizer could consume directly.
An extractor here can be as wrong as it wants about sentiment or event
classification without that error ever masquerading as a return
estimate downstream. That's the whole "LLMs interpret, quantitative
models measure" split in practice, not just as a stated principle.

The default extractor is a plain keyword-lexicon scorer -- the same
basic idea as the Loughran-McDonald financial sentiment word lists that
are the standard baseline in finance NLP research, just a much smaller
hand-built list here. It needs no external API, no key, and runs
entirely offline, which is exactly why it's the default: a real LLM-
backed extractor can be dropped in behind the same Evidence schema
later (same validate() call, different function producing the dict)
without anything downstream needing to change.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

POSITIVE_WORDS = {
    "beat", "beats", "beating", "growth", "expansion", "upgrade", "upgraded", "strong",
    "record", "surge", "surged", "outperform", "raise", "raised", "profitable", "resilient",
    "rebound", "recovery", "robust", "accelerating",
}

NEGATIVE_WORDS = {
    "miss", "misses", "missed", "decline", "declined", "downgrade", "downgraded", "weak",
    "recall", "lawsuit", "investigation", "shortfall", "layoffs", "layoff", "bankruptcy",
    "default", "delay", "delayed", "disruption", "cut", "cuts", "warning", "slump", "plunge",
}

EVENT_KEYWORDS = {
    "earnings": {"earnings", "revenue", "eps", "guidance", "quarter", "quarterly"},
    "regulatory": {"regulator", "regulation", "sec", "lawsuit", "investigation", "fine", "compliance"},
    "supply_chain": {"supply", "shipment", "shortage", "factory", "production", "logistics"},
    "macro": {"inflation", "rate", "rates", "fed", "recession", "gdp", "employment", "tariff", "tariffs"},
}


@dataclass(frozen=True)
class Evidence:
    entity: str  # company/asset name or ticker the text is about, as given by the caller
    event_type: str  # one of EVENT_KEYWORDS' keys, or "general"
    sentiment: float  # -1..1, a qualitative read only -- not a return estimate
    confidence: float  # 0..1, the extractor's own self-reported confidence
    source: str
    timestamp: str  # ISO 8601
    summary: str
    keywords_matched: tuple[str, ...] = field(default_factory=tuple)
    ticker: str | None = None  # matched instrument ticker, if the caller supplied a universe


REQUIRED_FIELDS = {"entity", "event_type", "sentiment", "source", "timestamp", "summary"}


def validate_evidence(data: dict) -> Evidence:
    """Schema check before anything gets treated as real evidence.

    A stand-in for the retry-on-validation-failure loop a real LLM
    extractor would need: here it just guards the rule-based extractor's
    own output, but it's the same contract a model-backed extractor
    would have to satisfy -- fail loud, don't let a malformed record
    through silently.
    """
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise ValueError(f"evidence record missing required fields: {sorted(missing)}")
    if not -1.0 <= data["sentiment"] <= 1.0:
        raise ValueError(f"sentiment out of range: {data['sentiment']}")
    confidence = data.get("confidence", 0.0)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"confidence out of range: {confidence}")
    return Evidence(
        entity=data["entity"], event_type=data["event_type"], sentiment=float(data["sentiment"]),
        confidence=float(confidence), source=data["source"], timestamp=data["timestamp"],
        summary=data["summary"], keywords_matched=tuple(data.get("keywords_matched", ())),
        ticker=data.get("ticker"),
    )


def _classify_event_type(tokens: set[str]) -> str:
    best_type, best_count = "general", 0
    for event_type, keywords in EVENT_KEYWORDS.items():
        count = len(tokens & keywords)
        if count > best_count:
            best_type, best_count = event_type, count
    return best_type


def extract_evidence(text: str, source: str, timestamp: str, ticker: str | None = None) -> Evidence:
    tokens = set(re.findall(r"[a-z]+", text.lower()))

    positive_hits = tokens & POSITIVE_WORDS
    negative_hits = tokens & NEGATIVE_WORDS
    total_hits = len(positive_hits) + len(negative_hits)

    sentiment = 0.0 if total_hits == 0 else (len(positive_hits) - len(negative_hits)) / total_hits
    confidence = min(total_hits / 5.0, 1.0)  # more keyword hits -> more confident in the read
    event_type = _classify_event_type(tokens)
    matched = tuple(sorted(positive_hits | negative_hits))

    tone = "Positive" if sentiment > 0.15 else "Negative" if sentiment < -0.15 else "Neutral"
    summary = (
        f"{tone} tone ({len(positive_hits)} positive / {len(negative_hits)} negative keyword "
        f"hits), classified as '{event_type}'."
    )

    data = {
        "entity": ticker or "unknown", "event_type": event_type, "sentiment": round(sentiment, 3),
        "confidence": round(confidence, 3), "source": source, "timestamp": timestamp,
        "summary": summary, "keywords_matched": matched, "ticker": ticker,
    }
    return validate_evidence(data)


def extract_evidence_batch(snippets: list[dict]) -> list[Evidence]:
    """snippets: list of {"text", "source", "timestamp", "ticker" (optional)}."""
    return [
        extract_evidence(s["text"], s["source"], s["timestamp"], s.get("ticker"))
        for s in snippets
    ]


def evidence_to_dict(evidence: Evidence) -> dict:
    return asdict(evidence)
