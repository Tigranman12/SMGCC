#!/usr/bin/env bash
#
# vault-bridge.sh — git bridge between the SMGCC repo and the Obsidian vault.
#
# Pushes this repo's source markdown docs into the vault's Karpathy LLM-Wiki
# ingest folder (_raw/SMGCC/) and commits the vault, so the wiki layer always
# has the latest sources to (re)compile from.
#
# Usage:
#   scripts/vault-bridge.sh            # sync + commit the vault
#   scripts/vault-bridge.sh --install  # install as a git post-commit hook
#   VAULT=/path/to/vault scripts/vault-bridge.sh   # override vault location
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VAULT="${VAULT:-$HOME/obsidian-vault}"
RAW_DIR="$VAULT/_raw/SMGCC"

# Source docs to ingest. Add files here as the project grows (BUGS.md, LOG.md…).
SOURCES=(README.md SMGCC.md PLAN.md RULES.md TASK.md EXPL_STAGE.md BUGS.md LOG.md)

install_hook() {
  local hook="$REPO_DIR/.git/hooks/post-commit"
  cat > "$hook" <<EOF
#!/usr/bin/env bash
# Auto-sync the Obsidian vault after every commit (installed by vault-bridge.sh).
exec "$REPO_DIR/scripts/vault-bridge.sh"
EOF
  chmod +x "$hook"
  echo "Installed post-commit hook -> $hook"
  exit 0
}

[[ "${1:-}" == "--install" ]] && install_hook

# --- sanity checks ---------------------------------------------------------
if [[ ! -d "$VAULT/.git" ]]; then
  echo "vault-bridge: '$VAULT' is not a git repo (set VAULT=... to override)" >&2
  exit 1
fi
mkdir -p "$RAW_DIR"

# --- sync ------------------------------------------------------------------
changed=0
for f in "${SOURCES[@]}"; do
  src="$REPO_DIR/$f"
  [[ -f "$src" ]] || continue
  if ! cmp -s "$src" "$RAW_DIR/$f" 2>/dev/null; then
    cp "$src" "$RAW_DIR/$f"
    changed=1
    echo "  synced $f"
  fi
done

if [[ "$changed" -eq 0 ]]; then
  echo "vault-bridge: sources already up to date, nothing to commit."
  exit 0
fi

# --- commit the vault ------------------------------------------------------
rev="$(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo 'working')"
git -C "$VAULT" add -A "_raw/SMGCC"
git -C "$VAULT" commit -q -m "bridge: ingest SMGCC sources @ $rev" \
  && echo "vault-bridge: committed updated sources to vault ($rev)"

echo "vault-bridge: done. Re-compile the wiki with: 'ingest new sources in _raw/ into the wiki, merging not duplicating.'"
