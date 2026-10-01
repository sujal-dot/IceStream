"""
IceStream Quality Engine — Test Configuration and Fixtures

Provides offline fixtures that mock the Iceberg/catalog boundary so that all
``@pytest.mark.integration`` quarantine tests can run without a live Iceberg
REST catalog, MinIO, or any container.

Mock boundary:
  ``quarantine.writer.QuarantineWriter.write_batch``
  This is the **only** method in QuarantineWriter that performs network I/O
  (catalog.load_table → tbl.append).  All business logic (routing decisions,
  error-code selection, severity ordering, deduplication, metrics) executes
  against real production code; only the final Iceberg append is intercepted.

For the single e2e test that also reads back from Iceberg
(``test_single_invalid_event_quarantine_e2e``), the catalog's ``load_table``
and ``scan().to_arrow()`` call chain is additionally mocked so that it returns
a synthetic Arrow table containing the record that was passed to write_batch.
"""

import pyarrow as pa
import pytest
from unittest.mock import MagicMock, patch


def _build_mock_catalog_factory(captured_records: list):
    """Return a factory function that produces a mock PyIceberg catalog.

    The catalog's ``load_table().scan().to_arrow()`` chain returns an Arrow
    table built from *captured_records*, which are populated by the
    write_batch interceptor in the same test invocation.
    """

    def _factory():
        mock_catalog = MagicMock()

        def _load_table(table_name):
            mock_table = MagicMock()
            mock_table.refresh.return_value = None

            def _scan():
                mock_scan = MagicMock()

                def _to_arrow():
                    if not captured_records:
                        return pa.table({
                            "quarantine_id": pa.array([], type=pa.string()),
                            "event_id": pa.array([], type=pa.string()),
                            "event": pa.array([], type=pa.string()),
                            "error_code": pa.array([], type=pa.string()),
                            "error_message": pa.array([], type=pa.string()),
                            "failed_rules": pa.array([], type=pa.list_(pa.string())),
                            "detected_at": pa.array([], type=pa.string()),
                            "pipeline_version": pa.array([], type=pa.string()),
                            "schema_version": pa.array([], type=pa.string()),
                        })
                    return pa.table({
                        "quarantine_id": [r.quarantine_id for r in captured_records],
                        "event_id": [r.event_id for r in captured_records],
                        "event": [r.event for r in captured_records],
                        "error_code": [r.error_code for r in captured_records],
                        "error_message": [r.error_message for r in captured_records],
                        "failed_rules": [r.failed_rules for r in captured_records],
                        "detected_at": [r.detected_at for r in captured_records],
                        "pipeline_version": [r.pipeline_version for r in captured_records],
                        "schema_version": [r.schema_version for r in captured_records],
                    })

                mock_scan.to_arrow = _to_arrow
                return mock_scan

            mock_table.scan = _scan
            return mock_table

        mock_catalog.load_table = _load_table
        mock_catalog.table_exists.return_value = True
        return mock_catalog

    return _factory


@pytest.fixture(autouse=True)
def _offline_iceberg_write_batch(request):
    """
    Intercept ``QuarantineWriter.write_batch`` at the Iceberg boundary for ALL
    tests in this quality-engine/tests package.

    For pure-unit tests that already inject a ``MagicMock(spec=QuarantineWriter)``
    as the writer this patch is harmless — the MagicMock shadow handles
    write_batch before the real implementation is reached.

    For integration tests that construct a real ``QuarantineWriter()``, this
    patch prevents all network I/O and returns ``(len(records), True)``.

    The ``get_catalog`` symbol is patched in three locations:
      1. ``quarantine.writer``       — used by the lazy ``catalog`` property
      2. ``iceberg.config.catalog``  — used inside ``ensure_table_exists``
      3. ``test_quarantine``         — the name already bound in the test
                                       module via ``from iceberg.config.catalog
                                       import get_catalog`` (needed for the
                                       Iceberg read-back assertion in
                                       ``test_single_invalid_event_quarantine_e2e``)

    Records captured by write_batch are replayed through the mock catalog's
    scan, so the e2e read-back assertions verify real routing output without
    touching the network.
    """
    captured_records: list = []

    def _fake_write_batch(records):
        """Simulate a successful Iceberg append without any network I/O."""
        captured_records.extend(records)
        return (len(records), True)

    catalog_factory = _build_mock_catalog_factory(captured_records)

    with (
        patch(
            "quarantine.writer.QuarantineWriter.write_batch",
            autospec=True,
            side_effect=lambda self, records: _fake_write_batch(records),
        ),
        patch("quarantine.writer.get_catalog", side_effect=catalog_factory),
        patch("iceberg.config.catalog.get_catalog", side_effect=catalog_factory),
        # test_quarantine.py does `from iceberg.config.catalog import get_catalog`
        # which binds `get_catalog` as a top-level name in the test module.
        # pytest loads quality-engine/tests/ as rootdir without a package prefix,
        # so the module name is simply ``test_quarantine`` (no package).
        patch("test_quarantine.get_catalog", side_effect=catalog_factory),
    ):
        yield
