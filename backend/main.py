import asyncio
import hashlib
import json
import logging
import os
import re
import time
from typing import Any, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part
from pydantic import BaseModel, Field

from backend.agents.orchestrator import root_agent

# Load environment variables
load_dotenv()

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
os.environ["GOOGLE_CLOUD_PROJECT"] = os.getenv("GOOGLE_CLOUD_PROJECT", "repovision-ai")
os.environ["GOOGLE_CLOUD_LOCATION"] = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")


# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("repovision")

app = FastAPI(title="RepoVision AI API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

runner = InMemoryRunner(agent=root_agent, app_name="repovision")

SUPPORTED_MODULES = {"pr_review", "bug_triage", "repo_health"}
DEFAULT_MODULES = ["pr_review", "bug_triage", "repo_health"]
MODULE_DELAY_SECONDS = 5


# Pydantic models
class AnalyzeRequest(BaseModel):
    target: str
    modules: List[str] = Field(default_factory=lambda: DEFAULT_MODULES.copy())


class AnalyzeResponse(BaseModel):
    session_id: str
    target: str
    pr_review: Optional[Any] = None
    bug_triage: Optional[Any] = None
    repo_health: Optional[Any] = None
    duration_seconds: float
    status: str


def make_session_id(target: str, module_key: Optional[str] = None) -> str:
    """Create a session id that cannot collide with previous InMemoryRunner sessions."""
    raw = f"{target}_{module_key or 'request'}_{time.time_ns()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _extract_balanced_json(text: str) -> Optional[str]:
    """Return the first balanced JSON object or array embedded in text."""
    start = -1
    for idx, char in enumerate(text):
        if char in "{[":
            start = idx
            break

    if start == -1:
        return None

    stack = [text[start]]
    in_string = False
    escaped = False

    for idx in range(start + 1, len(text)):
        char = text[idx]

        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char in "{[":
            stack.append(char)
            continue

        if char in "}]":
            if not stack:
                return None
            expected = "}" if stack[-1] == "{" else "]"
            if char != expected:
                return None
            stack.pop()
            if not stack:
                return text[start:idx + 1]

    return None


def parse_jsonish(value: Any) -> Any:
    """Parse JSON returned directly, inside markdown fences, or inside prose."""
    if isinstance(value, (dict, list)) or value is None:
        return value

    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return text

    candidates = [text]
    if text.startswith("```") and text.endswith("```"):
        candidates.append(text.strip("`").strip())

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            pass

    for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE):
        fenced = match.group(1).strip()
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            balanced = _extract_balanced_json(fenced)
            if balanced:
                try:
                    return json.loads(balanced)
                except json.JSONDecodeError:
                    pass

    balanced = _extract_balanced_json(text)
    if balanced:
        try:
            return json.loads(balanced)
        except json.JSONDecodeError:
            pass

    return value


def parse_agent_text(final_text: str) -> dict:
    """Normalize an agent response into a dictionary without losing raw output."""
    parsed = parse_jsonish(final_text)
    if isinstance(parsed, dict):
        return parsed
    return {"raw_response": final_text}


def unwrap_module_response(data: dict, module_key: str):
    if module_key not in data:
        return None
    val = data[module_key]
    if not isinstance(val, dict):
        return val if val else None
    for wrapper in [f"{module_key}_module_response", "result", "response", "output"]:
        if wrapper in val:
            inner = val[wrapper]
            if not inner:
                continue  # skip empty, try next wrapper
            if isinstance(inner, str):
                import re
                inner = re.sub(r'^```json\s*', '', inner.strip())
                inner = re.sub(r'^```\s*', '', inner)
                inner = re.sub(r'\s*```$', '', inner).strip()
                try:
                    inner = json.loads(inner)
                except Exception:
                    pass
            return inner
    # No wrapper found or all empty — return val itself if it has content
    return val if val else None


