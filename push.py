#!/usr/bin/env python3
"""Python equivalent of push.sh with interactive multi-repo management."""
from __future__ import annotations

import argparse
import os
import subprocess
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


class GitManagerError(Exception):
    """Raised for recoverable git-manager errors."""


def run_git(args: Sequence[str], *, cwd: Path) -> str:
    """Run a git command and return stdout as text."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise GitManagerError(f"git {' '.join(args)} failed in {cwd}: {stderr}")
    return result.stdout


def run_git_env(args: Sequence[str], *, cwd: Path, extra_env: dict[str, str]) -> str:
    env = os.environ.copy()
    env.update(extra_env)
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise GitManagerError(f"git {' '.join(args)} failed in {cwd}: {stderr}")
    return result.stdout

def detect_base_branch(repo: Path) -> str:
    if git_ok(["show-ref", "--verify", "--quiet", "refs/heads/main"], cwd=repo):
        return "main"
    if git_ok(["show-ref", "--verify", "--quiet", "refs/heads/master"], cwd=repo):
        return "master"
    origin_head = (
        subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "origin/HEAD"],
            cwd=str(repo),
            check=False,
            text=True,
            capture_output=True,
        ).stdout.strip()
        or ""
    )
    if origin_head and origin_head != "HEAD":
        return origin_head.removeprefix("origin/")
    return "main"


def ensure_main_branch(repo: Path) -> None:
    if git_ok(["show-ref", "--verify", "--quiet", "refs/heads/main"], cwd=repo):
        return
    if git_ok(["show-ref", "--verify", "--quiet", "refs/heads/master"], cwd=repo):
        try:
            run_git(["branch", "main", "master"], cwd=repo)
        except GitManagerError:
            pass
        return
    if git_ok(["show-ref", "--verify", "--quiet", "refs/remotes/origin/main"], cwd=repo):
        try:
            run_git(["branch", "main", "origin/main"], cwd=repo)
        except GitManagerError:
            pass
        return
    if git_ok(["show-ref", "--verify", "--quiet", "refs/remotes/origin/master"], cwd=repo):
        try:
            run_git(["branch", "main", "origin/master"], cwd=repo)
        except GitManagerError:
            pass
        return
    try:
        run_git(["branch", "main"], cwd=repo)
    except GitManagerError:
        pass


def current_branch(repo: Path) -> str:
    result = subprocess.run(
        ["git", "symbolic-ref", "--short", "-q", "HEAD"],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )
    branch = result.stdout.strip()
    return branch or "HEAD"


def repo_pending_count(repo: Path, base_branch: str) -> int:
    if not git_ok(["rev-parse", "--verify", "--quiet", "local_commit"], cwd=repo):
        return 0
    if not git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"], cwd=repo):
        return 0
    out = run_git(["rev-list", "--count", f"{base_branch}..local_commit"], cwd=repo)
    return int(out.strip() or "0")


def scan_repos(base_dir: Path) -> List[RepoState]:
    repo_states: List[RepoState] = []
    for child in sorted(base_dir.iterdir()):
        if not child.is_dir():
            continue
        if not (child / ".git").is_dir():
            continue
        ensure_main_branch(child)
        base_branch = detect_base_branch(child)
        branch = current_branch(child)
        local_exists = branch == "local_commit" or git_ok(
            ["show-ref", "--verify", "--quiet", "refs/heads/local_commit"], cwd=child
        )
        pending = repo_pending_count(child, base_branch) if local_exists else 0
        repo_states.append(
            RepoState(
                path=child,
                name=child.name,
                base_branch=base_branch,
                current_branch=branch,
                local_commit_exists=local_exists,
                pending_count=pending,
            )
        )
    return repo_states


def print_repo_table(base_dir: Path, states: Iterable[RepoState]) -> None:
    print(f"\n🔍 Scanning repositories in: {base_dir}")
    header = f"{'No.':<4} {'Repository':<36} {'local_commit':<14} {'commits':<10} {'branch':<24}"
    print("📋 Repository summary:")
    print(header)
    print(f"{'----':<4} {'-'*36:<36} {'-'*14:<14} {'-'*10:<10} {'-'*24:<24}")
    for idx, state in enumerate(states, start=1):
        local_flag = "yes" if state.local_commit_exists else "no"
        print(
            f"[{idx:<2}] {state.name:<36} {local_flag:<14} {state.pending_count:<10} {state.current_branch:<24}"
        )


def checkout_branch(repo: Path, branch: str, start_point: str | None = None) -> None:
    args = ["checkout"]
    if start_point:
        args += ["-b", branch, start_point]
    else:
        args.append(branch)
    run_git(args, cwd=repo)


def switch_to_local_commit(repo: Path, base_branch: str, current_branch: str) -> str:
    if git_ok(["show-ref", "--verify", "--quiet", "refs/heads/local_commit"], cwd=repo):
        checkout_branch(repo, "local_commit")
        return "local_commit"
    start_ref = base_branch if git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"], cwd=repo) else current_branch
    if git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{start_ref}"], cwd=repo):
        checkout_branch(repo, "local_commit", start_ref)
        return "local_commit"
    if git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{base_branch}"], cwd=repo):
        checkout_branch(repo, "local_commit", f"origin/{base_branch}")
        return "local_commit"
    checkout_branch(repo, "local_commit")
    return "local_commit"


def switch_to_base(repo: Path, base_branch: str) -> str:
    if git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"], cwd=repo):
        checkout_branch(repo, base_branch)
        return base_branch
    if git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{base_branch}"], cwd=repo):
        checkout_branch(repo, base_branch, f"origin/{base_branch}")
        return base_branch
    raise GitManagerError(f"Base branch '{base_branch}' not found locally or on origin")


def preview_commits(repo: Path, base_branch: str) -> None:
    out = run_git([
        "log",
        "--reverse",
        "--no-decorate",
        "--date=short",
        "--pretty=format:  %h  %ad  %s",
        f"{base_branch}..local_commit",
    ], cwd=repo)
    print("📜 Commits (oldest → newest):")
    print(out)
    print()


def move_commits(repo: Path, base_branch: str, pending_count: int, current_branch: str) -> None:
    if not git_ok(["rev-parse", "--verify", "--quiet", "local_commit"], cwd=repo):
        raise GitManagerError("local_commit does not exist")
    if not git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"], cwd=repo):
        raise GitManagerError(f"Base branch '{base_branch}' not found locally")

    # Refresh count
    refreshed = int(
        run_git(["rev-list", "--count", f"{base_branch}..local_commit"], cwd=repo).strip() or "0"
    )
    if refreshed == 0:
        print("❌ No commits to move.")
        return
    preview_commits(repo, base_branch)
    raw = input(f"➡ How many commits to move to {base_branch} (1..{refreshed})? ").strip()
    if not raw.isdigit():
        raise GitManagerError("Invalid number")
    num = int(raw)
    if num <= 0 or num > refreshed:
        raise GitManagerError("Invalid number")

    stashed = False
    if not working_tree_clean(repo):
        choice = input("Working tree not clean. Stash changes and continue? [y/N]: ").strip().lower()
        if choice.startswith("y"):
            stash_changes(repo, f"git-manager auto-stash before moving commits ({now_display()})")
            stashed = True
        else:
            raise GitManagerError("Aborted: working tree not clean")

    commits = run_git(["rev-list", "--reverse", f"{base_branch}..local_commit"], cwd=repo).strip().splitlines()
    commits = commits[:num]
    if not commits:
        raise GitManagerError("No commits to process")

    checkout_branch(repo, base_branch)
    now_iso_value = now_iso()
    for commit in commits:
        try:
            run_git(["cherry-pick", "--no-commit", commit], cwd=repo)
        except GitManagerError:
            # Detect conflicts
            conflict_names = run_git(["diff", "--name-only", "--diff-filter=U"], cwd=repo).strip()
            if conflict_names:
                print("❌ Cherry-pick failed with merge conflicts for commit", commit)
                print(conflict_names)
                run_git(["cherry-pick", "--abort"], cwd=repo)
                raise
            status = run_git(["status"], cwd=repo)
            if "nothing to commit" in status:
                run_git(["cherry-pick", "--skip"], cwd=repo)
                continue
            raise

        message = run_git(["show", "-s", "--format=%B", commit], cwd=repo)
        run_git_env(
            ["commit", "-m", message, "--date", now_iso_value],
            cwd=repo,
            extra_env={"GIT_AUTHOR_DATE": now_iso_value, "GIT_COMMITTER_DATE": now_iso_value},
        )
        print(run_git(["show", "-s", "--date=iso", "--pretty=format:  ✔ %h  %ad  %an <%ae>"], cwd=repo))

    print(f"📜 Latest moved commits on {base_branch} (with author info):")
    print(run_git(["log", "-n", str(num), "--no-decorate", "--date=iso", "--pretty=format:  %h  %ad  %an <%ae>"], cwd=repo))

    default_head = run_git(["remote", "show", "origin"], cwd=repo)
    for line in default_head.splitlines():
        if "HEAD branch:" in line:
            remote_head = line.split(":", 1)[1].strip()
            if remote_head and remote_head != base_branch:
                raise GitManagerError(
                    f"Remote default branch is '{remote_head}', but target is '{base_branch}'."
                )
            break

    today = datetime.now().strftime("%Y-%m-%d")
    dates = run_git(["log", "-n", str(num), "--date=short", "--pretty=format:%ad"], cwd=repo).splitlines()
    bad_dates = [d for d in dates if d and d != today]
    if bad_dates:
        raise GitManagerError(f"Found {len(bad_dates)} commit(s) with author date not equal to today ({today})")

    expected_email = run_git(["config", "user.email"], cwd=repo).strip()
    expected_name = run_git(["config", "user.name"], cwd=repo).strip()
    emails = run_git(["log", "-n", str(num), "--pretty=format:%ae"], cwd=repo).splitlines()
    names = run_git(["log", "-n", str(num), "--pretty=format:%an"], cwd=repo).splitlines()
    if any(e and e != expected_email for e in emails):
        raise GitManagerError(f"Found commit(s) with author email not matching '{expected_email}'")
    if any(n and n != expected_name for n in names):
        raise GitManagerError(f"Found commit(s) with author name not matching '{expected_name}'")

    print(f"✅ All {num} commits have correct author info (will be attributed to {expected_name} <{expected_email}>)")
    print(f"🚀 Pushing to origin {base_branch}...")
    run_git(["push", "origin", base_branch], cwd=repo)
    print(f"✅ Done! {num} commits moved with date/time {now_iso_value}.")

    remaining = run_git(["rev-list", "--reverse", f"{base_branch}..local_commit"], cwd=repo).strip().splitlines()
    if remaining:
        checkout_branch(repo, "local_commit")
        run_git(["reset", "--hard", base_branch], cwd=repo)
        for commit in remaining:
            try:
                run_git(["cherry-pick", commit], cwd=repo)
            except GitManagerError:
                run_git(["cherry-pick", "--abort"], cwd=repo)
                raise GitManagerError(
                    f"Cherry-pick failed while rewriting local_commit for commit {commit}. Resolve manually."
                )
        print("✅ local_commit updated to reflect remaining commits.")
    else:
        checkout_branch(repo, "local_commit")
        run_git(["reset", "--hard", base_branch], cwd=repo)
        print(f"✅ local_commit is now aligned with {base_branch}")

    if stashed:
        checkout_branch(repo, current_branch)
        try:
            run_git(["stash", "pop"], cwd=repo)
        except GitManagerError:
            print("⚠️ Stash pop had conflicts or failed. Resolve manually.")


def repo_menu(state: RepoState) -> None:
    repo = state.path
    ensure_git_identity(repo)
    print(
        f"\nℹ️  {state.name} | base: {state.base_branch} | current: {state.current_branch} | "
        f"local_commit: {'yes' if state.local_commit_exists else 'no'} | commits: {state.pending_count}"
    )
    print("Choose an action:")
    if state.current_branch == "local_commit":
        print(f"  1) Switch to {state.base_branch}")
    else:
        print("  1) Switch to local_commit (create if missing)")
    print(f"  2) Preview commits ({state.base_branch}..local_commit)")
    print(f"  3) Move N commits from local_commit to {state.base_branch}")
    print("  4) Back to list")
    action = input("Select 1-4: ").strip()

    if action == "1":
        if state.current_branch == "local_commit":
            new_branch = switch_to_base(repo, state.base_branch)
            print(f"✅ On branch {new_branch}")
        else:
            new_branch = switch_to_local_commit(repo, state.base_branch, state.current_branch)
            print(f"✅ On branch {new_branch}")
    elif action == "2":
        preview_commits(repo, state.base_branch)
    elif action == "3":
        move_commits(repo, state.base_branch, state.pending_count, state.current_branch)
    else:
        return


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")


def now_display() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S %z")


def ensure_git_identity(repo: Path) -> None:
    name = run_git(["config", "user.name"], cwd=repo).strip()
    email = run_git(["config", "user.email"], cwd=repo).strip()
    if not name or not email:
        raise GitManagerError("Git user identity is not configured (user.name / user.email)")


def working_tree_clean(repo: Path) -> bool:
    return git_ok(["diff", "--quiet"], cwd=repo) and git_ok(["diff", "--cached", "--quiet"], cwd=repo)


def stash_changes(repo: Path, message: str) -> None:
    run_git(["stash", "push", "-u", "-m", message], cwd=repo)


def git_ok(args: Sequence[str], *, cwd: Path) -> bool:
    """Return True if git command exits with 0, suppressing output."""
    result = subprocess.run(["git", *args], cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


@dataclass
class RepoState:
    path: Path
    name: str
    base_branch: str
    current_branch: str
    local_commit_exists: bool
    pending_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage multiple git repositories under a base directory.")
    parser.add_argument(
        "base_dir",
        nargs="?",
        default=os.environ.get("BASE_DIR"),
        help="Base directory containing git repositories (default: $BASE_DIR or /home/amir/GitHub)",
    )
    return parser.parse_args()


def resolve_base_dir(arg_base: str | None) -> Path:
    base_dir = Path(arg_base or "/home/amir/GitHub").expanduser().resolve()
    if not base_dir.is_dir():
        raise GitManagerError(f"Base directory '{base_dir}' not found")
    return base_dir


def main() -> None:
    args = parse_args()
    base_dir = resolve_base_dir(args.base_dir)
    while True:
        states = scan_repos(base_dir)
        print_repo_table(base_dir, states)
        choice = input("\n👉 Select a repository number (or 0 to quit): ").strip()
        if not choice.isdigit():
            print("❌ Invalid selection")
            continue
        idx = int(choice)
        if idx == 0:
            print("👋 Bye")
            return
        if idx < 1 or idx > len(states):
            print("❌ Invalid selection")
            continue
        repo_menu(states[idx - 1])
        input("Press Enter to refresh the list...")


if __name__ == "__main__":
    try:
        main()
    except GitManagerError as exc:
        print(f"Error: {exc}")
