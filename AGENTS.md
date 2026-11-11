# Research and model work

For scientific, data-source, ML or forecast changes, read
[the research workflow](docs/RESEARCH-WORKFLOW.md) and
[the recovery register](docs/RESEARCH-RECOVERY-2026-10.md) before deciding what to run or abandon.
The register distinguishes historical test verdicts from current development decisions.

- A failed adoption test does not automatically close a research project. Record the supported claim,
  uncertainty, next useful deliverable, owner and milestone. Bounded exploration and an honest observation
  feature can proceed without passing a main-forecast superiority test.
- Preserve original protocols and results. A new analysis on seen data is exploratory; do not change an old
  threshold, call a selected subgroup confirmatory, or rerun seeds until a result passes.
- Keep active evaluation windows and the 2027 primary evaluation frozen. New candidates get separate,
  versioned logs and a prospective evaluation where needed.
- Use a separate worktree and explicit scratch `DIPCAST_ROOT`, `DIPCAST_STATE` and output directories before
  importing build/research code. A worktree alone does not isolate data. Treat shared caches and model artifacts
  as read-only; check relevant input fingerprints before and after a run. Never call a writer against the main
  checkout to obtain a preview.
- Take already-authorized routine work through to a reviewable PR. Ask only for a real missing decision,
  external contact, purchase, new account/access, or change outside the authorized scope. Do not create
  another approval step merely because an earlier research gate failed.
- Develop promising work now. After a readout, do the next deliverable the evidence supports: a tested candidate,
  continuing an existing one, a concrete diagnosis, a data or coverage improvement, an observation feature, or an
  evidence-backed archive. "Nothing until 2027" alone is not a continuation: a wait needs a stated reason (a
  disproved mechanism, data that cannot answer, or a step only Ethan can take; then build up to it and name it).
  Label seen-data held-out results as development. See "Develop promising work now" in the workflow.
- Start a shadow log only with issue-time inputs, correct timestamps, an independent versioned log, a logged
  comparator and fallback, and known resource and permission limits. An interval including zero does not show
  non-inferiority. Do not require a new Worker or scheduler while its availability, permissions or cost are
  unresolved; record the blocker instead.
- Do not wait for a future season when history can answer: a model frozen before it is scored on held-out years
  that played no part in choosing it (a frozen-model backtest) is enough to release a limited forecast or observation
  now, with the prospective window kept as monitoring. See "Backtest instead of waiting" in the workflow.
- Public swimming guidance keeps its full evidence bar. Development and shadow logging never change issued
  predictions, frozen windows or what a swimmer is told.
- A public research label does not justify misleading claims. Missing imagery is not a negative algae
  observation; a satellite index is not a toxin measurement or swimming clearance.
- Update the register when work changes stage, ships, or encounters a concrete blocker. Link the PR and next
  check so promising work cannot disappear into a closed chat.

# Reviews, design and wording

- Read [the design reference](docs/DESIGN.md) before reviewing the site or proposing a layout, UX or wording
  change. Mark each recommendation as new, already decided (cite where), or reversing a decision (say why).
  A review written from the rendered site alone has contradicted decisions recorded there.
- Wait for the PR's checks to finish before merging. `main` may have no required check, so
  `gh pr merge --auto` can merge at once, before the tests have run.
