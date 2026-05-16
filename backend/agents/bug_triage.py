import sys
import os
from pydantic import BaseModel
from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
from google.adk.tools import exit_loop
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

# 1. Issue Classifier Agent
issue_classifier_agent = LlmAgent(
    name="issue_classifier_agent",
    model="gemini-2.0-flash",
    tools=[McpToolset(connection_params=_mcp_params)],
    instruction="""Use list_open_issues to fetch open issues.
    Classify each by: severity (critical/high/medium/low), type (bug/feature/docs/performance), complexity (easy/medium/hard).
    Focus only on bugs.
    Output ONLY valid JSON:
    {"bugs": [{"number": int, "title": str, "severity": str, "complexity": str, "affected_area": str}]}""",
    output_key="classified_bugs"
)

# 2. Fix Generator Agent
fix_generator_agent = LlmAgent(
    name="fix_generator_agent",
    model="gemini-2.0-flash",
    tools=[McpToolset(connection_params=_mcp_params)],
    instruction="""Read classified_bugs from session state. Take the first critical or high severity bug.
    Use get_file_content and get_repo_context to understand the codebase.
    Write a concrete code fix.
    Output ONLY valid JSON:
    {"issue_number": int, "filename": str, "original_snippet": str, "fixed_snippet": str, "explanation": str, "confidence": int}""",
    output_key="proposed_fix"
)

# 3. Test Writer Agent
test_writer_agent = LlmAgent(
    name="test_writer_agent",
    model="gemini-2.0-flash",
    tools=[McpToolset(connection_params=_mcp_params)],
    instruction="""Read proposed_fix from session state.
    Use get_file_content to check existing test patterns.
    Write a unit test that catches this bug if it regresses.
    Output ONLY valid JSON:
    {"test_filename": str, "test_function_name": str, "test_code": str, "what_it_tests": str}""",
    output_key="proposed_test"
)

# 4. Judge Agent (Loop Controller)
judge_agent = LlmAgent(
    name="judge_agent",
    model="gemini-2.0-flash",
    tools=[exit_loop],
    instruction="""Read proposed_fix and proposed_test from session state.
    Evaluate strictly: Does the fix address the root cause? Is the test meaningful?
    If the fix is correct and complete: call the exit_loop tool to stop the loop.
    If not: output feedback explaining what needs to change.
    Output ONLY valid JSON (no markdown fences):
    {"approved": true|false, "reason": str, "iteration": int}""",
    output_key="judge_verdict"
)

# 5. PR Drafter Agent
pr_drafter_agent = LlmAgent(
    name="pr_drafter_agent",
    model="gemini-2.0-flash",
    tools=[McpToolset(connection_params=_mcp_params)],
    instruction="""Read proposed_fix, proposed_test, and judge_verdict from session state.
    Use create_pull_request tool to open a PR.
    PR title format: 'fix: [issue title] (#[issue_number])'
    PR body: problem summary, root cause, fix approach, test added.
    Output the PR URL.""",
    output_key="pr_result"
)

# Loop Agent setup
fix_loop = LoopAgent(
    name="fix_loop",
    sub_agents=[fix_generator_agent, test_writer_agent, judge_agent],
    max_iterations=3
)

# Full Sequential Module
bug_triage_module = SequentialAgent(
    name="bug_triage_module",
    sub_agents=[issue_classifier_agent, fix_loop, pr_drafter_agent],
    description="Classifies bugs, auto-fixes with test-judge loop, opens PRs"
)
