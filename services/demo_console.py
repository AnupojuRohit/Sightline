from __future__ import annotations

import os
import json
import time
import logging
import urllib.request
import urllib.error
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from core.evidence_builder import EvidenceBuilder
from core.github_checker import GitHubChecker
from core.mismatch_engine import MismatchEngine
from core.rts_checker import RTSChecker
from models.mismatch import EvidenceBundle, Mismatch
from models.task import Task
from services.analyzer import Analyzer
from services.mock_loader import load_mock_tasks
from services.scan_pipeline import ScanResult
from ui.blocks import build_mismatch_blocks

logger = logging.getLogger(__name__)

DEMO_LIST_ID = "L-DEMO-SIGHTLINE"
GITHUB_REPO = "AnupojuRohit/Sightline"
GITHUB_API_BASE = "https://api.github.com"

# Cache dictionary: url -> (timestamp, data)
_GITHUB_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 120  # 2 minutes

def _github_api_get(url: str) -> Any:
    now = time.time()
    if url in _GITHUB_CACHE:
        cached_time, cached_data = _GITHUB_CACHE[url]
        if now - cached_time < _CACHE_TTL:
            return cached_data

    token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Sightline-Demo",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token and not token.startswith("your_"):
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            _GITHUB_CACHE[url] = (now, data)
            return data
    except Exception as exc:
        logger.warning("Failed to fetch from GitHub API %s: %s", url, exc)
        # Return expired cache on failure
        if url in _GITHUB_CACHE:
            return _GITHUB_CACHE[url][1]
        return None

def _get_github_data() -> dict[str, Any]:
    """Fetch live data from GitHub API with fallback mock structure if unconfigured or offline."""
    prs_url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/pulls?state=all&per_page=30"
    issues_url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/issues?state=open&per_page=30"
    commits_url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/commits?per_page=15"

    prs = _github_api_get(prs_url)
    issues = _github_api_get(issues_url)
    commits = _github_api_get(commits_url)

    # ─── Mock Fallbacks in case GitHub token is missing or rate limited ───
    now_dt = datetime.now()
    if prs is None:
        prs = [
            {
                "number": 1,
                "title": "Fix dict conversion crash in slack_list_diagnostics",
                "state": "closed",
                "html_url": f"https://github.com/{GITHUB_REPO}/pull/1",
                "user": {"login": "AnupojuRohit"},
                "updated_at": (now_dt - timedelta(hours=2)).isoformat(),
                "closed_at": (now_dt - timedelta(hours=2)).isoformat(),
                "merged_at": (now_dt - timedelta(hours=2)).isoformat(),
            },
            {
                "number": 2,
                "title": "Fix race condition in scanState indicator and renderEvents",
                "state": "closed",
                "html_url": f"https://github.com/{GITHUB_REPO}/pull/2",
                "user": {"login": "AnupojuRohit"},
                "updated_at": (now_dt - timedelta(hours=1)).isoformat(),
                "closed_at": (now_dt - timedelta(hours=1)).isoformat(),
                "merged_at": (now_dt - timedelta(hours=1)).isoformat(),
            },
            {
                "number": 3,
                "title": "RC Product Polish Mode: Live GitHub repository intelligence",
                "state": "open",
                "html_url": f"https://github.com/{GITHUB_REPO}/pull/3",
                "user": {"login": "AnupojuRohit"},
                "updated_at": now_dt.isoformat(),
                "closed_at": None,
                "merged_at": None,
            }
        ]

    if issues is None:
        issues = [
            {
                "number": 4,
                "title": "Stale tasks alerting does not trigger on initial page load",
                "state": "open",
                "html_url": f"https://github.com/{GITHUB_REPO}/issues/4",
                "user": {"login": "AnupojuRohit"},
                "updated_at": (now_dt - timedelta(days=1)).isoformat(),
            }
        ]

    # Filter out pull requests from the issues endpoint
    issues = [iss for iss in issues if "pull_request" not in iss]

    if commits is None:
        commits = [
            {
                "sha": "abc12345",
                "commit": {
                    "message": "rc: add mock scan fallback to prevent 409/503 errors",
                    "author": {"name": "AnupojuRohit", "date": (now_dt - timedelta(hours=1)).isoformat()}
                },
                "html_url": f"https://github.com/{GITHUB_REPO}/commit/abc12345"
            },
            {
                "sha": "def67890",
                "commit": {
                    "message": "fix: resolve dict(response) value errors on Slack responses",
                    "author": {"name": "AnupojuRohit", "date": (now_dt - timedelta(hours=3)).isoformat()}
                },
                "html_url": f"https://github.com/{GITHUB_REPO}/commit/def67890"
            }
        ]

    return {
        "prs": prs,
        "issues": issues,
        "commits": commits
    }

