from pipeline.models import ExtractedEntity
from pipeline.traced_pipeline import _full_entities_text


def test_entity_rendering_keeps_all_values():
    entity = ExtractedEntity(name="Total", value="814 EUR", entity_type="amount")
    assert "814 EUR" in _full_entities_text([entity])
