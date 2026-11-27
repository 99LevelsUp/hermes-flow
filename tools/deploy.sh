#!/usr/bin/env bash
# Install the live copies Hermes runs from this checkout (see AGENTS.md).
# Refuses when the checkout is not a clean origin/main, or when a live copy was changed since the
# last deploy (that change must be carried into the repo first, or it would be lost).
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
hermes_home="${HERMES_HOME:-$HOME/.hermes}"
skill_live="$hermes_home/skills/software-development/roadmap-issue-flow"
script_live="$hermes_home/scripts/issue-triage.py"
stamp="$hermes_home/data/hermes-flow/deployed-commit"
force=0
[[ "${1:-}" == "--force" ]] && force=1

cd "$repo"
git fetch -q origin
if [[ -n "$(git status --porcelain)" || "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]]; then
	echo "deploy: the checkout must be a clean origin/main" >&2
	exit 1
fi

# drift: live copies must equal what the last deploy installed
if [[ -f "$stamp" && $force -eq 0 ]]; then
	last="$(cat "$stamp")"
	tmp="$(mktemp -d)"
	trap 'rm -rf "$tmp"' EXIT
	git archive "$last" skills/roadmap-issue-flow | tar -x -C "$tmp"
	if ! diff -r -q -x scripts "$tmp/skills/roadmap-issue-flow" "$skill_live" >/dev/null ||
		! cmp -s "$tmp/skills/roadmap-issue-flow/scripts/issue-triage.py" "$script_live"; then
		echo "deploy: a live copy changed since $last; carry the change into the repo first:" >&2
		diff -r -u -x scripts "$tmp/skills/roadmap-issue-flow" "$skill_live" >&2 || true
		diff -u "$tmp/skills/roadmap-issue-flow/scripts/issue-triage.py" "$script_live" >&2 || true
		exit 1
	fi
fi

mkdir -p "$skill_live" "$(dirname "$script_live")" "$(dirname "$stamp")"
rsync -a --delete --exclude scripts skills/roadmap-issue-flow/ "$skill_live/"
install -m 0644 skills/roadmap-issue-flow/scripts/issue-triage.py "$script_live.tmp"
mv "$script_live.tmp" "$script_live"
git rev-parse HEAD >"$stamp"
echo "deployed $(git rev-parse --short HEAD) to $hermes_home"
