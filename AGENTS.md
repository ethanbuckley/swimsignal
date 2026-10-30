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
- A public research label does not justify misleading claims. Missing imagery is not a negative algae
  observation; a satellite index is not a toxin measurement or swimming clearance.
- Update the register when work changes stage, ships, or encounters a concrete blocker. Link the PR and next
  check so promising work cannot disappear into a closed chat.
