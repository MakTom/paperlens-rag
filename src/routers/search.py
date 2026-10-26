from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.schemas.api.search import SearchRequest, SearchResponse
from src.services.search.client import SearchClient, SearchServiceError

router = APIRouter(tags=["search"])


def get_search_client():
    with SearchClient() as client:
        yield client


@router.post("/search", response_model=SearchResponse)
def search_papers(
    request: SearchRequest,
    client: Annotated[SearchClient, Depends(get_search_client)],
) -> SearchResponse:
    """Return ranked source records. No model generation is performed."""
    try:
        return client.search(request)
    except SearchServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
