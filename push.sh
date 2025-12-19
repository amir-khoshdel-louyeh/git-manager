#!/bin/bash
set -euo pipefail

error_exit() {
    echo "❌ Error: $1"
    exit 1
}

NOW=$(date "+%Y-%m-%d %H:%M:%S")

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
                echo "❌ Working tree not clean. Commit or stash changes first."
                cd .. || error_exit "Cannot return to parent directory"
                return 0
            fi
            COMMITS=$(git rev-list --reverse "$BASE_BRANCH"..local_commit | head -n "$NUM")
            if [ -z "$COMMITS" ]; then
                echo "❌ No commits to process"
                cd .. || error_exit "Cannot return to parent directory"
                return 0
            fi
            echo "🕒 Rewriting dates for $NUM commits to $NOW..."
            git checkout "$BASE_BRANCH" || error_exit "Cannot checkout $BASE_BRANCH"
            for COMMIT in $COMMITS; do
                git cherry-pick "$COMMIT" || {
                    if git status | grep -q "nothing to commit"; then
                        git cherry-pick --skip
                    else
                        error_exit "Cherry-pick failed for commit $COMMIT"
                    fi
                }
                GIT_AUTHOR_DATE="$NOW" GIT_COMMITTER_DATE="$NOW" git commit --amend --no-edit || true
            done
            echo "🚀 Pushing to origin $BASE_BRANCH..."
            git push origin "$BASE_BRANCH" || error_exit "Push failed"
            echo "✅ Done! $NUM commits moved with date/time $NOW."
            # Offer to rewrite local_commit queue to drop the moved commits
            if git show-ref --verify --quiet refs/heads/local_commit; then
                # Recompute full commit list (oldest → newest)
                REMAINING_COMMITS=$(git rev-list --reverse "$BASE_BRANCH"..local_commit)
                # Build list of commits after the first NUM
                REMAINING_COMMITS=$(echo "$REMAINING_COMMITS" | tail -n +$((NUM+1)))
                if [ -n "$REMAINING_COMMITS" ]; then
                    echo "⚠️  You moved $NUM of $COUNT commits."
                    read -p "Do you want to drop those $NUM commits from local_commit (rewrite local history)? [y/N] " CONFIRM
                    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
                        echo "🔄 Rewriting local_commit to keep only remaining commits..."
                        git checkout local_commit || error_exit "Cannot checkout local_commit"
                        git reset --hard "$BASE_BRANCH" || error_exit "Failed to reset local_commit to $BASE_BRANCH"
                        for COMMIT in $REMAINING_COMMITS; do
                            git cherry-pick "$COMMIT" || {
                                if git status | grep -q "nothing to commit"; then
                                    git cherry-pick --skip
                                else
                                    error_exit "Cherry-pick failed while rewriting local_commit for commit $COMMIT"
                                fi
                            }
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

