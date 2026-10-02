"""Shared Bangla text normalisation, tokenisation and light stemming.

One normalisation for BOTH sides of every comparison (claim and evidence);
inconsistent normalisation is what makes identical strings fail to match.
"""

from __future__ import annotations

import re
import unicodedata

from app.shared.utils.bangla_normalizer import normalize_bangla_digits, normalize_bangla_text

# Bengali block U+0980-09FF (letters, vowel signs, digits) plus ASCII
# alphanumerics. `\w` alone is NOT enough: Bengali vowel signs are category
# Mc/Mn and are not \w, so it would split words at every matra.
_TOKEN_RE = re.compile(r"[ঀ-৿0-9A-Za-z]+(?:[.,][0-9]+)*")

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[।.!?‼])\s+|\n+")

# Words that carry meaning in a claim even though retrieval treats them as
# stopwords — they must survive stopword filtering in content checks.
NEGATION_WORDS: frozenset[str] = frozenset(
    {"না", "নি", "নেই", "নয়", "নন", "নাই", "not", "no", "never", "নাকচ"}
)
# Fused Bangla negation: হয়নি, করেনি, যায়নি, দেননি, পারেননি …  The text before
# "নি" must end in a vowel sign / য় / ন so that nouns like খনি, ধ্বনি, অগ্নি
# do not match.
_FUSED_NEGATION_RE = re.compile(r"^.{1,}(?:ে|া|ন|য়|য়)নি$")

QUALIFIER_GROUPS: dict[str, frozenset[str]] = {
    "UNIVERSAL": frozenset(
        {"সব", "সকল", "সবাই", "সবার", "সবাইকে", "সমস্ত", "প্রতিটি", "সর্বত্র", "প্রত্যেক"}
    ),
    "PARTIAL": frozenset(
        {"কিছু", "কয়েক", "কয়েকটি", "কিছুসংখ্যক", "আংশিক", "অনেকে", "একাংশ", "কিছুটা"}
    ),
    "EXCLUSIVE": frozenset({"শুধু", "শুধুমাত্র", "কেবল", "একমাত্র", "মাত্র"}),
    "LOWER_BOUND": frozenset({"অন্তত", "কমপক্ষে", "ন্যূনতম", "সর্বনিম্ন"}),
    "UPPER_BOUND": frozenset({"সর্বোচ্চ", "বড়জোর", "সর্বাধিক", "অনূর্ধ্ব"}),
    "APPROX": frozenset({"প্রায়", "আনুমানিক"}),
}
QUALIFIER_WORDS: frozenset[str] = frozenset().union(*QUALIFIER_GROUPS.values())

# Bangla function words excluded from content-token sets.
STOPWORDS: frozenset[str] = frozenset(
    {
        "এই", "এ", "ও", "এবং", "কিন্তু", "তবে", "যে", "যা", "তা", "তার", "আর",
        "হয়", "হয়েছে", "হয়েছিল", "হবে", "করা", "করে", "করেছে", "করেছিল",
        "করবে", "থেকে", "জন্য", "দিয়ে", "সঙ্গে", "সাথে", "মধ্যে", "উপর", "নিচে",
        "পরে", "আগে", "বলে", "বলা", "আছে", "ছিল", "আছেন", "ছিলেন", "একটি",
        "একটা", "এটি", "এটা", "সেটি", "সেটা", "তাদের", "তাকে", "তিনি", "তারা",
        "আমরা", "আমি", "তাই", "সেই", "যেন", "যদি", "কারণ", "অথবা", "বা", "এবার",
        "তখন", "এখন", "যখন", "প্রতি", "হলো", "হল", "দিন", "বছর", "the", "a", "an",
        "is", "are", "was", "were", "of", "in", "on", "at", "to", "for", "with",
        "by", "from", "and", "or",
    }
)

_MAGNITUDES: dict[str, int] = {
    "শত": 100, "হাজার": 1_000, "লাখ": 100_000, "লক্ষ": 100_000,
    "কোটি": 10_000_000,
}

# Spelled-out numerals (excluding এক "one/a" and নয় which is also "is not").
_WORD_NUMBERS: dict[str, int] = {
    "দুই": 2, "তিন": 3, "চার": 4, "পাঁচ": 5, "ছয়": 6, "সাত": 7, "আট": 8,
    "দশ": 10, "বিশ": 20, "ত্রিশ": 30, "চল্লিশ": 40, "পঞ্চাশ": 50, "ষাট": 60,
    "সত্তর": 70, "আশি": 80, "নব্বই": 90,
}

# Longest first. Applied repeatedly (see light_stem) so inflected and bare
# forms converge on one key.
# (suffix, replacement): "ার"/"ায়" keep the aa-kar so ঢাকার/ঢাকায়/ঢাকা converge.
_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("গুলোর", ""), ("গুলির", ""), ("গুলো", ""), ("গুলি", ""), ("দের", ""),
    ("েরা", ""), ("ের", ""), ("কে", ""), ("তে", ""), ("টির", ""), ("টি", ""),
    ("টা", ""), ("রা", ""), ("ার", "া"), ("ায়", "া"), ("ে", ""),
)
_MIN_STEM = 3