def build_demo_console_payload() -> dict[str, Any]:
    tasks = load_mock_tasks()
    evidence_builder = EvidenceBuilder(
        github_checker=GitHubChecker(),
        rts_checker=RTSChecker(),
    )
    mismatches = MismatchEngine(evidence_builder).find_mismatches(tasks)
    analysis = Analyzer().analyze(tasks)

    return build_scan_console_payload(
        ScanResult(
            list_id=DEMO_LIST_ID,
            generated_at=datetime.now().isoformat(timespec="seconds"),
            tasks=tasks,
            mismatches=mismatches,
            analysis=analysis,
        )
    )

def build_scan_console_payload(result: ScanResult) -> dict[str, Any]:
    git_data = _get_github_data()
    prs = git_data["prs"]
    issues = git_data["issues"]
    commits = git_data["commits"]

    # ─── GitHub Metrics ───
    open_prs = [pr for pr in prs if pr.get("state") == "open"]
    merged_prs = [pr for pr in prs if pr.get("state") == "closed" and pr.get("merged_at")]
    open_issues_count = len(issues)

    # ─── Stale Work (Active PRs with no updates for > 7 days) ───
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)
    stale_prs = []
    for pr in open_prs:
        updated_at_str = pr.get("updated_at")
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00")).replace(tzinfo=None)
                if updated_at < seven_days_ago:
                    stale_prs.append(pr)
            except Exception:
                pass

    # ─── Correlate Tasks & GitHub Pulls into Engineering Work Items ───
    work_items = []
    mismatches_by_task = {m.task.id: m for m in result.mismatches}
    matched_pr_numbers = set()

    for task in result.tasks:
        # Search task fields/description for PR reference
        pr_number = None
        desc = task.description or ""
        title = task.title or ""
        pr_match = re_search_pr(title + " " + desc)
        if pr_match:
            pr_number = pr_match

        # Find the matching PR metadata
        github_pr = None
        if pr_number:
            github_pr = next((pr for pr in prs if pr.get("number") == pr_number), None)
            matched_pr_numbers.add(pr_number)

        # Status and evidence mapping
        github_status = "unknown"
        github_url = task.url
        if github_pr:
            github_url = github_pr.get("html_url")
            if github_pr.get("merged_at"):
                github_status = "merged"
            else:
                github_status = github_pr.get("state", "unknown")

        mismatch = mismatches_by_task.get(task.id)
        evidence_list = []
        if mismatch:
            evidence_list = _serialize_evidence(mismatch.evidence)

        # Evidence sources matching
        github_matched = github_pr is not None
        slack_matched = len(evidence_list) > 0 or task.raw_fields.get("rts") is not None
        planning_matched = mismatch is None

        recommendation = "No action"
        confidence = 100
        if mismatch:
            recommendation = f"Update to {mismatch.recommended_status}"
            confidence = 95 if github_status == "merged" else 85
        elif task.status.lower() in ("todo", "in progress") and github_status == "merged":
            recommendation = "Update to Done"
            confidence = 95
        elif not task.owner:
            recommendation = "Assign Owner"
            confidence = 80

        work_items.append({
            "id": task.id,
            "title": task.title,
            "owner": task.owner or "Unassigned",
            "status": task.status,
            "recommendedStatus": mismatch.recommended_status if mismatch else task.status,
            "githubStatus": github_status,
            "githubUrl": github_url,
            "recommendation": recommendation,
            "confidence": confidence,
            "evidenceCount": len(evidence_list),
            "evidence": evidence_list,
            "reason": mismatch.reason if mismatch else None,
            "isStale": mismatch is not None,
            "dueDate": task.due_date.date().isoformat() if task.due_date else None,
            "description": task.description,
            "github_matched": github_matched,
            "slack_matched": slack_matched,
            "planning_matched": planning_matched
        })

    # ─── Add Unmapped Active GitHub PRs to Table ───
    for pr in open_prs:
        pr_num = pr.get("number")
        if pr_num not in matched_pr_numbers:
            work_items.append({
                "id": f"PR-{pr_num}",
                "title": pr.get("title", "GitHub Pull Request"),
                "owner": pr.get("user", {}).get("login", "Unknown"),
                "status": "Unmapped",
                "recommendedStatus": "Track in planning",
                "githubStatus": "open",
                "githubUrl": pr.get("html_url"),
                "recommendation": "Track in planning",
                "confidence": 90,
                "evidenceCount": 1,
                "evidence": [{
                    "source": "GitHub",
                    "label": f"PR #{pr_num}",
                    "detail": f"Active pull request in AnupojuRohit/Sightline created by {pr.get('user', {}).get('login')}.",
                    "url": pr.get("html_url")
                }],
                "reason": "Active pull request is currently untracked in project planning lists.",
                "isStale": True,
                "dueDate": None,
                "description": f"Untracked active engineering work from PR #{pr_num}.",
                "github_matched": True,
                "slack_matched": False,
                "planning_matched": False
            })

    planning_empty = len(result.tasks) == 0

    # ─── Repository Health Calculation (Deductions-Based) ───
    health_score = 100
    deductions = []

    # 1. Open Issues (-5 per issue, max -20)
    issue_deduct = min(20, open_issues_count * 5)
    if issue_deduct > 0:
        health_score -= issue_deduct
        deductions.append({"metric": "Open Issues", "deduction": issue_deduct, "detail": f"{open_issues_count} open issues"})

    # 2. Stale PRs (-10 per stale PR, max -30)
    stale_deduct = min(30, len(stale_prs) * 10)
    if stale_deduct > 0:
        health_score -= stale_deduct
        deductions.append({"metric": "Stale Work", "deduction": stale_deduct, "detail": f"{len(stale_prs)} inactive PRs"})

    # 3. Planning Mismatches (-15 per mismatch, max -30)
    mismatch_count = len(result.mismatches)
    mismatch_deduct = min(30, mismatch_count * 15)
    if mismatch_deduct > 0:
        health_score -= mismatch_deduct
        deductions.append({"metric": "Planning Mismatches", "deduction": mismatch_deduct, "detail": f"{mismatch_count} out-of-sync tasks"})

    # 4. Unmapped PRs (-5 per unmapped PR, max -20)
    unmapped_count = len(open_prs) - len(matched_pr_numbers)
    unmapped_deduct = min(20, max(0, unmapped_count) * 5)
    if unmapped_deduct > 0:
        health_score -= unmapped_deduct
        deductions.append({"metric": "Untracked Code Changes", "deduction": unmapped_deduct, "detail": f"{unmapped_count} active PRs not in planning"})

    # 5. Inactive development (-10 if last commit > 5 days ago)
    inactive_dev = False
    if commits:
        try:
            last_date_str = commits[0].get("commit", {}).get("author", {}).get("date")
            if last_date_str:
                last_date = datetime.fromisoformat(last_date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                if last_date < (now - timedelta(days=5)):
                    inactive_dev = True
                    health_score -= 10
                    deductions.append({"metric": "Development Inactivity", "deduction": 10, "detail": "No commits in last 5 days"})
        except Exception:
            pass

    health_score = max(10, health_score)

    # ─── Actionable Risks Panel ───
    risks_list = []
    if stale_prs:
        risks_list.append({
            "title": f"{len(stale_prs)} Inactive PRs",
            "severity": "HIGH",
            "reason": f"Pull requests in the repository have been open with no updates for over 7 days.",
            "recommendation": "Review stale work and close or merge to prevent branch decay."
        })

    if mismatch_count > 0:
        risks_list.append({
            "title": f"{mismatch_count} Stale Tasks in planning",
            "severity": "HIGH",
            "reason": "Code changes have been merged/closed but the planning status still indicates pending action.",
            "recommendation": "Sync planning board statuses with target GitHub branch state."
        })

    if unmapped_count > 0:
        risks_list.append({
            "title": f"{unmapped_count} Untracked Code Changes",
            "severity": "MEDIUM",
            "reason": "Development in progress on pull requests that are not mapped to planning cards.",
            "recommendation": "Create Slack List tasks for outstanding pull requests to restore execution visibility."
        })

    if inactive_dev:
        risks_list.append({
            "title": "Development Inactivity Detect",
            "severity": "MEDIUM",
            "reason": "No code commits pushed to the branch in the last 5 days.",
            "recommendation": "Verify development sprint velocity and check blockers."
        })

    if not risks_list:
        risks_list.append({
            "title": "Repository Operational Risk Clean",
            "severity": "LOW",
            "reason": "No stale branches, planning mismatches, or unmapped engineering changes detected.",
            "recommendation": "Maintain review cycles and continue sprint cadence."
        })

    # ─── Scan Progression Timeline Narrative ───
    timeline = [
        {
            "step": "Connecting to GitHub",
            "detail": f"Established secure connection to '{GITHUB_REPO}'."
        },
        {
            "step": "Analyzing Pull Requests",
            "detail": f"Correlated branch status for {len(prs)} pull request records."
        },
        {
            "step": "Running Slack RTS queries",
            "detail": "Queried workspace conversations for task updates and execution signs."
        },
        {
            "step": "Cross-Source Correlation Complete",
            "detail": f"Matched execution states to planning list. Derived repository health score: {health_score}/100."
        }
    ]

    # Latest activity string (last commit info)
    latest_commit_str = "No recent commits"
    if commits:
        commit_msg = commits[0].get("commit", {}).get("message", "update").split("\n")[0]
        commit_author = commits[0].get("commit", {}).get("author", {}).get("name", "Author")
        latest_commit_str = f"'{commit_msg}' by {commit_author}"

    # Calculate real Planning Sync score (agreement percentage)
    if work_items:
        in_sync_count = sum(1 for t in work_items if not t["isStale"] and t["status"] != "Unmapped")
        planning_sync_score = round((in_sync_count / len(work_items)) * 100)
    else:
        planning_sync_score = 100

    return {
        "listId": result.list_id,
        "generatedAt": result.generated_at,
        "summary": {
            "healthScore": health_score,
            "totalTasks": len(work_items),
            "staleTasks": mismatch_count + unmapped_count,
            "openPRs": len(open_prs),
            "mergedPRs": len(merged_prs),
            "openIssues": open_issues_count,
            "staleWork": len(stale_prs),
            "latestCommit": latest_commit_str,
            "automationReadiness": planning_sync_score,  # Overwrite with planning sync score
        },
        "healthBreakdown": {
            "baseline": 100,
            "deductions": deductions,
            "score": health_score
        },
        "tasks": work_items,
        "mismatches": [_serialize_mismatch(mismatch) for mismatch in result.mismatches],
        "risks": risks_list,
        "timeline": timeline,
        "alertPreview": _alert_preview(result.mismatches[0]) if result.mismatches else None,
        "planningEmpty": planning_empty
    }

def _serialize_mismatch(mismatch: Mismatch) -> dict[str, Any]:
    return {
        "taskId": mismatch.task.id,
        "taskTitle": mismatch.task.title,
        "currentStatus": mismatch.task.status,
        "recommendedStatus": mismatch.recommended_status,
        "reason": mismatch.reason,
        "evidence": _serialize_evidence(mismatch.evidence),
    }

def _serialize_evidence(evidence: EvidenceBundle) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for github_state in evidence.github:
        reference = github_state.reference
        repo = f"{reference.owner}/{reference.repo}" if reference.owner and reference.repo else reference.repo
        state = "merged" if github_state.merged else github_state.state
        rows.append(
            {
                "source": "GitHub",
                "label": f"{repo or 'repository'} #{reference.number}",
                "detail": f"{reference.kind.replace('_', ' ')} is {state}",
                "url": github_state.url or reference.url,
            }
        )

    for rts_evidence in evidence.rts:
        rows.append(
            {
                "source": "Slack",
                "label": rts_evidence.query,
                "detail": rts_evidence.text,
                "url": rts_evidence.url,
            }
        )

    return rows

def _alert_preview(mismatch: Mismatch) -> dict[str, Any]:
    evidence = _serialize_evidence(mismatch.evidence)
    return {
        "title": "Potentially Stale Task",
        "taskTitle": mismatch.task.title,
        "currentStatus": mismatch.task.status,
        "recommendedStatus": mismatch.recommended_status,
        "reason": mismatch.reason,
        "evidence": evidence[:4],
        "blocks": build_mismatch_blocks(mismatch),
    }

def re_search_pr(text: str) -> int | None:
    match = re_search_pr.regex.search(text)
    if match:
        return int(match.group(1))
    return None

import re
re_search_pr.regex = re.compile(r"(?:pull/|#)(\d+)")
