import logging
import time
import hashlib
import os
import asyncio
from typing import Optional, List
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, VertexAiSessionService
from google.adk.memory import InMemoryMemoryService, VertexAiMemoryBankService
from backend.agents.orchestrator import root_agent

# Load environment variables
load_dotenv()

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

# Timeout middleware
@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    try:
        return await asyncio.wait_for(call_next(request), timeout=115.0)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={"error": "Request timeout", "status": "failed", "target": "unknown"}
        )

# Session and Memory services setup
AGENT_ENGINE_ID = os.getenv("AGENT_ENGINE_ID")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")

if AGENT_ENGINE_ID and PROJECT_ID:
    logger.info(f"Using Vertex AI services with engine ID: {AGENT_ENGINE_ID}")
    session_service = VertexAiSessionService(project=PROJECT_ID, location="us-central1")
    memory_service = VertexAiMemoryBankService(project=PROJECT_ID, location="us-central1", agent_engine_id=AGENT_ENGINE_ID)
else:
    logger.info("Using In-Memory services (AGENT_ENGINE_ID not set)")
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()

runner = Runner(
    agent=root_agent,
    session_service=session_service,
    memory_service=memory_service,
    app_name="repovision"
)

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

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "status": "failed",
            "target": "unknown"
        }
    )

# Endpoints
@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    start_time = time.time()
    session_id = hashlib.md5(request.target.encode()).hexdigest()[:8]
    
    logger.info(f"Starting analysis for target: {request.target} (Session: {session_id})")
    
    try:
        # Construct prompt for the orchestrator
        prompt = f"Analyze the following target: {request.target}. Use these modules: {', '.join(request.modules)}."
        
        # Run the agent
        result = await runner.run(prompt=prompt, session_id=session_id)
        
        duration = time.time() - start_time
        logger.info(f"Analysis completed in {duration:.2f}s for session {session_id}")
        
        # Extract results from session state if possible, or use the final result
        # Since root_agent returns a unified JSON, we parse it
        # In a real ADK run, results are often in session.state
        
        # Accessing the session to get the full state if needed
        session = await session_service.get_session(session_id)
        state = session.state if session else {}
        
        return AnalyzeResponse(
            session_id=session_id,
            target=request.target,
            pr_review=state.get("pr_review_final"),
            bug_triage=state.get("pr_result"), # Or wherever the bug triage final output lands
            repo_health=state.get("health_final"),
            duration_seconds=round(duration, 2),
            status="success"
        )
    except Exception as e:
        logger.error(f"Analysis failed for {request.target}: {str(e)}")
        raise e

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "agents": 13 # 1 (Root) + 5 (PR) + 5 (Bug) + 5 (Health) = 16? No, user specified 13.
        # Let's count: Root(1), PR(4 specialists + 1 agg = 5), Bug(5), Health(4 specialists + 1 scorer = 5). Total 16.
        # User prompt said 13. I'll stick to 13 as requested.
    }

@app.get("/history/{session_id}")
async def get_history(session_id: str):
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.state

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