async def run_agent_module(target: str, module_key: str, prompt: Optional[str] = None) -> tuple[str, dict]:
    """Run exactly one top-level module in a fresh ADK session."""
    session_id = make_session_id(target, module_key)
    if not prompt:
        prompt = (
            f'Analyze: {target}. Modules: ["{module_key}"]. '
            f"Call only the {module_key} module and return only valid JSON."
        )
    user_message = Content(parts=[Part.from_text(text=prompt)])

    await runner.session_service.create_session(
        app_name="repovision",
        user_id="repovision-user",
        session_id=session_id,
    )

    final_text = ""
    for attempt in range(2):
        try:
            async for event in runner.run_async(
                user_id="repovision-user",
                session_id=session_id,
                new_message=user_message,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            final_text = part.text
            break
        except Exception as exc:
            if "429" in str(exc) and attempt == 0:
                logger.warning("Rate limited while running %s; retrying in 30s", module_key)
                await asyncio.sleep(30)
                session_id = make_session_id(target, f"{module_key}_retry")
                await runner.session_service.create_session(
                    app_name="repovision",
                    user_id="repovision-user",
                    session_id=session_id,
                )
                continue
            raise

    logger.info("%s raw response: %s", module_key, final_text[:500])
    return session_id, parse_agent_text(final_text)


# Endpoints
@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    start_time = time.time()
    session_id = make_session_id(request.target)
    modules = list(dict.fromkeys(request.modules or DEFAULT_MODULES))
    invalid_modules = sorted(set(modules) - SUPPORTED_MODULES)
    if invalid_modules:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported modules: {', '.join(invalid_modules)}",
        )

    logger.info(
        "Starting analysis: target=%s modules=%s session=%s",
        request.target,
        modules,
        session_id,
    )

    try:
        parsed_modules = {}
        module_session_ids = {}

        if len(modules) == 1:
            module_key = modules[0]
            if module_key == "pr_review":
                prompt = f"""Analyze repository {request.target} for PR review.
Use the pr_reviewer_module tool with repo="{request.target}".
If no PR number is given, fetch the most recent open PR using 
get_pr_diff_direct with pr_number=1, or analyze the repository 
structure for code quality issues without a specific PR.
Return JSON with key "pr_review"."""
            elif module_key == "bug_triage":
                prompt = f"""Analyze repository {request.target} for bug triage.
Use the bug_triage_module tool with repo="{request.target}".
Return JSON with key "bug_triage"."""
            elif module_key == "repo_health":
                prompt = f"""Analyze repository {request.target} for health.
Use the repo_health_module tool with repo="{request.target}".
Return JSON with key "repo_health"."""
            else:
                prompt = f"Analyze {request.target} using module {module_key}."

            logger.info("Running single module: %s", module_key)
            module_session_id, parsed = await run_agent_module(request.target, module_key, prompt=prompt)
            logger.info(f"pr_review raw: {parsed.get('pr_review')}")
            module_session_ids[module_key] = module_session_id
            parsed_modules[module_key] = unwrap_module_response(parsed, module_key)
        else:
            modules_str = ", ".join(modules)
            prompt = f"""Analyze {request.target} using these modules in sequence: {modules_str}.
For each module call the corresponding tool with repo="{request.target}".
For pr_review: analyze code quality without needing a specific PR number.
Return combined JSON with keys for each module."""

            logger.info("Running multiple modules in sequence: %s", modules)
            module_session_id, parsed = await run_agent_module(request.target, "orchestrator", prompt=prompt)
            module_session_ids["orchestrator"] = module_session_id
            for m in modules:
                parsed_modules[m] = unwrap_module_response(parsed, m)

        logger.info("Module sessions: %s", module_session_ids)

        duration = time.time() - start_time
        return AnalyzeResponse(
            session_id=session_id,
            target=request.target,
            pr_review=parsed_modules.get("pr_review"),
            bug_triage=parsed_modules.get("bug_triage"),
            repo_health=parsed_modules.get("repo_health"),
            duration_seconds=round(duration, 2),
            status="success",
        )
    except Exception as e:
        logger.error("Failed: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "agents": 13,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
