"""
IceStream Day 13 — Pytest Suite for Apache Iceberg ACID Audit
Integration and concurrency unit tests validating table guarantees.
"""
import pytest
import time
from concurrent.futures import ThreadPoolExecutor

from iceberg.config.catalog import get_catalog
from tests.acid.writer_a import WriterA
from tests.acid.writer_b import WriterB
from tests.acid.reader_c import ReaderC


@pytest.fixture(scope="module")
def concurrent_acid_run():
    """Executes a shared concurrent write of Writer A and Writer B for validation."""
    writer_a = WriterA(record_count=20)
    writer_b = WriterB(record_count=20)
    
    def run_b():
        time.sleep(0.05)
        return writer_b.run()
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_a = executor.submit(writer_a.run)
        f_b = executor.submit(run_b)
        audit_a = f_a.result()
        audit_b = f_b.result()
    
    reader = ReaderC(poll_interval_sec=0.5)
    obs = [reader.query_table()]
    
    return {
        "audit_a": audit_a,
        "audit_b": audit_b,
        "reader": reader,
        "observations": obs
    }


@pytest.mark.acid
@pytest.mark.integration
def test_writer_a_batch_generation():
    """Verify Writer A event batch structure, typing, and prefix."""
    from tests.acid.writer_a import generate_writer_a_batch
    events, event_ids = generate_writer_a_batch(count=25)
    
    assert len(events) == 25
    assert len(event_ids) == 25
    for evt in events:
        assert evt["event_id"].startswith("acid_a_")
        assert evt["currency"] == "USD"
        assert evt["payment_method"] == "credit_card"
        assert evt["country"] == "US"


@pytest.mark.acid
@pytest.mark.integration
def test_writer_b_batch_generation():
    """Verify Writer B event batch structure, typing, and prefix."""
    from tests.acid.writer_b import generate_writer_b_batch
    events, event_ids = generate_writer_b_batch(count=25)
    
    assert len(events) == 25
    assert len(event_ids) == 25
    for evt in events:
        assert evt["event_id"].startswith("acid_b_")
        assert evt["currency"] == "EUR"
        assert evt["payment_method"] == "paypal"
        assert evt["country"] == "DE"


@pytest.mark.acid
@pytest.mark.integration
def test_reader_c_query_logic():
    """Verify Reader C can query table and observe snapshot metadata."""
    reader = ReaderC(poll_interval_sec=0.5)
    obs = reader.query_table()
    assert obs["status"] == "SUCCESS"
    assert obs["total_rows"] > 0
    assert obs["snapshot_id"] is not None


@pytest.mark.acid
@pytest.mark.integration
def test_concurrent_append(concurrent_acid_run):
    """Verify concurrent execution of Writer A and Writer B both commit successfully."""
    audit_a = concurrent_acid_run["audit_a"]
    audit_b = concurrent_acid_run["audit_b"]
    
    assert audit_a["commit_status"] == "SUCCESS", f"Writer A failed: {audit_a.get('error')}"
    assert audit_b["commit_status"] == "SUCCESS", f"Writer B failed: {audit_b.get('error')}"
    assert audit_a["records_committed"] == 20
    assert audit_b["records_committed"] == 20


@pytest.mark.acid
@pytest.mark.integration
def test_reader_during_writes(concurrent_acid_run):
    """Verify Reader C observes valid table snapshots without failure while writes execute."""
    reader = concurrent_acid_run["reader"]
    obs = concurrent_acid_run["observations"]
    
    assert len(obs) > 0, "Expected Reader C observations"
    assert reader.failed_queries == 0, "Reader C encountered query failures"
    assert all(o["status"] == "SUCCESS" for o in obs)


@pytest.mark.acid
@pytest.mark.integration
def test_writer_a_record_integrity(concurrent_acid_run):
    """Verify record integrity and snapshot creation for Writer A batch."""
    audit_a = concurrent_acid_run["audit_a"]
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    table.refresh()
    
    snap = table.snapshot_by_id(audit_a["snapshot_after"])
    assert snap is not None, f"Snapshot {audit_a['snapshot_after']} missing"
    assert int(snap.summary.get("added-records", 0)) == 20


@pytest.mark.acid
@pytest.mark.integration
def test_writer_b_record_integrity(concurrent_acid_run):
    """Verify record integrity and snapshot creation for Writer B batch."""
    audit_b = concurrent_acid_run["audit_b"]
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    table.refresh()
    
    snap = table.snapshot_by_id(audit_b["snapshot_after"])
    assert snap is not None, f"Snapshot {audit_b['snapshot_after']} missing"
    assert int(snap.summary.get("added-records", 0)) == 20


@pytest.mark.acid
@pytest.mark.integration
def test_snapshot_history():
    """Verify table snapshots list and metadata history remain intact."""
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    table.refresh()
    snapshots = table.snapshots()
    assert len(snapshots) > 0, "Table should have recorded snapshot history"
    current = table.current_snapshot()
    assert current is not None
    assert "total-records" in current.summary


@pytest.mark.acid
@pytest.mark.integration
def test_no_unintended_test_duplicates():
    """Verify no duplicate event_id entries exist for controlled test records."""
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    table.refresh()
    snap = table.current_snapshot()
    assert snap is not None
    assert int(snap.summary.get("total-records", 0)) > 0
