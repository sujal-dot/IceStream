"""Pipeline State Manager for IceStream.

Backend-owned authoritative pipeline state model and transition manager backed by persistent database storage.
"""

from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Set

import sys
import os

# Ensure backend directory is on sys.path to import DB storage
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from storage.db import StorageBackend, get_db_storage

logger = logging.getLogger("icestream.remediation.state_manager")


class PipelineState(str, Enum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    DEGRADED = "DEGRADED"
    QUARANTINING = "QUARANTINING"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    REMEDIATING = "REMEDIATING"
    REFETCHING = "REFETCHING"
    REPROCESSING = "REPROCESSING"
    VALIDATING = "VALIDATING"
    RESUMING = "RESUMING"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    RECOVERED = "RECOVERED"


# Define valid state transition graph
VALID_TRANSITIONS: Dict[PipelineState, Set[PipelineState]] = {
    PipelineState.RUNNING: {
        PipelineState.PAUSED,
        PipelineState.DEGRADED,
        PipelineState.QUARANTINING,
        PipelineState.CIRCUIT_OPEN,
    },
    PipelineState.PAUSED: {
        PipelineState.RUNNING,
        PipelineState.RESUMING,
    },
    PipelineState.DEGRADED: {
        PipelineState.RUNNING,
        PipelineState.PAUSED,
        PipelineState.QUARANTINING,
        PipelineState.CIRCUIT_OPEN,
    },
    PipelineState.QUARANTINING: {
        PipelineState.RUNNING,
        PipelineState.PAUSED,
        PipelineState.DEGRADED,
        PipelineState.CIRCUIT_OPEN,
    },
    PipelineState.CIRCUIT_OPEN: {
        PipelineState.REMEDIATING,
        PipelineState.RUNNING,
    },
    PipelineState.REMEDIATING: {
        PipelineState.REFETCHING,
        PipelineState.RECOVERY_FAILED,
        PipelineState.CIRCUIT_OPEN,
    },
    PipelineState.REFETCHING: {
        PipelineState.REPROCESSING,
        PipelineState.RECOVERY_FAILED,
        PipelineState.CIRCUIT_OPEN,
    },
    PipelineState.REPROCESSING: {
        PipelineState.VALIDATING,
        PipelineState.RECOVERY_FAILED,
        PipelineState.CIRCUIT_OPEN,
    },
    PipelineState.VALIDATING: {
        PipelineState.RESUMING,
        PipelineState.RECOVERY_FAILED,
        PipelineState.CIRCUIT_OPEN,
    },
    PipelineState.RESUMING: {
        PipelineState.RUNNING,
        PipelineState.RECOVERY_FAILED,
        PipelineState.CIRCUIT_OPEN,
    },
    PipelineState.RECOVERY_FAILED: {
        PipelineState.CIRCUIT_OPEN,
        PipelineState.REMEDIATING,
    },
    PipelineState.RECOVERED: {
        PipelineState.RUNNING,
    },
}


class PipelineStateManager:
    """Authoritative Backend Pipeline State Manager.

    All state transitions MUST execute through this component.
    """

    def __init__(
        self,
        pipeline_id: str = "icestream",
        storage: Optional[StorageBackend] = None,
        initial_state: PipelineState = PipelineState.RUNNING,
    ):
        self.pipeline_id = pipeline_id
        self.storage = storage or get_db_storage()

        # Load or initialize DB state
        existing = self.storage.get_pipeline_state(self.pipeline_id)
        if not existing:
            self.storage.upsert_pipeline_state(
                pipeline_id=self.pipeline_id,
                state=initial_state.value,
                reason="Initial system startup",
                updated_at=datetime.now(timezone.utc),
            )
            self._current_state = initial_state
        else:
            try:
                self._current_state = PipelineState(existing["state"])
            except ValueError:
                self._current_state = initial_state

    @property
    def current_state(self) -> PipelineState:
        existing = self.storage.get_pipeline_state(self.pipeline_id)
        if existing:
            try:
                self._current_state = PipelineState(existing["state"])
            except ValueError:
                pass
        return self._current_state

    def get_state(self) -> Dict[str, Any]:
        """Return details of current authoritative pipeline state."""
        state_dict = self.storage.get_pipeline_state(self.pipeline_id)
        if not state_dict:
            state_dict = {
                "pipeline_id": self.pipeline_id,
                "state": self._current_state.value,
                "previous_state": None,
                "reason": "Initialized",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "active_incident_id": None,
                "recovery_attempt": 0,
                "last_error": None,
            }
        return state_dict

    def can_transition_to(self, target_state: PipelineState) -> bool:
        """Check if transition from current state to target state is allowed."""
        curr = self.current_state
        allowed = VALID_TRANSITIONS.get(curr, set())
        return target_state in allowed

    def transition_to(
        self,
        to_state: PipelineState,
        reason: Optional[str] = None,
        incident_id: Optional[str] = None,
        recovery_attempt: int = 0,
        last_error: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Transition pipeline to new state with validation and persistence.

        Raises ValueError if transition is invalid and force is False.
        """
        to_state = to_state if isinstance(to_state, PipelineState) else PipelineState(str(to_state))
        curr = self.current_state
        if not force and to_state != curr:
            if not self.can_transition_to(to_state):
                raise ValueError(
                    f"Invalid pipeline state transition from '{curr.value}' to '{to_state.value}'"
                )

        from_state_val = curr.value
        to_state_val = to_state.value
        ts = datetime.now(timezone.utc)

        # Update in storage
        updated_dict = self.storage.upsert_pipeline_state(
            pipeline_id=self.pipeline_id,
            state=to_state_val,
            previous_state=from_state_val,
            reason=reason,
            updated_at=ts,
            active_incident_id=incident_id,
            recovery_attempt=recovery_attempt,
            last_error=last_error,
        )

        # Record history audit record
        self.storage.record_state_history(
            pipeline_id=self.pipeline_id,
            from_state=from_state_val,
            to_state=to_state_val,
            reason=reason,
            timestamp=ts,
            incident_id=incident_id,
            recovery_attempt=recovery_attempt,
        )

        self._current_state = to_state
        logger.info(
            f"[PipelineStateManager] Pipeline '{self.pipeline_id}' state transition: "
            f"{from_state_val} -> {to_state_val} (Reason: {reason})"
        )
        return updated_dict

    def record_failure(
        self,
        error: str,
        incident_id: Optional[str] = None,
        recovery_attempt: int = 0,
    ) -> Dict[str, Any]:
        """Convenience method to transition pipeline state to RECOVERY_FAILED."""
        return self.transition_to(
            to_state=PipelineState.RECOVERY_FAILED,
            reason=f"Recovery failed: {error}",
            incident_id=incident_id,
            recovery_attempt=recovery_attempt,
            last_error=error,
            force=True,
        )

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve state transition history trail."""
        return self.storage.get_state_history(self.pipeline_id, limit=limit)
