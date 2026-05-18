#!/usr/bin/env bash
# =============================================================
# compile.sh — Build CV templates
#
# Usage (from repo root):
#   ./compile.sh                        # build ALL CV_*.tex across all template folders
#   ./compile.sh ai                     # shortcut → CV_AI_Data_Lato  (templates/lato/)
#   ./compile.sh it                     # shortcut → CV_IT_Infra_Lato (templates/lato/)
#   ./compile.sh phd                    # shortcut → CV_PhD_Lato      (templates/lato/)
#   ./compile.sh CV_Banking             # any CV_ filename (auto-finds the folder)
#
# To add a new template style: create templates/<style>/ with CV_*.tex inside.
# No changes to this script needed.
#
# Shared data: templates/shared/personal_data.tex|json
# Output: output/<filename>.pdf  (git-tracked)
# =============================================================

set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
TEMPLATES_ROOT="$REPO_ROOT/templates"
OUTPUT_DIR="$REPO_ROOT/output"
TMP_DIR="/tmp"

compile() {
  local name="$1"
  # Auto-find which template subfolder contains this file
  local tex_file
  tex_file=$(find "$TEMPLATES_ROOT" -name "${name}.tex" -not -path "*/shared/*" | head -1)

  if [[ -z "$tex_file" ]]; then
    echo "❌  Not found: ${name}.tex in any templates/ subfolder"
    return 1
  fi

  local dir
  dir="$(dirname "$tex_file")"

  echo "⚙️   Compiling $name  ($dir) ..."
  (cd "$dir" && pdflatex -output-directory="$TMP_DIR" -interaction=nonstopmode "${name}.tex") \
    > "$TMP_DIR/${name}_compile.log" 2>&1

  if grep -q "Output written" "$TMP_DIR/${name}_compile.log"; then
    cp "$TMP_DIR/${name}.pdf" "$OUTPUT_DIR/${name}.pdf"
    echo "✅  $OUTPUT_DIR/${name}.pdf"
  else
    echo "❌  Compilation failed — see $TMP_DIR/${name}_compile.log"
    tail -20 "$TMP_DIR/${name}_compile.log"
    return 1
  fi
}

compile_all() {
  local found=0
  while IFS= read -r tex; do
    compile "$(basename "$tex" .tex)"
    found=1
  done < <(find "$TEMPLATES_ROOT" -name "CV_*.tex" -not -path "*/shared/*" | sort)
  [[ $found -eq 1 ]] || echo "⚠️  No CV_*.tex files found under $TEMPLATES_ROOT"
}

# Shortcuts
case "${1:-all}" in
  ai)  compile CV_AI_Data_Lato ;;
  it)  compile CV_IT_Infra_Lato ;;
  phd) compile CV_PhD_Lato ;;
  all) compile_all ;;
  *)   compile "$1" ;;
esac

echo ""
echo "📂  Output: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"/*.pdf 2>/dev/null || true
