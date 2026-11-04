"""Illustrative sample commentary, one snippet per asset class, fed to
evidence.py's extractor so a recommendation can carry supporting
evidence for a reviewer to read -- not live news, not scraped, and
labeled as such everywhere it's displayed.

This is the honest version of "wire the evidence layer into
something": a real version would pull same-day text from an actual
news or filings feed per holding. That's a separate, larger piece of
work (point-in-time data integrity matters a lot once the text is real,
see ENGINEERING.md). This module exists so the review-queue path from
recommendation to evidence is real and testable today, without
pretending the underlying text is live.
"""

COMMENTARY = {
    "Equity": {
        "text": "Corporate earnings have broadly beat expectations this quarter, "
                "with several large caps raising forward guidance on resilient "
                "consumer demand.",
        "source": "illustrative sample commentary",
    },
    "Bonds": {
        "text": "Rate expectations have been volatile as the Fed weighs inflation "
                "data against signs of a cooling labor market.",
        "source": "illustrative sample commentary",
    },
    "Commodities": {
        "text": "Supply disruptions at several major shipping routes have raised "
                "near-term price pressure across industrial commodities.",
        "source": "illustrative sample commentary",
    },
    "Real Estate": {
        "text": "Commercial property valuations remain under pressure from higher "
                "financing costs, though residential demand has shown a modest rebound.",
        "source": "illustrative sample commentary",
    },
    "Private Markets": {
        "text": "Private equity exit activity has been slow, with sponsors extending "
                "hold periods amid a weaker IPO window.",
        "source": "illustrative sample commentary",
    },
    "Crypto": {
        "text": "Regulatory scrutiny of digital asset custody has increased, even as "
                "institutional adoption continues to expand.",
        "source": "illustrative sample commentary",
    },
}
