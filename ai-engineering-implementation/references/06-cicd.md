# CI/CD — the pipeline as the enforcement point

**Requirement being implemented:** NIST SP 800-218A (SSDF for GenAI — Prepare Organization / Protect
Software / Produce Well-Secured Software / Respond to Vulnerabilities), ISO 42001 A.6.2.3–A.6.2.5
(design documentation, V&V, deployment), OWASP LLM03 (Supply Chain), LLM04 (poisoning via persisted
state and dependencies).

The stance: **a control that isn't enforced in the pipeline is a hope.** Every guarantee made in the
other files — validated outputs, redaction, capability limits, eval thresholds — gets a pipeline
gate here, because with a team of one, the pipeline is also the four-eyes principle.

For GenAI, SP 800-218A's key insight is that the "software" being secured now includes **prompts,
golden sets, rubrics, capability manifests, and model version pins** — all of which change behavior
in production and therefore all of which go through the same review-build-test-promote flow as code.
In this repo they already live in git; the work is gating them.

---

## 1. What is version-controlled and what changing it triggers

| Artifact | Lives at | A change triggers |
|---|---|---|
| Application code | `*/app/` | full test suite, smoke evals |
| **Prompts** | `app/agent/prompts/` | **smoke evals + red-team suite + prompt checklist** |
| **Capability manifests** | `app/agent/capabilities.py` | **manifest diff surfaced in PR — reviewed like an IAM policy** |
| **Model ID pins** | env/Vault + `values/*.yaml` | **full eval suite + red-team suite** (a model change is a release) |
| Golden sets + rubrics | `evals/` | eval-of-the-eval: judge calibration re-run |
| Redaction policy | config | redaction test corpus |
| Helm charts / infra values | `charts/`, `infrastructure/` | infra pipeline (`05-supply-chain` in the `ai-platform-implementation` skill) |

Enforce the triggers with path filters — the monorepo already uses change-detection matrices; these
are additional rows, not a new system.

**The prompt-change checklist** (PR template, three questions): no secrets or client specifics? no
safety-critical logic that belongs in code? red-team suite green? — that's the ISO A.6.2.3 design
record for prompt changes, accumulated in PR history rather than a register nobody updates.

## 2. Pipeline stages and their gates

```
PR:        lint → unit tests → gateway-choke-point lint → deps audit
           └─ if prompts/ or model pin touched: smoke evals + red-team subset

Build:     image build (pinned base, --provenance=false --sbom=false for Lambda-style
           targets; keep buildx SBOM/attestation ON for K8s images)
           → SBOM generate (syft) → vuln scan (grype/trivy, fail on critical)
           → image sign (cosign) → push

RC:        full eval suite ([05], thresholds enforced) → full red-team corpus
           → eval report generated + attached to the release record

Promote:   staging soak (online eval sampling active) → manual approval gate
           → prod deploy (signed image verified at admission — infra side)
```

Gate rules that matter:

- **Eval thresholds are set before the run and fail the build.** A regression on faithfulness or
  injection resistance blocks promotion; overriding requires an explicit, recorded exception (that
  record is a risk-acceptance decision — ISO 6.1.3 language, one line in the release record).
- **Model upgrades ride the same rails.** Bumping the Sonnet/Haiku pin is a PR like any other: full
  evals, red team, release record. Never a config flip in prod. This is the concrete meaning of
  "treat the model as a supply-chain dependency" (LLM03, GOVERN 6.1).
- **Dependency discipline**: lockfiles committed, `pip-audit`/`npm audit` in PR, base images pinned
  by digest. LangGraph/langchain-aws move fast and sit directly on the request path — an upgrade PR
  gets the same eval smoke as a prompt change, because behavior *does* shift with them.

## 3. The release record — deployment evidence (ISO A.6.2.5)

One generated JSON/MD per production release, archived with the artifacts:

```yaml
release: 2026-07-30-r1
git_sha: <sha>                      # = prompt_version stamped into images/traces
images: {api: <digest>, product-api: <digest>, qa-api: <digest>, ui: <digest>}
model_ids: [us.anthropic.claude-sonnet-...-v..., us.anthropic.claude-haiku-...-v...]
sbom: <ref>          eval_report: <ref>          redteam_report: <ref>
approvals: [{gate: rc-promote, by: <approver>, at: ...}]
exceptions: []                      # threshold overrides, with rationale — usually empty
```

This single document answers the auditor's chain: *what ran in production on date X, who approved
it, what was it tested against, what did the tests say.* It also answers the incident responder's
first question (what changed?) — same artifact, both consumers. Cheap to generate in the deploy
job; nearly impossible to reconstruct honestly after the fact.

## 4. Respond-to-vulnerabilities (the 218A group everyone skips)

- **Intake**: dependency CVEs (scanner), model deprecation notices (Bedrock announcements — treat
  as supply-chain events with an EOL date), red-team regressions, incident-derived findings
  ([04 §5](04-observability.md)).
- **The GenAI-specific case — the model itself is the vulnerable component**: a jailbreak class or
  quality defect in a pinned model version. Response paths, in order: tighten input/output gates
  (redaction policy, ingest screening — config, fast), add the exploit to the red-team corpus
  (permanent), roll the model pin forward/back through the full pipeline (§2). The rollback path
  must be *practiced*: a model pin rollback is only a git revert + deploy **if** evals gate it —
  which they do, because it rides the same rails.
- Every response lands as: a red-team/golden case (so it can't recur silently) + a risk-register
  line + an incident record if it fired in prod. That loop — incident → test → gate — is
  continuous improvement (ISO 10.1/10.2) implemented as engineering practice instead of a meeting.

## 5. Mapping back

| Pipeline element | Satisfies |
|---|---|
| Prompts/manifests/pins under PR review with path-filtered gates | 218A Protect Software · ISO A.6.2.3 |
| SBOM + scan + sign | LLM03 · 218A Produce Well-Secured Software |
| Eval + red-team gates with pre-set thresholds | MEASURE 2.1/2.7 · ISO A.6.2.4 · LLM09 |
| Release record | ISO A.6.2.5 deployment · incident forensics |
| Model pins through full pipeline | LLM03 · GOVERN 6.1/6.2 (deprecation contingency) |
| Exception records on overridden gates | ISO 6.1.3 risk acceptance, documented |
| Incident → corpus → gate loop | ISO 10.1/10.2 · 218A Respond to Vulnerabilities |
