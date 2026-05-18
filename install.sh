#!/bin/bash

# ==============================================================================
# CV Automation Pipeline Installer
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

check_dep() {
    command -v "$1" &> /dev/null
}

print_status() {
    echo "├─ $1"
}

print_success() {
    echo "✅ $1"
}

print_error() {
    echo "❌ $1"
}

print_warning() {
    echo "⚠️  $1"
}

print_section() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  $1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ─────────────────────────────────────────────────────────────────────────────
# 0. Ensure `uv` is installed (Package manager preference)
# ─────────────────────────────────────────────────────────────────────────────

print_section "STEP 1: Package Manager Setup"

if ! check_dep uv; then
    print_status "🔁 'uv' not found — Installing uv (rust-based package manager)..."
    if check_dep curl; then
        curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null || {
            print_warning "uv standalone installation failed. Trying system package manager..."
            case "$OSTYPE" in
                darwin*) 
                    if check_dep brew; then
                        brew install uv >/dev/null 2>&1
                    else
                        print_error "Homebrew not found. Please install uv manually: https://github.com/astral-sh/uv"
                        exit 1
                    fi
                    ;;
                linux-gnu*)
                    if check_dep apt; then
                        sudo apt update -qq && sudo apt install -y uv >/dev/null 2>&1
                    elif check_dep yum; then
                        sudo yum install -y uv >/dev/null 2>&1
                    else
                        print_error "Could not install uv. Please install manually: https://github.com/astral-sh/uv"
                        exit 1
                    fi
                    ;;
                *)
                    print_error "Could not auto-install uv on this OS. Please install manually: https://github.com/astral-sh/uv"
                    exit 1
                    ;;
            esac
        }
        
        # Ensure uv is in PATH
        [[ -d "$HOME/.cargo/bin" ]] && export PATH="$HOME/.cargo/bin:$PATH"
        [[ -d "$HOME/.local/bin" ]] && export PATH="$HOME/.local/bin:$PATH"
    else
        print_error "'curl' not found. Please install 'curl' or 'uv' manually."
        exit 1
    fi
fi

if check_dep uv; then
    print_success "'uv' is installed and ready."
else
    print_error "Failed to verify 'uv' installation."
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# 1. Check System Dependencies (LaTeX, PDF tools)
# ─────────────────────────────────────────────────────────────────────────────

print_section "STEP 2: System Dependencies"

MISSING_DEPS=()

if ! check_dep pdflatex; then
    MISSING_DEPS+=("pdflatex (LaTeX distribution)")
fi

if ! check_dep xelatex; then
    MISSING_DEPS+=("xelatex (LaTeX Unicode support)")
fi

if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
    print_warning "Found ${#MISSING_DEPS[@]} missing system dependencies:"
    for dep in "${MISSING_DEPS[@]}"; do
        print_warning "  - $dep"
    done
    
    print_status "Installing LaTeX (TexLive)..."
    case "$OSTYPE" in
        darwin*)
            if check_dep brew; then
                print_status "Installing via Homebrew..."
                brew install --cask mactex-no-gui >/dev/null 2>&1 || \
                brew install basictex >/dev/null 2>&1 || \
                print_warning "LaTeX installation may need manual setup. Visit: https://www.tug.org/mactex/"
            else
                print_warning "Please install MacTeX or BasicTeX manually: https://www.tug.org/mactex/"
            fi
            ;;
        linux-gnu*)
            if check_dep apt; then
                sudo apt-get update -qq && sudo apt-get install -y texlive-xetex texlive-latex-extra texlive-fonts-recommended >/dev/null 2>&1
            elif check_dep yum; then
                sudo yum install -y texlive-xetex texlive-latex texlive-fonts >/dev/null 2>&1
            elif check_dep dnf; then
                sudo dnf install -y texlive-xetex texlive-latex texlive-fonts >/dev/null 2>&1
            else
                print_warning "Please install TexLive manually for your Linux distribution."
            fi
            ;;
        *)
            print_warning "Please install TexLive/LaTeX manually for your OS."
            ;;
    esac
