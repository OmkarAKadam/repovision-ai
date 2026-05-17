from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool
from backend.agents.pr_reviewer import pr_reviewer_module
from backend.agents.bug_triage import bug_triage_module
from backend.agents.repo_health import repo_health_module

# Wrap each module as an AgentTool for the Orchestrator
pr_tool = AgentTool(agent=pr_reviewer_module)
bug_tool = AgentTool(agent=bug_triage_module)
health_tool = AgentTool(agent=repo_health_module)

# Root Orchestrator Agent
root_agent = LlmAgent(
    name="repovision_orchestrator",
    model="gemini-2.5-flash",
    tools=[pr_tool, bug_tool, health_tool],
    instruction="""You are RepoVision AI — a GitHub intelligence platform with meta-vision over any codebase.

    For all tools, you MUST pass the repository name in the format 'owner/repo' as the 'repo' argument.

    When given a GitHub repo (format: owner/repo):
    - Run all 3 tools: pr_reviewer_module, bug_triage_module, repo_health_module (pass repo)
    - Wait for all to complete, return unified JSON with keys: "pr_review", "bug_triage", "repo_health"

    When given a PR URL (format: owner/repo/pull/N):
    - Run ONLY pr_reviewer_module (pass repo and pr_number)

    Always confirm what you are analyzing before starting.
    If the repo does not exist or is private, say so clearly.
    Never fabricate data — all analysis must come from tool outputs only."""
)
