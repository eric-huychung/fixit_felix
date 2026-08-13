"""Library surface exports."""

from felix import (
    Diagnosis,
    ScanResult,
    __version__,
    diagnose_error,
    scan_org,
)


def test_from_felix_imports() -> None:
    assert callable(scan_org)
    assert callable(diagnose_error)
    assert Diagnosis is not None
    assert ScanResult is not None
    assert __version__
