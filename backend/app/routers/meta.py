from fastapi import APIRouter, Depends

from ..deps import get_current_user
from ..knowledge import knowledge_retriever
from ..pipeline import COURSES


router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/indicators")
def indicators(user=Depends(get_current_user)) -> dict:
    return {
        "indicators": knowledge_retriever.indicator_options(),
        "courses": [{"key": v, "label": v} for v in sorted(set(COURSES.values()))],
    }

