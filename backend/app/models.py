from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Student(Base):
    __tablename__ = "student"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    gender: Mapped[int | None] = mapped_column(Integer, nullable=True)
    class_id: Mapped[str] = mapped_column(String(20), index=True)
    grade: Mapped[str] = mapped_column(String(20), index=True)
    major: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClassInfo(Base):
    __tablename__ = "class_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    class_name: Mapped[str] = mapped_column(String(50))
    grade: Mapped[str] = mapped_column(String(20), index=True)
    major: Mapped[str | None] = mapped_column(String(100), nullable=True)
    counselor_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudentScore(Base):
    __tablename__ = "student_score"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(20), index=True)
    course_id: Mapped[str] = mapped_column(String(20))
    course_name: Mapped[str] = mapped_column(String(100), index=True)
    exam_batch: Mapped[str] = mapped_column(String(50), index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_status: Mapped[int] = mapped_column(Integer, default=0)
    credit: Mapped[float | None] = mapped_column(Float, nullable=True)
    gpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    class_id: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("uk_student_course_batch", "student_id", "course_id", "exam_batch", unique=True),
        Index("idx_course_batch", "course_id", "exam_batch"),
        Index("idx_class_batch", "class_id", "exam_batch"),
    )


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    role: Mapped[int] = mapped_column(Integer)
    class_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ConversationLog(Base):
    __tablename__ = "conversation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(20), index=True)
    session_id: Mapped[str] = mapped_column(String(50), index=True)
    query: Mapped[str] = mapped_column(Text)
    rewritten_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sql_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sql_success: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

