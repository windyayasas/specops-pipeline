# SpecOps Architecture

## Design Overview

SpecOps Pipeline implements a **choreography-based multi-agent system** using LangGraph, where specialized AI agents collaborate to transform specifications into tested, production-ready code.

## Core Architecture

### 1. **Agent Orchestration (LangGraph)**

The pipeline uses LangGraph's `StateGraph` for workflow coordination:

- **Planner Graph**: Single-node workflow that converts spec → plan
- **Implementer Graph**: Multi-node with conditional routing (propose → review → refine loops)
- **Test Gen Graph**: Two-node workflow with iterative validation

Each graph represents immutable state transitions with LLM-powered nodes.

### 2. **State Management**

State is fully immutable within LangGraph workflows. Persistence happens via:

- **RunStore**: JSON-based state snapshots (`.state.json`, `.run.json`)
- **AuditLogger**: Append-only JSONL audit trail (`.audit.jsonl`)
- **Artifact Storage**: Code, tests, and reports in organized directories

### 3. **LLM Integration**

**GroqClient** wraps Groq API with:

- Exponential backoff retry logic (3 retries by default)
- Prompt hashing for audit logging (deterministic, no PII)
- JSON response parsing with validation
- Rate limit handling

**Jinja2 Templates** render context-specific prompts:
- `planner_prompt.j2`: Spec → plan
- `proposer_prompt.j2`: Spec + plan → code
- `reviewer_prompt.j2`: Code + spec → feedback
- `refiner_prompt.j2`: Code + feedback → refined code
- `test_proposer_prompt.j2`: Code + criteria → tests
- `test_validator_prompt.j2`: Tests → coverage validation

### 4. **Quality Assurance**

**Quality Gate** sequentially runs:
1. **Ruff** (linting)
2. **Mypy** (type checking)
3. **Pytest** (unit/integration tests)
4. **Bandit** (security scanning)

Tools are invoked via subprocess with isolated error handling. Any failure is reported in JSON quality_report.

### 5. **Approval Checkpoints**

Two human approval gates:

- **Checkpoint 1** (Post-Planning): Review design approach, risks, tasks
- **Checkpoint 2** (Post-Quality): Review code quality, test coverage, security

CLI uses `typer.confirm()` for interactive approval. API exposes `POST /runs/{id}/approve?checkpoint={n}` endpoint.

## Module Structure

```
specops/
├── __init__.py              # Version info
├── __main__.py              # CLI entry point
├── config.py                # Pydantic Settings
├── cli.py                   # Typer CLI app
├── api.py                   # FastAPI REST app
│
├── models/
│   ├── spec.py             # SpecModel (schema validation)
│   ├── plan.py             # PlanOutput, RunState
│   └── audit.py            # AuditEvent
│
├── observability/
│   └── logging.py           # Structlog setup + run_id context
│
├── llm/
│   ├── client.py            # GroqClient wrapper
│   ├── prompts.py           # Template rendering functions
│   └── prompts/
│       ├── planner_prompt.j2
│       ├── proposer_prompt.j2
│       ├── reviewer_prompt.j2
│       ├── refiner_prompt.j2
│       ├── test_proposer_prompt.j2
│       └── test_validator_prompt.j2
│
├── agents/
│   ├── state_graphs.py      # LangGraph TypedDicts
│   ├── planner_node.py      # Planner node
│   ├── implementer_nodes.py # Proposer, Reviewer, Refiner
│   └── test_gen_nodes.py    # Test Proposer, Validator
│
├── stages/
│   ├── intake.py            # Spec parser (JSON/YAML/Markdown)
│   ├── planner_agent.py     # Planner workflow executor
│   ├── implementer_agent.py # Implementer workflow executor
│   ├── test_gen_agent.py    # Test gen workflow executor
│   ├── quality_gate.py      # Quality orchestrator
│   └── approval.py          # Approval checkpoints
│
├── sandbox/
│   └── path_validator.py    # Safe path validation for file ops
│
├── storage/
│   └── run_store.py         # Persistent state storage
│
└── audit/
    └── logger.py            # Append-only JSONL audit trail
```

## Data Flow

### Full Pipeline Invocation (CLI)

