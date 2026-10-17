# Research Paper RAG — Day 1
A 28-day incremental learning project. Today's milestone is configuration and a real model connection. There is no document retrieval yet.

## Today's three-hour budget
- 20 minutes: understand the files and inspect Mac hardware.
- 40 minutes: install/sync the Python project.
- 50 minutes: start Ollama, download a small model and run a real request.
- 30 minutes: inspect code, try invalid configuration and resolve setup errors.
- 40 minutes: record results, review the Git diff, commit and push.
Downloads may take longer on a slow connection. Record a blocker honestly rather than claiming the model test passed.

## What the code does
| File | Responsibility | Why it exists |
|---|---|---|
| pyproject.toml | Python version and two direct dependencies | Small, explicit environment |
| uv.lock | Exact dependency resolution | Repeatable installation |
| .python-version | Python 3.12 selection | Avoids using a different base/Conda interpreter |
| .env.example | Shareable configuration template | Gives another developer the required settings |
| .gitignore | Excludes local environment, data and weights | Keeps the repository focused on source |
| src/config.py | Validated Settings object | Rejects bad URLs, blank model names and invalid timeouts early |
| src/services/ollama.py | HTTP adapter to Ollama | Keeps model-specific request handling outside scripts and the future API |
| scripts/check_config.py | Offline validation | Separates configuration problems from service failures |
| scripts/doctor.py | OS, CPU, RAM, tools and model-list checks | Provides actionable compatibility evidence |
| scripts/smoke_llm.py | One real model request | Proves that Python can receive a model answer |
| docs/daily-log.md | Actual progress and blockers | Preserves context for the next day's work |
| docs/decisions.md | Reasons for design choices | Supports interview explanations |
| ATTRIBUTION.md | Course reference and reuse policy | Makes project provenance clear |

## 1. Inspect your Mac
Run in Terminal:
```bash
uname -m
sw_vers
system_profiler SPHardwareDataType | egrep 'Chip|Processor Name|Memory'
uv --version
git --version
ollama --version
```
arm64 normally indicates an Apple Silicon process. x86_64 can mean Intel hardware or an Apple Silicon process under Rosetta; compare with the Chip/Processor output. Do not install an ARM interpreter onto an Intel Mac.

Current native Ollama documentation lists macOS 14+; Apple M chips support CPU/GPU, Intel is CPU-only. If your OS cannot run the current app, do the Python steps and send the diagnostic output before choosing a different inference setup. This package does not implement a hosted-provider fallback yet.

If uv is missing and Homebrew is already installed:
```bash
brew install uv
```
Otherwise use the official installation instructions: https://docs.astral.sh/uv/getting-started/installation/
If git is missing, run `xcode-select --install` and follow macOS prompts.

## 2. Extract the project
Extract RAG_Day1_Starter.zip with Finder. It contains a research-paper-rag folder, including hidden configuration files. Move that entire folder to your preferred development directory.

Open Terminal and change to that folder. For example, if you moved it into ~/Projects:
```bash
cd ~/Projects/research-paper-rag
uv python install 3.12
uv sync --locked
cp -n .env.example .env
uv run --locked python -m scripts.check_config
```
The example path must match where you placed the folder. Always run the module commands from the project root.

Expected:
```text
PASS: configuration loaded for research-paper-rag
Model: llama3.2:1b
Request timeout: 180 seconds
```
uv creates .venv; you do not need to activate it when using uv run. Keep this folder separate from your old course repository and its lockfile. The supplied lockfile was resolved and installed in Python 3.12 on Linux; your Mac installation remains an acceptance check.

## 3. Start Ollama and install the test model
If you already have a working Ollama server, reuse it. Do not start another process on the same port.
For a new supported Mac installation, download the app from https://ollama.com/download/mac and launch it.

If installed as an application:
```bash
open -a Ollama
```
If using only the CLI, run `ollama serve` in a separate Terminal window and leave it running.

Then, in your project Terminal:
```bash
ollama list
ollama pull llama3.2:1b
```
The 1B model is a small connectivity baseline. Its successful response does not establish the answer quality needed for the eventual RAG system. You can use an existing installed model by changing RAG_OLLAMA_MODEL in .env; the model name must match the server.

