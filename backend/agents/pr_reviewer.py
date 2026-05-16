import sys
import os
from typing import Any, Dict, List
from pydantic import BaseModel
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

# Input/Output Models
class PrReviewInput(BaseModel):
    repo: str
    pr_number: int

# MCP connection setup
# Use an absolute path to ensure the subprocess can find the server script
_server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp_server.py"))
_mcp_params = StdioConnectionParams(
    server_params=StdioServerParameters(
        command=sys.executable,
        args=[_server_path],
        env=os.environ.copy()
    )
)

# 1. Code Quality Agent
code_quality_agent = LlmAgent(
    name="code_quality_agent",
    model="gemini-2.0-flash",
    tools=[McpToolset(connection_params=_mcp_params)],
    instruction="""You are a senior code reviewer. Use get_pr_diff and get_repo_context tools to fetch the PR data.
    Identify: logic bugs, code smells, DRY/SOLID violations, performance issues, missing error handling.
    Cite exact filenames and line ranges.
    Output ONLY valid JSON (no markdown fences):
    {"issues": [{"file": str, "line_range": str, "severity": "critical"|"major"|"minor", "description": str, "suggestion": str}], "overall_score": float}""",
    output_key="code_quality_output"
)

# 2. Security Agent
security_agent = LlmAgent(
    name="security_agent",
    model="gemini-2.0-flash",
    tools=[McpToolset(connection_params=_mcp_params)],
    instruction="""You are a security engineer. Use get_pr_diff and get_repo_context tools.
    Scan for: hardcoded secrets, SQL injection, XSS, insecure dependencies, exposed data in logs, missing input validation.
    Output ONLY valid JSON:
    {"vulnerabilities": [{"file": str, "type": str, "severity": "critical"|"high"|"medium"|"low", "description": str, "fix": str}], "security_score": float}""",
    output_key="security_output"
)

# 3. Test Coverage Agent
test_coverage_agent = LlmAgent(
    name="test_coverage_agent",
    model="gemini-2.0-flash",
    tools=[McpToolset(connection_params=_mcp_params)],
    instruction="""You are a QA engineer. Use get_pr_diff and get_repo_context tools.
    Identify: untested functions, missing edge case tests, missing integration tests for API changes.
    Output ONLY valid JSON:
    {"untested_functions": [str], "missing_test_cases": [str], "suggested_test_snippets": [{"description": str, "pseudocode": str}], "coverage_score": float}""",
    output_key="test_coverage_output"
)

# 4. Changelog Agent
changelog_agent = LlmAgent(
    name="changelog_agent",
    model="gemini-2.0-flash",
    tools=[McpToolset(connection_params=_mcp_params)],
    instruction="""You are a technical writer. Use get_pr_diff tool.
    Write a professional changelog entry. Format: H3 heading with PR title, bullets grouped as Added/Changed/Fixed/Removed. Each bullet max 15 words.
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
    model="gemini-2.0-flash",
    instruction="""You receive outputs from 4 parallel review agents in the session state.
    Read: code_quality_output, security_output, test_coverage_output, changelog_output.
    Combine into ONE JSON object (no markdown fences):
    {
      "pr_summary": "2 sentence summary",
      "overall_score": float (avg of code/security/coverage scores),
      "verdict": "APPROVE" | "REQUEST_CHANGES" | "NEEDS_DISCUSSION",
      "critical_issues": [top 3 issues across all agents],
      "code_quality": {"score": float, "issues": []},
      "security": {"score": float, "vulnerabilities": []},
      "test_coverage": {"score": float, "untested_functions": [], "suggestions": []},
      "changelog": "markdown string"
    }
    Rule: verdict=APPROVE only if overall_score >= 7.5""",
    output_key="pr_review_final"
)

# Sequential Module wrap
pr_reviewer_module = SequentialAgent(
    name="pr_reviewer_module",
    sub_agents=[pr_review_parallel, pr_aggregator],
    description="Full PR review: 4 parallel checks then aggregation"
)
