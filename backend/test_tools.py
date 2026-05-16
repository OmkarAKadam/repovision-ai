import asyncio
import os
import json
from dotenv import load_dotenv
from backend.mcp_server import (
    get_pr_diff, get_repo_context, post_pr_comment,
    list_open_issues, get_file_content, create_pull_request,
    get_repo_stats, get_contributors, get_dependency_manifest
)

load_dotenv()

TEST_REPO = "microsoft/vscode"

async def run_all_tests():
    print(f"--- Starting Tests against {TEST_REPO} ---\n")

    # 1. get_pr_diff
    try:
        print("[get_pr_diff]")
        # We need a valid PR number. Let's assume PR #1 exists or find a recent one.
        # For VSCode, let's just pick a random number like 200000 or find one from recent issues.
        # Actually, let's just try PR #200000.
        res = await get_pr_diff(TEST_REPO, 200000)
        print(f"  → Title: {res['title']}")
        print(f"  → Files Changed: {len(res['files_changed'])}")
        print("  PASS ✓")
    except Exception as e:
        print(f"  FAIL ✗: {e}")

    # 2. get_repo_context
    try:
        print("\n[get_repo_context]")
        res = await get_repo_context(TEST_REPO)
        print(f"  → Primary Language: {res['primary_language']}")
        print(f"  → Folder Count: {len(res['folder_structure'])}")
        print(f"  → README Snippet: {res['readme_summary'][:50]}...")
        print("  PASS ✓")
    except Exception as e:
        print(f"  FAIL ✗: {e}")

    # 3. post_pr_comment
    print("\n[post_pr_comment]")
    print("  → SKIPPED (Requires write access/avoiding spam)")

    # 4. list_open_issues
    try:
        print("\n[list_open_issues]")
        res = await list_open_issues(TEST_REPO, limit=5)
        print(f"  → Issues Found: {len(res)}")
        if res:
            print(f"  → Sample: {res[0]['title']} (#{res[0]['number']})")
        print("  PASS ✓")
    except Exception as e:
        print(f"  FAIL ✗: {e}")

    # 5. get_file_content
    try:
        print("\n[get_file_content]")
        res = await get_file_content(TEST_REPO, "package.json")
        print(f"  → Content Length: {len(res)}")
        print(f"  → Starts with: {res[:30].strip()}...")
        print("  PASS ✓")
    except Exception as e:
        print(f"  FAIL ✗: {e}")

    # 6. create_pull_request
    print("\n[create_pull_request]")
    print("  → SKIPPED (Requires write access)")

    # 7. get_repo_stats
    try:
        print("\n[get_repo_stats]")
        res = await get_repo_stats(TEST_REPO)
        print(f"  → Stars: {res['stars']}")
        print(f"  → Open Issues: {res['open_issues_count']}")
        print(f"  → License: {res['license']}")
        print("  PASS ✓")
    except Exception as e:
        print(f"  FAIL ✗: {e}")

    # 8. get_contributors
    try:
        print("\n[get_contributors]")
        res = await get_contributors(TEST_REPO, limit=5)
        print(f"  → Top Contributor: {res[0]['login']} ({res[0]['contributions']} commits)")
        print("  PASS ✓")
    except Exception as e:
        print(f"  FAIL ✗: {e}")

    # 9. get_dependency_manifest
    try:
        print("\n[get_dependency_manifest]")
        res = await get_dependency_manifest(TEST_REPO)
        print(f"  → Ecosystem: {res['ecosystem']}")
        print(f"  → Found File: {res['found_file']}")
        print("  PASS ✓")
    except Exception as e:
        print(f"  FAIL ✗: {e}")

    print("\n--- All Tests Finished ---")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
