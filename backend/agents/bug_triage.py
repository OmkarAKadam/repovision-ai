import httpx
import os
from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.tools import FunctionTool, exit_loop

def list_open_issues_direct(repo: str) -> list:
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    resp = httpx.get(f"https://api.github.com/repos/{repo}/issues?state=open", 
                     headers=headers, timeout=30)
    return [{"number": i["number"], "title": i["title"]} for i in resp.json()] if resp.status_code == 200 else []

def get_file_content_direct(repo: str, path: str) -> dict:
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    resp = httpx.get(f"https://api.github.com/repos/{repo}/contents/{path}",
                     headers=headers, timeout=30)
    if resp.status_code == 200:
        import base64
        return {"content": base64.b64decode(resp.json()["content"]).decode("utf-8", errors="ignore")}
    return {"error": "Failed"}

def create_pull_request_direct(repo: str, title: str, body: str) -> dict:
    # Simplified placeholder for PR creation
    return {"pr_url": f"https://github.com/{repo}/pulls/999"}

# 1. Issue Classifier Agent
issue_classifier_agent = LlmAgent(
    name="issue_classifier_agent",
    model="gemini-2.5-flash",
    tools=[FunctionTool(list_open_issues_direct)],
    instruction="""Fetch issues. Focus on bugs. Output JSON:
    {"bugs": [{"number": int, "title": str, "severity": "high", "complexity": "medium", "affected_area": "core"}]}""",
    output_key="classified_bugs"
)

# 2. Fix Generator Agent
fix_generator_agent = LlmAgent(
    name="fix_generator_agent",
    model="gemini-2.5-flash",
    tools=[FunctionTool(get_file_content_direct)],
    instruction="""Write code fix. Output JSON:
    {"issue_number": int, "filename": str, "fixed_snippet": str, "explanation": str}""",
    output_key="proposed_fix"
)

# 3. Test Writer Agent
test_writer_agent = LlmAgent(
    name="test_writer_agent",
    model="gemini-2.5-flash",
    tools=[FunctionTool(get_file_content_direct)],
    instruction="""Write unit test. Output JSON:
    {"test_filename": str, "test_code": str}""",
    output_key="proposed_test"
)

# 4. Judge Agent
judge_agent = LlmAgent(
    name="judge_agent",
    model="gemini-2.5-flash",
    tools=[exit_loop],
    instruction="""Evaluate fix/test. If correct call exit_loop. Output JSON:
    {"approved": bool, "reason": str}""",
    output_key="judge_verdict"
)

# 5. PR Drafter Agent
pr_drafter_agent = LlmAgent(
    name="pr_drafter_agent",
    model="gemini-2.5-flash",
    tools=[FunctionTool(create_pull_request_direct)],
    instruction="""Create PR. Output JSON: {"pr_url": str}""",
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
