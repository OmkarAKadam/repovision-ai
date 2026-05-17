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
    instruction="""You are RepoVision AI.

When given a target like "cli/cli" with modules ["bug_triage"]:

1. Call bug_triage_module tool with the repo name "cli/cli"

2. Return the result as JSON: {"bug_triage": <result>}

When given modules ["repo_health"]:

1. Call repo_health_module tool with the repo name

2. Return: {"repo_health": <result>}

When given modules ["pr_review"]:

1. Call pr_reviewer_module tool with the repo name

2. Return: {"pr_review": <result>}

When given all 3 modules:

1. Call the tools one at a time with the repo name. Do not call tools in parallel.

2. Return: {"pr_review": <r1>, "bug_triage": <r2>, "repo_health": <r3>}

Production API note: backend/main.py normally invokes this orchestrator once per
module with a delay between calls to avoid Vertex AI rate limits.

ALWAYS pass the exact repo string as the first argument to each tool.

Output ONLY valid JSON. No explanations."""
)
