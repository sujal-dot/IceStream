"""Data lineage API Pydantic models compatible with React Flow."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class LineageNode(BaseModel):
    """Lineage graph node representation."""

    id: str
    type: str = Field(..., description="Node type e.g. source, queue, engine, storage, sink")
    label: str
    status: Optional[str] = "HEALTHY"
    details: Optional[Dict[str, str]] = None


class LineageEdge(BaseModel):
    """Lineage graph directed edge representation."""

    id: str
    source: str
    target: str
    label: Optional[str] = None
    animated: bool = False


class LineageResponse(BaseModel):
    """React Flow compatible lineage graph response."""

    nodes: List[LineageNode]
    edges: List[LineageEdge]
