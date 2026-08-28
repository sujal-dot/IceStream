"""Result mapping and normalization from raw Great Expectations results to IceStream ValidationResult format."""

from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional
from rules.base import Severity, ValidationResult, RuleStatus


@dataclass
class QualityBatchResult:
    """Normalized batch validation outcome produced by Great Expectations adapter."""

    batch_id: str
    total_expectations: int
    passed_expectations: int
    failed_expectations: int
    critical_failures: int
    success: bool
    results: List[ValidationResult] = dc_field(default_factory=list)
    metadata: Dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert batch result to a serializable dictionary."""
        return {
            "batch_id": self.batch_id,
            "total_expectations": self.total_expectations,
            "passed_expectations": self.passed_expectations,
            "failed_expectations": self.failed_expectations,
            "critical_failures": self.critical_failures,
            "success": self.success,
            "results": [r.to_dict() for r in self.results],
            "metadata": dict(self.metadata),
        }


class GEResultMapper:
    """Maps raw Great Expectations validation result objects/dicts into IceStream ValidationResults."""

    @staticmethod
    def map_expectation_result(
        raw_result: Any,
        exp_config: Any,  # ExpectationConfig
        batch_id: Optional[str] = None,
    ) -> ValidationResult:
        """Map a single GE expectation result dictionary or object into a ValidationResult.

        Args:
            raw_result: Dict or ExpectationValidationResult from GE execution.
            exp_config: ExpectationConfig matching this expectation.
            batch_id: Batch identifier (defaults to "batch").

        Returns:
            ValidationResult normalized to IceStream quality engine schema.
        """
        if isinstance(raw_result, dict):
            success = bool(raw_result.get("success", False))
            result_details = raw_result.get("result", {}) or {}
        else:
            success = bool(getattr(raw_result, "success", False))
            res_obj = getattr(raw_result, "result", {}) or {}
            if isinstance(res_obj, dict):
                result_details = res_obj
            elif hasattr(res_obj, "to_dict"):
                result_details = res_obj.to_dict()
            else:
                result_details = {}

        field_name = exp_config.column
        rule_name = exp_config.name
        severity = exp_config.severity

        # Build descriptive message
        if success:
            message = f"Expectation '{rule_name}' passed on column '{field_name}'"
        else:
            unexp_cnt = result_details.get("unexpected_count")
            unexp_pct = result_details.get("unexpected_percent")
            if unexp_cnt is not None:
                message = f"Expectation '{rule_name}' failed on column '{field_name}': {unexp_cnt} unexpected values"
                if unexp_pct is not None:
                    message += f" ({unexp_pct:.1f}%)"
            else:
                message = f"Expectation '{rule_name}' failed on column '{field_name}'"

        # Build metadata preserving source identification
        metadata = {
            "source": "great_expectations",
            "expectation": exp_config.expectation,
            "element_count": result_details.get("element_count", 0),
            "unexpected_count": result_details.get("unexpected_count", 0),
            "unexpected_percent": result_details.get("unexpected_percent", 0.0),
            "unexpected_values": result_details.get("partial_unexpected_list", []),
            "batch_id": batch_id or "batch",
        }

        return ValidationResult(
            rule_name=rule_name,
            passed=success,
            severity=severity,
            message=message,
            field=field_name,
            event_id=batch_id or "batch",
            metadata=metadata,
        )

    @staticmethod
    def build_batch_result(
        batch_id: str,
        results: List[ValidationResult],
        total_rows: int = 0,
    ) -> QualityBatchResult:
        """Summarize a list of normalized GE ValidationResults into a QualityBatchResult."""
        total_expectations = len(results)
        passed_expectations = sum(1 for r in results if r.passed)
        failed_expectations = sum(1 for r in results if not r.passed)
        critical_failures = sum(
            1 for r in results if not r.passed and r.severity in (Severity.CRITICAL, Severity.HIGH)
        )
        batch_success = (failed_expectations == 0)

        return QualityBatchResult(
            batch_id=batch_id,
            total_expectations=total_expectations,
            passed_expectations=passed_expectations,
            failed_expectations=failed_expectations,
            critical_failures=critical_failures,
            success=batch_success,
            results=results,
            metadata={"total_rows": total_rows, "source": "great_expectations"},
        )
