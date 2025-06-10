from fastapi import (
    APIRouter, Depends, HTTPException,
    status, BackgroundTasks
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from uuid import UUID
from pathlib import Path
import tempfile, zipfile, os, datetime

from core.database import SessionLocal
from models.project import Project
from models.user_project_access import UserProjectAccess
from services.flutter_generator import generate_flutter_app
from core.security import get_current_user                      # JWT helper
from schemas.project_schema import ProjectCreate, ProjectOut
from schemas.user_project_access_schema import UserProjectAccessOut

router = APIRouter(prefix="/projects", tags=["Projects"])

# --- DEPENDENCIA DB ---------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------------------------------------------------------
# 1. CREAR PROYECTO
# ---------------------------------------------------------------------------
@router.post("/", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    owner_id = UUID(user["sub"])

    project = Project(
        name=payload.name,
        owner_id=owner_id,
        data=payload.data
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # registrar el acceso del dueño
    access = UserProjectAccess(user_id=owner_id, project_id=project.id)
    db.add(access)
    db.commit()
    return project

# ---------------------------------------------------------------------------
# 2. OBTENER PROYECTO
# ---------------------------------------------------------------------------
@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    user_id = UUID(user["sub"])
    
    # Verificar si el usuario tiene acceso al proyecto
    access = db.query(UserProjectAccess).filter(
        UserProjectAccess.project_id == project_id,
        UserProjectAccess.user_id == user_id
    ).first()
    
    if not access:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or you don't have access"
        )
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project

# ---------------------------------------------------------------------------
# 3. OBTENER TODOS LOS PROYECTOS DEL USUARIO
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[ProjectOut])
def get_all_projects(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    user_id = UUID(user["sub"])
    
    # Obtener todos los proyectos a los que el usuario tiene acceso
    projects = (
        db.query(Project)
        .join(UserProjectAccess, UserProjectAccess.project_id == Project.id)
        .filter(UserProjectAccess.user_id == user_id)
        .all()
    )
    
    return projects

# ---------------------------------------------------------------------------
# 4. ACTUALIZAR PROYECTO
# ---------------------------------------------------------------------------
@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: UUID,
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    user_id = UUID(user["sub"])
    
    # Verificar si el proyecto existe
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Verificar si el usuario tiene permiso (solo el dueño puede actualizar)
    if project.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this project"
        )
    
    # Actualizar los campos del proyecto
    project.name = payload.name
    project.data = payload.data
    project.updated_at = datetime.datetime.utcnow()
    
    db.commit()
    db.refresh(project)
    return project

# ---------------------------------------------------------------------------
# 5. ELIMINAR PROYECTO
# ---------------------------------------------------------------------------
@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    user_id = UUID(user["sub"])
    
    # Verificar si el proyecto existe
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Verificar si el usuario tiene permiso (solo el dueño puede eliminar)
    if project.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this project"
        )
    
    # Eliminar los accesos asociados al proyecto
    db.query(UserProjectAccess).filter(UserProjectAccess.project_id == project_id).delete()
    
    # Eliminar el proyecto
    db.delete(project)
    db.commit()
    
    return None
