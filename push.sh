#!/bin/bash
set -euo pipefail

error_exit() {
    echo "❌ Error: $1"
    exit 1
}

# Capture timestamp with explicit timezone to avoid date-day ambiguity
# Use ISO 8601 format for git commands
NOW=$(date -u "+%Y-%m-%dT%H:%M:%S%z")
# Also capture a readable format for display
NOW_DISPLAY=$(date "+%Y-%m-%d %H:%M:%S %z")

# Detect default base branch for current repo (prefers local main/master, falls back to origin/HEAD if it points to a real branch)
detect_base_branch() {
    if git show-ref --verify --quiet refs/heads/main; then
        echo main
        return 0
    fi
    if git show-ref --verify --quiet refs/heads/master; then
        echo master
        return 0
    fi
    local origin_head
    origin_head=$(git rev-parse --abbrev-ref origin/HEAD 2>/dev/null || true)
    # If remote HEAD resolves to a branch name, use it; ignore if it's just 'HEAD'
    if [ -n "${origin_head:-}" ] && [ "$origin_head" != "HEAD" ]; then
        echo "${origin_head#origin/}"
        return 0
    fi
    echo main
}

# Ensure a local 'main' branch exists without switching branches.
# Strategy:
# 1) If local 'main' exists: do nothing
# 2) Else if local 'master' exists: create 'main' from 'master'
# 3) Else if remote 'origin/main' exists: create 'main' from 'origin/main'
# 4) Else if remote 'origin/master' exists: create 'main' from 'origin/master'
# 5) Else: create 'main' from current HEAD
ensure_main_branch() {
    if git show-ref --verify --quiet refs/heads/main; then
        return 0
    fi

    if git show-ref --verify --quiet refs/heads/master; then
        git branch main master >/dev/null 2>&1 || true
        return 0
    fi

    if git show-ref --verify --quiet refs/remotes/origin/main; then
        git branch main origin/main >/dev/null 2>&1 || true
        return 0
    fi

    if git show-ref --verify --quiet refs/remotes/origin/master; then
        git branch main origin/master >/dev/null 2>&1 || true
        return 0
    fi

    # Fallback to HEAD
    git branch main >/dev/null 2>&1 || true
}

# Determine base directory containing all repositories
# Priority: first CLI arg -> env BASE_DIR -> default path
BASE_DIR="${1:-${BASE_DIR:-/home/amir/GitHub}}"
if [ ! -d "$BASE_DIR" ]; then
    error_exit "Base directory '$BASE_DIR' not found"
fi

# Move to the base directory before scanning repos
cd "$BASE_DIR" || error_exit "Cannot enter base directory $BASE_DIR"

REPO_MAP=()
COUNT_MAP=()
BASE_MAP=()
BRANCH_MAP=()
LOCAL_EXISTS_MAP=()

scan_and_show() {
    REPO_MAP=()
    COUNT_MAP=()
    BASE_MAP=()
    BRANCH_MAP=()
    LOCAL_EXISTS_MAP=()

    echo "🔍 Scanning repositories in: $BASE_DIR"
    echo
    shopt -s nullglob
    echo "📋 Repository summary:"
    printf "%-4s %-36s %-14s %-10s %-24s\n" "No." "Repository" "local_commit" "commits" "branch"
    printf "%-4s %-36s %-14s %-10s %-24s\n" "----" "------------------------------------" "------------" "--------" "------------------------"

    i=0
    for repo in */; do
        if [ -d "$repo/.git" ]; then
            cd "$repo" || error_exit "Cannot enter directory $repo"

            # Ensure 'main' exists so commit counting against base is reliable
            ensure_main_branch

            LOCAL_EXISTS="no"
            COUNT=0
            BRANCH=$(git symbolic-ref --short -q HEAD 2>/dev/null || echo HEAD)
            BASE_BRANCH=$(detect_base_branch)

            if git show-ref --verify --quiet refs/heads/local_commit || [[ "$BRANCH" == "local_commit" ]]; then
                LOCAL_EXISTS="yes"
                if git show-ref --verify --quiet "refs/heads/$BASE_BRANCH" && git rev-parse --verify --quiet local_commit >/dev/null; then
                    COUNT=$(git rev-list --count "$BASE_BRANCH"..local_commit 2>/dev/null || echo 0)
                else
                    COUNT=0
                fi
            fi

            ((++i))
            printf "%-4s %-36s %-14s %-10s %-24s\n" "[$i]" "$(basename "$repo")" "$LOCAL_EXISTS" "$COUNT" "$BRANCH"

            REPO_MAP+=("$repo")
            COUNT_MAP+=("$COUNT")
            BASE_MAP+=("$BASE_BRANCH")
            BRANCH_MAP+=("$BRANCH")
            LOCAL_EXISTS_MAP+=("$LOCAL_EXISTS")

            cd .. || error_exit "Cannot return to parent directory"
        fi
    done
}

