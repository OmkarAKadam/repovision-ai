import logging
import time
import hashlib
import os
import asyncio
import json
import re
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part
from backend.agents.orchestrator import root_agent

# Load environment variables
load_dotenv()

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
os.environ["GOOGLE_CLOUD_PROJECT"] = os.getenv("GOOGLE_CLOUD_PROJECT", "repovision-ai")
os.environ["GOOGLE_CLOUD_LOCATION"] = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")


# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s"
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

# Pydantic models
class AnalyzeRequest(BaseModel):
    target: str
    modules: List[str] = ["pr_review", "bug_triage", "repo_health"]

class AnalyzeResponse(BaseModel):
    session_id: str
    target: str
    pr_review: Optional[dict] = None
    bug_triage: Optional[dict] = None
    repo_health: Optional[dict] = None
    duration_seconds: float
    status: str

# Endpoints
@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    start_time = time.time()
    session_id = hashlib.md5(request.target.encode()).hexdigest()[:8]
    logger.info(f"Starting analysis: {request.target}")

    try:
        user_message = Content(
            parts=[Part.from_text(text=f"Analyze: {request.target}. Modules: {', '.join(request.modules)}")]
        )

        # Create session for this request
        try:
            await runner.session_service.create_session(
                app_name="repovision",
                user_id="repovision-user",
                session_id=session_id
            )
        except Exception:
            logger.info(f"Session {session_id} already exists, proceeding.")

        final_text = ""
        async for event in runner.run_async(
            user_id="repovision-user",
            session_id=session_id,
            new_message=user_message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        final_text = part.text

        logger.info(f"Final text: {final_text[:500]}")

        # Try to parse as JSON
        import re

        clean = final_text.strip()

        # Strategy 1: Extract content between ```json and ``` fences
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', clean, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
            except Exception:
                parsed = {}
        else:
            # Strategy 2: Find any JSON object in the text
            obj_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', clean, re.DOTALL)
            if obj_match:
                try:
                    parsed = json.loads(obj_match.group())
                except Exception:
                    parsed = {}
            else:
                parsed = {}

        # Strategy 3: If parsed is empty, try the whole text as JSON
        if not parsed:
            try:
                parsed = json.loads(clean)
            except Exception:
                parsed = {"raw_response": final_text}

        logger.info(f"Parsed keys: {list(parsed.keys())}")

        duration = time.time() - start_time
        return AnalyzeResponse(
            session_id=session_id,
            target=request.target,
            pr_review=parsed.get("pr_review") or parsed.get("pr_review_final") or (parsed if parsed.get("verdict") else None),
            bug_triage=parsed.get("bug_triage") or parsed.get("pr_result") or (parsed if parsed.get("bugs") else None),
            repo_health=parsed.get("repo_health") or parsed.get("health_final") or (parsed if parsed.get("overall_health_score") else None),
            duration_seconds=round(duration, 2),
            status="success"
        )
    except Exception as e:
        logger.error(f"Failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "agents": 13
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
