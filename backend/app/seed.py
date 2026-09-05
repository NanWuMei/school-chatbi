from __future__ import annotations

import random
from pathlib import Path

from .config import settings
from .db import Base, SessionLocal, engine
from .models import ClassInfo, Student, StudentScore, User
from .security import hash_password


COURSES = [
    ("C001", "高等数学", 4.0),
    ("C002", "大学英语", 3.0),
    ("C003", "线性代数", 3.0),
    ("C004", "概率论与数理统计", 3.0),
    ("C005", "计算机基础", 2.0),
]
EXAM_BATCHES = ["2024-2025学年第一学期期中", "2024-2025学年第一学期期末"]
CLASSES = [
    ("class_2301", "计算机2301班", "2023"),
    ("class_2302", "计算机2302班", "2023"),
    ("class_2303", "软件2301班", "2023"),
]


def _ensure_dirs() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.knowledge_dir.mkdir(parents=True, exist_ok=True)


def _seed_users(db) -> None:
    old_student = db.query(User).filter(User.user_id == "202300101").first()
    if old_student is not None:
        db.delete(old_student)
        db.commit()

    existing_ids = {row[0] for row in db.query(User.user_id).all()}
    needed = [
        User(user_id="20230001", name="演示学生", role=1, class_id="class_2301", grade="2023", password_hash=hash_password("student123")),
        User(user_id="monitor01", name="演示班长", role=2, class_id="class_2301", grade="2023", password_hash=hash_password("monitor123")),
        User(user_id="counselor01", name="演示辅导员", role=3, class_id=None, grade="2023", password_hash=hash_password("counselor123")),
    ]
    for user in needed:
        if user.user_id not in existing_ids:
            db.add(user)
    db.commit()


def _seed_classes_and_students(db) -> None:
    if db.query(ClassInfo).count() > 0:
        return
    for class_id, class_name, grade in CLASSES:
        db.add(ClassInfo(class_id=class_id, class_name=class_name, grade=grade, major="计算机科学与技术", counselor_id="counselor01"))

    rng = random.Random(42)
    seq = 1
    for class_id, _, grade in CLASSES:
        for idx in range(15):
            student_id = f"2023{seq:04d}"
            seq += 1
            name = f"学生{student_id[-2:]}"
            db.add(
                Student(
                    student_id=student_id,
                    name=name,
                    gender=1 if idx % 2 == 0 else 2,
                    class_id=class_id,
                    grade=grade,
                    major="计算机科学与技术",
                )
            )
    db.commit()


def _seed_scores(db) -> None:
    if db.query(StudentScore).count() > 0:
        return
    students = db.query(Student).all()
    rng = random.Random(7)
    class_offset = {"class_2301": 0.0, "class_2302": -3.0, "class_2303": 2.0}
    course_base = {"高等数学": 72.0, "大学英语": 74.0, "线性代数": 70.0, "概率论与数理统计": 68.0, "计算机基础": 78.0}
    for student in students:
        for course_id, course_name, credit in COURSES:
            for batch in EXAM_BATCHES:
                if rng.random() < 0.02:
                    db.add(
                        StudentScore(
                            student_id=student.student_id,
                            course_id=course_id,
                            course_name=course_name,
                            exam_batch=batch,
                            score=None,
                            score_status=1,
                            credit=credit,
                            gpa=None,
                            class_id=student.class_id,
                        )
                    )
                    continue
                base = course_base[course_name] + class_offset[student.class_id]
                score = max(28.0, min(99.0, rng.gauss(base, 12.0)))
                score = round(score, 1)
                gpa = round(score / 100 * 4.0, 2)
                db.add(
                    StudentScore(
                        student_id=student.student_id,
                        course_id=course_id,
                        course_name=course_name,
                        exam_batch=batch,
                        score=score,
                        score_status=0,
                        credit=credit,
                        gpa=gpa,
                        class_id=student.class_id,
                    )
                )
    db.commit()


def run_seed() -> None:
    _ensure_dirs()
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        _seed_users(db)
        _seed_classes_and_students(db)
        _seed_scores(db)
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
    print("Seed complete.")
