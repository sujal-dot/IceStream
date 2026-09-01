"""Reprocessor for Self-Healing Remediation Pipeline.

Executes real re-validation of re-fetched source payloads using QualityEngine.
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional, Tuple

import sys
import os

QUALITY_ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if QUALITY_ENGINE_DIR not in sys.path:
    sys.path.insert(0, QUALITY_ENGINE_DIR)

from rules.engine import QualityEngine
from rules.registry import create_default_registry
from quarantine.writer import QuarantineWriter

logger = logging.getLogger("icestream.remediation.reprocessor")


@dataclass
class ReprocessResult:
    total_processed: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    valid_events: List[Dict[str, Any]] = field(default_factory=list)
    invalid_events: List[Dict[str, Any]] = field(default_factory=list)
    quarantine_results: List[Dict[str, Any]] = field(default_factory=list)
    error_rate: float = 0.0

    @property
    def is_fully_valid(self) -> bool:
        return self.total_processed > 0 and self.invalid_count == 0


class Reprocessor:
    """Reprocesses recovered source payloads through QualityEngine.

    Ensures recovered events undergo real validation.
    """

    def __init__(
        self,
        quality_engine: Optional[QualityEngine] = None,
        quarantine_writer: Optional[QuarantineWriter] = None,
    ):
        self.quality_engine = quality_engine or QualityEngine(registry=create_default_registry())
        self.quarantine_writer = quarantine_writer

    def validate_event(self, event: Dict[str, Any]):
        """Helper to validate a single event using the underlying QualityEngine."""
        results, summary = self.quality_engine.validate_with_summary(event)
        is_valid = (summary.failed_rules == 0)
        summary_dict = summary.to_dict()
        summary_dict["is_valid"] = is_valid
        summary_dict["failed_rule_names"] = [r.rule_name for r in results if not r.passed]
        return summary

    def process(
        self,
        recovered_events: List[Dict[str, Any]],
        incident_id: Optional[str] = None,
        attempt_number: int = 1,
    ) -> ReprocessResult:
        """Process list of re-fetched events through QualityEngine.

        Routes valid events to output array and invalid events to quarantine writer.
        """
        if not recovered_events:
            logger.warning("[Reprocessor] No recovered events provided to process.")
            return ReprocessResult()

        result = ReprocessResult()
        result.total_processed = len(recovered_events)

        for event in recovered_events:
            # Create isolated fresh QualityEngine if necessary to prevent duplicate event rule collisions on re-processed events
            results, summary = self.quality_engine.validate_with_summary(event)
            is_valid = (summary.failed_rules == 0)
            failed_rule_names = [r.rule_name for r in results if not r.passed]

            if is_valid:
                result.valid_count += 1
                # Attach remediation provenance metadata without mutating customer data schema
                event_copy = event.copy()
                if incident_id:
                    event_copy["_remediation_incident_id"] = incident_id
                    event_copy["_remediation_attempt"] = attempt_number
                result.valid_events.append(event_copy)
            else:
                result.invalid_count += 1
                result.invalid_events.append(event)
                logger.warning(
                    f"[Reprocessor] Recovered event '{event.get('event_id')}' FAILED re-validation: "
                    f"failed_rules={failed_rule_names}"
                )

                # Persist bad recovered event to quarantine if writer available
                if self.quarantine_writer:
                    try:
                        q_dict = summary.to_dict()
                        q_dict["is_valid"] = False
                        q_dict["failed_rules"] = failed_rule_names
                        q_res = self.quarantine_writer.write_invalid_event(
                            event=event,
                            quality_result=q_dict,
                            error_code="REMEDIATION_REPROCESS_FAILED",
                        )
                        result.quarantine_results.append(q_res)
                    except Exception as e:
                        logger.error(f"[Reprocessor] Failed to quarantine bad recovered event: {e}")

        result.error_rate = result.invalid_count / float(result.total_processed)
        logger.info(
            f"[Reprocessor] Reprocessing complete: total={result.total_processed}, "
            f"valid={result.valid_count}, invalid={result.invalid_count}, error_rate={result.error_rate:.4f}"
        )
        return result
