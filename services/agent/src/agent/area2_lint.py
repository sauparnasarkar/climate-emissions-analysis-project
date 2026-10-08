"""Deterministic checks for Area 2 answers -- SPEC.md §15.3 rule 6.

Pure functions over an answer's text and its scope notes, used by the golden-prompt eval
(`evals/run_area2.py`) and unit-tested hermetically. They are deliberately a coarse safety net:
a flagged sentence is a prompt for a human to look, and a clean result is not a proof of quality.
Negations ("never called TCRE", "not a contribution to warming") are recognised so the correct
framing is not flagged.
"""

from __future__ import annotations

import re

_NEGATION = re.compile(r"\b(not|never|no|n't|cannot|isn't|doesn't|without|neither|nor)\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")

# Large emitters a model might blame; a coarse list, not the country resolver.
_COUNTRIES = (
    "China", "United States", "USA", "US", "India", "Russia", "Japan", "Germany", "Brazil",
    "United Kingdom", "UK", "Indonesia", "Canada", "Australia", "Saudi Arabia", "Iran",
)
_BLAME = re.compile(r"\b(caus(?:ed|es|ing)|responsible for|to blame for|driving|driven by)\b", re.I)
_WARMING = re.compile(r"\b(warming|temperature (?:rise|increase|anomaly)|global temperature|climate change)\b", re.I)
_PROVE = re.compile(r"\b(prove[sd]?|proven|proof)\b", re.I)
_GAP = re.compile(r"\b5\s*(?:[-–]|to)\s*8\s*%")
_SLOPE = re.compile(r"°C per 1,?000 ?Gt", re.I)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text) if s.strip()]


def check_response(text: str, scope_notes: list[str] | None = None, *, scenario_answer: bool = False) -> list[str]:
    """Violations found in an answer (empty list = none flagged)."""
    notes = " ".join(scope_notes or [])
    combined = f"{text} {notes}"
    violations: list[str] = []

    for sentence in _sentences(text):
        negated = bool(_NEGATION.search(sentence))
        if re.search(r"\bTCRE\b", sentence) and re.search(r"all-gas|PRIMAP|total (?:GHG|greenhouse)", sentence, re.I) and not negated:
            violations.append(f"all-gas relationship presented as TCRE: {sentence!r}")
        if _BLAME.search(sentence) and _WARMING.search(sentence) and not negated:
            if any(re.search(rf"\b{re.escape(c)}\b", sentence) for c in _COUNTRIES):
                violations.append(f"warming attributed to a country: {sentence!r}")
        if _PROVE.search(sentence) and re.search(r"emission|CO2|warming|temperature", sentence, re.I) and not negated:
            violations.append(f"correlation presented as proof: {sentence!r}")
        # Negation is judged within the sentence that carries the figure: an unrelated "do not" in a
        # neighbouring sentence must not excuse quoting the unmeasured 5-8% as a measured result.
        if _GAP.search(sentence) and not negated:
            violations.append(f"OWID/PRIMAP 5-8% difference quoted as measured: {sentence!r}")

    if _SLOPE.search(text) and not re.search(r"preliminary", combined, re.I):
        violations.append("temperature slope quoted without the preliminary-release note")
    if scenario_answer and not re.search(r"illustrative", combined, re.I):
        violations.append("scenario temperature not labelled illustrative")
    return violations
