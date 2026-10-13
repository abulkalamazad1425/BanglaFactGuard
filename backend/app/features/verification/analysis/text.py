from __future__ import annotations

import re
import unicodedata

from app.shared.utils.bangla_normalizer import normalize_bangla_digits, normalize_bangla_text

_TOKEN_RE = re.compile(r"[ঀ-৿0-9A-Za-z]+(?:[.,][0-9]+)*")

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[।.!?‼])\s+|\n+")

NEGATION_WORDS: frozenset[str] = frozenset(
    {"না", "নি", "নেই", "নয়", "নন", "নাই", "not", "no", "never", "নাকচ"}
)
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

_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("গুলোর", ""), ("গুলির", ""), ("গুলো", ""), ("গুলি", ""), ("দের", ""),
    ("েরা", ""), ("ের", ""), ("কে", ""), ("তে", ""), ("টির", ""), ("টি", ""),
    ("টা", ""), ("রা", ""), ("ার", "া"), ("ায়", "া"), ("ে", ""),
)
_MIN_STEM = 3


def normalize_for_match(text: str) -> str:
    if not text:
        return ""
    t = normalize_bangla_text(text)
    t = normalize_bangla_digits(t)
    t = t.replace("▁", " ")
    t = unicodedata.normalize("NFC", t).lower()
    return re.sub(r"\s+", " ", t).strip()


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(normalize_for_match(text))


def light_stem(token: str) -> str:
    t = token
    changed = True
    while changed and len(t) > _MIN_STEM:
        changed = False
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
    sentences = split_sentences(text, min_len=1)
    chunks: list[str] = []
    cur = ""
    for sent in sentences:
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
