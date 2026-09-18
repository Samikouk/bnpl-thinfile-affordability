"""Journey SQL helpers: identifiers and literal escaping."""
import pytest

from journey.run_journey import require_app_id, sql_literal


def test_sql_literal_escapes_quotes():
    assert sql_literal("it's") == "'it''s'"


def test_require_app_id():
    assert require_app_id("A1007312") == "A1007312"
    with pytest.raises(ValueError):
        require_app_id("A1007312'; DROP TABLE")