```
parse_spec_file()
    ↓
run_planner_workflow()
    → LangGraph: planner_node()
    → Output: plan.json
    ↓
[Checkpoint 1]
    ↓
run_implementer_workflow()
    → LangGraph iteration loop:
        → proposer_node() [LLM call]
        → reviewer_node() [LLM call]
        → conditional: approved? → END : refine?
        → refiner_node() [LLM call] → back to review
    → Output: src/implementation.py + code_summary.json
    ↓
run_test_gen_workflow()
    → LangGraph iteration loop:
        → test_proposer_node() [LLM call]
        → test_validator_node() [LLM call]
        → conditional: valid? → END : refine?
    → Output: tests/test_acceptance_criteria.py + test_summary.json
    ↓
run_quality_gate()
    → subprocess: ruff, mypy, pytest, bandit
    → Output: quality_report.json
    ↓
[Checkpoint 2]
    ↓
save_state() → .state.json, .audit.jsonl
```

## Workflow Conditional Routing

### Implementer Graph

```python
graph.add_conditional_edges(
    "reviewer",
    should_refine,  # fn(state) → "refine" | "done"
    {"refine": "refiner", "done": END}
)
```

**Logic**: If `approved=True` OR iterations ≥ max_implementer_iterations → END, else → refiner

### Test Gen Graph

```python
graph.add_conditional_edges(
    "test_validator",
    should_refine_tests,  # fn(state) → "refine" | "done"
    {"refine": "test_proposer", "done": END}
)
```

**Logic**: If `valid=True` OR iterations ≥ max_test_iterations → END, else → test_proposer

## Error Handling

1. **Spec Parsing**: ValidationError with field paths; re-raise as ValueError
2. **LLM Calls**: RateLimitError → exponential backoff; other errors → RuntimeError
3. **JSON Parsing**: JSONDecodeError → ValueError with context
4. **Quality Gate**: Subprocess failures logged and collected; QualityGateError on first critical failure
5. **Approval**: TypeError if checkpoint unknown; no approval = user cancellation

All errors logged via structlog with run_id context for audit tracing.

## Security Considerations

1. **Path Safety**: `path_validator.py` rejects absolute paths, `..`, system directories
2. **API Input**: Pydantic models validate all inputs
3. **Audit Logging**: All significant actions logged; append-only design prevents tampering
4. **Secret Management**: Groq API key via `.env`, never logged
5. **Subprocess**: Quality gate tools run in isolated subprocesses with timeout
6. **Code Execution**: LLM-generated code NOT executed; only validated by Bandit scanner

## Testing Strategy

### Unit Tests

- Spec parsing (JSON, YAML, Markdown variants)
- Path validation
- Audit logging
- State persistence

### Integration Tests

- Full pipeline simulation (mocked LLM)
- Quality gate subprocess execution
- Approval checkpoint flow
- Artifact generation

### Test Coverage

Target: ≥60% (enforced in pytest.ini)

## Configuration & Extensibility

### Settings (pydantic-settings)

```python
class Settings(BaseSettings):
    groq_api_key: str
    log_level: str = "INFO"
    max_implementer_iterations: int = 3
    max_test_iterations: int = 2
    allowed_paths: list = ["outputs"]
    
    class Config:
        env_file = ".env"
```

### Custom Nodes

To add a new agent:

1. Define `XyzState(TypedDict)` in `state_graphs.py`
2. Implement `xyz_node(state: XyzState) → XyzState` in `xyz_nodes.py`
3. Build graph with `StateGraph(XyzState)` and add node
4. Wrap with executor function in `stages/xyz_agent.py`

### Custom Prompts

1. Add `xyz_prompt.j2` to `llm/prompts/`
2. Add render function to `llm/prompts.py`
3. Call in node implementation

## Performance Characteristics

- **LLM Latency**: ~2-5s per call (Groq API)
- **Planner**: Single call, ~2-5s
- **Implementer**: 1-3 iterations × (propose + review + maybe refine), ~6-15s total
- **Test Gen**: 1-2 iterations × (propose + validate), ~4-10s total
- **Quality Gate**: ~10-30s (subprocess invocations)
- **Total Pipeline**: ~30-60s per spec (Groq latency dominated)

Memory: ~200MB for Python + LangGraph state (no data accumulation)

## Deployment

### Docker

Single-stage Dockerfile (Python 3.11-slim), ~1.2GB image:
- Base Python 3.11
- pip install -e ".[dev]"
- Volume mount for specs and outputs

### CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):
1. Ruff check
2. Mypy strict
3. Pytest + coverage
4. Bandit security scan
5. Docker build (push skipped on PR)

## Future Enhancements

- [ ] Streaming LLM responses for real-time feedback
- [ ] Custom agent types (database schema gen, API doc gen)
- [ ] Approval webhooks (Slack, Teams)
- [ ] Run comparison/diff tool
- [ ] Spec versioning and change tracking
- [ ] Multi-model fallback (if Groq rate-limited, use OpenAI)
- [ ] Distributed execution (queue-based agent dispatch)
