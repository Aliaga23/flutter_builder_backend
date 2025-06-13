"""
Colaboración sin autenticación.
Cualquiera que abra /projects/{project_id}/ws entra en la sala.
Se le da un user_id anónimo generado al vuelo (guest-UUID).
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from uuid import UUID, uuid4
from typing import Dict, List
from datetime import datetime

from core.database import SessionLocal
from models.user_project_access import UserProjectAccess
from models.user import User                      # si existe tu tabla User

router = APIRouter(prefix="/projects", tags=["Realtime"])
_rooms: Dict[UUID, List[WebSocket]] = {}              # project_id → sockets


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.websocket("/{project_id}/ws")
async def project_ws(websocket: WebSocket, project_id: UUID):
    # 0) aceptar cuanto antes para no bloquear handshake
    await websocket.accept()

    # 1) ─── user_id anónimo ──────────────────────────────────────────
    guest_id = uuid4()                                 # "session id"
    #  opcional: crea entrada User/Access para estadísticas
    with next(_db()) as db:
        try:
            db.add(User(id=guest_id, email=f"guest-{guest_id}@noauth"))
            db.add(
                UserProjectAccess(
                    user_id=guest_id,
                    project_id=project_id,
                    granted_at=datetime.utcnow(),
                )
            )
            db.commit()
        except Exception:
            db.rollback()  # si la tabla User no lo permite, ignora

    # 2) ─── unir a la sala & broadcast ──────────────────────────────
    _rooms.setdefault(project_id, []).append(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            for peer in _rooms[project_id]:
                if peer is not websocket:
                    await peer.send_text(msg)
    except WebSocketDisconnect:
        _rooms[project_id].remove(websocket)
        if not _rooms[project_id]:
            _rooms.pop(project_id, None)
