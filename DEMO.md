# SpecOps Pipeline: Step-by-Step Demo

This guide walks you through a complete end-to-end pipeline run, demonstrating all 7 requirements in action.

## Prerequisites

```bash
# Set up your environment
export GROQ_API_KEY="your_groq_api_key_here"

# Install dependencies (if not already done)
pip install -e ".[dev]"
```

## Demo Scenario

We'll use the included `sample_spec.json` which defines an internal health-check endpoint feature. This is a realistic microservice requirement that showcases the full pipeline.

### Spec Overview
- **Feature**: Internal `/health` endpoint for monitoring
- **Acceptance Criteria**: HTTP 200, JSON response, uptime tracking
- **NFRs**: <50ms latency, no sensitive data exposed, structured logging
- **Risks**: Must not call downstream services (avoid cascading failures)

---

## Step 1: Parse Specification (Requirement 1: Spec Intake)

```bash
python3 -c "
from specops.stages.intake import parse_spec_file
from specops.models.spec import SpecModel

# Parse the example spec
spec = parse_spec_file('sample_spec.json')
print('✓ Spec parsed successfully')
print(f'  Feature: {spec.feature_objective[:60]}...')
print(f'  Acceptance Criteria: {len(spec.acceptance_criteria)} items')
print(f'  Business Rules: {len(spec.business_rules)} items')
"
```

**Output:**
```
✓ Spec parsed successfully
  Feature: Implement a secure, lightweight internal system health status...
  Acceptance Criteria: 9 items
  Business Rules: 8 items
```

---

## Step 2: Run Full Pipeline (All 7 Requirements)

```bash
# Option A: Non-interactive mode (for CI/automation)
python3 -m specops run sample_spec.json --skip-approval

# Option B: Interactive mode (shows approvals)
python3 -m specops run sample_spec.json
```

### What Happens During Execution:

**Pipeline Flow:**
```
1. [Intake] Parse spec ✓
2. [Planner] Generate plan (Requirement 2)
   → Generates tasks, design summary, risks, test strategy
3. [Approval #1] Human review checkpoint (Requirement 6)
   → CLI: "Approve plan? (Y/n)"
4. [Implementer] Generate code (Requirement 3)
   → Proposal → Review → Refine loop (max 3 iterations)
   → Sandbox validates all file paths
5. [Test Gen] Generate tests (Requirement 4)
   → Proposal → Validation loop (max 2 iterations)
   → Maps each test to acceptance criterion
6. [Quality Gate] Automated validation (Requirement 5)
   → ruff lint ✓
   → mypy type check ✓
   → pytest ✓
   → bandit security ✓
7. [Approval #2] Final approval (Requirement 6)
   → CLI: "Approve quality report? (Y/n)"
8. [Audit] Append-only JSONL trail (Requirement 7)
   → Full traceability logged
```

---

## Step 3: Monitor Run Status

In a separate terminal, check run progress:

```bash
# List all runs
python3 -m specops list-runs

# Check specific run status
RUN_ID="run_$(date +%s)"
python3 -m specops status $RUN_ID --output-dir ./outputs/$RUN_ID
```

**Output:**
```
Run: run_1717856400
Status: AWAITING_APPROVAL
Current Stage: Planning
Next Action: Approve plan to proceed with implementation
```

---

## Step 4: Inspect Generated Artifacts

After approval and completion:

```bash
# View generated code
ls -la outputs/run_*/src/
cat outputs/run_*/src/*.py

# View generated tests
ls -la outputs/run_*/tests/
cat outputs/run_*/tests/test_acceptance_criteria.py

# View quality report
cat outputs/run_*/quality_report.json | jq .

# View audit trail (full traceability)
cat outputs/run_*/audit.jsonl | jq .
```

### Key Artifacts:

| Artifact | Location | Contains |
|----------|----------|----------|
| **Specification** | `outputs/{run_id}/spec.json` | Parsed input spec |
| **Plan** | `outputs/{run_id}/plan.json` | Tasks, design, risks |
| **Code** | `outputs/{run_id}/src/*.py` | Generated implementation |
| **Tests** | `outputs/{run_id}/tests/` | Unit + integration + acceptance tests |
| **Quality Report** | `outputs/{run_id}/quality_report.json` | Ruff, Mypy, Pytest, Bandit results |
| **Audit Trail** | `outputs/{run_id}/audit.jsonl` | Every decision logged (immutable) |

---

## Step 5: Inspect Audit Trail (Requirement 7: Auditability)

The audit trail is your proof of governance and reproducibility:

```bash
# Pretty-print audit trail
cat outputs/run_*/audit.jsonl | jq .

# Filter by event type
cat outputs/run_*/audit.jsonl | jq 'select(.event_type == "proposal_created")'

# View all approval events
cat outputs/run_*/audit.jsonl | jq 'select(.event_type | contains("approval"))'
```

