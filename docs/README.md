# Performance Test Platform Documentation

**Author:** Manu Nicholas Jacob  
**Email:** ManuNicholas.Jacob@dell.com  
**Last Updated:** March 4, 2026

Welcome to the comprehensive documentation for the Performance Test Platform. This document serves as the main index for all available documentation.

## 📚 Documentation Structure

### Getting Started
- **[Main README](../README.md)** - Project overview, quick start, and basic usage
- **[VM Deployment Guide](../README_VM_DEPLOYMENT.md)** - Quick VM deployment instructions
- **[Deployment Guide](guides/deployment.md)** - Installation, setup, and deployment instructions
- **[Architecture Overview](architecture/overview.md)** - High-level system architecture and design
- **[Testing from VM](../TEST_FROM_VM.md)** - Complete VM testing guide

### Architecture Documentation
- **[System Diagrams](diagrams/system-overview.md)** - Visual architecture diagrams with Mermaid
- **[Benchmark System](architecture/benchmarks.md)** - Detailed benchmark agent and test phase documentation
- **[Telemetry System](architecture/telemetry.md)** - Data collection, storage, and streaming architecture
- **[Report Generation](architecture/reports.md)** - Excel report generation and data analysis

### API and Development
- **[REST API Reference](api/rest-api.md)** - Complete API documentation with examples
- **[Developer Guide](guides/development.md)** - Contributing, coding standards, and development setup
- **[Troubleshooting Guide](guides/troubleshooting.md)** - Common issues and solutions

## 🚀 Quick Navigation

### For Users
1. **New to the platform?** Start with the [main README](../README.md)
2. **Setting up your environment?** Follow the [Deployment Guide](guides/deployment.md)
3. **Running into issues?** Check the [Troubleshooting Guide](guides/troubleshooting.md)

### For Developers
1. **Understanding the system?** Read the [Architecture Overview](architecture/overview.md)
2. **Contributing code?** Follow the [Developer Guide](guides/development.md)
3. **Working with APIs?** See the [REST API Reference](api/rest-api.md)

### For System Administrators
1. **Deployment planning?** Review the [Deployment Guide](guides/deployment.md)
2. **System requirements?** Check the main README and architecture docs
3. **Troubleshooting?** Use the [Troubleshooting Guide](guides/troubleshooting.md)

## 📋 Documentation Index

### By Topic