If a Docker Ollama server is already running with port 11434 exposed, it can serve this smoke check. For Apple Silicon acceleration, prefer a supported native Ollama installation; decide on migration only after recording your existing setup.

## 4. Run the checks
```bash
uv run --locked python -m scripts.doctor
uv run --locked python -m scripts.smoke_llm
```
Doctor exits with an error if the server/model is unavailable. Docker can be absent today: it is reported for planning but is not a Day 1 requirement.

The generation script prints the model's actual answer and elapsed time, followed by:
```text
PASS: received a nonempty completed model response.
```
The answer text and timing will vary. The first request can be slower because the model has to load.

Code flow: smoke_llm loads Settings, creates OllamaClient, sends a bounded POST to /api/generate, checks HTTP status and completed response, then prints the answer. stream=false requests one complete JSON response. HTTP environment proxy settings are intentionally ignored for direct access to your configured Ollama server.

## 5. Read and experiment
Read src/config.py, src/services/ollama.py, then scripts/smoke_llm.py.
Try a temporary bad timeout:
```bash
RAG_REQUEST_TIMEOUT_SECONDS=-1 uv run --locked python -m scripts.check_config
```
This should fail with an actionable validation message. The command-scoped variable does not edit .env. Re-run the normal command afterward.

Explain these ideas in your own words:
1. Why .env and .env.example have different Git treatment.
2. What uv.lock adds beyond dependency ranges.
3. Why the HTTP adapter is separate from the smoke script.
4. Why a model response alone is not RAG.
5. Why a timeout and a missing model need different troubleshooting steps.

## 6. Update the log and push
Fill docs/daily-log.md with actual Mac output, model name, generation time and blockers. Only mark Day 1 complete when all acceptance checks pass.

For a new project folder that is not already a Git repository:
```bash
git init -b main
git status --short
git add .gitignore .python-version .env.example pyproject.toml uv.lock README.md ATTRIBUTION.md src scripts docs
git diff --cached --stat
git diff --cached
git commit -m "chore: bootstrap project and verify Mac runtime"
```
Review the staged diff before the commit. .env and .venv must not be staged. If Git asks for author identity, configure your own name and email; a GitHub private noreply address is also an option.

Create an empty GitHub repository with no initial README/license/gitignore. Replace YOUR_USERNAME below with your username:
```bash
git remote add origin https://github.com/YOUR_USERNAME/research-paper-rag.git
git push -u origin main
```
Use GitHub's supported authentication flow. Never put a token into committed files or the remote URL. If your folder already has an origin, inspect `git remote -v` and reuse the intended remote rather than adding it again. Do not force-push over an existing repository.

## Acceptance checklist
- [ ] uv sync --locked succeeds on my Mac.
- [ ] Configuration check passes.
- [ ] Doctor finds the configured server and model.
- [ ] Smoke command receives a real nonempty completed answer.
- [ ] I understand the three primary Python files.
- [ ] Daily log contains actual results.
- [ ] GitHub shows the intended source, with no .env/weights/virtual environment.

## Troubleshooting
| Symptom | Action |
|---|---|
| uv not found | Install uv and reopen Terminal |
| Can't find module scripts | cd into the folder containing pyproject.toml |
| Server unreachable | Launch Ollama; verify .env server URL and port |
| Model not found | Run ollama list, pull the configured model, or edit .env |
| Timeout | Try the 1B model; close memory-heavy apps; increase timeout up to 600 seconds if needed |
| Address already in use | Reuse the running server; do not start another |
| Native app unsupported | Send OS/CPU output; record the blocker; select a compatible remote/hosted route next |
| Docker unavailable | No action needed for Day 1 |
| GitHub push rejected | Share the error with secrets removed; do not force-push |

## Verification performed before delivery
Dependency installation and offline config validation were exercised in Python 3.12 on Linux. HTTP response and failure paths were checked with mocked HTTP responses; they do not count as real model inference. Actual Mac execution and Ollama generation must be verified by you.

## Next day
Day 2 wraps this foundation with FastAPI health endpoints, request/response schemas and offline CI. The same repository continues forward.

## References
- uv installation: https://docs.astral.sh/uv/getting-started/installation/
- Ollama Mac requirements: https://docs.ollama.com/macos
- Generate API: https://docs.ollama.com/api/generate
- Small model: https://ollama.com/library/llama3.2:1b

