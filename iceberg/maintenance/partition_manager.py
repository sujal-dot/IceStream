"""
Lakehouse Partition Manager & Spec Evolution for Apache Iceberg Tables.

Provides inspection of table partition schemes, partition distribution analysis,
file skew detection, and dynamic partition spec evolution.
"""
from collections import defaultdict
from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional

from pyiceberg.catalog import Catalog
from pyiceberg.exceptions import NoSuchTableError
from pyiceberg.table import Table

from iceberg.config.catalog import get_catalog

logger = logging.getLogger("icestream.iceberg.partition_manager")


@dataclass
class PartitionStats:
    """Partition distribution and skew metrics for an Iceberg table."""
    table_name: str
    is_partitioned: bool
    spec_id: int
    fields: List[Dict[str, Any]] = field(default_factory=list)
    partition_count: int = 0
    partitions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    total_files: int = 0
    total_records: int = 0
    total_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_name": self.table_name,
            "is_partitioned": self.is_partitioned,
            "spec_id": self.spec_id,
            "fields": self.fields,
            "partition_count": self.partition_count,
            "partitions": self.partitions,
            "total_files": self.total_files,
            "total_records": self.total_records,
            "total_bytes": self.total_bytes,
        }


class PartitionManager:
    """Inspects and manages partition specs and data distribution."""

    def __init__(
        self,
        catalog: Optional[Catalog] = None,
        is_internal: bool = False,
    ):
        self._catalog = catalog
        self.is_internal = is_internal

    @property
    def catalog(self) -> Catalog:
        """Lazily load catalog if not injected."""
        if self._catalog is None:
            self._catalog = get_catalog(is_internal=self.is_internal)
        return self._catalog

    def get_table(self, table_name: str) -> Table:
        """Load and return an Iceberg table instance."""
        return self.catalog.load_table(table_name)

    def get_partition_stats(self, table_name: str) -> PartitionStats:
        """Analyze partition distribution, file counts, and record distribution across partitions.

        Args:
            table_name: Fully qualified table identifier.

        Returns:
            PartitionStats with per-partition file/record/byte breakdowns.
        """
        tbl = self.get_table(table_name)
        tbl.refresh()

        spec = tbl.spec()
        is_partitioned = not spec.is_unpartitioned()
        spec_fields = [
            {
                "source_id": f.source_id,
                "field_id": f.field_id,
                "name": f.name,
                "transform": str(f.transform),
            }
            for f in spec.fields
        ]

        tasks = list(tbl.scan().plan_files())
        partition_data: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"file_count": 0, "record_count": 0, "total_bytes": 0}
        )

        total_files = len(tasks)
        total_records = 0
        total_bytes = 0

        for t in tasks:
            f = t.file
            p_key = str(f.partition) if is_partitioned else "unpartitioned"
            rec_cnt = f.record_count or 0
            size = f.file_size_in_bytes or 0

            partition_data[p_key]["file_count"] += 1
            partition_data[p_key]["record_count"] += rec_cnt
            partition_data[p_key]["total_bytes"] += size

            total_records += rec_cnt
            total_bytes += size

        return PartitionStats(
            table_name=table_name,
            is_partitioned=is_partitioned,
            spec_id=spec.spec_id,
            fields=spec_fields,
            partition_count=len(partition_data) if is_partitioned else 0,
            partitions=dict(partition_data),
            total_files=total_files,
            total_records=total_records,
            total_bytes=total_bytes,
        )

    def add_identity_partition(self, table_name: str, field_name: str) -> bool:
        """Evolve table partition spec by adding an identity partition field."""
        tbl = self.get_table(table_name)
        try:
            with tbl.update_spec() as update:
                update.add_identity(field_name)
            logger.info(f"Added identity partition on '{field_name}' for {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add partition field '{field_name}' to {table_name}: {e}")
            raise e
