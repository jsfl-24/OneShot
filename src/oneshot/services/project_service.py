"""Project lifecycle service: hard deletion of a project and its dependents."""

from pathlib import Path

from sqlmodel import Session, select

from oneshot.config import settings
from oneshot.db_models import ProductionConstraints, Project, Scene, Screenplay, Shot
from oneshot.services.errors import NotFoundError


def _unlink_uploaded_source(source_path: str) -> None:
    """Best-effort removal of an uploaded source file located inside UPLOAD_DIR."""
    try:
        path = Path(source_path)
        if path.resolve().parent != settings.UPLOAD_DIR.resolve():
            return
        path.unlink(missing_ok=True)
    except OSError:
        return


def delete_project(project_id: int, session: Session) -> bool:
    """Delete a project, cascading to its screenplays, scenes, shots and constraints.

    Child rows are removed explicitly because SQLite foreign keys are not enforced
    in this application. Uploaded source files are unlinked afterwards on a
    best-effort basis.
    """
    project = session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} not found")

    screenplays = list(
        session.exec(select(Screenplay).where(Screenplay.project_id == project_id)).all()
    )
    scenes = list(session.exec(select(Scene).where(Scene.project_id == project_id)).all())
    source_paths = [screenplay.source_path for screenplay in screenplays]
    scene_ids = [scene.id for scene in scenes if scene.id is not None]

    constraints = session.exec(
        select(ProductionConstraints).where(
            ProductionConstraints.project_id == project_id
        )
    ).all()
    if scene_ids:
        by_scene = session.exec(
            select(ProductionConstraints).where(
                ProductionConstraints.scene_id.in_(scene_ids)
            )
        ).all()
        constraints = [*constraints, *by_scene]
    for constraint in {row.id: row for row in constraints if row.id is not None}.values():
        session.delete(constraint)

    if scene_ids:
        for shot in session.exec(select(Shot).where(Shot.scene_id.in_(scene_ids))).all():
            session.delete(shot)

    for scene in scenes:
        session.delete(scene)
    for screenplay in screenplays:
        session.delete(screenplay)

    session.delete(project)
    session.commit()

    for source_path in source_paths:
        _unlink_uploaded_source(source_path)

    return True