#### Installation & Setup
- [Prerequisites](../README.md#prerequisites)
- [Installation Steps](../README.md#installation)
- [VM Deployment](../README_VM_DEPLOYMENT.md)
- [Docker Deployment](guides/deployment.md#docker-deployment)
- [Configuration](../README.md#configuration)
- [Network Setup](guides/deployment.md#network-configuration)

#### System Architecture
- [High-Level Architecture](architecture/overview.md#high-level-architecture)
- [Component Architecture](architecture/overview.md#component-architecture)
- [Data Flow Architecture](architecture/overview.md#data-flow-architecture)
- [Technology Stack](../README.md#technology-stack)

#### Benchmarks & Testing
- [Test Phases](../README.md#test-phases--benchmarks)
- [Benchmark Agent](architecture/benchmarks.md#benchmark-agent-bench_agentsh)
- [HPL Configuration](architecture/benchmarks.md#hpl-high-performance-linpack)
- [FIO Configuration](architecture/benchmarks.md#fio-flexible-io-tester)
- [stress-ng Usage](architecture/benchmarks.md#stress-ng-cpu-stress-testing)

#### Telemetry & Data
- [Collection Architecture](telemetry.md#collection-architecture)
- [Database Schema](telemetry.md#database-schema)
- [WebSocket Broadcasting](telemetry.md#websocket-broadcasting)
- [Performance Characteristics](telemetry.md#performance-characteristics)

#### Reports & Analysis
- [Excel Workbook Structure](reports.md#excel-workbook-structure)
- [Data Aggregation](reports.md#data-aggregation-logic)
- [Chart Generation](reports.md#charts-included)
- [CSV Exports](reports.md#csv-exports)

#### API Reference
- [Configuration Endpoints](api/rest-api.md#configuration-endpoints)
- [Connection Endpoints](api/rest-api.md#connection-endpoints)
- [Test Execution](api/rest-api.md#test-execution)
- [Telemetry Endpoints](api/rest-api.md#telemetry-endpoints)
- [WebSocket API](api/rest-api.md#websocket-api)

#### Development
- [Development Environment](guides/development.md#development-environment-setup)
- [Code Organization](guides/development.md#code-organization)
- [Coding Standards](guides/development.md#coding-standards)
- [Testing](guides/development.md#testing)
- [Contributing](guides/development.md#contributing-guidelines)

### By Role

#### End Users
- [Quick Start](../README.md#quick-start)
- [Usage Workflow](../README.md#usage-workflow)
- [Test Phases Explained](../README.md#test-phases--benchmarks)
- [Understanding Reports](../README.md#reports)

#### System Administrators
- [System Requirements](guides/deployment.md#system-requirements)
- [Network Configuration](guides/deployment.md#network-configuration)
- [Security Considerations](guides/deployment.md#security-considerations)
- [Backup and Recovery](guides/deployment.md#backup-and-recovery)

#### Developers
- [Architecture Overview](architecture/overview.md)
- [Adding New Features](guides/development.md#adding-new-features)
- [Performance Optimization](guides/development.md#performance-optimization)
- [Code Review Checklist](guides/development.md#code-review-checklist)

#### Support Engineers
- [Troubleshooting Checklist](guides/troubleshooting.md#quick-diagnostic-checklist)
- [Common Error Messages](guides/troubleshooting.md#common-error-messages)
- [Debug Information Collection](guides/troubleshooting.md#getting-help)
- [Log Locations](guides/troubleshooting.md#log-locations)

## 🔍 Finding Information

### Search Tips

Looking for something specific? Try these search terms:

- **Setup and Installation**: "install", "setup", "requirements", "dependencies"
- **Configuration**: "config", "settings", "environment", "credentials"
- **Benchmarks**: "HPL", "FIO", "stress-ng", "test phases", "workload"
- **Telemetry**: "metrics", "data", "WebSocket", "real-time", "charts"
- **Reports**: "Excel", "analysis", "export", "charts", "summary"
- **API**: "endpoint", "REST", "WebSocket", "payload", "authentication"
- **Troubleshooting**: "error", "issue", "problem", "debug", "fix"

### Document Relationships

```
Main README
    ↓
Deployment Guide ← → Architecture Overview ← → Developer Guide
    ↓                    ↓                    ↓
Troubleshooting ← → API Reference ← → Benchmark System
    ↓                    ↓                    ↓
System Diagrams ← → Telemetry System ← → Report Generation
```

## 🆘 Getting Help

### Self-Service Resources

1. **Search the documentation** - Use the search tips above
2. **Check the troubleshooting guide** - Covers most common issues
3. **Review the API reference** - For integration and development questions
4. **Examine the architecture docs** - For understanding system behavior

### Community Support

- **GitHub Issues** - Report bugs and request features
- **Discussions** - Ask questions and share experiences
- **Wiki** - Community-contributed tips and tricks

### Professional Support

For enterprise support, contact the maintainers through the project repository.

## 📝 Contributing to Documentation

### Documentation Standards

- **Clear and concise** - Use simple language, avoid jargon
- **Structured format** - Use headings, lists, and code blocks
- **Practical examples** - Include real commands and configurations
- **Cross-references** - Link to related documentation
- **Up-to-date** - Keep docs current with code changes

### Making Changes

1. **Fork the repository**
2. **Create a documentation branch**
3. **Make your changes**
4. **Test the documentation** - Follow your own instructions
5. **Submit a pull request**

### Documentation Types

- **Conceptual docs** - Architecture, design decisions, overviews
- **Procedural docs** - Step-by-step guides, tutorials
- **Reference docs** - API specs, configuration options
- **Troubleshooting docs** - Common problems and solutions

---

## 📖 Additional Resources

### External Documentation
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Paramiko Documentation](https://www.paramiko.org/)
- [OpenPyXL Documentation](https://openpyxl.readthedocs.io/)

### Related Projects
- [stress-ng](https://github.com/ColinIanKing/stress-ng) - CPU stress testing
- [FIO](https://github.com/axboe/fio) - Storage I/O testing
- [HPL](http://www.netlib.org/benchmark/hpl/) - High Performance Linpack

### Performance Testing Resources
- [Phoronix Test Suite](https://www.phoronix-test-suite.com/)
- [SPEC CPU Benchmark](https://www.spec.org/cpu/)
- [TPC Benchmarks](https://www.tpc.org/)

---

*This documentation is continuously updated. Last updated: March 2026*
