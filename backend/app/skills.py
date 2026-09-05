from __future__ import annotations

from .db import engine
from .models import ClassInfo, Student, StudentScore, User
from .query_engine import PermissionDeniedError, QueryResult, _allowed_class_ids, _base_filters, _latest_exam_batch, _render_sql


score_table = StudentScore.__table__
student_table = Student.__table__
class_table = ClassInfo.__table__


def run_overall_distribution(user: User, exam_batch: str | None, course_name: str | None) -> QueryResult:
    if user.role == 1:
        raise PermissionDeniedError("您没有权限查看")
    from sqlalchemy import and_, case, func, select

    with engine.connect() as conn:
        batch = exam_batch or _latest_exam_batch(conn)
        conds = _base_filters(user, {"exam_batch": batch, "course_name": course_name})
        bucket_expr = case(
            (score_table.c.score < 60, "0-59"),
            (score_table.c.score < 70, "60-69"),
            (score_table.c.score < 80, "70-79"),
            (score_table.c.score < 90, "80-89"),
            else_="90-100",
        )
        dist_stmt = (
            select(bucket_expr.label("bucket"), func.count(score_table.c.id).label("count"))
            .where(and_(*conds))
            .group_by(bucket_expr)
        )
        raw = [dict(r) for r in conn.execute(dist_stmt).mappings().all()]
        order = {"0-59": 0, "60-69": 1, "70-79": 2, "80-89": 3, "90-100": 4}
        raw.sort(key=lambda r: order.get(str(r["bucket"]), 99))

        summary_stmt = (
            select(
                func.count(score_table.c.id).label("count"),
                func.avg(score_table.c.score).label("avg_score"),
                func.min(score_table.c.score).label("min_score"),
                func.max(score_table.c.score).label("max_score"),
                func.sum(case((score_table.c.score >= 60, 1), else_=0)).label("pass_count"),
            ).where(and_(*conds))
        )
        summary = dict(conn.execute(summary_stmt).mappings().one())
        count = int(summary["count"] or 0)
        pass_count = int(summary["pass_count"] or 0)
        rows = [
            {
                "metric": "整体成绩分布",
                "count": count,
                "avg_score": round(float(summary["avg_score"]), 2) if summary["avg_score"] is not None else None,
                "min_score": summary["min_score"],
                "max_score": summary["max_score"],
                "pass_rate": round(pass_count / count, 4) if count else 0,
                "fail_rate": round((count - pass_count) / count, 4) if count else 0,
            }
        ]
        chart_config = {
            "type": "bar",
            "title": "整体成绩分布",
            "x": [r["bucket"] for r in raw],
            "series": [{"name": "人数", "data": [r["count"] for r in raw]}],
        }
        return QueryResult(rows=rows, chart_config=chart_config, sql=_render_sql(dist_stmt), answer_type="report")


def run_risk_warning(user: User, exam_batch: str | None, course_name: str | None) -> QueryResult:
    if user.role == 1:
        raise PermissionDeniedError("您没有权限查看")
    from sqlalchemy import and_, func, select

    with engine.connect() as conn:
        batch = exam_batch or _latest_exam_batch(conn)
        conds = _base_filters(user, {"exam_batch": batch, "course_name": course_name})
        stmt = (
            select(
                score_table.c.student_id,
                func.count(score_table.c.id).label("fail_count"),
                func.group_concat(score_table.c.course_name).label("fail_courses"),
            )
            .where(and_(*conds, score_table.c.score < 60))
            .group_by(score_table.c.student_id)
            .order_by(func.count(score_table.c.id).desc())
        )
        rows = [dict(r) for r in conn.execute(stmt).mappings().all()]
        chart_data = rows[:12]
        chart_config = {
            "type": "bar",
            "title": "挂科风险预警",
            "x": [r["student_id"] for r in chart_data],
            "series": [{"name": "挂科数", "data": [r["fail_count"] for r in chart_data]}],
            "show_table": True,
            "columns": [
                {"prop": "student_id", "label": "学号"},
                {"prop": "fail_count", "label": "挂科数"},
                {"prop": "fail_courses", "label": "挂科课程"},
            ],
        }
        return QueryResult(rows=rows, chart_config=chart_config, sql=_render_sql(stmt), answer_type="report")


