from fastapi import APIRouter, HTTPException

from src.schemas.api.ask import AskRequest, AskResponse

router = APIRouter(tags=["questions"])


@router.post(
    "/ask",
    response_model=AskResponse,
    responses={501: {"description": "RAG pipeline is not implemented yet"}},
)
def ask(request: AskRequest) -> AskResponse:
    """Validate input now. Retrieval and real answers arrive on Day 5."""
    raise HTTPException(
        status_code=501,
        detail="Question contract validated. RAG generation is scheduled for Day 5.",
    )
