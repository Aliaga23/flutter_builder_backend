from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from uuid import UUID
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from core.database import SessionLocal
from models.user_project_access import UserProjectAccess
from core.security import decode_token         # tu helper JWT

router = APIRouter(prefix="/projects", tags=["Realtime"])
_rooms = {}

def db():
    d = SessionLocal()
    try:
        yield d
    finally:
        d.close()

@router.websocket("/{project_id}/ws")
async def project_ws(ws: WebSocket, project_id: UUID):
    # ── 1) Token desde el sub-protocolo ────────────────────────────
    proto_hdr = ws.headers.get("sec-websocket-protocol", "")
    #     Ej.:  "jwt.eyJhbGciOiJIUzI1NiIsInR..."
    token = ""
    for part in proto_hdr.split(","):
        part = part.strip()
        if part.startswith("jwt."):
            token = part[4:]            # quita "jwt."
            break

    payload = decode_token(token)
    if payload is None:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id = UUID(payload["sub"])

    # ── 2) Inserta acceso si falta ─────────────────────────────────
    with next(db()) as session:
        exists = (
            session.query(UserProjectAccess)
            .filter_by(user_id=user_id, project_id=project_id)
            .first()
        )
        if not exists:
            try:
                session.add(
                    UserProjectAccess(
                        user_id=user_id,
                        project_id=project_id,
                        granted_at=datetime.utcnow(),
                    )
                )
                session.commit()
            except IntegrityError:
                session.rollback()

    # ── 3) Conexión y broadcast ───────────────────────────────────
    await ws.accept(subprotocol=f"jwt")   # responde con uno de los protocolos ofrecidos
    _rooms.setdefault(project_id, []).append(ws)
    try:
        while True:
            msg = await ws.receive_text()
            for peer in _rooms[project_id]:
                if peer is not ws:
                    await peer.send_text(msg)
    except WebSocketDisconnect:
        _rooms[project_id].remove(ws)
        if not _rooms[project_id]:
            _rooms.pop(project_id)
