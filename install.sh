#!/usr/bin/env bash
# =============================================================================
# ApplyForge — Zero-Touch Installer
# Fresh clone → working project, no user intervention.
# Implements the `bootstrap-installer` skill (agent-constitution).
#   curl -fsSL .../install.sh | bash   OR   ./install.sh
# =============================================================================
set -euo pipefail

# ─── 0. Preamble ─────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
success() { printf "${GREEN}✅ %s${NC}\n" "$1"; }
warn()    { printf "${YELLOW}⚠️  %s${NC}\n" "$1"; }
error()   { printf "${RED}❌ %s${NC}\n" "$1" >&2; exit 1; }
section() { printf "\n${BLUE}── %s ──${NC}\n" "$1"; }

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# ─── 1. OS detection ─────────────────────────────────────────────────────────
section "OS"
case "$(uname -s)" in
  Darwin) OS=mac ;  PKG="brew install" ;;
  Linux)  OS=linux; PKG="sudo apt-get install -y" ;;
  *) error "Unsupported OS: $(uname -s)" ;;
esac
success "$OS"

# ─── 2. uv (mandatory; never pip) ────────────────────────────────────────────
section "uv"
if ! command -v uv >/dev/null 2>&1; then
  warn "uv not found — installing"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || error "uv install failed — see https://docs.astral.sh/uv/"
uv self update >/dev/null 2>&1 || true
success "uv $(uv --version 2>/dev/null | awk '{print $2}')"

# ─── 3. System deps (idempotent; optional = warn only) ───────────────────────
section "System dependencies"
have() { command -v "$1" >/dev/null 2>&1; }

if have pdflatex && have xelatex; then
  success "LaTeX present"
else
  warn "LaTeX missing — installing TeX (required for CV compilation)"
  if [ "$OS" = mac ]; then
    have brew || error "Homebrew required: https://brew.sh"
    brew install --cask mactex-no-gui 2>/dev/null || brew install basictex 2>/dev/null \
      || warn "install MacTeX manually: https://www.tug.org/mactex/"
  else
    sudo apt-get update -qq
    sudo apt-get install -y texlive-xetex texlive-latex-extra texlive-fonts-recommended \
      || warn "install TeX Live manually"
  fi
fi

if have tesseract; then
  success "tesseract present"
else
  warn "tesseract missing (optional — OCR for image CVs); installing"
  $PKG tesseract ${OS:+} 2>/dev/null || $PKG tesseract-ocr 2>/dev/null \
    || warn "OCR disabled — install tesseract to enable image parsing"
fi

# ─── 4. Python environment ───────────────────────────────────────────────────
section "Python environment"
uv sync
success "dependencies synced (uv.lock)"

# ─── 5. Constitution bootstrap (single source of truth — NO submodule) ───────
section "Agent constitution"
CENTRAL="${AGENT_CONSTITUTION_DIR:-$HOME/@-github/agent-constitution}"
REMOTE="git@github.com:su6i/agent-constitution.git"
if [ -d "$CENTRAL/.git" ]; then
  git -C "$CENTRAL" pull --ff-only >/dev/null 2>&1 && success "constitution updated" \
    || warn "could not fast-forward $CENTRAL (local changes?) — using current state"
else
  warn "cloning constitution → $CENTRAL"
  mkdir -p "$(dirname "$CENTRAL")"
  git clone "$REMOTE" "$CENTRAL" || error "failed to clone constitution"
fi
mkdir -p .agent
if [ -e .agent/constitution ] && [ ! -L .agent/constitution ]; then
  error ".agent/constitution exists and is not a symlink — remove it first (old submodule?)"
fi
ln -sfn "$CENTRAL" .agent/constitution
success "linked .agent/constitution → $CENTRAL"

# ─── 6. Register skills into ~/.claude/skills (so /skills sees them) ─────────
# Version-safe: skills from the single central source are symlinked (idempotent).
# If another project already registered a skill from a DIFFERENT source, only
# overwrite when our version is strictly newer — never clobber a newer skill.
section "Skills registration"
SKILLS_SRC="$CENTRAL/skills"
SKILLS_DST="$HOME/.claude/skills"
skill_version() { grep -m1 '^version:' "$1" 2>/dev/null | sed 's/^version:[[:space:]]*//' | tr -d '"' || true; }
is_newer() { [ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1)" = "$1" ]; }
if [ -d "$SKILLS_SRC" ]; then
  mkdir -p "$SKILLS_DST"
  reg=0; upd=0; kept=0
  for f in "$SKILLS_SRC"/*.md; do
    [ -e "$f" ] || continue
    name="$(basename "$f" .md)"; dst="$SKILLS_DST/$name/SKILL.md"
    if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$f" ]; then
      ln -sfn "$f" "$dst"; reg=$((reg+1)); continue          # same source → idempotent
    fi
    if [ -e "$dst" ]; then                                    # registered from a DIFFERENT source
      vnew="$(skill_version "$f")"; vold="$(skill_version "$dst")"
      vnew="${vnew:-0.0.0}"; vold="${vold:-0.0.0}"
      if is_newer "$vnew" "$vold"; then
        mkdir -p "$SKILLS_DST/$name"; ln -sfn "$f" "$dst"; upd=$((upd+1))
      else
        warn "kept $name (registered v$vold ≥ our v$vnew)"; kept=$((kept+1))
      fi
    else
      mkdir -p "$SKILLS_DST/$name"; ln -sfn "$f" "$dst"; reg=$((reg+1))
    fi
  done
  success "skills: $reg linked, $upd updated (newer), $kept kept (existing newer) → $SKILLS_DST"
  printf "   run /skills to view (restart Claude Code if absent)\n"
else
  warn "no skills dir at $SKILLS_SRC"
fi

# ─── 7. Config / secrets (vault — never in the repo) ─────────────────────────
section "Configuration"
VAULT="${APPLYFORGE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/agent-projects/applyforge}"
mkdir -p "$VAULT"/{data,shared,references,secrets,workspace}
ENV="$VAULT/secrets/.env"
if [ -f "$ENV" ]; then
  success ".env present (vault) — left untouched"
else
  cp .env.example "$ENV"
  warn "seeded $ENV from .env.example — add your provider keys (DEEPSEEK/OPENAI/GEMINI, TELEGRAM)"
fi

# ─── 8. Verify ───────────────────────────────────────────────────────────────
section "Verify"
if uv run python -c "import src.core.settings" >/dev/null 2>&1; then
  success "import OK"
else
  error "verification failed — settings did not import"
fi
printf "\n${GREEN}ApplyForge ready.${NC}  Try:  uv run python main.py spontaneous ai-en\n"
