"""
Builds a per-page (text, word->bbox index) so char-offset-based matches --
regex finditer spans, GLiNER2 entity spans -- can be mapped back to PDF-point
bounding boxes.

This is deliberately not built on page.search_for (what search_text.py's
plain-substring fast path uses): search_for re-searches the page for an exact
string and can't be driven by a (start, end) offset, so it breaks down once a
match's text isn't unique on the page (e.g. a name or date that appears more
than once). Building the index once per page and unioning the word boxes that
fall inside a given char range handles that correctly and is shared by
app.services.regex_concepts and app.services.ner_search.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import fitz  # PyMuPDF


@dataclass
class WordSpan:
    start: int
    end: int
    bbox: Tuple[float, float, float, float]


@dataclass
class PageTextIndex:
    text: str
    words: List[WordSpan] = field(default_factory=list)

    def bbox_for_range(self, start: int, end: int) -> Optional[List[float]]:
        """Unions the boxes of every word overlapping [start, end). Returns
        None if the range covers no indexed word (e.g. pure whitespace)."""
        boxes = [w.bbox for w in self.words if w.end > start and w.start < end]
        if not boxes:
            return None
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[2] for b in boxes)
        y1 = max(b[3] for b in boxes)
        return [x0, y0, x1, y1]


def build_page_index(page: "fitz.Page") -> PageTextIndex:
    """Joins the page's words with single spaces. This normalizes whitespace
    (multiple spaces/newlines collapse to one) rather than reproducing the
    PDF's exact layout text -- fine for regex/NER matching, not meant for
    display (Page/GetText's own build_text path is unaffected by this)."""
    words = page.get_text("words")  # (x0, y0, x1, y1, word, block_no, line_no, word_no)
    text_parts: List[str] = []
    spans: List[WordSpan] = []
    offset = 0
    for x0, y0, x1, y1, word, *_ in words:
        start = offset
        end = start + len(word)
        spans.append(WordSpan(start, end, (x0, y0, x1, y1)))
        text_parts.append(word)
        offset = end + 1  # +1 for the joining space
    return PageTextIndex(text=" ".join(text_parts), words=spans)
