"""Small HTTP adapter; retrieval and prompt construction will be added later."""
import httpx

from src.config import Settings


class ModelServiceError(RuntimeError):
    """A safe, actionable model-service error."""


class OllamaClient:
    def __init__(self, settings: Settings, *, transport=None):
        self.settings = settings
        self.transport = transport

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        if not prompt.strip():
            raise ValueError("Prompt must not be empty.")
        endpoint = str(self.settings.ollama_base_url).rstrip("/") + "/api/generate"
        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.settings.request_timeout_seconds, connect=5),
                transport=self.transport,
                trust_env=False,  # Connect directly to the configured Ollama server.
            ) as client:
                response = client.post(
                    endpoint,
                    json={
                        "model": self.settings.ollama_model,
                        "prompt": prompt,
                        **({"system": system} if system else {}),
                        "stream": False,
                        "options": {"temperature": 0, "num_predict": 256, "num_ctx": 8192},
                    },
                )
                if response.status_code == 404:
                    raise ModelServiceError(
                        "Model or endpoint not found. Check the server URL and run "
                        "'ollama list'; pull the model configured in .env."
                    )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise ModelServiceError(
                "Generation timed out. Try the small configured model, close "
                "memory-heavy apps, or increase RAG_REQUEST_TIMEOUT_SECONDS (max 600)."
            ) from exc
        except httpx.ConnectError as exc:
            raise ModelServiceError(
                "Cannot connect to Ollama. Start the Ollama app (or ollama serve), "
                "then check RAG_OLLAMA_BASE_URL."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ModelServiceError(
                f"Ollama returned HTTP {exc.response.status_code}. Inspect its local logs."
            ) from exc
        except (httpx.RequestError, ValueError) as exc:
            raise ModelServiceError(
                "Ollama returned an invalid response or the request failed."
            ) from exc

        if not isinstance(payload, dict):
            raise ModelServiceError("Expected an Ollama JSON object.")
        if payload.get("done_reason") == "length":
            raise ModelServiceError("Generation reached its output limit; try a narrower question.")
        answer = payload.get("response")
        if payload.get("error") or payload.get("done") is not True:
            raise ModelServiceError("Ollama did not report a completed generation.")
        if not isinstance(answer, str) or not answer.strip():
            raise ModelServiceError("Ollama returned an empty answer.")
        return answer.strip()
