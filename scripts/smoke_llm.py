"""One real request: verifies connectivity and generation, not RAG quality."""
import time
from pydantic import ValidationError
from src.config import Settings
from src.services.ollama import ModelServiceError, OllamaClient


def main() -> int:
    try:
        settings = Settings()
        print(f"Requesting a short answer from {settings.ollama_model} ...", flush=True)
        start = time.perf_counter()
        answer = OllamaClient(settings).generate(
            "In one short sentence, explain what retrieval-augmented generation means."
        )
    except (ValidationError, ModelServiceError) as exc:
        print("FAIL: invalid settings." if isinstance(exc, ValidationError) else f"FAIL: {exc}")
        return 1
    print(f"Answer: {answer}")
    print(f"Elapsed: {time.perf_counter() - start:.2f} seconds")
    print("PASS: received a nonempty completed model response.")
    print("This checks inference only. Document retrieval begins later in the roadmap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
