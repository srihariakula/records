"""
Combines multiple search criteria -- the free-text query and any number of
concept ids (app.services.concepts_registry) -- into a single AND search:
only pages where every selected criterion has at least one match are
returned, with the union of all their matched boxes on those pages so the
viewer can highlight everything at once. Backs Factory/SearchMultiCriteria.

Kept as its own module rather than folded into search_text.py /
regex_concepts.py / ner_search.py since it only ever calls into those, one
criterion at a time -- this is composition, not another matching strategy.
"""
from pathlib import Path
from typing import Dict, List, Optional

from app.services import ner_search, regex_concepts, search_text
from app.services.concepts_registry import get_ner_concept, get_regex_concept
from app.services.errors import ConversionError

Matches = Dict[int, List[List[float]]]


def _concept_matches(pdf_path: Path, concept_id: str) -> Matches:
    if get_regex_concept(concept_id) is not None:
        return regex_concepts.find_concept_matches(pdf_path, concept_id)
    if get_ner_concept(concept_id) is not None:
        return ner_search.find_concept_matches(pdf_path, concept_id)
    raise ConversionError(f"Unknown concept: {concept_id}", status_code=400)


def search_multi_criteria(
    pdf_path: Path,
    query: Optional[str],
    concept_ids: List[str],
    case_sensitive: bool = False,
    whole_word: bool = False,
    use_regex: bool = False,
    use_ner: bool = False,
) -> Matches:
    """Returns {page: [[x0,y0,x1,y1], ...]} for pages where EVERY criterion
    (the text query, if given, plus every concept id) has at least one
    match -- boxes from all criteria on a qualifying page are unioned
    together. Raises a 400 if neither a query nor any concept id is given.

    With `use_ner`, the query is sent to the GLiNER2 sidecar as a zero-shot
    entity label (e.g. "medication") instead of being matched literally, and
    the case/whole-word/regex flags are ignored."""
    criteria_results: List[Matches] = []
    if query and use_ner:
        criteria_results.append(ner_search.find_label_matches(pdf_path, query))
    elif query:
        criteria_results.append(
            search_text.search_document(
                pdf_path, query, case_sensitive=case_sensitive, whole_word=whole_word, use_regex=use_regex
            )
        )
    for concept_id in concept_ids:
        criteria_results.append(_concept_matches(pdf_path, concept_id))

    if not criteria_results:
        raise ConversionError("Provide a search query and/or at least one conceptId", status_code=400)

    qualifying_pages = set(criteria_results[0].keys())
    for result in criteria_results[1:]:
        qualifying_pages &= set(result.keys())

    combined: Matches = {}
    for page in sorted(qualifying_pages):
        boxes: List[List[float]] = []
        for result in criteria_results:
            boxes.extend(result.get(page, []))
        combined[page] = boxes
    return combined
