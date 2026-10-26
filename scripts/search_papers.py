"""Search from the terminal without starting the FastAPI server."""
import argparse

from pydantic import ValidationError

from src.schemas.api.search import SearchRequest
from src.services.search.client import SearchClient, SearchServiceError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--category", action="append", default=[])
    args = parser.parse_args()
    try:
        request = SearchRequest(query=args.query, top_k=args.top_k, categories=args.category)
        with SearchClient() as client:
            result = client.search(request)
        print(result.model_dump_json(indent=2))
        return 0
    except SearchServiceError as exc:
        print(f"FAIL: {exc}")
        return 1
    except ValidationError:
        print("FAIL: use a nonblank query, top-k from 1 to 20, and valid settings.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
