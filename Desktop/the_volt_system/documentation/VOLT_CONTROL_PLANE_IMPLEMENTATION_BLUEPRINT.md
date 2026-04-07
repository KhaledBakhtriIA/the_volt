# Volt Control Plane Implementation Blueprint

Execution blueprint for production-hard autonomy of the Volt system control plane.

Primary source context:
- `documentation/the start of the volt.md`
- `AutoData_Analyst_v1_aymen.ipynb`

Target: convert current control-plane maturity from ~63% to >=85%.

## 1. Scope and Objectives
This blueprint covers four domains:
1. Self-healing state machine and verification loop
2. Meta-supervisor and supervisor canonicalization
3. Orchestrator transactional reliability
4. Runtime operations (retry budgets, circuit breakers, escalation)

Success target:
1. Every automated healing action becomes auditable, verifiable, and reversible.
2. One canonical control-plane path is used in runtime.
3. Orchestration is idempotent and recoverable across interruptions.
4. Failure handling is policy-driven instead of ad hoc.

## 2. Architecture Baseline to Preserve
Keep these strengths while hardening:
1. Regime-aware decision orchestration and weighted consensus
2. Dominant-brain attribution and supervisor reporting
3. Existing fallback and health-check patterns
4. Existing risk containment logic (drawdown and position isolation)

## 3. Canonical Runtime Boundary (Critical)
Define one runtime contract and route all execution through it.

Canonical classes to keep:
1. `CanonicalOrchestrator`
2. `CanonicalMetaSupervisor`
3. `CanonicalPipelineSupervisor`
4. `CanonicalHealingController`

Deprecation policy:
1. Keep legacy notebook variants for research only.
2. Mark all non-canonical variants with `LEGACY_EXPERIMENTAL` tag.
3. Add a guard that raises if runtime tries to instantiate non-canonical classes.

Acceptance criteria:
1. Runtime creates only canonical classes.
2. CI check fails if non-canonical class is used in production entrypoint.

## 4. P0 Implementation Plan (Must-Do)
### P0.1 Healing State Machine
Implement strict state transitions:
1. `DETECT`
2. `PLAN`
3. `ACT`
4. `VERIFY`
5. `ROLLBACK` or `CONFIRM`

Required interfaces:
1. `detect_incident(metrics) -> Incident`
2. `plan_actions(incident) -> ActionPlan`
3. `execute_action(plan) -> ActionResult`
4. `verify_outcome(result, slos) -> VerificationResult`
5. `rollback(result) -> RollbackResult`

Hard rules:
1. No direct mutation of model state outside `ACT`.
2. `VERIFY` timeout required.
3. Failure to verify must force rollback or downgrade mode.

Acceptance criteria:
1. Invalid transitions are blocked.
2. Every incident reaches terminal state (`CONFIRMED` or `ROLLED_BACK`).

### P0.2 Healing Ledger (Persistent)
Create append-only ledger schema:
1. `incident_id`
2. `action_id`
3. `model_id`
4. `state_before`
5. `state_after`
6. `metrics_before`
7. `metrics_after`
8. `verification_status`
9. `rollback_status`
10. `timestamp_utc`
11. `actor` (`auto` or `human`)

Operational requirements:
1. Durable storage (SQLite/Postgres acceptable).
2. Idempotent writes using unique `action_id`.
3. Query endpoints for incident timeline and action replay.

Acceptance criteria:
1. Any healing action can be reconstructed end-to-end from ledger.
2. Duplicate action writes are rejected safely.

### P0.3 Orchestrator Idempotency and Step Commits
Add orchestration run contract:
1. `run_id` and `idempotency_key`
2. step registry with statuses: `PENDING`, `RUNNING`, `COMMITTED`, `FAILED`, `SKIPPED`
3. restart behavior resumes from last committed step

Step contract:
1. each step must define `prepare`, `execute`, `commit`, `compensate`
2. step outputs must be versioned and checksummed

Acceptance criteria:
1. Re-running same `idempotency_key` does not duplicate side effects.
2. Crash during step N resumes safely without replaying committed N-1.

### P0.4 Canonical Entry Point
Introduce single entry point:
1. `run_control_plane(config, run_id, idempotency_key)`
2. all CLI/API paths call this only

Acceptance criteria:
1. no direct calls to legacy supervisor/orchestrator paths in production mode
2. one structured startup report showing canonical components loaded

