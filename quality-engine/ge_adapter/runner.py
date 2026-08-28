"""Execution engine for running Great Expectations declarative expectations against data batches."""

import logging
import time
from typing import Any, Dict, List, Optional, Union
import pandas as pd
from great_expectations.dataset import PandasDataset

from schemas.event import QualityEvent
from rules.base import Severity, ValidationResult
from ge_adapter.expectations import ExpectationConfig
from ge_adapter.result_mapper import GEResultMapper, QualityBatchResult

logger = logging.getLogger("quality_engine.ge_adapter.runner")


class GERunner:
    """Executes Great Expectations declarative expectations against pandas DataFrames or event batches."""

    def __init__(self) -> None:
        pass

    def convert_to_dataframe(
        self, batch_input: Union[pd.DataFrame, List[QualityEvent], List[Dict[str, Any]]]
    ) -> pd.DataFrame:
        """Convert input events or dicts into a clean pandas DataFrame."""
        if isinstance(batch_input, pd.DataFrame):
            return batch_input.copy()
        elif isinstance(batch_input, list):
            if not batch_input:
                return pd.DataFrame()
            first_item = batch_input[0]
            if isinstance(first_item, QualityEvent):
                records = [e.to_dict() for e in batch_input]  # type: ignore
            elif isinstance(first_item, dict):
                records = batch_input  # type: ignore
            else:
                raise TypeError(
                    f"Unsupported batch item type: {type(first_item).__name__}. Expected QualityEvent or dict"
                )
            return pd.DataFrame(records)
        else:
            raise TypeError(
                f"Unsupported batch input type: {type(batch_input).__name__}. Expected DataFrame or List"
            )

    def validate_batch(
        self,
        batch_input: Union[pd.DataFrame, List[QualityEvent], List[Dict[str, Any]]],
        expectations: List[ExpectationConfig],
        batch_id: Optional[str] = None,
    ) -> QualityBatchResult:
        """Validate a batch of data against configured Great Expectations declarations.

        Args:
            batch_input: DataFrame, list of QualityEvents, or list of event dictionaries.
            expectations: List of enabled ExpectationConfig declarations to run.
            batch_id: Optional batch identifier string (defaults to auto-generated ID).

        Returns:
            QualityBatchResult containing list of normalized ValidationResults and batch summary stats.
        """
        start_time = time.perf_counter()
        bid = batch_id or f"batch_{int(time.time())}"
        df = self.convert_to_dataframe(batch_input)
        total_rows = len(df)

        results: List[ValidationResult] = []

        if total_rows == 0:
            logger.info("GERunner evaluating empty batch '%s' (0 records)", bid)
            for exp in expectations:
                if not exp.enabled:
                    continue
                results.append(
                    ValidationResult(
                        rule_name=exp.name,
                        passed=True,
                        severity=exp.severity,
                        message=f"Expectation '{exp.name}' passed: empty batch (0 rows evaluated)",
                        field=exp.column,
                        event_id=bid,
                        metadata={
                            "source": "great_expectations",
                            "expectation": exp.expectation,
                            "element_count": 0,
                            "unexpected_count": 0,
                            "batch_id": bid,
                            "empty_batch": True,
                        },
                    )
                )
            return GEResultMapper.build_batch_result(bid, results, total_rows=0)

        # Wrap dataframe in Great Expectations PandasDataset
        ge_df = PandasDataset(df)

        for exp in expectations:
            if not exp.enabled:
                logger.debug("Skipping disabled GE expectation '%s'", exp.name)
                continue

            col_name = exp.column

            # Handle missing column pre-check (Step 36)
            if col_name and col_name not in df.columns and exp.expectation != "expect_column_to_exist":
                logger.warning("Column '%s' missing from batch DataFrame for expectation '%s'", col_name, exp.name)
                res = ValidationResult(
                    rule_name=exp.name,
                    passed=False,
                    severity=exp.severity,
                    message=f"Expectation '{exp.name}' failed: required column '{col_name}' is missing from batch DataFrame",
                    field=col_name,
                    event_id=bid,
                    metadata={
                        "source": "great_expectations",
                        "expectation": exp.expectation,
                        "error_type": "MissingColumnError",
                        "batch_id": bid,
                    },
                )
                results.append(res)
                continue

            try:
                ge_method = getattr(ge_df, exp.expectation, None)
                if not ge_method:
                    raise AttributeError(f"Great Expectations PandasDataset has no method '{exp.expectation}'")

                ge_kwargs = exp.to_ge_kwargs()
                ge_raw_result = ge_method(**ge_kwargs)
                res = GEResultMapper.map_expectation_result(
                    raw_result=ge_raw_result,
                    exp_config=exp,
                    batch_id=bid,
                )
            except Exception as e:
                logger.error("Error executing GE expectation '%s': %s", exp.name, str(e), exc_info=True)
                res = ValidationResult(
                    rule_name=exp.name,
                    passed=False,
                    severity=Severity.CRITICAL,
                    message=f"GE execution error for '{exp.name}': {type(e).__name__}: {str(e)}",
                    field=col_name,
                    event_id=bid,
                    metadata={
                        "source": "great_expectations",
                        "expectation": exp.expectation,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "batch_id": bid,
                    },
                )

            results.append(res)

        batch_result = GEResultMapper.build_batch_result(bid, results, total_rows=total_rows)

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        rows_per_sec = (total_rows / (duration_ms / 1000.0)) if duration_ms > 0 else 0.0

        logger.info(
            "GE validation finished for batch '%s': rows=%d, total_exp=%d, passed=%d, failed=%d, duration=%.2fms (%.0f rows/sec)",
            bid,
            total_rows,
            batch_result.total_expectations,
            batch_result.passed_expectations,
            batch_result.failed_expectations,
            duration_ms,
            rows_per_sec,
        )

        return batch_result
