"""Export API routes."""

from fastapi import APIRouter

from oneshot.services import export_service

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/json")
def export_json():
    """Export approved shots as JSON."""
    # TODO: retrieve approved shots
    return export_service.export_json(shots=[], metadata={"project": "TODO"})
