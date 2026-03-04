#!/bin/bash
# Script to push all documentation and deployment files to GitHub

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

info() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')] INFO: $1${NC}"
}

# Check if we're in the right directory
if [[ ! -f "run.py" || ! -d "backend" ]]; then
    error "Not in the perf-platform directory. Please run from the project root."
fi

# Check if git is initialized
if [[ ! -d ".git" ]]; then
    error "Git repository not initialized. Please run 'git init' first."
fi

# Check if remote is set to the correct repository
REPO_URL="https://github.com/Jake-1226/perf-platform.git"
CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")

if [[ "$CURRENT_REMOTE" != "$REPO_URL" && "$CURRENT_REMOTE" != "git@github.com:Jake-1226/perf-platform.git" ]]; then
    warn "Remote URL doesn't match expected repository."
    info "Setting remote to: $REPO_URL"
    git remote set-url origin "$REPO_URL" || git remote add origin "$REPO_URL"
fi

log "Starting GitHub push process..."

# Stage all new and modified files
log "Staging files for commit..."

# Add all documentation files
git add docs/ || true
git add README.md || true
git add ARCHITECTURE.md || true

# Add all deployment scripts and files
git add scripts/ || true
git add DEPLOY_TO_VM.sh || true
git add DEPLOY_TO_DEV_VM.sh || true
git add DEPLOY_TO_DEV_VM_FIXED.sh || true
git add QUICK_DEPLOY.sh || true

# Add Docker files
git add docker-compose.yml || true
git add Dockerfile || true

# Add deployment guides
git add README_VM_DEPLOYMENT.md || true
git add TEST_FROM_VM.md || true
git add DEPLOYMENT_GUIDE.md || true
git add DOCUMENTATION_UPDATES_SUMMARY.md || true

# Add any other new files
git add . || true

# Check what's being staged
log "Files staged for commit:"
git status --porcelain

# Create commit
log "Creating commit..."
git commit -m "Add comprehensive VM deployment and documentation

Features Added:
- Complete VM deployment automation with one-command setup
- Production-ready systemd service and nginx configuration
- Comprehensive CLI tools for remote test execution and monitoring
- Health monitoring system with automated verification
- Docker deployment support with multi-stage builds
- Complete documentation suite (architecture, API, guides, troubleshooting)
- Automated test execution scripts and scheduler integration
- Security hardening with non-root user and firewall configuration

Documentation Updates:
- Updated main README with VM deployment as recommended option
- Enhanced architecture documentation with deployment diagrams
- Added comprehensive deployment guide with VM and Docker options
- Updated API reference with CLI tool integration
- Added troubleshooting guide for VM deployment issues
- Created complete testing guide for VM deployments

VM Deployment Components:
- Automated deployment scripts (DEPLOY_TO_VM.sh, QUICK_DEPLOY.sh)
- CLI tool for remote control (/opt/perf-platform/cli.py)
- Health monitoring system (/opt/perf-platform/health_check.py)
- Automated test execution (/opt/perf-platform/scripts/run_automated_test.sh)
- Scheduler integration examples (/opt/perf-platform/scripts/scheduler_example.sh)

Docker Support:
- Multi-stage Dockerfile for optimized image size
- Docker Compose configuration with nginx reverse proxy
- Health checks and volume persistence
- Production-ready container deployment

All requirements met for VM deployment, automation, monitoring, and production use." || {
    warn "No changes to commit or commit failed"
}

# Push to GitHub
log "Pushing to GitHub..."
git push -u origin main || {
    error "Failed to push to GitHub. Please check your credentials and repository access."
}

log "✅ Successfully pushed to GitHub!"
echo ""
echo "Repository URL: https://github.com/Jake-1226/perf-platform"
echo ""
echo "Files pushed include:"
echo "  - Complete documentation suite (docs/)"
echo "  - VM deployment scripts (DEPLOY_TO_*.sh, QUICK_DEPLOY.sh)"
echo "  - CLI tools and automation (scripts/)"
echo "  - Docker configuration (docker-compose.yml, Dockerfile)"
echo "  - Deployment guides and documentation"
echo "  - Updated README and ARCHITECTURE.md"
echo ""
echo "Your repository now includes:"
echo "  ✅ One-command VM deployment"
echo "  ✅ Production-ready automation"
echo "  ✅ Comprehensive documentation"
echo "  ✅ CLI tools for remote control"
echo "  ✅ Docker deployment support"
echo "  ✅ Health monitoring system"
echo "  ✅ Automated testing framework"