def normalize_for_match(text: str) -> str:
    """NFC, Bangla punctuation/zero-width cleanup, digits -> ASCII, casefold."""
    if not text:
        return ""
    t = normalize_bangla_text(text)
    t = normalize_bangla_digits(t)
    t = t.replace("▁", " ")
    t = unicodedata.normalize("NFC", t).lower()
    return re.sub(r"\s+", " ", t).strip()


def tokenize(text: str) -> list[str]:
    """Normalised tokens in order (no stopword removal)."""
    return _TOKEN_RE.findall(normalize_for_match(text))


def light_stem(token: str) -> str:
    """Conservative inflection stripping, applied identically to both sides.

    Strips case/plural markers only while at least _MIN_STEM code points
    remain. This is for *matching* only; it is not linguistic stemming.
    """
    t = token
    changed = True
    while changed and len(t) > _MIN_STEM:
        changed = False
        # possessive -র after a vowel sign (সেতুর -> সেতু, মন্ত্রীর -> মন্ত্রী)
        if t.endswith("র") and len(t) - 1 >= _MIN_STEM and t[-2] in "িীুূোৌ":
            t = t[:-1]
            changed = True
            continue
        for suf, repl in _SUFFIXES:
            if t.endswith(suf) and len(t) - len(suf) + len(repl) >= _MIN_STEM:
                new = t[: -len(suf)] + repl
                if new != t:
                    t = new
                    changed = True
                    break
    return t


def is_negation_token(token: str) -> bool:
    if token in NEGATION_WORDS:
        return True
    return bool(len(token) >= 4 and _FUSED_NEGATION_RE.match(token))


def is_qualifier_token(token: str) -> bool:
    return token in QUALIFIER_WORDS


def is_number_token(token: str) -> bool:
    return bool(re.fullmatch(r"[0-9][0-9.,]*", token))


def content_tokens(text: str) -> list[str]:
    """Tokens that carry claim content: stopwords dropped, but negation and
    qualifier words are RETAINED (they are meaning-bearing in content checks
    even though retrieval would filter them)."""
    out: list[str] = []
    for tok in tokenize(text):
        if is_negation_token(tok) or is_qualifier_token(tok) or is_number_token(tok):
            out.append(tok)
        elif tok not in STOPWORDS and len(tok) >= 2:
            out.append(tok)
    return out


def split_sentences(text: str, *, min_len: int = 8) -> list[str]:
    if not text:
        return []
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text.strip())]
    return [p for p in parts if len(p) >= min_len]


def chunk_text(text: str, *, max_chars: int = 450, max_chunks: int = 120) -> tuple[list[str], bool]:
    """Group consecutive sentences into chunks of at most `max_chars`.

    Nothing is dropped for being long: a long body becomes many chunks.
    Returns (chunks, truncated) where `truncated` is True only if the
    `max_chunks` safety cap had to drop trailing text — callers must then
    treat the body comparison as partial.
    """
    sentences = split_sentences(text, min_len=1)
    chunks: list[str] = []
    cur = ""
    for sent in sentences:
        # A single over-long sentence is split on whitespace so no text is lost.
        while len(sent) > max_chars:
            cut = sent.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            piece, sent = sent[:cut].strip(), sent[cut:].strip()
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(piece)
        if not sent:
            continue
        if cur and len(cur) + 1 + len(sent) > max_chars:
            chunks.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        chunks.append(cur)
    truncated = len(chunks) > max_chunks
    return chunks[:max_chunks], truncated


def parse_number_phrases(text: str) -> list[tuple[float, str | None, str]]:
    """(value, unit, surface) triples. Magnitude words fold into the value
    (১০ লাখ -> 1_000_000); the unit is the next non-magnitude token."""
    toks = tokenize(text)
    out: list[tuple[float, str | None, str]] = []
    i = 0
    while i < len(toks):
        tok = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        word_val = _WORD_NUMBERS.get(tok)
        if word_val is not None and nxt and nxt not in STOPWORDS:
            toks[i] = tok = str(word_val)
        if is_number_token(tok):
            try:
                value = float(tok.replace(",", ""))
            except ValueError:
                i += 1
                continue
            j = i + 1
            surface = tok
            while j < len(toks) and toks[j] in _MAGNITUDES:
                value *= _MAGNITUDES[toks[j]]
                surface += f" {toks[j]}"
                j += 1
            unit = None
            if j < len(toks) and not is_number_token(toks[j]) and toks[j] not in STOPWORDS:
                unit = light_stem(toks[j])
            out.append((value, unit, surface))
            i = j
        else:
            i += 1
    return out
