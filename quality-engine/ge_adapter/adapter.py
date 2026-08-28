"""High-level Great Expectations Adapter isolating GE internals from the IceStream Quality Engine."""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd

from schemas.event import QualityEvent
from rules.base import Severity, ValidationResult
from metrics.collector import MetricsCollector
from ge_adapter.expectations import GEExpectationRegistry
from ge_adapter.runner import GERunner
from ge_adapter.result_mapper import QualityBatchResult

logger = logging.getLogger("quality_engine.ge_adapter.adapter")

DEFAULT_EXPECTATIONS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "expectations.yaml",
)


class GEAdapter:
    """Adapter for running Great Expectations batch validations cleanly in IceStream."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        registry: Optional[GEExpectationRegistry] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ) -> None:
        self._metrics = metrics_collector

        if registry is not None:
            self._registry = registry
        else:
            cfg_path = config_path or DEFAULT_EXPECTATIONS_PATH
            if os.path.exists(cfg_path):
                self._registry = GEExpectationRegistry.load_from_yaml(cfg_path)
            else:
                logger.warning("Config path '%s' not found, initializing empty GEExpectationRegistry", cfg_path)
                self._registry = GEExpectationRegistry()

        self._runner = GERunner()

    @property
    def registry(self) -> GEExpectationRegistry:
        """Access expectation registry."""
        return self._registry

    def validate(
        self,
        batch: Union[pd.DataFrame, List[QualityEvent], List[Dict[str, Any]]],
        batch_id: Optional[str] = None,
    ) -> List[ValidationResult]:
        """Validate batch and return list of normalized ValidationResults.

        Args:
            batch: DataFrame, list of QualityEvents, or list of event dictionaries.
            batch_id: Optional batch identifier string.

        Returns:
            List of ValidationResult objects.
        """
        results, _ = self.validate_with_summary(batch, batch_id=batch_id)
        return results

    def validate_with_summary(
        self,
        batch: Union[pd.DataFrame, List[QualityEvent], List[Dict[str, Any]]],
        batch_id: Optional[str] = None,
    ) -> Tuple[List[ValidationResult], QualityBatchResult]:
        """Validate batch and return both results and QualityBatchResult.

        Args:
            batch: DataFrame, list of QualityEvents, or list of dicts.
            batch_id: Optional batch identifier.

        Returns:
            Tuple of (List[ValidationResult], QualityBatchResult).
        """
        active_exp = self._registry.active()

        try:
            batch_result = self._runner.validate_batch(
                batch_input=batch,
                expectations=active_exp,
                batch_id=batch_id,
            )
        except Exception as e:
            logger.error("GEAdapter encountered unhandled error during validation: %s", str(e), exc_info=True)
            # Step 33: GE adapter failure: do not swallow error silently, raise controlled error
            raise RuntimeError(f"GEAdapter validation execution failed: {type(e).__name__}: {str(e)}") from e

        # Record metrics if metrics collector present
        if self._metrics is not None:
            if hasattr(self._metrics, "record_ge_batch_metrics"):
                self._metrics.record_ge_batch_metrics(batch_result)  # type: ignore
            else:
                for res in batch_result.results:
                    self._metrics.record_rule_result(res)

        return batch_result.results, batch_result
