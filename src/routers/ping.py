from fastapi import APIRouter

from src.dependencies import SettingsDep
from src.schemas.api.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: SettingsDep) -> HealthResponse:
    """Liveness only: does not test Ollama, retrieval or databases."""
    return HealthResponse(app_name=settings.app_name, version="0.7.0")
