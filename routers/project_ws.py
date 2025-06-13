"""
Collaboration WebSocket ― se crea acceso en caliente.

URL:  /projects/{project_id}/ws?token=<JWT>

• El JWT se decodifica con core/security.decode_token
• Si el user aún NO está en user_project_access ⇒ se inserta
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from uuid import UUID
from typing import Dict, List
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from core.database import SessionLocal
from core.security import decode_token
from models.user_project_access import UserProjectAccess

router = APIRouter(prefix="/projects", tags=["Realtime"])
_rooms: Dict[UUID, List[WebSocket]] = {}   # project_id → [ws…]


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.websocket("/{project_id}/ws")
async def project_ws(websocket: WebSocket, project_id: UUID):
    # 1 ─── JWT ───────────────────────────────────────────────────────
    token = websocket.query_params.get("token", "")
    payload = decode_token(token)
    if payload is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id = UUID(payload["sub"])

    # 2 ─── Conexión DB y alta “on-the-fly” ───────────────────────────
    db_iter = _db()
    db = next(db_iter)
    access = (
        db.query(UserProjectAccess)
        .filter_by(user_id=user_id, project_id=project_id)
        .first()
    )
    if access is None:
        try:
            access = UserProjectAccess(
                user_id=user_id,
                project_id=project_id,
                granted_at=datetime.utcnow(),    # si tu modelo lo tiene
            )
            db.add(access)
            db.commit()
        except IntegrityError:
            db.rollback()   # alguien lo insertó a la vez; seguimos
    db_iter.close()

    # 3 ─── Aceptar y retransmitir ────────────────────────────────────
    await websocket.accept()
    _rooms.setdefault(project_id, []).append(websocket)

    try:
        while True:
            msg = await websocket.receive_text()        # → JSON / Patch
            for peer in _rooms[project_id]:
                if peer is not websocket:
                    await peer.send_text(msg)
    except WebSocketDisconnect:
        _rooms[project_id].remove(websocket)
        if not _rooms[project_id]:
            _rooms.pop(project_id, None)
