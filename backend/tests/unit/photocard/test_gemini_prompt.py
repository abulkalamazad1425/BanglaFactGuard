"""What Gemini is offered (only active sources, by id) and how its answer is read."""

from app.features.photocard.gemini_prompt import (
    FieldStatus,
    GeminiPhotocardFields,
    SourceOption,
    SourceStatus,
    build_response_schema,
    build_user_prompt,
)

PALO = SourceOption("prothomalo.com", "প্রথম আলো", "Prothom Alo", ("প্রথম আলো", " palo ", ""))


def test_the_prompt_lists_each_source_with_its_known_names_and_the_schema_restricts_ids():
    prompt = build_user_prompt([PALO])
    assert "- prothomalo.com: প্রথম আলো | Prothom Alo | palo" in prompt
    assert "can never be IDENTIFIED" in build_user_prompt([])
    assert build_response_schema([PALO])["properties"]["source"] == {"type": "STRING", "nullable": True, "enum": ["prothomalo.com"]}
    assert "enum" not in build_response_schema([])["properties"]["source"]


def test_values_count_only_when_marked_present_or_identified():
    fields = GeminiPhotocardFields(headline="শিরোনাম", headline_status=FieldStatus.PRESENT, source=" prothomalo.com ",
                                   source_status=SourceStatus.IDENTIFIED, date="  ", date_status=FieldStatus.PRESENT,
                                   extra_field="ignored")
    assert (fields.present("headline"), fields.present("date"), fields.identified_source()) == ("শিরোনাম", None, "prothomalo.com")
    unsure = fields.model_copy(update={"headline_status": FieldStatus.UNREADABLE, "source_status": SourceStatus.UNCLEAR})
    assert unsure.present("headline") is None and unsure.identified_source() is None
