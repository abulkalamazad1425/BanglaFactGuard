"""Every OpenAPI example attached to a schema must be a valid instance of it,
so documentation examples cannot drift from the models they describe."""

import pytest

from app.features.articles import schemas as article_schemas
from app.features.sources import schemas as source_schemas
from app.features.verification import schemas as verification_schemas

MODELS = [
    model
    for module in (article_schemas, source_schemas, verification_schemas)
    for model in vars(module).values()
    if isinstance(model, type)
    and hasattr(model, "model_config")
    and isinstance(model.model_config.get("json_schema_extra"), dict)
    and "example" in model.model_config["json_schema_extra"]
]


def test_examples_were_found():
    assert MODELS


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_example_validates(model):
    model.model_validate(model.model_config["json_schema_extra"]["example"])
