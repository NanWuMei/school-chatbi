from __future__ import annotations

import json

from sqlalchemy import and_, case, func, select

from .config import settings
from .db import engine
from .llm import get_llm
from .models import StudentScore, User
from .query_engine import _base_filters
from .skills import _ordered_exam_batches


score_table = StudentScore.__table__


def _class_summary(user: User, exam_batch: str, course_name: str | None) -> list[dict]:
    conds = _base_filters(user, {"exam_batch": exam_batch, "course_name": course_name})
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
    with engine.connect() as conn:
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
            }
        )
    return rows


def run_attribution(user: User, course_name: str | None, exam_batch: str | None) -> dict:
    batches = _ordered_exam_batches()
    if len(batches) < 2:
        return {"answer_type": "error", "text": "至少需要两个考试批次才能做归因分析。", "data_rows": []}

    current = exam_batch if exam_batch in batches else batches[-1]
    current_idx = batches.index(current)
    baseline = batches[current_idx - 1] if current_idx > 0 else None
    if baseline is None:
        return {"answer_type": "error", "text": "当前批次没有可对比的上一次考试数据。", "data_rows": []}

    current_rows = _class_summary(user, current, course_name)
    baseline_rows = _class_summary(user, baseline, course_name)
    baseline_map = {r["class_id"]: r for r in baseline_rows}
    comparison_rows = []
    for row in current_rows:
        base = baseline_map.get(row["class_id"], {})
        comparison_rows.append(
            {
                "class_id": row["class_id"],
                "current_avg": row["avg_score"],
                "baseline_avg": base.get("avg_score"),
                "avg_change": round((row["avg_score"] or 0) - (base.get("avg_score") or 0), 2),
                "current_fail_rate": row["fail_rate"],
                "baseline_fail_rate": base.get("fail_rate"),
            }
        )

    prompt = f"""
你是学业成绩归因分析专家。请基于以下数据，分析考试成绩变化的主要原因。
课程：{course_name or "全部课程"}
本次考试：{current}
上次考试：{baseline}
数据：{json.dumps(comparison_rows, ensure_ascii=False)}

要求：
1. 结论先行，再用数据支撑。
2. 只归因到班级、科目，不涉及学生个人因素。
3. 不超过 200 字。
4. 数据不足时明确说明。
"""
    llm = get_llm()
    text = llm.chat_text(
        [
            {"role": "system", "content": "你是专业的学业成绩归因分析助手。"},
            {"role": "user", "content": prompt},
        ],
        model=settings.deepseek_reasoner_model,
        temperature=0.3,
    )
    return {"answer_type": "text", "text": text, "data_rows": comparison_rows}

