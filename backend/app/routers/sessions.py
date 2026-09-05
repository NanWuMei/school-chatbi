import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import ConversationLog, User
from ..schemas import MessageOut, SessionCreateResponse


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreateResponse)
def create_session(user: User = Depends(get_current_user)) -> SessionCreateResponse:
    return SessionCreateResponse(session_id=uuid.uuid4().hex)


def _parse_response_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


@router.get("/{session_id}/messages", response_model=list[MessageOut])
def list_messages(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MessageOut]:
    logs = db.scalars(
        select(ConversationLog)
        .where(ConversationLog.session_id == session_id, ConversationLog.user_id == user.user_id)
        .order_by(ConversationLog.created_at.asc())
    ).all()
    messages: list[MessageOut] = []
    for log in logs:
        payload = _parse_response_json(log.response_json)
        messages.append(
            MessageOut(
                id=log.id,
                role="user",
                text=log.query,
                created_at=log.created_at.isoformat(),
            )
        )
        messages.append(
            MessageOut(
                id=log.id,
                role="assistant",
                text=log.result_summary or "",
                answer_type=log.answer_type,
                chart_config=payload.get("chart_config"),
                data_rows=payload.get("data_rows", []),
                generated_sql=log.sql_text,
                suggestions=payload.get("suggestions", []),
                created_at=log.created_at.isoformat(),
            )
        )
    return messages
