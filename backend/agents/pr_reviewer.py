import httpx
import os
import base64
from pydantic import BaseModel
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools import FunctionTool

def get_pr_diff_direct(repo: str, pr_number: int) -> dict:
    """Fetch PR diff directly."""
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    resp = httpx.get(f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
                     headers={**headers, "Accept": "application/vnd.github.v3.diff"}, timeout=30)
    return {"diff": resp.text[:2000]} if resp.status_code == 200 else {"error": "Failed"}

def get_repo_context_direct(repo: str) -> dict:
    """Fetch repo file structure."""
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    resp = httpx.get(f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1",
                     headers=headers, timeout=30)
    if resp.status_code != 200:
        resp = httpx.get(f"https://api.github.com/repos/{repo}/git/trees/master?recursive=1",
                         headers=headers, timeout=30)
    return {"files": [f['path'] for f in resp.json().get('tree', [])[:100]]} if resp.status_code == 200 else {"error": "Failed"}

# 1. Code Quality Agent
code_quality_agent = LlmAgent(
    name="code_quality_agent",
    model="gemini-2.5-flash",
    tools=[FunctionTool(get_pr_diff_direct), FunctionTool(get_repo_context_direct)],
    instruction="""Use get_pr_diff_direct and get_repo_context_direct.
    Identify: logic bugs, code smells, DRY/SOLID violations, performance issues.
    Cite exact filenames.
    Output JSON (no markdown):
    {"issues": [{"file": str, "severity": "major", "description": str, "suggestion": str}], "overall_score": float}""",
    output_key="code_quality_output"
)

# 2. Security Agent
security_agent = LlmAgent(
    name="security_agent",
    model="gemini-2.5-flash",
    tools=[FunctionTool(get_pr_diff_direct)],
    instruction="""Use get_pr_diff_direct.
    Scan for: hardcoded secrets, SQL injection, XSS, insecure dependencies.
    Output JSON (no markdown):
    {"vulnerabilities": [{"file": str, "type": str, "severity": "high", "description": str, "fix": str}], "security_score": float}""",
    output_key="security_output"
)

# 3. Test Coverage Agent
test_coverage_agent = LlmAgent(
    name="test_coverage_agent",
    model="gemini-2.5-flash",
    tools=[FunctionTool(get_pr_diff_direct), FunctionTool(get_repo_context_direct)],
    instruction="""Use get_pr_diff_direct and get_repo_context_direct.
    Identify: untested functions, missing edge case tests.
    Output JSON (no markdown):
    {"untested_functions": [str], "missing_test_cases": [str], "coverage_score": float}""",
    output_key="test_coverage_output"
)

# 4. Changelog Agent
changelog_agent = LlmAgent(
    name="changelog_agent",
    model="gemini-2.5-flash",
    tools=[FunctionTool(get_pr_diff_direct)],
    instruction="""Use get_pr_diff_direct.
    Write a professional changelog entry. Format: H3 heading with PR title, bullets grouped.
    Output plain markdown string only.""",
    output_key="changelog_output"
)

# Parallel Agent setup
pr_review_parallel = ParallelAgent(
    name="pr_review_parallel",
    sub_agents=[code_quality_agent, security_agent, test_coverage_agent, changelog_agent],
    description="Runs all 4 PR review checks simultaneously"
)

# 5. Aggregator Agent
pr_aggregator = LlmAgent(
    name="pr_aggregator",
    model="gemini-2.5-flash",
    instruction="""Combine outputs into JSON (no markdown fences):
    {
      "pr_summary": str,
      "overall_score": float,
      "verdict": "APPROVE" | "REQUEST_CHANGES",
      "critical_issues": [top 3],
      "changelog": "markdown string"
    }""",
    output_key="pr_review_final"
)

# Sequential Module wrap
pr_reviewer_module = SequentialAgent(
    name="pr_reviewer_module",
    sub_agents=[pr_review_parallel, pr_aggregator],
    description="Full PR review: 4 parallel checks then aggregation"
)
