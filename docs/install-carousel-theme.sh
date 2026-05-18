#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# install-carousel-theme.sh
# Installs the LinkedIn carousel theme into amir-cli
# Usage: bash install-carousel-theme.sh
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

AMIR_CLI="/Users/su6i/@-github/amir-cli"
THEMES_DIR="$AMIR_CLI/lib/themes"
RENDERER="$AMIR_CLI/lib/nodejs/render_puppeteer.js"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CSS_SRC="$SCRIPT_DIR/carousel.css"

# ── 1. Themes directory ──────────────────────────────────────────
mkdir -p "$THEMES_DIR"
cp "$CSS_SRC" "$THEMES_DIR/carousel.css"
echo "✅ Theme installed: $THEMES_DIR/carousel.css"

# ── 2. Patch render_puppeteer.js to support --theme ─────────────
if grep -q '"--theme"' "$RENDERER" 2>/dev/null || grep -q 'themeArg' "$RENDERER" 2>/dev/null; then
    echo "ℹ️  render_puppeteer.js already patched — skipping."
else
    # Backup
    cp "$RENDERER" "${RENDERER}.bak"
    echo "📦 Backed up renderer → ${RENDERER}.bak"

    # Inject theme support: add themeArg parameter and theme CSS loading
    node - "$RENDERER" "$THEMES_DIR" << 'JSEOF'
const fs = require('fs');
const path = require('path');
const rendererPath = process.argv[2];
const themesDir = process.argv[3];
let src = fs.readFileSync(rendererPath, 'utf8');

// 1. Add themeArg to function signature
src = src.replace(
  'async function renderMarkdown(inputPath, outputPath, fontPath, userDataDir, freeSize, pageWidthArg, pageHeightArg)',
  'async function renderMarkdown(inputPath, outputPath, fontPath, userDataDir, freeSize, pageWidthArg, pageHeightArg, themeArg)'
);

// 2. Inject theme CSS loading right after "const style = `" line
const themeInjection = `
    // ── Theme support ──────────────────────────────────────────
    let themeCSS = '';
    if (themeArg && themeArg.trim() !== '') {
        const themePath = path.join('${themesDir}', themeArg.trim() + '.css');
        if (fs.existsSync(themePath)) {
            themeCSS = fs.readFileSync(themePath, 'utf8');
        } else {
            console.error(\`⚠️  Theme not found: \${themePath}\`);
        }
    }
`;

src = src.replace(
  "    const style = `",
  themeInjection + "\n    const style = `"
);

// 3. Inject themeCSS at end of style block (before closing backtick)
// The style block ends with: `;\n\n    const fullHtml
src = src.replace(
  /(`;\s*\n\s*const fullHtml)/,
  '${themeCSS}\n    `;\n\n    const fullHtml'
);

// 4. Pass themeArg from CLI args
src = src.replace(
  'renderMarkdown(args[0], args[1], args[2], args[3], args[4], args[5], args[6])',
  'renderMarkdown(args[0], args[1], args[2], args[3], args[4], args[5], args[6], args[7])'
);

fs.writeFileSync(rendererPath, src);
console.log('✅ render_puppeteer.js patched with --theme support');
JSEOF

fi

# ── 3. Patch pdf.sh to pass --theme argument ────────────────────
PDF_SH="$AMIR_CLI/lib/commands/pdf.sh"
if grep -q '"--theme"' "$PDF_SH" 2>/dev/null || grep -q 'theme=' "$PDF_SH" 2>/dev/null; then
    echo "ℹ️  pdf.sh already patched — skipping."
else
    cp "$PDF_SH" "${PDF_SH}.bak"
    echo "📦 Backed up pdf.sh → ${PDF_SH}.bak"

    # Use Python for reliable multiline sed replacement
    python3 - "$PDF_SH" << 'PYEOF'
import re, sys

path = sys.argv[1]
src = open(path).read()

# Add --theme to argument parsing (after --no-deskew line)
src = src.replace(
    "            --no-deskew|--no-straighten) do_deskew=false; shift ;;",
    "            --no-deskew|--no-straighten) do_deskew=false; shift ;;\n            --theme) theme=\"$2\"; shift; shift ;;"
)

# Initialize theme variable near top of function
src = src.replace(
    "    local inputs=() output=\"\" engine=\"puppeteer\"\n    local raw_output=\"\" free_size=false",
    "    local inputs=() output=\"\" engine=\"puppeteer\" theme=\"\"\n    local raw_output=\"\" free_size=false"
)

# Pass theme to node call
src = src.replace(
    'node "${LIB_DIR}/nodejs/render_puppeteer.js" "$abs_file" "$tmp_out" "$font_fa" "$chrome_profile" "$free_size" "$page_width" "$page_height" &>/dev/null && success=true',
    'node "${LIB_DIR}/nodejs/render_puppeteer.js" "$abs_file" "$tmp_out" "$font_fa" "$chrome_profile" "$free_size" "$page_width" "$page_height" "$theme" &>/dev/null && success=true'
)

open(path, 'w').write(src)
print("✅ pdf.sh patched with --theme support")
PYEOF

fi

echo ""
echo "🎉 Setup complete! You can now use:"
echo "   amir pdf --theme carousel IT_Job_Market_Stats.fr.md"
echo "   amir pdf --theme carousel --page-width 1080 --page-height 1080 ..."
