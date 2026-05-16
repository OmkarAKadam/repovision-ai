import os
import base64
import httpx
from typing import Any, Optional, Dict, List
from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import BaseModel

# Load environment variables
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

mcp = FastMCP("RepoVision")

async def _gh(method: str, path: str, **kwargs) -> Any:
    """Helper to make GitHub API calls with httpx and handle errors."""
    url = f"https://api.github.com{path}"
    async with httpx.AsyncClient() as client:
        response = await client.request(method, url, headers=HEADERS, **kwargs)
        response.raise_for_status()
        return response.json()

# TOOL GROUP A — PR Tools

@mcp.tool()
async def get_pr_diff(repo: str, pr_number: int) -> Dict[str, Any]:
    """Fetches PR metadata + full file diffs. repo format: 'owner/repo'"""
    pr_data = await _gh("GET", f"/repos/{repo}/pulls/{pr_number}")
    files_data = await _gh("GET", f"/repos/{repo}/pulls/{pr_number}/files")
    
    files_changed = [
        {
            "filename": f["filename"],
            "patch": f.get("patch", ""),
            "additions": f["additions"],
            "deletions": f["deletions"]
        }
        for f in files_data
    ]
    
    return {
        "title": pr_data["title"],
        "description": pr_data.get("body", ""),
        "author": pr_data["user"]["login"],
        "files_changed": files_changed,
        "base_branch": pr_data["base"]["ref"],
        "head_branch": pr_data["head"]["ref"]
    }

@mcp.tool()
async def get_repo_context(repo: str) -> Dict[str, Any]:
    """Fetches README summary, folder structure, primary language, last 10 commits."""
    repo_data = await _gh("GET", f"/repos/{repo}")
    
    # README (raw content)
    readme_content = ""
    try:
        # Use specific Accept header for raw content
        async with httpx.AsyncClient() as client:
            readme_resp = await client.get(
                f"https://api.github.com/repos/{repo}/readme",
                headers={**HEADERS, "Accept": "application/vnd.github.v3.raw"}
            )
            if readme_resp.status_code == 200:
                readme_content = readme_resp.text[:500]
    except Exception:
        readme_content = "README not found or inaccessible."

    # Root folder listing
    contents = await _gh("GET", f"/repos/{repo}/contents/")
    folder_structure = [item["path"] for item in contents]
    
    # Last 10 commits
    commits_data = await _gh("GET", f"/repos/{repo}/commits?per_page=10")
    recent_commits = [c["commit"]["message"] for c in commits_data]
    
    return {
        "readme_summary": readme_content,
        "folder_structure": folder_structure,
        "primary_language": repo_data.get("language", "Unknown"),
        "recent_commits": recent_commits
    }

@mcp.tool()
async def post_pr_comment(repo: str, pr_number: int, comment: str) -> Dict[str, Any]:
    """Posts a review comment to a GitHub PR."""
    path = f"/repos/{repo}/issues/{pr_number}/comments"
    result = await _gh("POST", path, json={"body": comment})
    return {
        "comment_url": result["html_url"],
        "success": True
    }

# TOOL GROUP B — Bug/Issue Tools

@mcp.tool()
async def list_open_issues(repo: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Fetches open issues (excludes PRs)."""
    issues_data = await _gh("GET", f"/repos/{repo}/issues?state=open&per_page={limit}")
    # Filter out PRs
    issues = [
        {
            "number": i["number"],
            "title": i["title"],
            "body": i.get("body", ""),
            "labels": [label["name"] for label in i.get("labels", [])],
            "created_at": i["created_at"],
            "comments_count": i["comments"]
        }
        for i in issues_data if "pull_request" not in i
    ]
    return issues

@mcp.tool()
async def get_file_content(repo: str, filepath: str) -> str:
    """Fetches raw file content from the default branch. Max 50KB."""
    data = await _gh("GET", f"/repos/{repo}/contents/{filepath}")
    if isinstance(data, list):
        return "[Error: Path is a directory]"
    
    encoded_content = data.get("content", "").replace("\n", "")
    decoded_bytes = base64.b64decode(encoded_content)
    
    max_size = 50 * 1024
    if len(decoded_bytes) > max_size:
        return decoded_bytes[:max_size].decode("utf-8", errors="replace") + "\n[TRUNCATED]"
    
    return decoded_bytes.decode("utf-8", errors="replace")

@mcp.tool()
async def create_pull_request(repo: str, branch: str, title: str, body: str, base: str = "main") -> Dict[str, Any]:
    """Creates a new PR from a branch."""
    data = {
        "title": title,
        "body": body,
        "head": branch,
        "base": base
    }
    result = await _gh("POST", f"/repos/{repo}/pulls", json=data)
    return {
        "pr_url": result["html_url"],
        "pr_number": result["number"]
    }

# TOOL GROUP C — Repo Health Tools

@mcp.tool()
async def get_repo_stats(repo: str) -> Dict[str, Any]:
    """Fetches repo statistics and metadata."""
    data = await _gh("GET", f"/repos/{repo}")
    return {
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "open_issues_count": data["open_issues_count"],
        "last_push": data["pushed_at"],
        "license": data["license"]["name"] if data.get("license") else "None",
        "topics": data.get("topics", []),
        "watchers": data["watchers_count"],
        "has_wiki": data.get("has_wiki", False),
        "has_discussions": data.get("has_discussions", False)
    }

@mcp.tool()
async def get_contributors(repo: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Fetches top contributors."""
    data = await _gh("GET", f"/repos/{repo}/contributors?per_page={limit}")
    return [
        {
            "login": c["login"],
            "contributions": c["contributions"],
            "avatar_url": c["avatar_url"]
        }
        for c in data
    ]

@mcp.tool()
async def get_dependency_manifest(repo: str) -> Dict[str, Any]:
    """Tries to fetch package.json, requirements.txt, go.mod, pom.xml, or Cargo.toml."""
    manifests = {
        "package.json": "npm/nodejs",
        "requirements.txt": "python",
        "go.mod": "go",
        "pom.xml": "java/maven",
        "Cargo.toml": "rust"
    }
    
    for filename, ecosystem in manifests.items():
        try:
            content = await get_file_content(repo, filename)
            if not content.startswith("[Error"):
                # Simplified parsing: for now, just returning the raw content snippet
                # In a real app, we'd use ecosystem-specific parsers
                return {
                    "ecosystem": ecosystem,
                    "dependencies": {"raw_manifest": content[:1000]}, # Simplified for stub
                    "found_file": filename
                }
        except Exception:
            continue
            
    return {"ecosystem": "unknown", "dependencies": {}, "found_file": None}

if __name__ == "__main__":
    mcp.run(transport="stdio")
