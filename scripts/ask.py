"""Ask through the local API; run Uvicorn first."""
import argparse
import json

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    try:
        with httpx.Client(timeout=650, trust_env=False) as client:
            response = client.post("http://127.0.0.1:8000/api/v1/ask",
                                   json={"query": args.query, "top_k": args.top_k})
        print(json.dumps(response.json(), indent=2))
        return 0 if response.is_success else 1
    except (httpx.RequestError, ValueError):
        print("FAIL: check that the API is running on 127.0.0.1:8000 and inspect its logs.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
