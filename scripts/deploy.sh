#!/bin/bash
# SFT GitHub + Netlify Deployment Script
# Run this after setting up GitHub authentication

set -e

PROJECT_DIR="/Users/editsuite/sft-website"
cd "$PROJECT_DIR"

echo "=== SFT Deployment Setup ==="

# Step 1: Check GitHub authentication
echo ""
echo "Step 1: GitHub Authentication"
echo "-----------------------------"
if gh auth status 2>/dev/null; then
    echo "✓ GitHub authenticated"
    GITHUB_USER=$(gh api user --jq '.login' 2>/dev/null)
    echo "  User: $GITHUB_USER"
else
    echo "✗ GitHub not authenticated"
    echo ""
    echo "Option A — PAT (recommended):"
    echo "  1. Go to https://github.com/settings/tokens/new"
    echo "  2. Name: 'SFT Deploy'"
    echo "  3. Scope: 'repo' (full)"
    echo "  4. Generate and copy token"
    echo "  5. Run: gh auth login --with-token <token>"
    echo ""
    echo "Option B — Browser:"
    echo "  Run: gh auth login --web"
    echo ""
    read -p "Press Enter after authenticating, or Ctrl+C to cancel..."
    GITHUB_USER=$(gh api user --jq '.login')
fi

# Step 2: Create repository
echo ""
echo "Step 2: Create GitHub Repository"
echo "---------------------------------"
REPO_NAME="sft-website"
if gh repo view "$GITHUB_USER/$REPO_NAME" 2>/dev/null; then
    echo "✓ Repository already exists: $GITHUB_USER/$REPO_NAME"
else
    gh repo create "$REPO_NAME" --public --description "Samsung Firmware Tool — Device detection, firmware management, and flashing guidance" --source=. --remote=origin --push 2>&1
    echo "✓ Repository created and pushed: $GITHUB_USER/$REPO_NAME"
fi

# Step 3: Configure remote and push
echo ""
echo "Step 3: Push to GitHub"
echo "----------------------"
git remote remove origin 2>/dev/null || true
git remote add origin "git@github.com:$GITHUB_USER/$REPO_NAME.git"
git push -u origin main --force 2>&1
echo "✓ Code pushed to GitHub"

# Step 4: Set up Netlify
echo ""
echo "Step 4: Netlify Deployment"
echo "---------------------------"
echo ""
echo "To deploy on Netlify:"
echo "  1. Go to https://app.netlify.com/start"
echo "  2. Connect to GitHub → Select '$REPO_NAME'"
echo "  3. Build command: (leave empty — static site)"
echo "  4. Publish directory: ."
echo "  5. Click 'Deploy site'"
echo ""
echo "Or install Netlify CLI:"
echo "  npm install -g netlify-cli"
echo "  netlify init"
echo "  netlify deploy --prod"
echo ""

# Step 5: Verify
echo "Step 5: Verification"
echo "--------------------"
echo "GitHub: https://github.com/$GITHUB_USER/$REPO_NAME"
echo "Local:  http://localhost:5000"
echo ""
echo "Daily updates configured via cron (9am daily)"
echo "Logs: $PROJECT_DIR/logs/daily_update.log"
