# Volt Control Plane Backlog

Implementation backlog derived from:
- `documentation/VOLT_CONTROL_PLANE_IMPLEMENTATION_BLUEPRINT.md`
- `documentation/the start of the volt.md`

Format:
1. Epic
2. Story
3. Tasks
4. Test cases
5. Definition of done

Priority labels:
- `P0` Critical
- `P1` High
- `P2` Medium

Status labels:
- `Todo`
- `In Progress`
- `Blocked`
- `Done`

## Epic E1 - Canonical Control Plane Boundary (`P0`, `Todo`)
### Story S1.1 - Enforce one canonical runtime path
Owner: Platform Engineering

Tasks:
1. Create `CanonicalOrchestrator` runtime entry class.
2. Create `CanonicalMetaSupervisor` runtime class.
3. Create `CanonicalPipelineSupervisor` runtime class.
4. Create `CanonicalHealingController` runtime class.
5. Add startup guard to block non-canonical runtime class usage.
6. Add static check to fail CI if legacy class names appear in production entrypoint.

Test cases:
1. Runtime boot succeeds with canonical classes only.
2. Runtime boot fails when a legacy class is requested in production mode.
3. CI check fails with legacy symbol in production path.

Definition of done:
1. Production entrypoint constructs canonical classes only.
2. Legacy paths are marked `LEGACY_EXPERIMENTAL` and cannot run in production mode.

### Story S1.2 - Legacy path labeling and migration map
Owner: Architecture

Tasks:
1. Inventory all supervisor/orchestrator variants.
2. Tag each as `canonical`, `legacy`, or `research`.
3. Publish migration map from each legacy variant to canonical equivalent.

Test cases:
1. Inventory report includes all discovered control-plane variants.
2. Migration map links every legacy variant to a target or deprecation note.

Definition of done:
1. No unclassified control-plane variant remains.

## Epic E2 - Self-Healing State Machine (`P0`, `Todo`)
### Story S2.1 - Implement strict healing state transitions
Owner: Reliability Engineering

Tasks:
1. Define states: `DETECT`, `PLAN`, `ACT`, `VERIFY`, `ROLLBACK`, `CONFIRM`.
2. Implement transition validator to reject invalid jumps.
3. Add timeouts for `VERIFY` stage.
4. Force fallback policy when `VERIFY` timeout occurs.

Test cases:
1. Valid transition path completes to `CONFIRM`.
2. Invalid transition is rejected with explicit error.
3. Verify timeout triggers rollback or safe-mode policy.

Definition of done:
1. All incidents terminate in `CONFIRM` or `ROLLED_BACK`.

### Story S2.2 - Add action planning and execution contracts
Owner: Reliability Engineering

Tasks:
1. Add `detect_incident(metrics)` contract.
2. Add `plan_actions(incident)` contract.
3. Add `execute_action(plan)` contract.
4. Add `verify_outcome(result, slos)` contract.
5. Add `rollback(result)` contract.

Test cases:
1. Each contract returns typed response with mandatory fields.
2. Failed action execution cannot skip verify/rollback path.

Definition of done:
1. Healing flow runs only via contracts.

## Epic E3 - Healing Ledger and Auditability (`P0`, `Todo`)
### Story S3.1 - Persistent append-only healing ledger
Owner: Data Platform

Tasks:
1. Create ledger table with keys: `incident_id`, `action_id`, `model_id`, `timestamp_utc`.
2. Add before/after state and metrics payload columns.
3. Add verification and rollback status fields.
4. Enforce uniqueness on `action_id`.
5. Implement idempotent writer with retry-safe semantics.

Test cases:
1. Duplicate `action_id` insert is rejected or safely ignored.
2. Incident timeline reconstruction returns all lifecycle events in order.
3. Ledger writes remain consistent across restart.

Definition of done:
1. Every healing action is queryable and replay-auditable.

### Story S3.2 - Incident and action query API
Owner: Backend Engineering

Tasks:
1. Add endpoint/query function for incident timeline.
2. Add endpoint/query for latest unresolved incidents.
3. Add endpoint/query for rollback failures and age.

Test cases:
1. Incident timeline returns complete ordered action list.
2. Unresolved incident query returns only non-terminal incidents.

Definition of done:
1. Operations team can diagnose any incident from ledger alone.

## Epic E4 - Transactional Orchestrator Reliability (`P0`, `Todo`)
### Story S4.1 - Idempotency keys and run registry
Owner: Platform Engineering

Tasks:
1. Add `run_id` and `idempotency_key` to orchestration API.
2. Persist run registry with status by step.
3. Implement replay behavior for existing `idempotency_key`.

Test cases:
1. Re-run with same key does not duplicate side effects.
2. New key starts independent run.

Definition of done:
1. Duplicate requests are safe and deterministic.

### Story S4.2 - Step commit and compensation model
Owner: Platform Engineering

Tasks:
1. For each step, add lifecycle: `prepare`, `execute`, `commit`, `compensate`.
2. Persist step state transitions.
3. Add restart-resume logic from last committed step.
4. Add output checksums for step artifacts.

Test cases:
1. Crash between `execute` and `commit` is recovered safely.
2. Committed prior steps are not re-executed after resume.
3. Compensation path runs on commit failure.

Definition of done:
1. Mid-run interruption cannot corrupt end state.

## Epic E5 - Retry, Breakers, and Failure Budgets (`P1`, `Todo`)
### Story S5.1 - Centralized retry policy engine
Owner: Reliability Engineering

Tasks:
1. Implement bounded exponential backoff with jitter.
2. Add per-dependency retry budgets.
3. Add error taxonomy: `transient`, `persistent`, `fatal`.
4. Remove hardcoded retry sleeps in runtime paths.

