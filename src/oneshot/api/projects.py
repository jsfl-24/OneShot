"""Project API routes."""

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from oneshot.api.deps import DbSession
from oneshot.db_models import Project
from oneshot.schemas import ProjectCreate, ProjectRead
from oneshot.services import project_service
from oneshot.services.errors import NotFoundError

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead)
def create_project(project: ProjectCreate, session: DbSession):
    db_project = Project(name=project.name, description=project.description)
    session.add(db_project)
    session.commit()
    session.refresh(db_project)
    return db_project


@router.get("", response_model=list[ProjectRead])
def list_projects(session: DbSession):
    return list(session.exec(select(Project)).all())


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, session: DbSession):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


@router.delete("/{project_id}")
def delete_project(project_id: int, session: DbSession):
    try:
        project_service.delete_project(project_id, session)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"id": project_id, "deleted": True}