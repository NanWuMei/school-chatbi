from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import LoginRequest, TokenResponse
from ..security import create_access_token, verify_password


router = APIRouter(prefix="/auth", tags=["auth"])


def _user_dict(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "name": user.name,
        "role": user.role,
        "role_name": {1: "学生", 2: "班长", 3: "辅导员"}.get(user.role, "未知"),
        "class_id": user.class_id,
        "grade": user.grade,
    }


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.user_id == payload.user_id))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    user.last_login_at = datetime.utcnow()
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user.user_id),
        user=_user_dict(user),
    )


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return _user_dict(user)

