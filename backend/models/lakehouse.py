"""Pydantic API Request and Response Models for Lakehouse Maintenance and Health."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TableHealthResponse(BaseModel):
    """Health and fragmentation diagnostics for an Iceberg table."""
    table_name: str = Field(..., description="Fully qualified table name (e.g. bronze.checkout_events)")
    exists: bool = Field(..., description="Whether the table exists in the catalog")
    total_files: int = Field(default=0, description="Total active data files in active snapshot")
    total_records: int = Field(default=0, description="Total record count in active snapshot")
    total_bytes: int = Field(default=0, description="Total size in bytes of active data files")
    avg_file_size_bytes: int = Field(default=0, description="Average size of data files")
    small_files_count: int = Field(default=0, description="Count of files smaller than small file threshold")
    snapshot_count: int = Field(default=0, description="Total snapshot count in table history")
    fragmentation_status: str = Field(default="HEALTHY", description="HEALTHY, NEEDS_COMPACTION, or CRITICALLY_FRAGMENTED")
    partition_count: int = Field(default=0, description="Number of distinct partitions")
    current_snapshot_id: Optional[int] = Field(default=None, description="Active snapshot ID")
    last_updated_at: Optional[str] = Field(default=None, description="ISO timestamp of last update")


class CompactionRequest(BaseModel):
    """Request payload to trigger table compaction."""
    table_name: str = Field(default="bronze.checkout_events", description="Target Iceberg table identifier")
    target_file_size_mb: int = Field(default=128, ge=1, le=1024, description="Target size for compacted files in MB")
    min_file_count: int = Field(default=2, ge=1, description="Minimum small files required to trigger compaction")


class CompactionResponse(BaseModel):
    """Response payload for table compaction execution."""
    table_name: str
    needed: bool
    files_before: int
    files_after: int
    bytes_before: int
    bytes_after: int
    records_compacted: int
    duration_ms: float
    success: bool
    error: Optional[str] = None
    snapshot_id: Optional[int] = None


class MaintenanceRequest(BaseModel):
    """Request payload to trigger full lakehouse maintenance."""
    table_name: str = Field(default="bronze.checkout_events", description="Target Iceberg table identifier")
    compact: bool = Field(default=True, description="Execute small-file compaction")
    expire_snapshots: bool = Field(default=True, description="Expire old snapshots")
    cleanup_orphans: bool = Field(default=False, description="Scan and delete unreferenced S3 files")
    retain_last: int = Field(default=5, ge=1, description="Number of recent snapshots to retain")
    orphan_safety_seconds: int = Field(default=3600, ge=60, description="Safety age buffer for orphan deletion")
    dry_run: bool = Field(default=False, description="Simulate without destructive changes")
    target_file_size_mb: int = Field(default=128, ge=1, le=1024, description="Target size for compacted files in MB")
    min_file_count: int = Field(default=2, ge=1, description="Minimum files to trigger compaction")


class MaintenanceResponse(BaseModel):
    """Response payload for maintenance run."""
    table_name: str
    run_id: Optional[int] = None
    status: str
    compaction: Optional[Dict[str, Any]] = None
    snapshot_expiration: Optional[Dict[str, Any]] = None
    orphan_cleanup: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float


class MaintenanceHistoryItem(BaseModel):
    """Individual lakehouse maintenance run record."""
    id: int
    table_name: str
    operation: str
    status: str
    files_before: int = 0
    files_after: int = 0
    records_compacted: int = 0
    snapshots_expired: int = 0
    orphan_files_deleted: int = 0
    bytes_reclaimed: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None


class MaintenanceHistoryResponse(BaseModel):
    """Response containing lakehouse maintenance execution audit history."""
    runs: List[MaintenanceHistoryItem]
    total: int
