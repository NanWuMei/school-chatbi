from __future__ import annotations

import json
import re
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import engine
from .knowledge import knowledge_retriever
from .llm import BaseLLM, LLMError, MockLLM, get_llm
from .models import ConversationLog, StudentScore, User
from .query_engine import PermissionDeniedError, run_metric
from .schemas import ChatResponse


COURSES = {
    "高数": "高等数学",
    "高等数学": "高等数学",
    "数学": "高等数学",
    "英语": "大学英语",
    "大学英语": "大学英语",
    "线代": "线性代数",
    "线性代数": "线性代数",
    "概率": "概率论与数理统计",
    "概率论": "概率论与数理统计",
    "计算机": "计算机基础",
    "计算机基础": "计算机基础",
}


def _valid_exam_batches() -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(select(StudentScore.exam_batch).distinct()).all()
    return {row[0] for row in rows}


def _extract_course(query: str) -> str | None:
    for key, value in COURSES.items():
        if key in query:
            return value
    return None


def _rule_intent(query: str) -> dict[str, Any]:
    lower = query.lower()
    if any(word in lower for word in ["你好", "在吗", "谢谢", "天气", "你是谁", "能做什么"]):
        return {"intent": "chat", "metric": None, "course_name": None, "exam_batch": None}

    course = _extract_course(query)
    metric = None
    if any(word in query for word in ["哪门", "哪个科目", "哪科", "各科", "科目对比", "课程对比", "科目最差"]):
        metric = "course_compare"
    elif any(word in query for word in ["各班", "班级对比", "哪个班", "班平均", "班级平均"]):
        metric = "class_compare"
    elif any(word in query for word in ["挂科", "不及格"]):
        metric = "fail_rate"
    elif any(word in query for word in ["及格率", "通过率"]):
        metric = "pass_rate"
    elif any(word in query for word in ["排名", "排第几", "GPA", "绩点"]):
        metric = "gpa_rank"
    elif any(word in query for word in ["分数段", "分布"]):
        metric = "score_distribution"
    elif any(word in query for word in ["平均分", "均分", "整体成绩", "成绩怎么样", "考得怎么样", "考得咋样", "分析", "情况", "怎么样"]):
        metric = "avg_score"
    elif any(word in query for word in ["多少分", "考了多少", "分数"]):
        metric = "score"

    if metric is None and course:
        metric = "score"
    if metric is None:
        metric = "avg_score"
    return {"intent": "query", "metric": metric, "course_name": course, "exam_batch": None}


def _llm_intent(llm: BaseLLM, query: str, history: list[str]) -> dict[str, Any]:
    if isinstance(llm, MockLLM):
        return _rule_intent(query)
    history_text = "\n".join(history[-3:]) or "无"
    messages = [
        {
            "role": "system",
            "content": (
                "你是学业成绩分析助手的意图识别模块。请只输出 JSON。"
                "JSON 字段：intent(chat|query|analysis|attribution)、metric、course_name、exam_batch。"
                "可用 metric：score,gpa,gpa_rank,avg_score,pass_rate,fail_rate,score_distribution,class_compare,course_compare。"
                "课程名称请使用标准名称；不明确的字段填 null。"
            ),
        },
        {"role": "user", "content": f"历史对话：\n{history_text}\n\n当前问题：{query}"},
    ]
    try:
        data = llm.chat_json(messages)
    except LLMError:
        return _rule_intent(query)
    if not isinstance(data, dict):
        return _rule_intent(query)
    metric = data.get("metric")
    if metric not in {
        "score",
        "gpa",
        "gpa_rank",
        "avg_score",
        "pass_rate",
        "fail_rate",
        "score_distribution",
        "class_compare",
        "course_compare",
    }:
        data["metric"] = _rule_intent(query)["metric"]
    data.setdefault("intent", "query")
    course_name = data.get("course_name") or _extract_course(query)
    if course_name:
        for key, value in COURSES.items():
            if course_name == value or key == course_name:
                course_name = value
                break
    exam_batch = data.get("exam_batch")
    if exam_batch and exam_batch not in _valid_exam_batches():
        exam_batch = None
    data["course_name"] = course_name
    data["exam_batch"] = exam_batch
    explicit_metric = _explicit_metric_override(query)
    if explicit_metric:
        data["metric"] = explicit_metric
    return data


