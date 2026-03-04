#!/bin/bash
# Final GitHub Push Script for Performance Test Platform
# Author: Manu Nicholas Jacob (ManuNicholas.Jacob@dell.com)
# Repository: https://github.com/Jake-1226/Perf-Watt-Platform

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

# Repository configuration
REPO_URL="https://github.com/Jake-1226/Perf-Watt-Platform.git"
REPO_NAME="Perf-Watt-Platform"

log "Starting final GitHub push to $REPO_NAME..."

# Check if we're in the right directory
if [[ ! -f "run.py" || ! -d "backend" ]]; then
    error "Not in the perf-platform directory. Please run from the project root."
fi

# Update remote URL to the new repository
log "Updating remote URL to: $REPO_URL"
git remote set-url origin "$REPO_URL" || git remote add origin "$REPO_URL"

# Verify remote configuration
CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
if [[ "$CURRENT_REMOTE" != "$REPO_URL" ]]; then
    error "Failed to set remote URL. Current: $CURRENT_REMOTE, Expected: $REPO_URL"
fi

log "Remote URL configured successfully"

# Stage all files for final push
log "Staging all files for final commit..."

# Add all documentation files
git add README.md ARCHITECTURE.md || true
git add docs/ || true

# Add deployment and automation files
git add scripts/ DEPLOY_TO_VM.sh DEPLOY_TO_DEV_VM.sh QUICK_DEPLOY.sh || true
git add README_VM_DEPLOYMENT.md TEST_FROM_VM.md DEPLOYMENT_GUIDE.md || true

# Add Docker files
git add docker-compose.yml Dockerfile || true

# Add all platform code
git add backend/ static/ run.py requirements.txt || true

# Add any additional files
git add . || true

# Check what's being staged
log "Files staged for commit:"
git status --porcelain | head -20

# Create final comprehensive commit
log "Creating final commit for GitHub publication..."
git commit -m "🚀 Publish Performance Test Platform to GitHub

Author: Manu Nicholas Jacob (ManuNicholas.Jacob@dell.com)
Repository: https://github.com/Jake-1226/Perf-Watt-Platform

📚 COMPLETE DOCUMENTATION SUITE
• Comprehensive README.md with platform overview and quick start
• Detailed architecture documentation (docs/architecture/)
• System diagrams and visualizations (docs/diagrams/)
• Complete API reference and WebSocket documentation (docs/api/)
• Deployment guides and automation (docs/guides/)
• Developer contribution and troubleshooting guides

🏗️ PLATFORM FEATURES
• Full-stack benchmarking and power telemetry tool for Dell servers
• CPU stress testing using stress-ng (100% and 50% targets)
• Storage benchmarking with FIO on all NVMe data drives
• Combined CPU + I/O workloads for realistic testing
• Real-time telemetry collection from OS and iDRAC
• Live dashboard with WebSocket streaming
• Comprehensive Excel report generation

🚀 DEPLOYMENT & AUTOMATION
• VM deployment automation with one-command setup
• Docker containerization with multi-stage builds
• Production deployment with systemd and nginx
• CLI tools for remote automation and monitoring
• Health monitoring and service management

📊 TECHNICAL DOCUMENTATION
• Backend architecture: FastAPI, SSH management, telemetry system
• Frontend architecture: React/HTM, WebSocket integration, real-time charts
• Database schema: SQLite with platform and per-run databases
• API endpoints: REST API with complete reference and examples
• System diagrams: ASCII and Mermaid visualizations

🔧 DEVELOPER RESOURCES
• Development environment setup and configuration
• Code organization and module responsibilities
• Testing strategies and debugging techniques
• Contribution guidelines and code review process
• Performance monitoring and optimization

🐛 SUPPORT & TROUBLESHOOTING
• Common issues and solutions guide
• VM deployment troubleshooting
• API and WebSocket debugging
• Performance optimization tips

✨ PRODUCTION READY
• Security hardening with non-root user and firewall
• Backup and recovery procedures
• Monitoring and alerting capabilities
• Scalable architecture design

All documentation includes author attribution and is ready for:
• Developer onboarding and contribution
• System administrator deployment and maintenance
• Performance testing and analysis
• Production environment operation

Ready for immediate use and collaboration!

🌟 Repository: https://github.com/Jake-1226/Perf-Watt-Platform
📧 Contact: ManuNicholas.Jacob@dell.com" || {
    warn "No changes to commit (repository may be up to date)"
}

# Push to GitHub
log "Pushing to GitHub repository: $REPO_NAME"
log "Repository URL: $REPO_URL"

# First push to set upstream
git push -u origin master || {
    error "Failed to push to GitHub. Please check:"
    echo "1. Repository exists at: $REPO_URL"
    echo "2. You have push permissions to the repository"
    echo "3. Your GitHub authentication is configured"
}

log "✅ Successfully pushed to GitHub!"
echo ""
echo "🎉 Performance Test Platform is now live on GitHub!"
echo ""
echo "📚 Repository: https://github.com/Jake-1226/Perf-Watt-Platform"
echo ""
echo "📖 Documentation includes:"
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
echo "🚀 Ready for:"
echo "  • Developer onboarding and contribution"
echo "  • System administrator deployment and maintenance"
echo "  • Performance testing and analysis"
echo "  • Production environment operation"
echo ""
echo "👤 Author: Manu Nicholas Jacob"
echo "📧 Email: ManuNicholas.Jacob@dell.com"
echo ""
echo "🎯 Next Steps:"
echo "  1. Visit your repository: https://github.com/Jake-1226/Perf-Watt-Platform"
echo "  2. Verify documentation displays correctly"
echo "  3. Share with your team and stakeholders"
echo "  4. Start accepting contributions and issues"
