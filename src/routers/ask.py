from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.dependencies import SettingsDep
from src.routers.search import get_search_client
from src.schemas.api.ask import AskRequest, AskResponse
from src.services.ollama import ModelServiceError, OllamaClient
from src.services.rag import RagService
from src.services.search.client import SearchClient, SearchServiceError

router = APIRouter(tags=["questions"])


def get_generator(settings: SettingsDep):
    return OllamaClient(settings)


@router.post("/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    settings: SettingsDep,
    search: Annotated[SearchClient, Depends(get_search_client)],
    generator: Annotated[OllamaClient, Depends(get_generator)],
) -> AskResponse:
    if request.use_hybrid:
        raise HTTPException(status_code=501, detail="Hybrid retrieval is not implemented; use use_hybrid=false.")
    if request.model is not None and request.model != settings.ollama_model:
        raise HTTPException(status_code=422, detail="Use the configured model or omit model; change RAG_OLLAMA_MODEL in .env to switch.")
    try:
        return RagService(search, generator).answer(request)
    except (SearchServiceError, ModelServiceError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