**Example Audit Events:**
```json
{
  "timestamp": "2024-01-15T10:23:45Z",
  "run_id": "run_1705325025",
  "stage": "intake",
  "event_type": "spec_loaded",
  "status": "success",
  "details": {
    "spec_hash": "abc123...",
    "format": "json"
  }
}

{
  "timestamp": "2024-01-15T10:23:46Z",
  "run_id": "run_1705325025",
  "stage": "planner",
  "event_type": "plan_generated",
  "status": "success",
  "details": {
    "tasks_count": 5,
    "risks_identified": 2,
    "llm_tokens_used": 1240
  }
}

{
  "timestamp": "2024-01-15T10:23:52Z",
  "run_id": "run_1705325025",
  "stage": "implementer",
  "event_type": "proposal_created",
  "status": "success",
  "details": {
    "proposal_number": 1,
    "files": ["health_check.py", "models.py"]
  }
}

{
  "timestamp": "2024-01-15T10:23:55Z",
  "run_id": "run_1705325025",
  "stage": "implementer",
  "event_type": "review_feedback",
  "status": "success",
  "details": {
    "verdict": "needs_refinement",
    "issues": [
      "Missing error handling for edge case",
      "Response should include timestamp"
    ]
  }
}

{
  "timestamp": "2024-01-15T10:24:02Z",
  "run_id": "run_1705325025",
  "stage": "implementer",
  "event_type": "approval_checkpoint_1_requested",
  "status": "pending",
  "actor": "system"
}

{
  "timestamp": "2024-01-15T10:24:15Z",
  "run_id": "run_1705325025",
  "stage": "implementer",
  "event_type": "approval_checkpoint_1_granted",
  "status": "success",
  "actor": "user@example.com"
}
```

---

## Step 6: Use REST API (Production Mode)

For integration with CI/CD pipelines:

```bash
# Start API server
uvicorn specops.api:app --reload --port 8000 &

# Create a new run
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d "{\"spec_file\": \"sample_spec.json\"}"

# Response:
# {
#   "run_id": "run_abc123",
#   "status": "CREATED",
#   "spec": {...}
# }

# Poll run status
curl http://localhost:8000/runs/run_abc123

# Get audit trail
curl http://localhost:8000/runs/run_abc123/audit

# Approve at checkpoint
curl -X POST http://localhost:8000/runs/run_abc123/approve \
  -H "Content-Type: application/json" \
  -d "{\"approval_type\": \"checkpoint_1\", \"actor\": \"ci-system\"}"
```

---

## Step 7: Docker Deployment

For production-like testing:

```bash
# Build and run with docker-compose
docker-compose up

# In another terminal, trigger a run via API
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d "{\"spec_file\": \"sample_spec.json\"}"
```

---

## Step 8: Verify Quality Gates (Requirement 5)

The quality report shows all 4 gates:

```bash
cat outputs/run_*/quality_report.json
```

**Expected Output:**
```json
{
  "passed": true,
  "tools": {
    "ruff": {
      "passed": true,
      "errors": []
    },
    "mypy": {
      "passed": true,
      "errors": []
    },
    "pytest": {
      "passed": true,
      "tests_run": 12,
      "failures": 0,
      "coverage": 0.87
    },
    "bandit": {
      "passed": true,
      "issues": []
    }
  }
}
```

---

## Verification Checklist

After running the demo, verify:

- [ ] **Requirement 1 (Spec Intake)**: `spec.json` exists in outputs
- [ ] **Requirement 2 (Planning)**: `plan.json` generated with tasks + design + risks
- [ ] **Requirement 3 (Implementation)**: Code files generated in `src/`
- [ ] **Requirement 4 (Tests)**: Test files generated in `tests/` with criterion mapping
- [ ] **Requirement 5 (Quality)**: `quality_report.json` shows all 4 tools passed
- [ ] **Requirement 6 (Approval)**: Audit log shows 2 approval checkpoints
- [ ] **Requirement 7 (Auditability)**: `audit.jsonl` append-only trail with full history

---

## Troubleshooting

### GROQ_API_KEY not set
```
Error: GROQ_API_KEY environment variable not found
```
**Solution:**
```bash
export GROQ_API_KEY="gsk_your_actual_key_here"
```

### LLM timeouts
```
Error: Groq API timeout on attempt 1/3
```
**Solution:** Retry logic will automatically backoff and retry. If persistent, check network connectivity.

### Path validation errors
```
Error: Path /etc/passwd not allowed (sandbox violation)
```
**This is expected!** The sandbox prevents dangerous file writes. Implementation respects allowlist.

### Tests don't match acceptance criteria
If tests don't fully map to criteria, the test validator loop will generate additional tests (up to 2 iterations).

---

## Assessment Mapping

This demo directly demonstrates all Newton Russell requirements:

| Req # | Requirement | Demonstrated By |
|-------|-------------|---|
| 1 | **Spec Intake** | Step 1: Parse spec.json |
| 2 | **Planning** | Step 2: Generate plan.json |
| 3 | **Implementation** | Step 2 + Step 4: Code in src/ |
| 4 | **Test Generation** | Step 2 + Step 4: Tests in tests/ |
| 5 | **Quality Gates** | Step 2 + Step 8: quality_report.json |
| 6 | **Approval Workflow** | Step 2 + Step 5: 2 checkpoints in audit |
| 7 | **Auditability** | Step 5: audit.jsonl with full traceability |

---

## Next Steps

- **Production Deployment**: Use docker-compose in production environments
- **CI/CD Integration**: POST /runs from GitHub Actions / GitLab CI / Jenkins
- **Scale**: Multiple parallel runs via API (per-run isolation ensures safety)
- **Monitor**: Tail audit.jsonl for compliance + observability dashboards

