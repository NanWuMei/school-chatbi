from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import Connection

from .db import engine
from .models import ClassInfo, Student, StudentScore, User


@dataclass
class QueryResult:
    rows: list[dict[str, Any]]
    chart_config: dict[str, Any] | None
    sql: str | None
    answer_type: str


class PermissionDeniedError(RuntimeError):
    pass


student_table = Student.__table__
class_table = ClassInfo.__table__
score_table = StudentScore.__table__


def _render_sql(stmt: Any) -> str | None:
    if stmt is None:
        return None
    return str(stmt.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": False}))


def _allowed_class_ids(user: User) -> list[str]:
    if user.role == 2:
        return [user.class_id or ""]
    if user.role == 3:
        with engine.connect() as conn:
            rows = conn.execute(
                select(class_table.c.class_id).where(class_table.c.grade == user.grade)
            ).all()
        return [row[0] for row in rows]
    return []


def _scope_condition(user: User):
    if user.role == 1:
        return score_table.c.student_id == user.user_id
    if user.role == 2:
        return score_table.c.class_id == (user.class_id or "")
    if user.role == 3:
        class_ids = _allowed_class_ids(user)
        return score_table.c.class_id.in_(class_ids)
    return None


def _latest_exam_batch(conn: Connection) -> str | None:
    return conn.scalar(select(func.max(score_table.c.exam_batch)))


def _base_filters(user: User, filters: dict[str, Any]) -> list[Any]:
    conds = []
    scope = _scope_condition(user)
    if scope is not None:
        conds.append(scope)
    if filters.get("course_name"):
        conds.append(score_table.c.course_name == filters["course_name"])
    if filters.get("exam_batch"):
        conds.append(score_table.c.exam_batch == filters["exam_batch"])
    conds.append(score_table.c.score_status == 0)
    return conds


def _resolve_exam_batch(conn: Connection, filters: dict[str, Any]) -> str | None:
    return filters.get("exam_batch") or _latest_exam_batch(conn)


def _row_dict(row: Any) -> dict[str, Any]:
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def _value_only(rows: list[dict[str, Any]], key: str) -> Any:
    if rows and key in rows[0]:
        return rows[0][key]
    return None


def run_score_query(user: User, filters: dict[str, Any]) -> QueryResult:
    with engine.connect() as conn:
        batch = _resolve_exam_batch(conn, filters)
        conds = _base_filters(user, {**filters, "exam_batch": batch})
        stmt = select(
            score_table.c.student_id,
            score_table.c.course_name,
            score_table.c.exam_batch,
            score_table.c.score,
        ).where(and_(*conds))
        rows = [_row_dict(r) for r in conn.execute(stmt).mappings().all()]
        return QueryResult(rows=rows, chart_config=None, sql=_render_sql(stmt), answer_type="text")


def _gpa_stmt(user: User, filters: dict[str, Any]):
    batch = filters.get("exam_batch")
    conds = _base_filters(user, filters)
    return (
        select(
            score_table.c.student_id,
            func.sum(score_table.c.credit * score_table.c.gpa).label("weighted"),
            func.sum(score_table.c.credit).label("credits"),
        )
        .where(and_(*conds))
        .group_by(score_table.c.student_id)
    )


def run_gpa_query(user: User, filters: dict[str, Any]) -> QueryResult:
    with engine.connect() as conn:
        filters = {**filters, "exam_batch": _resolve_exam_batch(conn, filters)}
        stmt = _gpa_stmt(user, filters)
        raw = [_row_dict(r) for r in conn.execute(stmt).mappings().all()]
        rows = []
        for item in raw:
            credits = float(item["credits"] or 0)
            weighted = float(item["weighted"] or 0)
            rows.append(
                {
                    "student_id": item["student_id"],
                    "gpa": round(weighted / credits, 3) if credits else None,
                }
            )
        return QueryResult(rows=rows, chart_config=None, sql=_render_sql(stmt), answer_type="text")


def run_gpa_rank_query(user: User, filters: dict[str, Any]) -> QueryResult:
    with engine.connect() as conn:
        filters = {**filters, "exam_batch": _resolve_exam_batch(conn, filters)}
        gpa_rows = run_gpa_query(user, filters).rows
        gpa_rows = [r for r in gpa_rows if r["gpa"] is not None]
        gpa_rows.sort(key=lambda r: r["gpa"], reverse=True)
        rank_map: dict[str, int] = {}
        last_gpa = None
        last_rank = 0
        for idx, item in enumerate(gpa_rows, start=1):
            if last_gpa is not None and abs(last_gpa - item["gpa"]) < 1e-9:
                rank = last_rank
            else:
                rank = idx
                last_rank = idx
                last_gpa = item["gpa"]
            rank_map[item["student_id"]] = rank

        if user.role == 1:
            rows = [
                {
                    "student_id": user.user_id,
                    "rank": rank_map.get(user.user_id),
                    "total": len(gpa_rows),
                    "gpa": next((r["gpa"] for r in gpa_rows if r["student_id"] == user.user_id), None),
                }
            ]
        else:
            rows = [
                {
                    "student_id": item["student_id"],
                    "rank": rank_map[item["student_id"]],
                    "total": len(gpa_rows),
                    "gpa": item["gpa"],
                }
                for item in gpa_rows
            ]
        return QueryResult(rows=rows, chart_config=None, sql=None, answer_type="text")


def _aggregate_stmt(user: User, filters: dict[str, Any]):
    conds = _base_filters(user, filters)
    return (
        select(
            func.count(score_table.c.id).label("count"),
            func.avg(score_table.c.score).label("avg_score"),
            func.sum(case((score_table.c.score >= 60, 1), else_=0)).label("pass_count"),
        ).where(and_(*conds))
    )


def run_avg_query(user: User, filters: dict[str, Any]) -> QueryResult:
    with engine.connect() as conn:
        filters = {**filters, "exam_batch": _resolve_exam_batch(conn, filters)}
        stmt = _aggregate_stmt(user, filters)
        row = _row_dict(conn.execute(stmt).mappings().one())
        count = int(row["count"] or 0)
        pass_count = int(row["pass_count"] or 0)
        fail_count = count - pass_count
        rows = [
            {
                "count": count,
                "avg_score": round(float(row["avg_score"]), 2) if row["avg_score"] is not None else None,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "pass_rate": round(pass_count / count, 4) if count else 0,
                "fail_rate": round(fail_count / count, 4) if count else 0,
            }
        ]
        return QueryResult(rows=rows, chart_config=None, sql=_render_sql(stmt), answer_type="chart")


def run_rate_query(user: User, filters: dict[str, Any], metric: str) -> QueryResult:
    result = run_avg_query(user, filters)
    value = result.rows[0]["pass_rate"] if metric == "pass_rate" else result.rows[0]["fail_rate"]
    return QueryResult(
        rows=[{metric: value}],
        chart_config={
            "type": "gauge",
            "value": round(float(value or 0) * 100, 1),
            "title": "及格率" if metric == "pass_rate" else "挂科率",
        },
        sql=result.sql,
        answer_type="chart",
    )


def run_distribution_query(user: User, filters: dict[str, Any]) -> QueryResult:
    with engine.connect() as conn:
        filters = {**filters, "exam_batch": _resolve_exam_batch(conn, filters)}
        conds = _base_filters(user, filters)
        bucket_expr = case(
            (score_table.c.score < 60, "0-59"),
            (score_table.c.score < 70, "60-69"),
            (score_table.c.score < 80, "70-79"),
            (score_table.c.score < 90, "80-89"),
            else_="90-100",
        )
        stmt = (
            select(bucket_expr.label("bucket"), func.count(score_table.c.id).label("count"))
            .where(and_(*conds))
            .group_by(bucket_expr)
        )
        raw = [_row_dict(r) for r in conn.execute(stmt).mappings().all()]
        order = {"0-59": 0, "60-69": 1, "70-79": 2, "80-89": 3, "90-100": 4}
        raw.sort(key=lambda r: order.get(str(r["bucket"]), 99))
        chart = {
            "type": "bar",
            "title": "分数段分布",
            "x": [r["bucket"] for r in raw],
            "series": [{"name": "人数", "data": [r["count"] for r in raw]}],
        }
        return QueryResult(rows=raw, chart_config=chart, sql=_render_sql(stmt), answer_type="chart")


def run_class_compare_query(user: User, filters: dict[str, Any]) -> QueryResult:
    with engine.connect() as conn:
        filters = {**filters, "exam_batch": _resolve_exam_batch(conn, filters)}
        conds = _base_filters(user, filters)
        stmt = (
            select(
                score_table.c.class_id,
                func.avg(score_table.c.score).label("avg_score"),
                func.count(score_table.c.id).label("count"),
            )
            .where(and_(*conds))
            .group_by(score_table.c.class_id)
        )
        raw = [_row_dict(r) for r in conn.execute(stmt).mappings().all()]
        rows = [
            {
                "class_id": r["class_id"],
                "avg_score": round(float(r["avg_score"]), 2) if r["avg_score"] is not None else None,
                "count": r["count"],
            }
            for r in raw
        ]
        chart = {
            "type": "bar",
            "title": "班级平均分对比",
            "x": [r["class_id"] for r in rows],
            "series": [{"name": "平均分", "data": [r["avg_score"] for r in rows]}],
        }
        return QueryResult(rows=rows, chart_config=chart, sql=_render_sql(stmt), answer_type="chart")


def run_course_compare_query(user: User, filters: dict[str, Any]) -> QueryResult:
    with engine.connect() as conn:
        filters = {**filters, "exam_batch": _resolve_exam_batch(conn, filters)}
        conds = _base_filters(user, filters)
        stmt = (
            select(
                score_table.c.course_name,
                func.avg(score_table.c.score).label("avg_score"),
                func.count(score_table.c.id).label("count"),
            )
            .where(and_(*conds))
            .group_by(score_table.c.course_name)
        )
        raw = [_row_dict(r) for r in conn.execute(stmt).mappings().all()]
        rows = [
            {
                "course_name": r["course_name"],
                "avg_score": round(float(r["avg_score"]), 2) if r["avg_score"] is not None else None,
                "count": r["count"],
            }
            for r in raw
        ]
        chart = {
            "type": "bar",
            "title": "各科平均分对比",
            "x": [r["course_name"] for r in rows],
            "series": [{"name": "平均分", "data": [r["avg_score"] for r in rows]}],
        }
        return QueryResult(rows=rows, chart_config=chart, sql=_render_sql(stmt), answer_type="chart")


def run_metric(user: User, metric: str, filters: dict[str, Any]) -> QueryResult:
    require_metric_permission(user, metric)
    if metric == "score":
        return run_score_query(user, filters)
    if metric == "gpa":
        return run_gpa_query(user, filters)
    if metric == "gpa_rank":
        return run_gpa_rank_query(user, filters)
    if metric == "avg_score":
        return run_avg_query(user, filters)
    if metric in {"pass_rate", "fail_rate"}:
        return run_rate_query(user, filters, metric)
    if metric == "score_distribution":
        return run_distribution_query(user, filters)
    if metric == "class_compare":
        return run_class_compare_query(user, filters)
    if metric == "course_compare":
        return run_course_compare_query(user, filters)
    raise ValueError(f"不支持的指标：{metric}")


def require_metric_permission(user: User, metric: str) -> None:
    if user.role == 1 and metric in {"class_compare"}:
        raise PermissionDeniedError("您没有权限查看")
