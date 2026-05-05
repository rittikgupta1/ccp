#!/usr/bin/env bash
set -euo pipefail

# ================================================================
# CCP — Central Context Package — Setup Script
# Run once per team member. Sets up the knowledge base locally.
# ================================================================

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${BLUE}[CCP]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail()  { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

CCP_REPO="${CCP_REPO:-}"
CCP_DIR="${CCP_DIR:-$HOME/ccp}"

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   CCP — Central Context Package       ║"
echo "  ║   Team Knowledge Base Setup            ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# ── Step 1: Check prerequisites ──
info "Checking prerequisites..."

if ! command -v git &>/dev/null; then
  fail "git not found. Install: brew install git (Mac) or apt install git (Linux)"
fi
ok "git found"

if ! command -v python3 &>/dev/null; then
  fail "python3 not found. Install: brew install python3"
fi
ok "python3 found"

if ! command -v gh &>/dev/null; then
  warn "GitHub CLI (gh) not found. Installing..."
  if [[ "$(uname)" == "Darwin" ]]; then
    brew install gh 2>/dev/null || fail "Could not install gh. Run: brew install gh"
  else
    fail "Install GitHub CLI: https://cli.github.com/"
  fi
fi
ok "GitHub CLI found"

# ── Step 2: GitHub auth ──
info "Checking GitHub authentication..."
if gh auth status &>/dev/null 2>&1; then
  ACCOUNT=$(gh api user --jq '.login' 2>/dev/null || echo "authenticated")
  ok "Logged in as ${ACCOUNT}"
else
  info "Opening browser for GitHub login..."
  gh auth login --web
fi

# ── Step 3: Get user identity ──
echo ""
read -p "Your name (lowercase, no spaces — e.g., ritik, abhiram): " CCP_USER
if [ -z "$CCP_USER" ]; then
  fail "Name required."
fi

PS3="Select your team: "
select CCP_TEAM in data ops product engineering; do
  if [ -n "$CCP_TEAM" ]; then
    break
  fi
done
echo ""

# ── Step 4: Clone or update repo ──
if [ -z "$CCP_REPO" ]; then
  read -p "GitHub repo URL (e.g., git@github.com:snabbit-tech/ccp.git): " CCP_REPO
fi

if [ -d "$CCP_DIR" ]; then
  info "Repo already cloned at $CCP_DIR — pulling latest..."
  git -C "$CCP_DIR" pull --rebase || warn "Pull failed, continuing with existing"
else
  info "Cloning $CCP_REPO into $CCP_DIR..."
  git clone "$CCP_REPO" "$CCP_DIR"
fi
ok "Repo ready at $CCP_DIR"

# ── Step 5: Create personal folder ──
mkdir -p "$CCP_DIR/teams/$CCP_TEAM"
ok "Team folder ready: teams/$CCP_TEAM"

# ── Step 6: Install Python deps ──
info "Installing Python dependencies..."
pip3 install --quiet pyyaml 2>/dev/null || warn "pyyaml install failed"
pip3 install --quiet "anthropic[vertex]" 2>/dev/null || warn "anthropic install failed (AI review won't work)"
ok "Python deps installed"

# ── Step 7: Set up shell config ──
if [[ -n "${ZSH_VERSION:-}" ]] || [[ "$SHELL" == */zsh ]]; then
  PROFILE="$HOME/.zshrc"
else
  PROFILE="$HOME/.bashrc"
fi

if ! grep -q "CCP_USER" "$PROFILE" 2>/dev/null; then
  cat >> "$PROFILE" <<EOF

# ── CCP — Central Context Package ──
export CCP_USER="$CCP_USER"
export CCP_TEAM="$CCP_TEAM"
export CCP_ROOT="$CCP_DIR"
alias kb='python3 $CCP_DIR/scripts/kb.py'
alias kb-private='CCP_SKIP_REVIEW=1 kb'
EOF
  ok "Added CCP config to $PROFILE"
else
  warn "CCP config already in $PROFILE"
fi

# Export for current session
export CCP_USER="$CCP_USER"
export CCP_TEAM="$CCP_TEAM"
export CCP_ROOT="$CCP_DIR"

# ── Step 8: Set up auto-sync (pull every 2 hours) ──
info "Setting up auto-sync..."

if [[ "$(uname)" == "Darwin" ]]; then
  PLIST_DIR="$HOME/Library/LaunchAgents"
  PLIST_FILE="$PLIST_DIR/com.ccp.autosync.plist"
  mkdir -p "$PLIST_DIR"

  cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ccp.autosync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/git</string>
        <string>-C</string>
        <string>${CCP_DIR}</string>
        <string>pull</string>
        <string>--rebase</string>
        <string>-q</string>
    </array>
    <key>StartInterval</key>
    <integer>7200</integer>
    <key>StandardOutPath</key>
    <string>/tmp/ccp-sync.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ccp-sync.log</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF

  launchctl unload "$PLIST_FILE" 2>/dev/null || true
  launchctl load "$PLIST_FILE" 2>/dev/null || warn "Could not load launchd job"
  ok "Auto-sync every 2 hours (launchd)"
else
  CRON_CMD="0 */2 * * * cd $CCP_DIR && git pull --rebase -q >> /tmp/ccp-sync.log 2>&1"
  (crontab -l 2>/dev/null | grep -v "ccp.*git pull"; echo "$CRON_CMD") | crontab -
  ok "Auto-sync every 2 hours (cron)"
fi

# ── Step 9: Optional — Claude Desktop MCP server ──
echo ""
read -p "Set up CCP for Claude Desktop app? (y/N): " SETUP_MCP
if [[ "$SETUP_MCP" =~ ^[Yy]$ ]]; then
  CLAUDE_CONFIG_DIR="$HOME/Library/Application Support/Claude"
  CLAUDE_CONFIG="$CLAUDE_CONFIG_DIR/claude_desktop_config.json"

  if [ -d "$CLAUDE_CONFIG_DIR" ]; then
    python3 - <<PYEOF
import json, os

config_path = os.path.expanduser("$CLAUDE_CONFIG")
if os.path.exists(config_path):
    with open(config_path) as f:
        config = json.load(f)
else:
    config = {}

config.setdefault("mcpServers", {})
config["mcpServers"]["ccp"] = {
    "command": "python3",
    "args": ["$CCP_DIR/scripts/mcp_server.py"],
    "env": {
        "CCP_USER": "$CCP_USER",
        "CCP_TEAM": "$CCP_TEAM",
        "CCP_ROOT": "$CCP_DIR"
    }
}

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)
PYEOF
    ok "Claude Desktop MCP server configured"
    info "Restart Claude Desktop to activate."
  else
    warn "Claude Desktop config dir not found. Skipping MCP setup."
  fi
fi

# ── Step 10: Test ──
echo ""
info "Running test..."
python3 "$CCP_DIR/scripts/kb.py" "CCP Setup Test — $CCP_USER" --team "$CCP_TEAM" --type insight --dry-run

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "Setup complete!"
echo ""
echo "  Your identity:  $CCP_USER ($CCP_TEAM team)"
echo "  Repo location:  $CCP_DIR"
echo "  Auto-sync:      Every 2 hours"
echo ""
echo "  Usage:"
echo "    kb \"Title\" --team $CCP_TEAM --type analysis     # save knowledge"
echo "    kb \"Title\" --team $CCP_TEAM --file output.md    # save from file"
echo "    echo \"content\" | kb \"Title\" --team $CCP_TEAM    # save from pipe"
echo "    kb \"Title\" --team $CCP_TEAM --dry-run           # preview only"
echo ""
echo "  Restart your shell or run: source $PROFILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
