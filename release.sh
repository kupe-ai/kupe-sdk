#!/usr/bin/env bash
# Ship kupe to GitHub + PyPI.
#
#   ./release.sh                 bump patch (0.3.2 -> 0.3.3), commit, tag, push, watch PyPI
#   ./release.sh 0.4.0           set that version
#   ./release.sh 0.3.3 -m "..."  version + release notes
#   ./release.sh --dry-run       print the next version, do not push
#
# Publish is the tag workflow: push vX.Y.Z -> .github/workflows/publish.yml
set -euo pipefail
cd "$(dirname "$0")"

DRY=0
VERSION=""
NOTES=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    -m|--message) NOTES="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '2,11p' "$0"
      exit 0
      ;;
    -*)
      echo "unknown flag: $1" >&2
      exit 2
      ;;
    *)
      VERSION="$1"
      shift
      ;;
  esac
done

current() {
  python3 - <<'PY'
import pathlib, re
text = pathlib.Path("pyproject.toml").read_text()
m = re.search(r'^version = "([^"]+)"', text, re.M)
print(m.group(1) if m else "")
PY
}

bump_patch() {
  python3 -c '
import sys
a, b, c = map(int, sys.argv[1].split("."))
print(f"{a}.{b}.{c+1}")
' "$1"
}

set_versions() {
  local v="$1"
  python3 - "$v" <<'PY'
import pathlib, re, sys
v = sys.argv[1]
for path, pat, repl in [
    ("pyproject.toml", r'^version = "[^"]+"', f'version = "{v}"'),
    ("src/kupe/__init__.py", r'^__version__ = "[^"]+"', f'__version__ = "{v}"'),
    ("src/kupe/client.py", r'^__version__ = "[^"]+"', f'__version__ = "{v}"'),
]:
    p = pathlib.Path(path)
    text = p.read_text()
    new, n = re.subn(pat, repl, text, count=1, flags=re.M)
    if n != 1:
        raise SystemExit(f"could not set version in {path}")
    p.write_text(new)
print(v)
PY
}

CUR="$(current)"
[[ -n "$CUR" ]] || { echo "could not read version from pyproject.toml" >&2; exit 1; }
if [[ -z "$VERSION" ]]; then
  VERSION="$(bump_patch "$CUR")"
fi
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "version must look like 0.3.3, got: $VERSION" >&2
  exit 2
fi
if git rev-parse "v$VERSION" >/dev/null 2>&1; then
  echo "tag v$VERSION already exists" >&2
  exit 1
fi

echo "==> $CUR -> $VERSION"

if [[ "$DRY" == 1 ]]; then
  echo "dry-run: would commit, tag v$VERSION, push, gh release, watch PyPI"
  exit 0
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$branch" != "main" ]]; then
  echo "release from main (on $branch)" >&2
  exit 1
fi

set_versions "$VERSION" >/dev/null
git add pyproject.toml src/kupe/__init__.py src/kupe/client.py
git add -u src/kupe

if git diff --cached --quiet; then
  echo "nothing to ship" >&2
  exit 1
fi

if [[ -z "$NOTES" ]]; then
  NOTES="$(git log --pretty=format:'- %s' "v$CUR"..HEAD 2>/dev/null || true)"
fi
if [[ -z "$NOTES" ]]; then
  NOTES="Release $VERSION"
fi

headline="${NOTES%%$'\n'*}"
git commit -m "$(cat <<EOF
Release $VERSION: ${headline#"- "}

EOF
)"

git tag -a "v$VERSION" -m "$(cat <<EOF
Release $VERSION

$NOTES
EOF
)"

git push origin HEAD
git push origin "v$VERSION"

gh release create "v$VERSION" --title "$VERSION" --notes "$(cat <<EOF
$NOTES

\`\`\`bash
pip install -U 'kupe[thinkspark]'
\`\`\`
EOF
)"

echo "==> waiting for PyPI publish"
RUN_ID="$(gh run list --workflow=publish.yml --limit 1 --json databaseId,headBranch --jq \
  ".[] | select(.headBranch==\"v$VERSION\") | .databaseId" | head -1)"
if [[ -z "$RUN_ID" ]]; then
  sleep 3
  RUN_ID="$(gh run list --workflow=publish.yml --limit 1 --json databaseId,headBranch --jq \
    ".[] | select(.headBranch==\"v$VERSION\") | .databaseId" | head -1)"
fi
if [[ -n "$RUN_ID" ]]; then
  gh run watch "$RUN_ID" --exit-status
else
  echo "publish workflow not visible yet — check: gh run list --workflow=publish.yml"
fi

echo "==> https://github.com/kupe-ai/kupe-sdk/releases/tag/v$VERSION"
echo "==> https://pypi.org/project/kupe/$VERSION/"
echo "    pip install -U 'kupe[thinkspark]'"
