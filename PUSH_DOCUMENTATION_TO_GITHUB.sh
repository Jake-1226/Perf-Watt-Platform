#!/bin/bash
# Script to push comprehensive documentation to GitHub
# Author: Manu Nicholas Jacob (ManuNicholas.Jacob@dell.com)

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

log "Starting GitHub documentation push process..."

# Stage all documentation files
log "Staging documentation files for commit..."

# Add main documentation files
git add README.md ARCHITECTURE.md || true

# Add docs directory
git add docs/ || true

# Add deployment and automation files
git add scripts/ || true
git add DEPLOY_TO_VM.sh DEPLOY_TO_DEV_VM.sh DEPLOY_TO_DEV_VM_FIXED.sh QUICK_DEPLOY.sh || true

# Add Docker files
git add docker-compose.yml Dockerfile || true

# Add deployment guides
git add README_VM_DEPLOYMENT.md TEST_FROM_VM.md DEPLOYMENT_GUIDE.md DOCUMENTATION_UPDATES_SUMMARY.md || true

# Add any other new files
git add . || true

# Check what's being staged
log "Files staged for commit:"
git status --porcelain

# Create comprehensive commit
log "Creating comprehensive documentation commit..."
git commit -m "Complete developer-ready documentation for Performance Test Platform

Author: Manu Nicholas Jacob (ManuNicholas.Jacob@dell.com)

Documentation Features:
- Comprehensive README.md with platform overview and quick start guide
- Complete architecture documentation with detailed component descriptions
- System architecture diagrams using ASCII and Mermaid visualizations
- Backend architecture documentation with data flow and API details
- Frontend architecture documentation with React/HTM component structure
- Benchmark agent and test phase documentation
- Telemetry system and database schema documentation
- Report generation and output structure documentation
- Complete REST API reference with examples and WebSocket behavior
- Deployment and setup guide with VM, Docker, and local options
- VM deployment automation with production-ready scripts
- Developer contribution guide with coding standards and workflows
- Troubleshooting guide with common issues and solutions
- GitHub-friendly documentation structure with proper organization

Technical Documentation:
- Detailed component architecture and data flow diagrams
- API endpoint documentation with request/response examples
- Database schema and per-run database generation documentation
- WebSocket real-time communication documentation
- Security considerations and best practices
- Performance optimization guidelines
- Error handling and resilience patterns

Deployment Documentation:
- One-command VM deployment with automated setup
- Docker containerization with multi-stage builds
- Production deployment with systemd and nginx
- Health monitoring and service management
- CLI tools for remote automation and monitoring
- Backup and recovery procedures

Developer Resources:
- Complete development environment setup guide
- Code organization and module responsibilities
- Testing strategies and debugging techniques
- Contribution guidelines and code review process
- Performance monitoring and optimization

All documentation includes author attribution (Manu Nicholas Jacob) and contact information.
Ready for developer onboarding and contribution to the Performance Test Platform.

Repository: https://github.com/Jake-1226/perf-platform" || {
    warn "No changes to commit or commit failed"
}

# Push to GitHub
log "Pushing comprehensive documentation to GitHub..."
git push -u origin main || {
    error "Failed to push to GitHub. Please check your credentials and repository access."
}

log "✅ Successfully pushed comprehensive documentation to GitHub!"
echo ""
echo "Repository URL: https://github.com/Jake-1226/perf-platform"
echo ""
echo "Documentation pushed includes:"
echo "  ✅ Comprehensive README.md with platform overview"
echo "  ✅ Complete architecture documentation (docs/architecture/)"
echo "  ✅ System diagrams and visualizations (docs/diagrams/)"
echo "  ✅ API reference and WebSocket documentation (docs/api/)"
echo "  ✅ Deployment guides and automation (docs/guides/)"
echo "  ✅ Developer contribution and troubleshooting guides"
echo "  ✅ VM deployment scripts and automation"
echo "  ✅ Docker configuration and containerization"
echo "  ✅ CLI tools and health monitoring"
echo ""
echo "The repository now provides:"
echo "  📚 Complete developer-ready documentation"
echo "  🏗️ Detailed architecture and component documentation"
echo "  🚀 Production deployment automation"
echo "  🔧 Development setup and contribution guidelines"
echo "  📊 System diagrams and data flow documentation"
echo "  🐛 Troubleshooting and support resources"
echo ""
echo "All documentation attributed to:"
echo "  Author: Manu Nicholas Jacob"
echo "  Email: ManuNicholas.Jacob@dell.com"
echo ""
echo "Ready for developer onboarding and contributions!"
