import httpx
import os
import base64
from pydantic import BaseModel
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools import FunctionTool

def get_repo_stats_direct(repo: str) -> dict:
    """Fetch repo stats directly from GitHub API."""
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    resp = httpx.get(f"https://api.github.com/repos/{repo}", 
                     headers=headers, timeout=30)
    if resp.status_code != 200:
        return {"error": f"GitHub API error: {resp.status_code}"}
    d = resp.json()
    return {
        "stars": d.get("stargazers_count", 0),
        "forks": d.get("forks_count", 0),
        "open_issues_count": d.get("open_issues_count", 0),
        "last_push": d.get("pushed_at", ""),
        "license": d.get("license", {}).get("name", "None") if d.get("license") else "None",
        "topics": d.get("topics", []),
        "watchers": d.get("watchers_count", 0),
        "has_wiki": d.get("has_wiki", False),
        "has_discussions": d.get("has_discussions", False),
        "created_at": d.get("created_at", ""),
        "description": d.get("description", "")
    }

def get_contributors_direct(repo: str) -> list:
    """Fetch contributors directly from GitHub API."""
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    resp = httpx.get(f"https://api.github.com/repos/{repo}/contributors?per_page=20",
                     headers=headers, timeout=30)
    if resp.status_code != 200:
        return []
    return [{"login": c["login"], "contributions": c["contributions"]} 
            for c in resp.json()]

def get_dependency_manifest_direct(repo: str) -> dict:
    """Try to fetch dependency manifest from GitHub API."""
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    for filename in ["requirements.txt", "package.json", "go.mod", "Cargo.toml", "pom.xml"]:
        resp = httpx.get(
            f"https://api.github.com/repos/{repo}/contents/{filename}",
            headers=headers, timeout=30)
        if resp.status_code == 200:
            content = base64.b64decode(resp.json().get("content", "")).decode("utf-8", errors="ignore")
            return {"found_file": filename, "content_preview": content[:500]}
    return {"found_file": "none", "content_preview": "No manifest found"}

def get_readme_direct(repo: str) -> dict:
    """Fetch README from GitHub API."""
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    resp = httpx.get(f"https://api.github.com/repos/{repo}/readme",
                     headers=headers, timeout=30)
    if resp.status_code == 200:
        content = base64.b64decode(resp.json().get("content","")).decode("utf-8", errors="ignore")
        return {"readme": content[:1000]}
    return {"readme": "No README found"}

# 1. Docs Auditor Agent
docs_auditor_agent = LlmAgent(
    name="docs_auditor_agent",
    model="gemini-2.5-flash",
    tools=[FunctionTool(get_readme_direct), FunctionTool(get_repo_stats_direct)],
    instruction="""Use get_readme_direct and get_repo_stats_direct tools with the repo name.
    Audit documentation quality. Output JSON only (no markdown):
    {"docs_score": 0-10, "findings": [string], "missing": [string]}"""
)

# 2. Dependency Scanner Agent
dependency_scanner_agent = LlmAgent(
    name="dependency_scanner_agent",
    model="gemini-2.5-flash",
    tools=[FunctionTool(get_dependency_manifest_direct), FunctionTool(get_repo_stats_direct)],
    instruction="""Use get_dependency_manifest_direct and get_repo_stats_direct tools.
    Analyze dependencies. Output JSON only (no markdown):
    {"dep_score": 0-10, "outdated": [string], "risks": [string], "total_deps": int}"""
)

# 3. Contributor Health Agent
contributor_health_agent = LlmAgent(
    name="contributor_health_agent",
    model="gemini-2.5-flash",
    tools=[FunctionTool(get_contributors_direct), FunctionTool(get_repo_stats_direct)],
    instruction="""Use get_contributors_direct and get_repo_stats_direct tools.
    Analyze contributor health. Output JSON only (no markdown):
    {"contributor_score": 0-10, "bus_factor": int, "active_contributors": int, 
     "risk_level": "low|medium|high", "findings": [string]}"""
)

# 4. Activity Agent
activity_agent = LlmAgent(
    name="activity_agent",
    model="gemini-2.5-flash",
    tools=[FunctionTool(get_repo_stats_direct)],
    instruction="""Use get_repo_stats_direct tool.
    Evaluate repo activity. Output JSON only (no markdown):
    {"activity_score": 0-10, "status": "active|maintained|slow|abandoned", 
     "findings": [string]}"""
)

# Parallel Health Checks
health_parallel = ParallelAgent(
    name="health_parallel",
    sub_agents=[docs_auditor_agent, dependency_scanner_agent, contributor_health_agent, activity_agent],
    description="Runs 4 health checks simultaneously"
)

# 5. Scorer Agent
health_scorer = LlmAgent(
    name="health_scorer",
    model="gemini-2.5-flash",
    instruction="""Read docs_report, deps_report, contributors_report, activity_report from session state.
    Combine into ONE repo health report JSON (no markdown fences):
    {
      "overall_health_score": float (weighted: docs 20%, deps 25%, contributors 30%, activity 25%),
      "grade": "A"|"B"|"C"|"D"|"F",
      "status_label": str,
      "summary": "3 sentences max",
      "scores": {"docs": float, "dependencies": float, "contributors": float, "activity": float},
      "top_strengths": [3 items],
      "top_risks": [3 items],
      "recommendations": [up to 5 actionable items]
    }""",
    output_key="health_final"
)

# Full Sequential Module
repo_health_module = SequentialAgent(
    name="repo_health_module",
    sub_agents=[health_parallel, health_scorer],
    description="4 parallel health checks then scoring"
)
