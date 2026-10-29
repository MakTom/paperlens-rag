"""Read-only API version and request-validation check; no model request."""
import httpx


def main():
    try:
        with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10, trust_env=False) as client:
            response = client.get("/api/v1/health")
            response.raise_for_status()
            data = response.json()
            if data.get("version") != "0.7.0" or data.get("status") != "ok":
                print("FAIL: restart the API from the Day 7 checkout; expected version 0.7.0.")
                return 1
            invalid = client.post("/api/v1/ask", json={"query": " "})
            if invalid.status_code != 422:
                print("FAIL: blank question must return HTTP 422.")
                return 1
    except (httpx.HTTPError, ValueError, AttributeError):
        print("FAIL: start make serve on 127.0.0.1:8000 and inspect its logs.")
        return 1
    print("PASS: Day 7 API liveness/version and request validation. Live generation checked separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
