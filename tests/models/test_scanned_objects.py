"""scanned_objects helper."""

from felix.models import scanned_objects
from tests.helpers import sample_scan_result


def test_scanned_objects_lists_opportunity() -> None:
    assert scanned_objects(sample_scan_result()) == ["Opportunity"]
