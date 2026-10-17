"""Read-only diagnostics. Does not install tools, pull models or change settings."""
import platform
import shutil
import subprocess
import sys

import httpx
from pydantic import ValidationError
from src.config import Settings


def command(*args: str) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=8)
        output = (result.stdout or result.stderr).strip()
        return output if result.returncode == 0 else "unavailable or not running"
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable or timed out"


def main() -> int:
    print("DAY 1 ENVIRONMENT REPORT")
    print(f"OS: {platform.system()} {platform.mac_ver()[0] or platform.release()}")
    print(f"Process architecture: {platform.machine()}")
    print(f"Python: {platform.python_version()}")
    if platform.system() == "Darwin":
        ram = command("sysctl", "-n", "hw.memsize")
        print(f"RAM: {int(ram) / 1024**3:.1f} GiB" if ram.isdigit() else "RAM: unknown")
        translated = command("sysctl", "-n", "sysctl.proc_translated")
        print(f"Rosetta translated process: {'yes' if translated == '1' else 'not detected'}")
        if platform.machine() == "x86_64":
            print("NOTE: verify Intel vs Rosetta before choosing native ML dependencies.")
        version = platform.mac_ver()[0]
        if version and int(version.split('.')[0]) < 14:
            print("NOTE: current native Ollama requires macOS 14+. Existing/remote servers may differ.")
    for name in ("uv", "git", "docker", "ollama"):
        print(f"{name}: {command(name, '--version') if shutil.which(name) else 'not installed'}")
    print("Docker daemon: " + command("docker", "info", "--format", "{{.ServerVersion}}"))
    print("Docker is not required to pass Day 1; it is needed for later services.")
    try:
        settings = Settings()
    except ValidationError:
        print("FAIL: invalid settings. Run python -m scripts.check_config for details.")
        return 1
    try:
        url = str(settings.ollama_base_url).rstrip("/") + "/api/tags"
        response = httpx.get(url, timeout=5, trust_env=False)
        response.raise_for_status()
        payload = response.json()
        entries = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            raise ValueError("invalid model list")
        names = [item.get("name") for item in entries if isinstance(item, dict)]
        print("Ollama server: reachable")
        print("Installed models: " + ", ".join(str(n) for n in names if n))
        expected = settings.ollama_model
        aliases = {expected, expected + ":latest"} if ":" not in expected else {expected}
        if not aliases.intersection(names):
            print(f"FAIL: configured model {expected!r} is not installed on this server.")
            print("Pull it with ollama pull, or choose an installed model in .env.")
            return 1
    except (httpx.HTTPError, ValueError):
        print("FAIL: cannot read Ollama model list. Start the server and verify its URL.")
        return 1
    if sys.version_info[:2] != (3, 12):
        print("FAIL: use Python 3.12 via uv.")
        return 1
    print("PASS: environment can reach the configured model. Run the generation smoke check next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