repo_menu() {
    local idx=$1
    local REPO="${REPO_MAP[$idx]}"
    local COUNT="${COUNT_MAP[$idx]}"
    local BASE_BRANCH="${BASE_MAP[$idx]}"
    local BRANCH="${BRANCH_MAP[$idx]}"
    local LOCAL_EXISTS="${LOCAL_EXISTS_MAP[$idx]}"
    local STASHED=0
    local ORIG_BRANCH="$BRANCH"

    cd "$REPO" || error_exit "Cannot enter $REPO"
    
    # Verify git user is configured (needed for cherry-pick commits)
    local GIT_USER_NAME=$(git config user.name 2>/dev/null || true)
    local GIT_USER_EMAIL=$(git config user.email 2>/dev/null || true)
    if [ -z "$GIT_USER_NAME" ] || [ -z "$GIT_USER_EMAIL" ]; then
        echo "❌ Git user not configured"
        echo "   Please configure git identity:"
        echo "     git config user.name \"Your Name\""
        echo "     git config user.email \"you@example.com\""
        if [ -n "$SUDO_USER" ]; then
            echo "   (Or run without sudo to use your own git config)"
        fi
        cd .. || error_exit "Cannot return to parent directory"
        return 0
    fi

    cd .. || error_exit "Cannot return to parent directory"

    echo
    echo "ℹ️  $(basename "$REPO") | base: $BASE_BRANCH | current: $BRANCH | local_commit: $LOCAL_EXISTS | commits: $COUNT"
    echo "Choose an action:"
    if [ "$BRANCH" = "local_commit" ]; then
        echo "  1) Switch to $BASE_BRANCH"
    else
        echo "  1) Switch to local_commit (create if missing)"
    fi
    echo "  2) Preview commits ($BASE_BRANCH..local_commit)"
    echo "  3) Move N commits from local_commit to $BASE_BRANCH"
    echo "  4) Back to list"
    read -p "Select 1-4: " ACTION

    cd "$REPO" || error_exit "Cannot enter $REPO"

    case "$ACTION" in
        1)
            if [ "$BRANCH" = "local_commit" ]; then
                echo "➡ Switching to $BASE_BRANCH..."
                TARGET="$BASE_BRANCH"
                if git show-ref --verify --quiet "refs/heads/$TARGET"; then
                    git checkout "$TARGET" || error_exit "Failed to switch to $TARGET"
                else
                    # Try to create local branch from origin
                    if git show-ref --verify --quiet "refs/remotes/origin/$TARGET"; then
                        git checkout -b "$TARGET" "origin/$TARGET" || error_exit "Failed to create $TARGET from origin/$TARGET"
                    else
                        error_exit "Base branch '$TARGET' not found locally or on origin"
                    fi
                fi
                echo "✅ On branch $TARGET"
            else
                echo "➡ Switching to local_commit (create if missing)..."
                if git show-ref --verify --quiet refs/heads/local_commit; then
                    git checkout local_commit || error_exit "Failed to switch to local_commit"
                else
                    # Determine a safe start-point: prefer base branch, else current branch
                    START_REF="$BASE_BRANCH"
                    if ! git show-ref --verify --quiet "refs/heads/$START_REF"; then
                        START_REF="$BRANCH"
                    fi
                    if git show-ref --verify --quiet "refs/heads/$START_REF"; then
                        git checkout -b local_commit "$START_REF" || error_exit "Failed to create local_commit from $START_REF"
                    else
                        # Try origin/$BASE_BRANCH if local not available
                        if git show-ref --verify --quiet "refs/remotes/origin/$BASE_BRANCH"; then
                            git checkout -b local_commit "origin/$BASE_BRANCH" || error_exit "Failed to create local_commit from origin/$BASE_BRANCH"
                        else
                            # Fallback to current HEAD
                            git checkout -b local_commit || error_exit "Failed to create local_commit from HEAD"
                        fi
                    fi
                fi
                echo "✅ On branch local_commit"
            fi
            ;;
        2)
            echo "📜 Commits (oldest → newest):"
            git log --reverse --no-decorate --date=short --pretty=format:'  %h  %ad  %s' "$BASE_BRANCH"..local_commit || true
            echo
            ;;
        3)
            # Refresh count in case of changes
            if git show-ref --verify --quiet "refs/heads/$BASE_BRANCH" && git rev-parse --verify --quiet local_commit >/dev/null; then
                COUNT=$(git rev-list --count "$BASE_BRANCH"..local_commit 2>/dev/null || echo 0)
            else
                COUNT=0
            fi
            if [ "$COUNT" -eq 0 ]; then
                echo "❌ No commits to move."
                cd .. || error_exit "Cannot return to parent directory"
                return 0
            fi
            echo "📜 Commits (oldest → newest):"
            git log --reverse --no-decorate --date=short --pretty=format:'  %h  %ad  %s' "$BASE_BRANCH"..local_commit || true
            echo
            read -p "➡ How many commits to move to $BASE_BRANCH (1..$COUNT)? " NUM
            if ! [[ "$NUM" =~ ^[0-9]+$ ]] || [ "$NUM" -le 0 ] || [ "$NUM" -gt "$COUNT" ]; then
                echo "❌ Invalid number"
                cd .. || error_exit "Cannot return to parent directory"
                return 0
            fi
            if ! git diff --quiet || ! git diff --cached --quiet; then
                echo "❌ Working tree not clean."
                echo "  Options:"
                echo "    s) Stash changes (incl. untracked) and continue"
                echo "    a) Abort"
                read -p "Choose [s/a]: " DIRTY_ACTION
                if [[ "$DIRTY_ACTION" =~ ^[Ss]$ ]]; then
                    # Check if there's an ongoing merge/cherry-pick/rebase
                    if [ -d ".git/MERGE_HEAD" ] || [ -f ".git/MERGE_HEAD" ] || [ -d ".git/CHERRY_PICK_HEAD" ] || [ -f ".git/CHERRY_PICK_HEAD" ] || [ -d ".git/rebase-merge" ]; then
                        echo "⚠️  Detected ongoing merge/cherry-pick operation. Aborting it first..."
                        if [ -f ".git/MERGE_HEAD" ]; then
                            git merge --abort 2>/dev/null || true
                        fi
                        if [ -f ".git/CHERRY_PICK_HEAD" ]; then
                            git cherry-pick --abort 2>/dev/null || true
                        fi
                        if [ -d ".git/rebase-merge" ]; then
                            git rebase --abort 2>/dev/null || true
                        fi
                    fi
                    git stash push -u -m "git-manager auto-stash before moving commits ($NOW_DISPLAY)" || error_exit "Failed to stash changes"
                    STASHED=1
                    echo "✅ Changes stashed. Proceeding..."
                else
                    echo "🛑 Aborted. Please commit or stash changes and retry."
                    cd .. || error_exit "Cannot return to parent directory"
                    return 0
                fi
            fi
            # Avoid pipeline SIGPIPE from head causing exit under set -euo pipefail
            COMMITS=$(git rev-list --reverse "$BASE_BRANCH"..local_commit | head -n "$NUM" || true)
            if [ -z "$COMMITS" ]; then
                echo "❌ No commits to process"
                cd .. || error_exit "Cannot return to parent directory"
                return 0
            fi
            echo "🕒 Rewriting dates for $NUM commits to $NOW_DISPLAY..."
            git checkout "$BASE_BRANCH" || error_exit "Cannot checkout $BASE_BRANCH"
            for COMMIT in $COMMITS; do
                if ! git cherry-pick "$COMMIT" 2>/dev/null; then
                    # Check if cherry-pick resulted in merge conflicts
                    if git diff --name-only --diff-filter=U | grep -q .; then
                        echo "❌ Cherry-pick failed with merge conflicts for commit $COMMIT"
                        echo "   Conflicted files:"
                        git diff --name-only --diff-filter=U | sed 's/^/     - /'
                        echo
                        echo "   How to resolve:"
                        echo "     1) Keep $BASE_BRANCH version (ours) - discard incoming changes"
                        echo "     2) Use incoming version (theirs) - accept commit's changes"
                        echo "     3) Manual resolution - exit and resolve manually"
                        echo "     4) Skip this commit - don't cherry-pick it"
                        read -p "Choose [1-4]: " CONFLICT_CHOICE
                        case "$CONFLICT_CHOICE" in
                            1)
                                echo "✓ Resolving conflicts by keeping $BASE_BRANCH version..."
                                git checkout --ours . || error_exit "Failed to resolve with 'ours'"
                                git add . || error_exit "Failed to stage resolved files"
                                git cherry-pick --continue --no-edit || error_exit "Failed to continue cherry-pick"
                                # Amend commit with new dates
                                GIT_AUTHOR_DATE="$NOW" GIT_COMMITTER_DATE="$NOW" git commit --amend --no-edit --date "$NOW" --reset-author || error_exit "Failed to amend commit with new dates"
                                git show -s --date=iso --pretty=format:'  ✔ %h  %ad  %s' || error_exit "Failed to display amended commit"
                                ;;
                            2)
                                echo "✓ Resolving conflicts by accepting incoming changes..."
                                git checkout --theirs . || error_exit "Failed to resolve with 'theirs'"
                                git add . || error_exit "Failed to stage resolved files"
                                git cherry-pick --continue --no-edit || error_exit "Failed to continue cherry-pick"
                                # Amend commit with new dates
                                GIT_AUTHOR_DATE="$NOW" GIT_COMMITTER_DATE="$NOW" git commit --amend --no-edit --date "$NOW" --reset-author || error_exit "Failed to amend commit with new dates"
                                git show -s --date=iso --pretty=format:'  ✔ %h  %ad  %s' || error_exit "Failed to display amended commit"
                                ;;
                            3)
                                echo "❌ Aborting to allow manual resolution"
                                git cherry-pick --abort || echo "⚠️  Could not abort cherry-pick state"
                                echo "   Please resolve the conflicts and re-run the script"
                                cd .. || error_exit "Cannot return to parent directory"
                                return 0
                                ;;
                            4)
                                echo "⊘ Skipping commit $COMMIT"
                                git cherry-pick --abort || error_exit "Failed to abort cherry-pick"
                                continue
                                ;;
                            *)
                                echo "❌ Invalid choice"
                                git cherry-pick --abort || echo "⚠️  Could not abort cherry-pick state"
                                cd .. || error_exit "Cannot return to parent directory"
                                return 0
                                ;;
                        esac
                    elif git status | grep -q "nothing to commit"; then
                        # Empty commit, skip it
                        git cherry-pick --skip || error_exit "Failed to skip empty commit $COMMIT"
                    else
                        error_exit "Cherry-pick failed for commit $COMMIT"
                    fi
                else
                    # Explicitly set both author and committer dates, reset author to local config to ensure attribution
                    GIT_AUTHOR_DATE="$NOW" GIT_COMMITTER_DATE="$NOW" git commit --amend --no-edit --date "$NOW" --reset-author || error_exit "Failed to amend commit $COMMIT with new dates"
                    # Show confirmation of updated author date for the just-amended commit
                    git show -s --date=iso --pretty=format:'  ✔ %h  %ad  %s' || error_exit "Failed to display amended commit"
                fi
            done
            echo "📜 Latest moved commits on $BASE_BRANCH (author dates shown):"
            git log -n "$NUM" --no-decorate --date=iso --pretty=format:'  %h  %ad  %s'
            # ===== Pre-push validation =====
            # 1) Ensure remote default branch matches target base branch
            DEFAULT_REMOTE_HEAD=$(git remote show origin 2>/dev/null | sed -n 's/.*HEAD branch: \(.*\)$/\1/p' || true)
            if [ -n "$DEFAULT_REMOTE_HEAD" ] && [ "$DEFAULT_REMOTE_HEAD" != "$BASE_BRANCH" ]; then
                error_exit "Remote default branch is '$DEFAULT_REMOTE_HEAD', but you're pushing to '$BASE_BRANCH'. Set the repo default branch correctly or switch base."
            fi
            # 2) Ensure author date day equals today's day for all moved commits
            TODAY=$(date "+%Y-%m-%d")
            BAD_DATE_COUNT=0
            while IFS= read -r AD; do
                if [ -n "$AD" ] && [ "$AD" != "$TODAY" ]; then
                    BAD_DATE_COUNT=$((BAD_DATE_COUNT+1))
                fi
            done < <(git log -n "$NUM" --date=short --pretty=format:'%ad' || true)
            if [ "$BAD_DATE_COUNT" -gt 0 ]; then
                error_exit "Found $BAD_DATE_COUNT commit(s) with author date not equal to today ($TODAY). Aborting push."
            fi
            # 3) Ensure author email matches local git config (so GitHub can attribute contributions)
            EXPECTED_EMAIL=$(git config user.email || true)
            if [ -z "${EXPECTED_EMAIL:-}" ]; then
                error_exit "Git 'user.email' is not set. Configure it (git config user.email you@example.com) before pushing."
            fi
            BAD_EMAIL_COUNT=0
            while IFS= read -r AE; do
                if [ -n "$AE" ] && [ "$AE" != "$EXPECTED_EMAIL" ]; then
                    BAD_EMAIL_COUNT=$((BAD_EMAIL_COUNT+1))
                fi
            done < <(git log -n "$NUM" --pretty=format:'%ae' || true)
            if [ "$BAD_EMAIL_COUNT" -gt 0 ]; then
                error_exit "Found $BAD_EMAIL_COUNT commit(s) with author email not matching '$EXPECTED_EMAIL'. Aborting push."
            fi
            echo "🚀 Pushing to origin $BASE_BRANCH..."
            git push origin "$BASE_BRANCH" || error_exit "Push failed"
            echo "✅ Done! $NUM commits moved with date/time $NOW."
            # ===== Clean up local_commit ONLY AFTER successful push =====
            if git show-ref --verify --quiet refs/heads/local_commit; then
                # Recompute full commit list (oldest → newest)
                REMAINING_COMMITS=$(git rev-list --reverse "$BASE_BRANCH"..local_commit)
                # Build list of commits after the first NUM
                REMAINING_COMMITS=$(echo "$REMAINING_COMMITS" | tail -n +$((NUM+1)))
                if [ -n "$REMAINING_COMMITS" ]; then
                    echo "⚠️  You moved $NUM of $COUNT commits."
                    echo "Do you want to drop those $NUM commits from local_commit (rewrite local history)? [y/N]"
                    CONFIRM="y"
                    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
                        echo "🔄 Rewriting local_commit to keep only remaining commits..."
                        git checkout local_commit || error_exit "Cannot checkout local_commit"
                        git reset --hard "$BASE_BRANCH" || error_exit "Failed to reset local_commit to $BASE_BRANCH"
                        for COMMIT in $REMAINING_COMMITS; do
                            if ! git cherry-pick "$COMMIT" 2>/dev/null; then
                                if git diff --name-only --diff-filter=U | grep -q .; then
                                    error_exit "Merge conflict while rewriting local_commit for commit $COMMIT. Run 'git cherry-pick --abort' and try again."
                                elif git status | grep -q "nothing to commit"; then
                                    git cherry-pick --skip || error_exit "Failed to skip empty commit $COMMIT"
                                else
                                    error_exit "Cherry-pick failed while rewriting local_commit for commit $COMMIT"
                                fi
                            fi
                        done
                        echo "✅ local_commit updated to reflect remaining commits."
                    fi
                else
                    # If we moved all pending commits, align local_commit to base so counts go to 0
                    echo "🔄 Syncing local_commit to $BASE_BRANCH..."
                    git checkout local_commit || error_exit "Cannot checkout local_commit to sync"
                    git reset --hard "$BASE_BRANCH" || error_exit "Failed to reset local_commit to $BASE_BRANCH"
                    echo "✅ local_commit is now aligned with $BASE_BRANCH"
                fi
            fi
            # Restore stashed changes if we stashed earlier
            if [ "$STASHED" -eq 1 ]; then
                echo "🔧 Restoring stashed changes to $ORIG_BRANCH..."
                git checkout "$ORIG_BRANCH" || error_exit "Cannot checkout $ORIG_BRANCH to restore stash"
                if git stash list | head -n 1 | grep -q "git-manager auto-stash before moving commits"; then
                    git stash pop || echo "⚠️ Stash pop had conflicts or failed. Resolve manually."
                else
                    echo "⚠️ No matching stash found. Check 'git stash list'."
                fi
            fi
            ;;
        *)
            ;;
    esac

    cd .. || error_exit "Cannot return to parent directory"
}

# Main interactive loop
while true; do
    scan_and_show
    echo
    read -p "👉 Select a repository number (or 0 to quit): " CHOICE
    if ! [[ "$CHOICE" =~ ^[0-9]+$ ]]; then
        echo "❌ Invalid selection"
        continue
    fi
    if [ "$CHOICE" -eq 0 ]; then
        echo "👋 Bye"
        exit 0
    fi
    if [ "$CHOICE" -gt ${#REPO_MAP[@]} ]; then
        echo "❌ Invalid selection"
        continue
    fi
    INDEX=$((CHOICE - 1))
    repo_menu "$INDEX"
    echo
    read -p "Press Enter to refresh the list..." _
done