from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_current_user
from ..models import User
from ..query_engine import PermissionDeniedError
from ..schemas import SkillRunRequest, SkillRunResponse
from ..skills import (
    run_class_compare,
    run_course_deep,
    run_group_diff,
    run_overall_distribution,
    run_risk_warning,
    run_trend_compare,
)


router = APIRouter(prefix="/skills", tags=["skills"])


@router.post("/run", response_model=SkillRunResponse)
def run_skill(payload: SkillRunRequest, user: User = Depends(get_current_user)) -> SkillRunResponse:
    try:
        if payload.skill == "overall_distribution":
            result = run_overall_distribution(user, payload.exam_batch, payload.course_name)
        elif payload.skill == "risk_warning":
            result = run_risk_warning(user, payload.exam_batch, payload.course_name)
        elif payload.skill == "class_compare":
            result = run_class_compare(user, payload.exam_batch, payload.course_name)
        elif payload.skill == "course_deep":
            result = run_course_deep(user, payload.exam_batch, payload.course_name)
        elif payload.skill == "trend_compare":
            result = run_trend_compare(user, payload.exam_batch, payload.course_name)
        elif payload.skill == "group_diff":
            result = run_group_diff(user, payload.exam_batch, payload.course_name)
        else:
            raise HTTPException(status_code=400, detail="不支持的 Skill")

        if result.answer_type == "report":
            text = "已生成分析报告，请查看图表与数据。"
        else:
            text = "已生成查询结果。"
        return SkillRunResponse(
            answer_type=result.answer_type,
            text=text,
            data_rows=result.rows,
            chart_config=result.chart_config,
            generated_sql=result.sql,
        )
    except PermissionDeniedError:
        return SkillRunResponse(answer_type="error", text="您没有权限查看")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