def _needs_clarification(intent: dict[str, Any]) -> bool:
    metric = intent.get("metric")
    if metric in {"score", "gpa", "gpa_rank"} and not intent.get("course_name"):
        return True
    return False


def _explicit_metric_override(query: str) -> str | None:
    if any(word in query for word in ["各科", "科目", "哪门", "哪科", "课程对比"]):
        return "course_compare"
    if any(word in query for word in ["各班", "班级对比", "哪个班", "班平均", "班级平均"]):
        return "class_compare"
    if any(word in query for word in ["挂科", "不及格"]):
        return "fail_rate"
    if any(word in query for word in ["及格率", "通过率"]):
        return "pass_rate"
    if any(word in query for word in ["排名", "排第几", "GPA", "绩点"]):
        return "gpa_rank"
    if any(word in query for word in ["分数段", "分布"]):
        return "score_distribution"
    if any(word in query for word in ["多少分", "考了多少"]):
        return "score"
    return None


def _metric_label(metric: str) -> str:
    return {
        "score": "分数",
        "gpa": "加权绩点",
        "gpa_rank": "加权绩点排名",
        "avg_score": "平均分",
        "pass_rate": "及格率",
        "fail_rate": "挂科率",
        "score_distribution": "分数段分布",
        "class_compare": "班级平均分对比",
        "course_compare": "各科平均分对比",
    }.get(metric, metric)