def _require_manager(user: User) -> None:
    if user.role == 1:
        raise PermissionDeniedError("您没有权限查看")


def run_class_compare(user: User, exam_batch: str | None, course_name: str | None) -> QueryResult:
    _require_manager(user)
    from sqlalchemy import and_, case, func, select

    with engine.connect() as conn:
        batch = exam_batch or _latest_exam_batch(conn)
        conds = _base_filters(user, {"exam_batch": batch, "course_name": course_name})
        stmt = (
            select(
                score_table.c.class_id,
                func.count(score_table.c.id).label("count"),
                func.avg(score_table.c.score).label("avg_score"),
                func.sum(case((score_table.c.score >= 60, 1), else_=0)).label("pass_count"),
            )
            .where(and_(*conds))
            .group_by(score_table.c.class_id)
        )
        raw = [dict(r) for r in conn.execute(stmt).mappings().all()]
        rows = []
        for r in raw:
            count = int(r["count"] or 0)
            pass_count = int(r["pass_count"] or 0)
            rows.append(
                {
                    "class_id": r["class_id"],
                    "avg_score": round(float(r["avg_score"]), 2) if r["avg_score"] is not None else None,
                    "pass_rate": round(pass_count / count, 4) if count else 0,
                    "fail_rate": round((count - pass_count) / count, 4) if count else 0,
                    "count": count,
                }
            )
        chart_config = {
            "type": "bar",
            "title": "班级横向对比",
            "x": [r["class_id"] for r in rows],
            "series": [{"name": "平均分", "data": [r["avg_score"] for r in rows]}],
            "show_table": True,
            "columns": [
                {"prop": "class_id", "label": "班级"},
                {"prop": "avg_score", "label": "平均分"},
                {"prop": "pass_rate", "label": "及格率"},
                {"prop": "fail_rate", "label": "挂科率"},
            ],
        }
        return QueryResult(rows=rows, chart_config=chart_config, sql=_render_sql(stmt), answer_type="report")


def run_course_deep(user: User, exam_batch: str | None, course_name: str | None) -> QueryResult:
    _require_manager(user)
    from sqlalchemy import and_, case, func, select

    with engine.connect() as conn:
        batch = exam_batch or _latest_exam_batch(conn)
        conds = _base_filters(user, {"exam_batch": batch, "course_name": course_name})
        stmt = (
            select(
                score_table.c.course_name,
                func.count(score_table.c.id).label("count"),
                func.avg(score_table.c.score).label("avg_score"),
                func.sum(case((score_table.c.score >= 60, 1), else_=0)).label("pass_count"),
            )
            .where(and_(*conds))
            .group_by(score_table.c.course_name)
        )
        raw = [dict(r) for r in conn.execute(stmt).mappings().all()]
        rows = []
        for r in raw:
            count = int(r["count"] or 0)
            pass_count = int(r["pass_count"] or 0)
            rows.append(
                {
                    "course_name": r["course_name"],
                    "avg_score": round(float(r["avg_score"]), 2) if r["avg_score"] is not None else None,
                    "pass_rate": round(pass_count / count, 4) if count else 0,
                    "fail_rate": round((count - pass_count) / count, 4) if count else 0,
                    "count": count,
                }
            )
        rows.sort(key=lambda r: r["avg_score"] or 0)
        chart_config = {
            "type": "bar",
            "title": "单科深度分析",
            "x": [r["course_name"] for r in rows],
            "series": [{"name": "平均分", "data": [r["avg_score"] for r in rows]}],
            "show_table": True,
            "columns": [
                {"prop": "course_name", "label": "科目"},
                {"prop": "avg_score", "label": "平均分"},
                {"prop": "pass_rate", "label": "及格率"},
                {"prop": "fail_rate", "label": "挂科率"},
            ],
        }
        return QueryResult(rows=rows, chart_config=chart_config, sql=_render_sql(stmt), answer_type="report")


def _ordered_exam_batches() -> list[str]:
    from sqlalchemy import select

    with engine.connect() as conn:
        rows = conn.execute(select(score_table.c.exam_batch).distinct()).all()
    return sorted([r[0] for r in rows])


