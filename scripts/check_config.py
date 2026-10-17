"""Validate configuration without contacting any service."""
from pydantic import ValidationError
from src.config import Settings


def main() -> int:
    try:
        settings = Settings()
    except ValidationError as exc:
        print("FAIL: configuration is invalid.")
        for error in exc.errors(include_input=False, include_url=False):
            print(f"  {'.'.join(map(str, error['loc']))}: {error['msg']}")
        return 1
    print(f"PASS: configuration loaded for {settings.app_name}")
    print(f"Model: {settings.ollama_model}")
    print(f"Request timeout: {settings.request_timeout_seconds:g} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