def _answer_text(llm: BaseLLM, user: User, query: str, metric: str, rows: list[dict[str, Any]]) -> str:
    compact = json.dumps(rows[:12], ensure_ascii=False, default=str)
    try:
        if isinstance(llm, MockLLM):
            raise LLMError("mock mode uses deterministic answer")
        return llm.chat_text(
            [
                {
                    "role": "system",
                    "content": (
                        "你是学业成绩分析助手。请基于数据用简洁中文回答，不得编造数据。"
                        "说明你的数据权限范围，但不要泄露他人个体隐私。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"用户问题：{query}\n指标：{_metric_label(metric)}\n查询结果：{compact}",
                },
            ],
            temperature=0.3,
        )
    except LLMError:
        if not rows:
            return "当前权限范围内没有查询到相关成绩数据。"
        first = rows[0]
        if metric == "fail_rate":
            return f"当前权限范围内挂科率为 {round(float(first.get('fail_rate', 0)) * 100, 1)}%。"
        if metric == "pass_rate":
            return f"当前权限范围内及格率为 {round(float(first.get('pass_rate', 0)) * 100, 1)}%。"
        if metric == "avg_score":
            return f"当前权限范围内平均分为 {first.get('avg_score')} 分，共 {first.get('count')} 条有效成绩。"
        if metric == "score_distribution":
            return "已生成分数段分布，请查看图表。"
        if metric == "class_compare":
            return "已生成班级平均分对比，请查看图表。"
        if metric == "course_compare":
            return "已生成各科平均分对比，请查看图表。"
        if metric == "score":
            if len(rows) == 1:
                return f"该课程成绩为 {rows[0].get('score')} 分。"
            return "已返回查询到的成绩记录。"
        if metric == "gpa":
            return f"加权绩点为 {rows[0].get('gpa')}。"
        if metric == "gpa_rank":
            if rows and rows[0].get("rank"):
                return f"加权绩点排名第 {rows[0].get('rank')} 名，共 {rows[0].get('total')} 人。"
            return "暂未查询到有效绩点排名。"
        return "已返回查询结果。"


def _suggestions(metric: str, course_name: str | None) -> list[dict[str, Any]]:
    base = [
        {"key": "avg_score", "label": "查看平均分"},
        {"key": "score_distribution", "label": "查看分数段分布"},
        {"key": "class_compare", "label": "查看班级对比"},
    ]
    if course_name:
        return [{"key": "fail_rate", "label": f"{course_name}挂科率"}] + base[:2]
    return base


def _store_log(
    db: Session,
    user: User,
    session_id: str,
    query: str,
    rewritten_query: str,
    intent_type: str,
    result: Any,
    answer_type: str,
    text: str,
    suggestions: list[dict[str, Any]],
    response_ms: int,
) -> int:
    response_json = {
        "chart_config": getattr(result, "chart_config", None),
        "data_rows": getattr(result, "rows", []),
        "suggestions": suggestions,
    }
    log = ConversationLog(
        user_id=user.user_id,
        session_id=session_id,
        query=query,
        rewritten_query=rewritten_query or None,
        intent_type=intent_type,
        sql_text=getattr(result, "sql", None),
        sql_success=1 if result is not None else 0,
        result_summary=text,
        answer_type=answer_type,
        response_json=json.dumps(response_json, ensure_ascii=False, default=str),
        response_time_ms=response_ms,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log.id


def handle_chat(
    db: Session,
    user: User,
    session_id: str,
    query: str,
) -> ChatResponse:
    started = time.time()
    llm = get_llm()

    history_rows = db.scalars(
        select(ConversationLog)
        .where(ConversationLog.session_id == session_id)
        .order_by(ConversationLog.created_at.desc())
        .limit(6)
    ).all()
    history = [f"Q:{row.query} A:{row.result_summary}" for row in reversed(history_rows)]

    intent = _llm_intent(llm, query, history)
    rewritten_query = query
    if intent["intent"] == "chat":
        try:
            text = llm.chat_text(
                [
                    {"role": "system", "content": "你是学业成绩分析助手，请友好地引导用户提问成绩相关问题。"},
                    {"role": "user", "content": query},
                ]
            )
        except LLMError:
            text = "我可以帮你查分数、排名、挂科率、平均分，并生成成绩分析图表。试试问：我们班高数平均分是多少？"
        log_id = _store_log(
            db,
            user,
            session_id,
            query,
            rewritten_query,
            "chat",
            None,
            "text",
            text,
            [],
            int((time.time() - started) * 1000),
        )
        return ChatResponse(message_id=log_id, answer_type="text", text=text)

    if _needs_clarification(intent):
        metric = intent["metric"]
        suggestions = [
            {"key": "course", "label": "请先选择课程", "options": sorted(set(COURSES.values()))},
            {"key": "metric", "label": "你可能想查", "options": [
                {"key": metric, "label": _metric_label(metric)},
                {"key": "avg_score", "label": "平均分"},
                {"key": "fail_rate", "label": "挂科率"},
            ]},
        ]
        text = "这个问题还缺少课程信息。你想查询哪门课程？"
        log_id = _store_log(
            db,
            user,
            session_id,
            query,
            rewritten_query,
            "clarify",
            None,
            "clarify",
            text,
            suggestions,
            int((time.time() - started) * 1000),
        )
        return ChatResponse(
            message_id=log_id,
            answer_type="clarify",
            text=text,
            suggestions=suggestions,
        )

    metric = intent["metric"] or "avg_score"
    filters = {
        "course_name": intent.get("course_name"),
        "exam_batch": intent.get("exam_batch"),
    }
    try:
        result = run_metric(user, metric, filters)
        text = _answer_text(llm, user, query, metric, result.rows)
        suggestions = _suggestions(metric, intent.get("course_name"))
        log_id = _store_log(
            db,
            user,
            session_id,
            query,
            rewritten_query,
            intent["intent"],
            result,
            result.answer_type,
            text,
            suggestions,
            int((time.time() - started) * 1000),
        )
        return ChatResponse(
            message_id=log_id,
            answer_type=result.answer_type,
            text=text,
            data_rows=result.rows,
            chart_config=result.chart_config,
            generated_sql=result.sql,
            suggestions=suggestions,
        )
    except PermissionDeniedError:
        text = "您没有权限查看"
        log_id = _store_log(
            db,
            user,
            session_id,
            query,
            rewritten_query,
            intent["intent"],
            None,
            "error",
            text,
            [],
            int((time.time() - started) * 1000),
        )
        return ChatResponse(message_id=log_id, answer_type="error", text=text)
    except Exception as exc:
        text = f"查询失败：{exc}"
        log_id = _store_log(
            db,
            user,
            session_id,
            query,
            rewritten_query,
            intent["intent"],
            None,
            "error",
            text,
            [],
            int((time.time() - started) * 1000),
        )
        return ChatResponse(message_id=log_id, answer_type="error", text=text)
