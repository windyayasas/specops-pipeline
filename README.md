# SpecOps Pipeline

**Multi-agent AI-native spec-driven development pipeline** using LangGraph, Groq LLM, and FastAPI.

Automatically transforms feature specifications into tested, production-ready code through a choreographed workflow of specialized AI agents (planner, implementer, reviewer, refiner, test generator, and quality validator).

## Features

- 📋 **Spec-Driven**: Converts detailed specs (JSON/YAML/Markdown) into implementation plans
- 🤖 **Multi-Agent Orchestration**: LangGraph-based agents for planning, coding, review, and testing
- 🔄 **Iterative Refinement**: Automatic code proposal → review → refinement loops
- ✅ **Quality Gates**: Automated linting (ruff), type checking (mypy), testing (pytest), and security scanning (bandit)
- 📝 **Audit Trail**: Append-only JSONL audit logs for compliance
- 🎯 **Approval Checkpoints**: Pause pipeline for human review at key stages
- 💻 **Dual Interface**: CLI (Typer) and REST API (FastAPI)
- 🐳 **Docker Ready**: Complete Docker/docker-compose setup

## Quick Start

### Prerequisites

- Python 3.11+
- Groq API key (get one at https://console.groq.com)
- pip

### Installation

```bash
# Clone and setup
git clone https://github.com/yourusername/specops-pipeline.git
cd specops-pipeline

# Install in development mode
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### CLI Usage

```bash
# Run full pipeline on a spec
specops run samples/health-check.json

# Check status of a run
specops status run_abc123 --output-dir ./outputs/run_abc123

# List all runs
specops list-runs

# Skip approval checkpoints (CI mode)
specops run samples/health-check.json --skip-approval
```

### API Usage

```bash
# Start API server
uvicorn specops.api:app --reload

# Create a run (POST /runs)
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"spec_file": "samples/health-check.json"}'

# Get run status (GET /runs/{run_id})
curl http://localhost:8000/runs/run_abc123

# Get audit trail
curl http://localhost:8000/runs/run_abc123/audit
```

### Docker

```bash
# Start with docker-compose
docker-compose up

# Run CLI command in container
docker-compose run specops-cli run samples/health-check.json

# Access API at http://localhost:8000
```

## Pipeline Flow

```
Spec File
    ↓
[INTAKE] Parse & Validate Spec
    ↓
[PLANNER] Generate Implementation Plan
    ↓
🔵 Checkpoint 1: Review Plan (approval required)
    ↓
[IMPLEMENTER] Code Generation Loop
    → Proposer: Generate code
    → Reviewer: Evaluate against spec
    → [If approved] Continue
    → [If rejected] Refiner: Fix issues → Reviewer
    ↓
[TEST_GEN] Test Generation Loop
    → Test Proposer: Generate unit/integration tests
    → Test Validator: Verify coverage
    ↓
[QUALITY] Run Quality Gates
    → Ruff: Linting
    → Mypy: Type checking
    → Pytest: Run tests
    → Bandit: Security scan
    ↓
🔵 Checkpoint 2: Review Quality Report (approval required)
    ↓
✅ DEPLOYED
```

## Spec Format

Specs can be JSON, YAML, or Markdown with YAML frontmatter:

```json
{
  "featureObjective": "Implement a health check endpoint...",
  "userStory": "As a DevOps engineer...",
  "businessRules": [
    "Read-only endpoint",
    "No database calls"
  ],
  "acceptanceCriteria": [
    "GET /health returns 200 with status='ok'"
  ],
  "nonFunctionalRequirements": [
    "p95 latency < 50ms"
  ],
  "outOfScope": [
    "Deep dependency checks"
  ]
}
```

## Configuration

Set via `.env`:

```env
GROQ_API_KEY=your_key_here
LOG_LEVEL=INFO
MAX_IMPLEMENTER_ITERATIONS=3
MAX_TEST_ITERATIONS=2
```

## Output Structure

```
outputs/{run_id}/
├── .state.json              # Run state
├── .run.json                # Metadata
├── plan.json                # Generated plan
├── code_summary.json        # Implementation summary
├── test_summary.json        # Test generation summary
├── quality_report.json      # Quality gate results
├── src/
│   └── implementation.py     # Generated code
└── tests/
    └── test_acceptance_criteria.py  # Generated tests
```

## Development

### Run Tests

```bash
pytest tests/ -v --cov=specops
```

### Lint & Type Check

```bash
ruff check specops tests
mypy specops --strict
```

### Format Code

```bash
ruff format specops tests
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design decisions, state management, and workflow orchestration.

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -am 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

All code must pass quality gates (ruff, mypy, pytest, bandit).

## License

MIT License - see LICENSE file for details

## Support

For issues, questions, or contributions, please open a GitHub issue.

---

**Built with ❤️ for spec-driven development**