## 5. P1 Implementation Plan (Stability Hardening)
### P1.1 Central Retry Policy
Replace fixed retry sleeps with centralized policy:
1. bounded exponential backoff
2. jitter
3. retry budget per dependency
4. error taxonomy (`transient`, `persistent`, `fatal`)

Acceptance criteria:
1. retries stop at budget limit
2. persistent failures escalate to policy engine

### P1.2 Circuit Breakers
Add per-dependency breaker states:
1. `CLOSED`
2. `OPEN`
3. `HALF_OPEN`

Trip conditions:
1. failure rate threshold
2. timeout threshold
3. consecutive failure threshold

Acceptance criteria:
1. breaker state transitions are logged
2. open breaker routes execution to fallback/degraded path

### P1.3 Escalation Policy Engine
Policy levels:
1. `WARN`
2. `DEGRADED`
3. `SAFE_MODE`
4. `HALT`

Policy inputs:
1. health score
2. stale model ratio
3. critical incident count
4. rollback failure count

Acceptance criteria:
1. every severity level has deterministic behavior
2. escalation and de-escalation events are auditable

## 6. P2 Implementation Plan (World-Class Ops)
### P2.1 Canary Healing
1. apply healing to cohort subset first
2. compare control vs canary metrics
3. promote only if predefined win criteria are met

### P2.2 Causal Post-Healing Reports
1. root-cause hypothesis
2. expected vs observed impact
3. confidence score
4. operator recommendation

### P2.3 Chaos Engineering for Control Plane
Inject faults in:
1. data ingestion
2. model scoring
3. state store
4. external API dependencies
5. orchestrator step boundaries

Acceptance criteria:
1. system remains within SLO envelopes under injected faults
2. unrecoverable faults trigger deterministic halt path

## 7. Test Strategy
### 7.1 Unit Tests
1. state-machine transition tests (valid and invalid)
2. idempotency key semantics
3. circuit breaker transitions
4. policy engine level transitions

### 7.2 Integration Tests
1. incident detect -> plan -> act -> verify -> confirm
2. incident detect -> plan -> act -> verify fail -> rollback
3. orchestrator crash/restart recovery with step commits
4. fallback path activation under dependency outage

### 7.3 Reliability Tests
1. soak test for long-running control loop
2. retry budget exhaustion scenarios
3. stale model supervisor alerts
4. split-brain simulation for concurrent runs

### 7.4 Acceptance Gate (Release Blockers)
Release is blocked unless all are true:
1. zero failed P0 tests
2. no orphan incidents in non-terminal state
3. no duplicate side effects under idempotency replay
4. all escalation levels exercised in staging

## 8. Metrics and SLOs
### Core SLOs
1. Incident MTTR <= 5 minutes
2. Verification success rate >= 95%
3. Rollback success rate >= 99%
4. Orchestrator step replay safety = 100%
5. False halt rate < 1 per 30 days

### Health KPIs
1. control-plane health score
2. stale model percentage
3. mean retries per dependency
4. open breaker count
5. unresolved incident age P95

## 9. Delivery Plan (6-week example)
### Week 1-2
1. canonical runtime boundary
2. state machine skeleton
3. healing ledger schema and write path

### Week 3-4
1. verify/rollback implementation
2. idempotent orchestrator step commits
3. centralized retry and circuit breakers

### Week 5
1. escalation engine
2. integration and reliability suites
3. staging drills

### Week 6
1. canary healing
2. chaos tests
3. release hardening and runbook sign-off

## 10. Runbooks Required Before Production
1. Incident handling runbook (per escalation level)
2. Manual override and safe-mode runbook
3. Rollback runbook for failed healing
4. Data integrity runbook for step commit corruption
5. Dependency outage runbook (breaker + fallback)

## 11. Definition of Done
Control-plane hardening is complete when:
1. P0, P1 are fully implemented and tested.
2. Runtime uses only canonical control-plane classes.
3. Healing is fully auditable and reversible.
4. Orchestration is idempotent and restart-safe.
5. Staging chaos tests pass with SLO compliance.

## 12. Immediate Next Actions
1. Freeze canonical class list and label legacy paths this week.
2. Implement healing ledger first, then state-machine enforcement.
3. Add idempotency keys and step commits before adding more model complexity.
4. Run first rollback drill before any live autonomy expansion.
