# git-manager

A small interactive Bash tool to manage multiple Git repositories under a single directory. It scans all repos, shows their status, and lets you:

- Switch between `main`/`master` and `local_commit`
- Preview commits pending on `local_commit` relative to the base branch
- Move N commits from `local_commit` onto the base branch (oldest → newest), rewrite timestamps to “now”, and push

## Requirements
- Linux/macOS shell with Bash
- Git installed and available on `PATH`

## Layout Assumption
By default the tool scans repositories under `/home/amir/GitHub`, where each subfolder is a Git repo:

```
/home/amir/GitHub/
  repo-a/
  repo-b/
  ...
```

You can override the scan root:
- Pass it as the first CLI argument: `./push.sh /path/to/root`
- Or via env var: `BASE_DIR=/path/to/root ./push.sh`

## Quick Start
```bash
chmod +x push.sh
./push.sh
```

- Enter a repository number to manage it, or `0` to quit.
- The list refreshes after each action.

## What You’ll See
The tool prints a table for every repo with:
- `local_commit`: yes/no (exists or current unborn branch)
- `commits`: number of commits ahead of base (`main`/`master`) on `local_commit`
- `branch`: current branch name

Then, for a selected repo, you’ll get this menu:

1) Switch to local_commit (create if missing) OR Switch to base (contextual)
2) Preview commits (base..local_commit)
3) Move N commits from local_commit to base
4) Back to list

## Base Branch Detection
The base branch is chosen per-repo as follows:
1. Local `main` if present, else
2. Local `master` if present, else
3. `origin/HEAD` if it points to a real branch, else
4. `main`

`HEAD` is never shown as a base; the script falls back gracefully.

## “Move N” Details (Option 3)
- Recomputes pending count: `git rev-list --count base..local_commit`
- Requires a clean working tree (no staged/unstaged changes)
- Previews the commits oldest → newest
- Cherry-picks the first N commits from `local_commit` onto base in order
- For each cherry-pick, it amends the commit timestamp to the current time (author + committer) without changing the message
- Pushes the updated base branch: `git push origin <base>`
- If N equals the total pending count, it syncs `local_commit` to base (`git reset --hard <base>`) so the next scan shows 0 pending commits

Conflict behavior:
- If cherry-pick results in “nothing to commit”, the script skips that commit
- Any other conflict aborts with a helpful error so you can resolve manually

## Working Safely
- Always commit your work on `local_commit`. The tool won’t proceed if the working tree isn’t clean.
- Moving commits preserves order. It never rewrites `local_commit` history, except when you explicitly move ALL pending commits (then it fast-aligns `local_commit` to base for a clean slate).
- If your remote base moved, push may fail. Consider pulling/rebasing base before moving.

## Tips
- To move all pending commits, enter the full pending count when prompted.
- To set `origin/HEAD` correctly on a new repo:
  ```bash
  git remote set-head origin -a
  ```

## Troubleshooting
- “Base branch not found”: ensure `main`/`master` exists locally or on origin.
- “No commits to move”: nothing ahead on `local_commit` relative to base.
- “Working tree not clean”: commit or stash your changes.

## License
This repository does not include a license file. Add one if you plan to share/distribute.
