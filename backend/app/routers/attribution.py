from fastapi import APIRouter, Depends

from ..attribution import run_attribution
from ..deps import get_current_user
from ..models import User
from ..schemas import AttributionRequest, AttributionResponse


router = APIRouter(prefix="/attribution", tags=["attribution"])


@router.post("", response_model=AttributionResponse)
def create_attribution(
    payload: AttributionRequest,
    user: User = Depends(get_current_user),
) -> AttributionResponse:
    result = run_attribution(user, payload.course_name, payload.exam_batch)
    return AttributionResponse(**result)