else
    print_success "All system dependencies present."
fi

# ─────────────────────────────────────────────────────────────────────────────
# 2. Create Virtual Environment
# ─────────────────────────────────────────────────────────────────────────────

print_section "STEP 3: Python Virtual Environment"

if [[ -d "$VENV_DIR" ]]; then
    print_status "Virtual environment already exists at $VENV_DIR"
else
    print_status "Creating virtual environment..."
    uv venv "$VENV_DIR" --python 3.11 >/dev/null 2>&1
    if [[ $? -eq 0 ]]; then
        print_success "Virtual environment created."
    else
        print_error "Failed to create virtual environment."
        exit 1
    fi
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate" 2>/dev/null || {
    print_error "Failed to activate virtual environment."
    exit 1
}

# ─────────────────────────────────────────────────────────────────────────────
# 3. Install Python Dependencies
# ─────────────────────────────────────────────────────────────────────────────

print_section "STEP 4: Python Dependencies"

if [[ ! -f "$PROJECT_DIR/requirements.txt" ]]; then
    print_error "requirements.txt not found at $PROJECT_DIR/requirements.txt"
    exit 1
fi

print_status "Installing Python packages (this may take a minute)..."
uv pip install -r "$PROJECT_DIR/requirements.txt" >/dev/null 2>&1

if [[ $? -eq 0 ]]; then
    print_success "All Python packages installed."
else
    print_error "Failed to install Python packages. Try manually with:"
    echo "    source $VENV_DIR/bin/activate"
    echo "    pip install -r $PROJECT_DIR/requirements.txt"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# 4. Configuration (Environment Variables)
# ─────────────────────────────────────────────────────────────────────────────

print_section "STEP 5: Configuration"

ENV_FILE="$PROJECT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$PROJECT_DIR/.env.example" ]]; then
        print_status "Copying .env.example to .env..."
        cp "$PROJECT_DIR/.env.example" "$ENV_FILE"
        print_success ".env created. You may need to add API keys manually."
    fi
else
    print_status ".env file already exists."
fi

# ─────────────────────────────────────────────────────────────────────────────
# 5. Verify Installation
# ─────────────────────────────────────────────────────────────────────────────

print_section "STEP 6: Verification"

# Check if main dependencies are importable
python -c "import langchain_openai; import loguru; import requests; print('✅ Core imports successful')" 2>/dev/null
if [[ $? -ne 0 ]]; then
    print_warning "Some imports failed. This might be OK if you're not using all features."
fi

# ─────────────────────────────────────────────────────────────────────────────
# 6. Usage Instructions
# ─────────────────────────────────────────────────────────────────────────────

print_section "INSTALLATION COMPLETE ✨"

echo ""
echo "Next steps:"
echo ""
echo "  1. Activate the virtual environment:"
echo "     source $VENV_DIR/bin/activate"
echo ""
echo "  2. Verify installation:"
echo "     python main.py --help"
echo ""
echo "  3. Try a preview:"
echo "     python main.py preview --role it --lang fr"
echo ""
echo "  4. Or apply to a job posting:"
echo "     python main.py apply --url <job_url> --lang auto"
echo ""

# Suggest adding to shell config
ACTIVE_SHELL=$(basename "$SHELL")
case "$ACTIVE_SHELL" in
    zsh)
        SHELL_RC="$HOME/.zshrc"
        ;;
    bash)
        SHELL_RC="$HOME/.bashrc"
        ;;
    *)
        SHELL_RC=""
        ;;
esac

if [[ -n "$SHELL_RC" ]] && ! grep -q "CV.*venv.*activate" "$SHELL_RC" 2>/dev/null; then
    echo ""
    echo "💡 Tip: Add this to $SHELL_RC to auto-activate on new terminals:"
    echo "   # Auto-activate CV venv"
    echo "   if [[ -d '$VENV_DIR' ]]; then"
    echo "       source '$VENV_DIR/bin/activate'"
    echo "   fi"
fi

echo ""
