#!/bin/bash
set -euo pipefail

error_exit() {
    echo "❌ Error: $1"
    exit 1
}

NOW=$(date "+%Y-%m-%d %H:%M:%S")

REPOS=()
COUNTS=()

echo "🔍 Scanning repositories..."
echo

i=0
for repo in */; do
    if [ -d "$repo/.git" ]; then
        cd "$repo" || error_exit "Cannot enter directory $repo"

        if git show-ref --verify --quiet refs/heads/local_commit && git show-ref --verify --quiet refs/heads/main; then
            COUNT=$(git rev-list --count main..local_commit 2>/dev/null || echo 0)
            if [ "$COUNT" -gt 0 ]; then
                echo "[$((i+1))] $(basename "$repo") → $COUNT local commits"
                REPOS+=("$repo")
                COUNTS+=("$COUNT")
                ((i++))
            fi
        fi
        cd .. || error_exit "Cannot return to parent directory"
    fi
done

if [ ${#REPOS[@]} -eq 0 ]; then
    echo "❌ No repositories with local commits found."
    exit 0
fi

echo
read -p "👉 Select a repository number: " CHOICE

# تبدیل انتخاب کاربر به index 0-based
INDEX=$((CHOICE - 1))
if [ -z "${REPOS[$INDEX]:-}" ]; then
    error_exit "Invalid selection"
fi

REPO="${REPOS[$INDEX]}"
COUNT="${COUNTS[$INDEX]}"

echo "🔢 $COUNT local commits found in $REPO"

read -p "➡ How many commits do you want to push to main? " NUM

if ! [[ "$NUM" =~ ^[0-9]+$ ]] || [ "$NUM" -le 0 ] || [ "$NUM" -gt "$COUNT" ]; then
    error_exit "Invalid number of commits"
fi

cd "$REPO" || error_exit "Cannot enter $REPO"
git checkout local_commit || error_exit "Cannot checkout local_commit"

# گرفتن N commit اول نسبت به main
COMMITS=$(git rev-list --reverse main..local_commit | head -n "$NUM")

if [ -z "$COMMITS" ]; then
    error_exit "No commits to process"
fi

echo "🕒 Rewriting dates for $NUM commits to $NOW..."

# cherry-pick هر commit به ترتیب
git checkout main || error_exit "Cannot checkout main"

for COMMIT in $COMMITS; do
    # اگر commit اثرش روی main هست، skip می‌کنه
    git cherry-pick "$COMMIT" || {
        if git status | grep -q "nothing to commit"; then
            git cherry-pick --skip
        else
            error_exit "Cherry-pick failed for commit $COMMIT"
        fi
    }
    # تاریخ commit را override می‌کنیم
    GIT_AUTHOR_DATE="$NOW" GIT_COMMITTER_DATE="$NOW" git commit --amend --no-edit || true
done

echo "🚀 Pushing to origin main..."
git push origin main || error_exit "Push failed"

echo "✅ Done! $NUM commits pushed with date/time $NOW. Contribution should appear on GitHub."
cd ..

