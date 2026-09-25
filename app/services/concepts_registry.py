"""
Single source of truth for the search bar's REGEX CONCEPTS / AI-ASSISTED NER
pills (see web/index.html). Factory/ListConcepts exposes this to the viewer;
Factory/SearchConcept dispatches a conceptId to app.services.regex_concepts or
app.services.ner_search based on which list it's found in.

Chase ID has no fixed standard format across health plans, so its pattern is
a generic placeholder (prefix letters + digits) overridable via
DOCSVC_CHASE_ID_REGEX without touching code.
"""
import os
import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RegexConcept:
    id: str
    label: str
    pattern: "re.Pattern"


@dataclass(frozen=True)
class NerConcept:
    id: str
    label: str
    gliner_label: str  # zero-shot label text sent to the GLiNER2 sidecar
    threshold: Optional[float] = None  # None = use ner_client's global default


_DATE_PATTERN = r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b"
_CHASE_ID_PATTERN = os.environ.get("DOCSVC_CHASE_ID_REGEX", r"\b[A-Z]{2,5}-?\d{6,10}\b")

REGEX_CONCEPTS = [
    RegexConcept("email", "Email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    RegexConcept("phone", "Phone", re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    # DOB and Visit Date share a pattern -- regex alone can't tell the two
    # apart semantically, only "AI-assisted NER"'s "Any date" concept does
    # that. Kept as two pills to match the source design and because a real
    # deployment would likely scope each to a page region/label context.
    RegexConcept("dob", "DOB", re.compile(_DATE_PATTERN)),
    RegexConcept("visit_date", "Visit Date", re.compile(_DATE_PATTERN)),
    RegexConcept("chase_id", "Chase ID", re.compile(_CHASE_ID_PATTERN)),
]

NER_CONCEPTS = [
    NerConcept("person_name", "Person / member name", "person or member full name"),
    NerConcept("any_date", "Any date", "date"),
    NerConcept("diagnosis", "Diagnosis / condition", "medical diagnosis or condition"),
    NerConcept("medication", "Medication", "medication or drug name"),
    NerConcept("quality_measure", "Quality measure", "healthcare quality measure name"),
    NerConcept("submeasure", "Submeasure", "healthcare quality submeasure name"),
    # Lower threshold than the other NER concepts: this label needs it to
    # reliably catch vitals lines (blank at the 0.4 global default in testing).
    NerConcept("vitals", "Vitals", "vital signs", threshold=0.25),
]

_REGEX_BY_ID = {c.id: c for c in REGEX_CONCEPTS}
_NER_BY_ID = {c.id: c for c in NER_CONCEPTS}


def get_regex_concept(concept_id: str):
    return _REGEX_BY_ID.get(concept_id)


def get_ner_concept(concept_id: str):
    return _NER_BY_ID.get(concept_id)
