"""Keyword search for the application's own lists (Fact Explorer, expert
queue, review history) - not the verification evidence search.

A query is split into unique, meaningful keywords (Bangla/English, Unicode
NFC, whitespace/punctuation separated, stopwords dropped). An item matches
when ANY keyword appears in any searched column (OR), so a three-word query
also returns partial matches. Ranking: more distinct keywords matched first
(a word repeated in the text never counts twice); ties prefer an exact phrase
match, then keywords found in the headline; the caller's existing ordering
and a stable id tie-break follow. Values are always bound parameters and
`%`/`_`/`\\` are escaped, so the query is never interpreted as a pattern.
"""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import ColumnElement, case, literal, or_

from app.shared.utils.keyword_extractor import BANGLA_STOPWORDS

MAX_KEYWORDS = 8
_SPLIT_RE = re.compile(r"[\s\.,।॥!?\"'`()\[\]{}<>:;|/\\\-–—_+=*&^%$#@~]+")
_ENGLISH_STOPWORDS = frozenset(
    {"a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "is", "are", "was", "by", "with"}
)


def normalize_query(text: str | None) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text or "")).strip()


def split_keywords(text: str | None) -> list[str]:
    """Unique meaningful keywords, in query order."""
    out: list[str] = []
    seen: set[str] = set()
    for token in _SPLIT_RE.split(normalize_query(text)):
        key = token.casefold()
        if not key or key in seen:
            continue
        if key in _ENGLISH_STOPWORDS or token in BANGLA_STOPWORDS:
            continue
        if len(key) < 2 and key.isascii() and not key.isdigit():
            continue
        seen.add(key)
        out.append(token)
        if len(out) >= MAX_KEYWORDS:
            break
    return out


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# য় ড় ঢ় have precomposed code points (U+09DF, U+09DC, U+09DD) that are
# Unicode composition exclusions: NFC always splits them into letter + nukta.
# Stored text keeps whichever form was typed, so a term is matched in both.
_NUKTA_PRECOMPOSED = {"য়": "য়", "ড়": "ড়", "ঢ়": "ঢ়"}


def spellings(term: str) -> list[str]:
    """The term as typed in NFC, plus its precomposed-nukta spelling if different."""
    nfc = unicodedata.normalize("NFC", term)
    composed = nfc
    for split, joined in _NUKTA_PRECOMPOSED.items():
        composed = composed.replace(split, joined)
    return [nfc] if composed == nfc else [nfc, composed]


def _contains(column, term: str) -> ColumnElement[bool]:
    return or_(*[column.ilike(f"%{escape_like(t)}%", escape="\\") for t in spellings(term)])


class KeywordSearch:
    """`condition` filters (OR of keywords over the columns, or None when the
    query has no usable keyword); `order_by` ranks matches."""

    def __init__(self, query: str | None, columns: list, *, headline_column=None) -> None:
        self.phrase = normalize_query(query)
        # A query made only of stopwords still searches for what was typed.
        self.keywords = split_keywords(query) or ([self.phrase] if self.phrase else [])
        self.columns = list(columns)
        self.headline_column = headline_column

    @property
    def active(self) -> bool:
        return bool(self.keywords)

    def _any_column(self, term: str) -> ColumnElement[bool]:
        return or_(*[_contains(c, term) for c in self.columns])

    @property
    def condition(self) -> ColumnElement[bool] | None:
        if not self.active:
            return None
        return or_(*[self._any_column(k) for k in self.keywords])

    def order_by(self) -> list:
        if not self.active:
            return []
        distinct_hits = sum(
            (case((self._any_column(k), 1), else_=0) for k in self.keywords), literal(0)
        )
        order = [distinct_hits.desc()]
        if self.phrase and [self.phrase.casefold()] != [k.casefold() for k in self.keywords]:
            order.append(case((self._any_column(self.phrase), 1), else_=0).desc())
        if self.headline_column is not None:
            headline_hits = sum(
                (case((_contains(self.headline_column, k), 1), else_=0) for k in self.keywords), literal(0)
            )
            order.append(headline_hits.desc())
        return order
