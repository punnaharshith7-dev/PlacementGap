# Architecture decisions

## 2026-10-16 — Use a deterministic solver for schedules

**Choice:** Greedy-by-score scheduling with topological ordering, a bounded rebalance pass, explicit deferrals, and a separate validity checker. LLMs cannot write or sum the schedule.

**Alternatives:** Ask an LLM to produce week assignments; run a general-purpose optimization package.

**Measured:** The 60-case dev and 20-case heldout fixture runs both pass the deterministic plan-validity checker on 100% of cases. The LLM-scheduler alternative is not measured offline because no model cassette is bundled; it is reported as `N/A` rather than estimated. The seeded demo schedules its 48-hour budget over six balanced weeks. The solver is a bounded heuristic, not a claim of global optimality.

## 2026-10-16 — Use a skill ontology instead of raw string equality

**Choice:** Canonical skill nodes, curated aliases, prerequisite/adjacency/specialization edges, and an unresolved result that preserves raw text.

**Alternatives:** Keyword substring matching; unrestricted model-generated skill names.

**Measured:** On 128 frozen alias cases, exact+alias resolution is 100.0% accurate; exact canonical-name matching alone is 96.9% (124/128). The heldout `no_ontology` fixture run is measured separately in the generated ablation report.

## 2026-10-16 — Cap critic retries at two

**Choice:** The critic can request at most two deterministic rebuilds before the approval gate, with any remaining critique attached to the report.

**Alternatives:** No critique pass; unlimited repair loops.

**Measured:** On the current frozen heldout fixture, full and no-critic runs both have 100% plan validity; p95 latency is 1,398 ms and 1,279 ms respectively. The 119 ms difference is an overhead observation, not evidence that critic feedback improves quality in fixture mode. Critique loop utilization is recorded by the dev eval.

## 2026-10-16 — Route extraction and review to different model tiers

**Choice:** `config/models.yaml` assigns extraction/normalization to the cheap tier and critic/report reasoning to the strong tier. Deterministic fixture mode remains the no-key default.

**Alternatives:** One strong model for every node; one cheap model for every node.

**Measured:** Offline runs cost $0 because model calls are disabled. Per-node traces record token and USD spend when configured; provider-tier cost and quality differences remain unmeasured until a provider cassette is available.

## 2026-10-16 — Fence untrusted input and grant no model tools

**Choice:** JD and profile text appear only in user messages inside explicit untrusted markers. LLM requests have no tool definitions; node tool allowlists are recorded in traces.

**Alternatives:** Put the job text in the system prompt; permit model-directed tool execution.

**Measured:** Adversarial fixtures include plain text, HTML comments, and alt text. `python -m evals.runner --adversarial` reports verdict invariance against clean controls.

## 2026-10-17 — Allow a learning objective to span several weeks

**Choice:** Keep one plan item per skill, but allocate its study hours across multiple week sessions. Require prerequisite completion before dependent objectives and check every weekly load with the deterministic validity checker.

**Alternatives:** Treat each objective as indivisible and defer it when it exceeds the weekly budget; duplicate the skill as separate tasks.

**Measured:** The seeded 48-hour demo fits six 8-hour weeks with no deferred objectives or validity violations. The current 60-case dev and 20-case heldout runs both pass plan validity on 100% of cases. The greedy scheduler remains a heuristic; the fixture results do not establish global optimality.
