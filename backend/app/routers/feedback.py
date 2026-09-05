from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import ConversationLog, User
from ..schemas import FeedbackRequest, FeedbackResponse


router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse)
def create_feedback(
    payload: FeedbackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackResponse:
    log = db.scalar(
        select(ConversationLog).where(
            ConversationLog.id == payload.message_id,
            ConversationLog.user_id == user.user_id,
        )
    )
    if log is None:
        raise HTTPException(status_code=404, detail="消息不存在")
    log.feedback = payload.feedback
    log.feedback_reason = payload.feedback_reason
    db.commit()
    db.refresh(log)
    return FeedbackResponse(
        id=log.id,
        message_id=log.id,
        feedback=log.feedback or 0,
        feedback_reason=log.feedback_reason,
        query=log.query,
        result_summary=log.result_summary,
        created_at=log.created_at.isoformat(),
    )


@router.get("", response_model=list[FeedbackResponse])
def list_feedback(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FeedbackResponse]:
    logs = db.scalars(
        select(ConversationLog)
        .where(ConversationLog.user_id == user.user_id, ConversationLog.feedback.is_not(None))
        .order_by(ConversationLog.created_at.desc())
        .limit(100)
    ).all()
    return [
        FeedbackResponse(
            id=log.id,
            message_id=log.id,
            feedback=log.feedback or 0,
            feedback_reason=log.feedback_reason,
            query=log.query,
            result_summary=log.result_summary,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]

