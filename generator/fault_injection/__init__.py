"""Fault injection package for IceStream event generator."""

from generator.fault_injection.engine import FaultInjectionEngine
from generator.fault_injection.modes import FaultMode
from generator.fault_injection.statistics import FaultStatistics

__all__ = ["FaultMode", "FaultInjectionEngine", "FaultStatistics"]