def run_trend_compare(user: User, exam_batch: str | None, course_name: str | None) -> QueryResult:
    _require_manager(user)
    from sqlalchemy import and_, case, func, select

    batches = _ordered_exam_batches()
    if not batches:
        return QueryResult(rows=[], chart_config=None, sql=None, answer_type="report")
    if exam_batch and exam_batch in batches:
        idx = batches.index(exam_batch)
        selected = batches[max(0, idx - 1) : idx + 1]
    else:
        selected = batches[-2:]
    rows = []
    with engine.connect() as conn:
        for batch in selected:
            conds = _base_filters(user, {"exam_batch": batch, "course_name": course_name})
            stmt = (
                select(
                    func.count(score_table.c.id).label("count"),
                    func.avg(score_table.c.score).label("avg_score"),
                    func.sum(case((score_table.c.score >= 60, 1), else_=0)).label("pass_count"),
                ).where(and_(*conds))
            )
            r = dict(conn.execute(stmt).mappings().one())
            count = int(r["count"] or 0)
            pass_count = int(r["pass_count"] or 0)
            rows.append(
                {
                    "exam_batch": batch,
                    "avg_score": round(float(r["avg_score"]), 2) if r["avg_score"] is not None else None,
                    "pass_rate": round(pass_count / count, 4) if count else 0,
                    "fail_rate": round((count - pass_count) / count, 4) if count else 0,
                    "count": count,
                }
            )
    chart_config = {
        "type": "line",
        "title": "纵向趋势对比",
        "x": [r["exam_batch"] for r in rows],
        "series": [
            {"name": "平均分", "data": [r["avg_score"] for r in rows], "type": "line"},
            {"name": "及格率", "data": [round((r["pass_rate"] or 0) * 100, 1) for r in rows], "type": "line"},
        ],
        "show_table": True,
        "columns": [
            {"prop": "exam_batch", "label": "考试批次"},
            {"prop": "avg_score", "label": "平均分"},
            {"prop": "pass_rate", "label": "及格率"},
            {"prop": "fail_rate", "label": "挂科率"},
        ],
    }
    return QueryResult(rows=rows, chart_config=chart_config, sql=None, answer_type="report")


def run_group_diff(user: User, exam_batch: str | None, course_name: str | None) -> QueryResult:
    _require_manager(user)
    from sqlalchemy import and_, case, func, select

    with engine.connect() as conn:
        batch = exam_batch or _latest_exam_batch(conn)
        conds = _base_filters(user, {"exam_batch": batch, "course_name": course_name})
        stmt = (
            select(
                student_table.c.gender.label("gender"),
                func.count(score_table.c.id).label("count"),
                func.avg(score_table.c.score).label("avg_score"),
                func.sum(case((score_table.c.score >= 60, 1), else_=0)).label("pass_count"),
            )
            .select_from(score_table.join(student_table, score_table.c.student_id == student_table.c.student_id))
            .where(and_(*conds))
            .group_by(student_table.c.gender)
        )
        raw = [dict(r) for r in conn.execute(stmt).mappings().all()]
        rows = []
        for r in raw:
            count = int(r["count"] or 0)
            pass_count = int(r["pass_count"] or 0)
            rows.append(
                {
                    "gender": "男" if r["gender"] == 1 else "女",
                    "avg_score": round(float(r["avg_score"]), 2) if r["avg_score"] is not None else None,
                    "pass_rate": round(pass_count / count, 4) if count else 0,
                    "fail_rate": round((count - pass_count) / count, 4) if count else 0,
                    "count": count,
                }
            )
    chart_config = {
        "type": "bar",
        "title": "群体差异分析",
        "x": [r["gender"] for r in rows],
        "series": [{"name": "平均分", "data": [r["avg_score"] for r in rows]}],
        "show_table": True,
        "columns": [
            {"prop": "gender", "label": "群体"},
            {"prop": "avg_score", "label": "平均分"},
            {"prop": "pass_rate", "label": "及格率"},
            {"prop": "fail_rate", "label": "挂科率"},
        ],
    }
    return QueryResult(rows=rows, chart_config=chart_config, sql=None, answer_type="report")
