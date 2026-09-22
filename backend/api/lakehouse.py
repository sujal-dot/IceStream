"""FastAPI Router for Lakehouse Health, Compaction, and Table Maintenance."""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.models.lakehouse import (
    CompactionRequest,
    CompactionResponse,
    MaintenanceHistoryItem,
    MaintenanceHistoryResponse,
    MaintenanceRequest,
    MaintenanceResponse,
    TableHealthResponse,
)
from backend.storage.db import StorageBackend, get_db_storage
from iceberg.maintenance.manager import LakehouseMaintenanceService

logger = logging.getLogger("icestream.api.lakehouse")

router = APIRouter(prefix="/lakehouse", tags=["Lakehouse"])

# Global singleton instance for LakehouseMaintenanceService
_global_maintenance_service: Optional[LakehouseMaintenanceService] = None


def get_maintenance_service() -> LakehouseMaintenanceService:
    """Retrieve or initialize the global shared LakehouseMaintenanceService."""
    global _global_maintenance_service
    if _global_maintenance_service is None:
        storage = get_db_storage()
        _global_maintenance_service = LakehouseMaintenanceService(storage=storage)
    return _global_maintenance_service


def set_maintenance_service(service: Optional[LakehouseMaintenanceService]) -> None:
    """Override or reset the global maintenance service (useful for testing)."""
    global _global_maintenance_service
    _global_maintenance_service = service


@router.get("/health", response_model=List[TableHealthResponse])
def get_all_tables_health(
    service: LakehouseMaintenanceService = Depends(get_maintenance_service),
) -> List[TableHealthResponse]:
    """Retrieve health and fragmentation diagnostics across all registered lakehouse tables."""
    try:
        reports = service.get_all_tables_health()
        return [TableHealthResponse(**r.to_dict()) for r in reports]
    except Exception as e:
        logger.error(f"Error fetching lakehouse table health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query lakehouse table health: {str(e)}",
        )


@router.get("/tables/{namespace}/{table}/health", response_model=TableHealthResponse)
def get_table_health(
    namespace: str,
    table: str,
    service: LakehouseMaintenanceService = Depends(get_maintenance_service),
) -> TableHealthResponse:
    """Retrieve health and fragmentation metrics for a specific Iceberg table."""
    full_table_name = f"{namespace}.{table}"
    try:
        report = service.get_table_health(full_table_name)
        if not report.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table '{full_table_name}' does not exist in catalog",
            )
        return TableHealthResponse(**report.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching health for {full_table_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to inspect table {full_table_name}: {str(e)}",
        )


@router.post("/compact", response_model=CompactionResponse)
def compact_table(
    req: CompactionRequest,
    service: LakehouseMaintenanceService = Depends(get_maintenance_service),
) -> CompactionResponse:
    """Trigger on-demand small-file compaction for an Iceberg table."""
    try:
        target_bytes = req.target_file_size_mb * 1024 * 1024
        result = service.compactor.compact_table(
            table_name=req.table_name,
            target_file_size_bytes=target_bytes,
            min_file_count=req.min_file_count,
        )
        return CompactionResponse(**result.to_dict())
    except Exception as e:
        logger.error(f"Error during compaction of {req.table_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compaction failed for table {req.table_name}: {str(e)}",
        )


@router.post("/maintenance", response_model=MaintenanceResponse)
def run_maintenance(
    req: MaintenanceRequest,
    service: LakehouseMaintenanceService = Depends(get_maintenance_service),
) -> MaintenanceResponse:
    """Trigger full maintenance workflow (compaction, snapshot expiration, orphan cleanup)."""
    try:
        target_bytes = req.target_file_size_mb * 1024 * 1024
        result = service.run_table_maintenance(
            table_name=req.table_name,
            compact=req.compact,
            expire_snapshots=req.expire_snapshots,
            cleanup_orphans=req.cleanup_orphans,
            retain_last_snapshots=req.retain_last,
            orphan_safety_seconds=req.orphan_safety_seconds,
            dry_run=req.dry_run,
            target_file_size_bytes=target_bytes,
            min_file_count=req.min_file_count,
        )
        return MaintenanceResponse(**result.to_dict())
    except Exception as e:
        logger.error(f"Error executing maintenance on {req.table_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Maintenance execution failed for {req.table_name}: {str(e)}",
        )


@router.get("/maintenance/history", response_model=MaintenanceHistoryResponse)
def get_maintenance_history(
    table_name: Optional[str] = Query(None, description="Filter history by table name"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of historical records to return"),
    storage: StorageBackend = Depends(get_db_storage),
) -> MaintenanceHistoryResponse:
    """Retrieve audit history of lakehouse maintenance operations."""
    try:
        raw_runs = storage.get_maintenance_history(table_name=table_name, limit=limit)
        items = []
        for r in raw_runs:
            items.append(
                MaintenanceHistoryItem(
                    id=r["id"],
                    table_name=r["table_name"],
                    operation=r["operation"],
                    status=r["status"],
                    files_before=r.get("files_before", 0),
                    files_after=r.get("files_after", 0),
                    records_compacted=r.get("records_compacted", 0),
                    snapshots_expired=r.get("snapshots_expired", 0),
                    orphan_files_deleted=r.get("orphan_files_deleted", 0),
                    bytes_reclaimed=r.get("bytes_reclaimed", 0),
                    duration_ms=r.get("duration_ms", 0.0),
                    error=r.get("error"),
                    started_at=str(r["started_at"]),
                    completed_at=str(r["completed_at"]) if r.get("completed_at") else None,
                )
            )
        return MaintenanceHistoryResponse(runs=items, total=len(items))
    except Exception as e:
        logger.error(f"Error fetching maintenance history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query maintenance history: {str(e)}",
        )
