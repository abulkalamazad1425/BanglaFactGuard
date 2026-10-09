"""Conservative entity matching: different people are never merged."""

import pytest

from app.features.verification.analysis.entities import (
    EntityMention,
    entity_key,
    match_entity,
    mentions_in_sentence,
)


def keys(text: str) -> tuple[str, ...]:
    return entity_key(text)


@pytest.mark.parametrize("claimed,evidence,text,status", [
    ("ঢাকার", ["ঢাকা"], "", "exact"),                                    # inflected surface
    ("বাংলাদেশ জাতীয়তাবাদী দল", ["বিএনপি"], "", "alias"),              # alias entity
    ("ঢাকা", [], "dhaka city news", "alias"),                           # alias in the text only
    ("মুহাম্মদ ইউনূস", ["ড. মুহাম্মদ ইউনূস"], "", "span"),               # claimed inside a longer name
    ("ড. মুহাম্মদ ইউনূস", ["মুহাম্মদ ইউনূস"], "", "span"),               # longer claimed name
    ("রহমান", ["মুজিবুর রহমান", "জিয়াউর রহমান"], "", "ambiguous"),      # shared surname
    ("জিয়াউর রহমান", ["মুজিবুর রহমান"], "মুজিবুর রহমান", "unmatched"),  # different person
    ("পদ্মা সেতু", [], "আজ পদ্মা সেতু খুলে দেওয়া হয়", "text"),          # literal presence
    ("।।", [], "", "unmatched"),                                       # no usable tokens
])
def test_match_status(claimed, evidence, text, status):
    m = match_entity(EntityMention(claimed, "PER"), [EntityMention(e, "PER") for e in evidence], keys(text))
    assert m.status == status
    assert m.matched is (status in {"exact", "alias", "span", "text"})


def test_mentions_in_a_sentence_are_found_once_each():
    mentions = [EntityMention("সাকিব", "PER"), EntityMention("সাকিব", "PER"), EntityMention("তামিম", "PER")]
    assert mentions_in_sentence("সাকিবকে নিয়ে কথা হলো", mentions) == [mentions[0]]
