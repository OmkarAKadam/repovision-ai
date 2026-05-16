import sys
import os
from pydantic import BaseModel
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

# MCP connection setup
_server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp_server.py"))
_mcp_params = StdioConnectionParams(
    server_params=StdioServerParameters(
        command=sys.executable,
        args=[_server_path],
        env=os.environ.copy()
    )
)

# 1. Docs Auditor Agent
docs_auditor_agent = LlmAgent(
    name="docs_auditor_agent",
    model="gemini-2.0-flash",
    tools=[McpToolset(connection_params=_mcp_params)],
    instruction="""Use get_file_content and get_repo_context tools.
    Audit documentation: README quality (install instructions, usage examples, badges),
    presence of CONTRIBUTING.md, CHANGELOG.md, LICENSE, code comment density.
    Output ONLY valid JSON:
    {"docs_score": float, "findings": [str], "missing": [str]}""",
    output_key="docs_report"
)

# 2. Dependency Scanner Agent
dependency_scanner_agent = LlmAgent(
    name="dependency_scanner_agent",
    model="gemini-2.0-flash",
    tools=[McpToolset(connection_params=_mcp_params)],
    instruction="""Use get_dependency_manifest and get_repo_stats tools.
    Flag: outdated major versions, deprecated packages, large dependency trees, missing lockfiles.
    Output ONLY valid JSON:
    {"dep_score": float, "outdated": [str], "risks": [str], "total_deps": int}""",
    output_key="deps_report"
)

# 3. Contributor Health Agent
contributor_health_agent = LlmAgent(
    name="contributor_health_agent",
    model="gemini-2.0-flash",
    tools=[McpToolset(connection_params=_mcp_params)],
    instruction="""Use get_contributors and get_repo_stats tools.
    Evaluate: bus factor (contributors with >50% commits), contribution distribution, activity.
    Output ONLY valid JSON:
    {"contributor_score": float, "bus_factor": int, "active_contributors": int, "risk_level": "low"|"medium"|"high", "findings": [str]}""",
    output_key="contributors_report"
)

# 4. Activity Agent
activity_agent = LlmAgent(
    name="activity_agent",
    model="gemini-2.0-flash",
    tools=[McpToolset(connection_params=_mcp_params)],
    instruction="""Use get_repo_stats tool.
    Assess: star count, open issues trend, last push date, whether maintained or abandoned.
    Output ONLY valid JSON:
    {"activity_score": float, "status": "active"|"maintained"|"slow"|"abandoned", "findings": [str]}""",
    output_key="activity_report"
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
    model="gemini-2.0-flash",
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