Test cases:
1. Retry stops at budget exhaustion.
2. Fatal errors bypass retry and escalate immediately.
3. Transient errors respect backoff + jitter distribution.

Definition of done:
1. No production dependency uses ad hoc retry loops.

### Story S5.2 - Circuit breaker framework
Owner: Reliability Engineering

Tasks:
1. Implement breaker states: `CLOSED`, `OPEN`, `HALF_OPEN`.
2. Add tripping conditions by timeout, failure rate, and consecutive failures.
3. Add recovery probes in `HALF_OPEN` state.
4. Add breaker telemetry and logs.

Test cases:
1. Breaker opens after configured failure threshold.
2. Open breaker routes to fallback/degraded path.
3. Half-open probes restore closed state on success.

Definition of done:
1. External dependency failures are contained and observable.

## Epic E6 - Policy-Driven Escalation (`P1`, `Todo`)
### Story S6.1 - Escalation engine by severity
Owner: SRE

Tasks:
1. Define escalation levels: `WARN`, `DEGRADED`, `SAFE_MODE`, `HALT`.
2. Map triggers from health score, stale model ratio, incident rate, rollback failures.
3. Implement deterministic behavior for each level.
4. Add de-escalation policy with hysteresis.

Test cases:
1. Trigger crossing moves system to expected level.
2. De-escalation requires sustained recovery window.
3. Halt level blocks risky actions.

Definition of done:
1. Escalation behavior is deterministic and reproducible.

### Story S6.2 - Operator notification and runbook integration
Owner: SRE

Tasks:
1. Add event hooks for alert channels.
2. Attach runbook links in alert payloads.
3. Add incident context bundle in alert metadata.

Test cases:
1. Every escalation event creates one alert with context.
2. Alert contains runbook pointer and incident id.

Definition of done:
1. Operators can act immediately with complete context.

## Epic E7 - Validation and Release Gates (`P1`, `Todo`)
### Story S7.1 - Unit and integration reliability suite
Owner: QA Engineering

Tasks:
1. Add state-machine transition test matrix.
2. Add orchestration idempotency tests.
3. Add rollback success/failure branch tests.
4. Add breaker and retry policy tests.

Test cases:
1. All P0 critical paths have positive and negative tests.
2. Coverage threshold for control-plane modules >= 90%.

Definition of done:
1. Reliability suite is required in CI for merge.

### Story S7.2 - Staging failure drills
Owner: SRE + QA

Tasks:
1. Run dependency outage drill.
2. Run orchestrator mid-run crash drill.
3. Run healing verification failure drill.
4. Run stale-model storm drill.

Test cases:
1. Each drill produces expected escalation and recovery sequence.
2. MTTR and rollback SLOs are met.

Definition of done:
1. All required drills pass in staging before release.

## Epic E8 - Advanced Operations (`P2`, `Todo`)
### Story S8.1 - Canary healing rollout
Owner: Reliability Engineering

Tasks:
1. Add canary cohort selection.
2. Add control-vs-canary metric comparator.
3. Add promote/abort decision policy.

Test cases:
1. Canary healing aborts automatically if guardrails fail.
2. Promotion occurs only when canary outperforms thresholds.

Definition of done:
1. High-risk healing actions are never globally rolled out first.

### Story S8.2 - Chaos engineering for control-plane faults
Owner: SRE

Tasks:
1. Inject faults in ingestion, scoring, state store, and API dependencies.
2. Add scheduled chaos runs in staging.
3. Track SLO impact per chaos scenario.

Test cases:
1. System preserves required SLOs under fault injection envelope.
2. Unrecoverable scenarios trigger deterministic halt path.

Definition of done:
1. Chaos tests are part of regular release readiness.

## Epic E9 - Metrics, SLOs, and Observability (`P1`, `Todo`)
### Story S9.1 - Control-plane KPI dashboard
Owner: Data Platform

Tasks:
1. Publish `MTTR`, verification success rate, rollback success rate.
2. Publish open breaker count and unresolved incident age.
3. Publish stale model percentage and escalation level timeline.

Test cases:
1. Dashboard updates within expected freshness window.
2. KPI values match raw ledger/query outputs.

Definition of done:
1. On-call can assess control-plane health in under 2 minutes.

### Story S9.2 - Release gate automation
Owner: DevOps

Tasks:
1. Encode release blockers in CI/CD pipeline.
2. Block deploy on failed P0 tests or unresolved critical incidents.
3. Block deploy if idempotency replay tests fail.

Test cases:
1. Pipeline blocks release when any blocker is present.
2. Pipeline passes only with full gate compliance.

Definition of done:
1. No manual override required for standard release acceptance.

## Program Milestones
### Milestone M1 (End Week 2)
1. E1 and E2 complete.
2. Canonical runtime path active in staging.

### Milestone M2 (End Week 4)
1. E3 and E4 complete.
2. Ledger + idempotent orchestration validated.

### Milestone M3 (End Week 5)
1. E5, E6, E7 complete.
2. Staging failure drills pass.

### Milestone M4 (End Week 6)
1. E8 and E9 baseline complete.
2. Release gate approvals and runbook sign-off complete.

## Import Mapping for Jira/Azure DevOps
Suggested fields:
1. `Issue Type`: Epic/Story/Task/Test
2. `Priority`: P0/P1/P2
3. `Area`: Platform/Reliability/SRE/QA/Data/DevOps
4. `Sprint`: Week-based milestone buckets
5. `Labels`: `control-plane`, `self-healing`, `orchestrator`, `supervisor`, `resilience`

Suggested hierarchy conversion:
1. Each `Epic E*` -> Epic ticket
2. Each `Story S*` -> Story ticket linked to Epic
3. Each task bullet -> Task/Sub-task ticket linked to Story
4. Each test-case bullet -> Test Case ticket linked to Story
