# From research to useful features

Effective for new work from 30 October 2026, following Ethan's request to recover promising research and get it
working on SwimSignal. This changes development and release decisions prospectively. It does not change any
historical test verdict, fit, production threshold, or active evaluation protocol.

## Two decisions, recorded separately

1. **What did this test establish?** Keep its original verdict, estimates, intervals, population and limitations.
2. **What should the project do next?** Continue, specialise, collect observations, run in shadow, publish an
   observation feature, adopt a validated forecast, or archive with a reason to reopen.

“Failed as stated”, “too few” and “not shown” answer the first question. None, on its own, answers the second.
“Not shown” is not evidence of equivalence. A tiny miss of a cutoff is not a discontinuity in the underlying
evidence. Several large losses or a mechanism disproved by the measurements still justify stopping that variant.

The [recovery register](RESEARCH-RECOVERY-2026-10.md) holds current project decisions. Old protocols remain
historical records. Its specific development decisions supersede earlier blanket parking instructions; spending,
credentials, external-contact restrictions and frozen primary evaluations remain in force.

## Routes to use

These routes are not a requirement to pass every stage in order. An observation product can be useful without
becoming a forecast. A candidate can collect shadow predictions while its model is being improved.

| Route | Useful output | Evidence needed for this route | What happens next |
|---|---|---|---|
| Bounded exploration | Reproducible analysis, mechanism check, improved candidate | A plausible question; inspectable data; a stated time/data budget; an explicit exploratory label on reused data | Deliver a candidate, a data/coverage product, a collection plan, or an archive reason at the milestone |
| Running comparison (shadow) | Predictions saved alongside the current model before outcomes arrive | Correct timestamps and features available at issue time, isolated versioned logs, missing-data fallback, manageable cost | Read at the agreed date against production **and** useful simple references |
| Public research observations | Dated measurements, satellite indices, coverage and historical patterns | Correct extraction, identity/units/source/method, visible age and missingness, understandable limits; relevant source terms checked | Publish through a discoverable Research page; improve coverage and usability; forecast claims need their own evidence |
| Limited forecast | A calibrated estimate for specified lakes/companies/seasons/horizons | Evidence for that population and claim, honest uncertainty and failure behaviour, prospective confirmation where selection used seen outcomes | Staged rollout with fallback and monitoring; unsupported groups keep their existing output |
| Main forecast | A default used to guide the existing product | Pre-stated useful improvement or justified non-inferiority, appropriate calibration, subgroup guardrails, prospective operation and a reviewed rollout | Monitor drift, coverage and incidents; keep a reproducible rollback |

For satellite work, the first public output can be an **historical, dated NDCI observation series**, not an estimate
of harmful algae. A historical release must say so prominently; becoming “latest observations” requires an actual
refresh pipeline and measured coverage. A public feature is not “live” merely because a research record is merged.
A biological model's validated season does not automatically prohibit an off-season **index observation**: state
the new display scope prospectively, check extraction quality (including low light, snow/ice and water masks),
and disclose that biological interpretation outside the tested season is unvalidated. Do not extend a seasonal
forecast claim merely because its underlying observations can be displayed.

## Design a test for the decision it must support

- State the target and proposed user benefit first: better ranking, better calibrated probabilities, fewer missed
  events at a tolerable alert rate, better coverage, useful uncertainty, or a dated observation. A universal Brier
  gain, AUC cutoff or minimum row count cannot decide all of these.
- For adoption, choose the main metric, practical margin, population, reference models, subgroup guardrails and
  uncertainty method **before** examining the evaluation outcomes. A simpler, cheaper or better-covered model may
  have a justified non-inferiority route; choose its margin and benefit in advance, not after a tie.
- Report effect sizes and uncertainty even when a binary historical verdict is required. Do not demand that every
  subgroup's point estimate improve. Use uncertainty and justified harm margins; protect small subgroups with
  fallback rather than automatically blocking gains elsewhere. Conversely, a wide interval does not prove safety
  or non-inferiority.
- Use clustering that reflects the sampling: waterbody/site and time blocks for lake studies; overflow/company and
  time blocks for spill studies as appropriate. Explain low cluster counts and sensitivity to the resampling
  method. Fix seeds for reproducibility; do not treat a bootstrap's last decimal as a biological boundary.
- A gate should test whether the next analysis is informative or runnable. A “symptom is large enough” gate must
  not automatically replace a direct, affordable comparison of a fitted remedy with its reference. If an old gate
  is unsuitable, preserve its failed result and write a new development protocol explaining why.
- A company/lake-type specialisation selected from the old results is a development hypothesis. Evaluate the
  entire routing rule on new data, including its fallback and coverage, before claiming confirmed improvement.
- Reused 2024–26 outcomes remain usable for development and diagnosis. They cannot become unseen confirmation by
  changing the model's name, reshuffling folds, changing the threshold, or publishing a new document. Use grouped
  or time-embargoed development splits where shared events would leak; freeze the candidate before collecting a
  fresh confirmation window.
- Negative results get a precise scope. “This dynamic-flow variant did not help these sites” is useful;
  “hydrology cannot help” is unsupported. Keep the data and reusable extraction code discoverable.

## A continuation decision at every readout

Each research PR and register entry records:

| Field | Minimum content |
|---|---|
| Identity | Stable project ID, owner/session, PR and code/data locations |
| Evidence | Original verdict, relevant estimates and uncertainty, seen/unseen data boundary |
| Current stage and claim | Exploration, shadow, observations, limited/default forecast, scheduled, or archived; exact supported output |
| Next deliverable | A concrete artifact or public behaviour and its completion check |
| Milestone and budget | Read date or bounded work package; cached-first fetch/cost cap; named dependency if blocked |
| Release route | Who integrates it, what evidence is still missing, and the fallback/rollback |

Do not close a promising project with only “ask Ethan if he wants another test” when his existing instruction
already authorizes the bounded development. At a milestone, publish the result even if negative and decide the
next step explicitly. Iteration is permitted; repeating an unchanged test until it passes is not. An archive entry
must say what new evidence or changed need would justify reopening. A scheduled window is active work, not an
abandoned idea.

## Deliver visibly

The product and research owners share one versioned data contract. A Research page should identify what is usable
now, show the observation or tool, state its scope and limitations in plain language, and link its method and
progress. A private query flag is useful for review; it is not the final destination for a useful feature.

Before publishing an observation feature, check actual data through exporter, file and page: identity, dates,
units, quality flags, stale/missing/cloudy behaviour, empty series, provenance, mobile layout and intelligibility.
Do not invent live values for a demo. Keep official advice conspicuous. Experimental wording cannot repair a
misleading green “clear” signal, an unvalidated concentration conversion, or an implied forecast between images.

For predictions used in guidance, additionally document calibration and uncertainty for the relevant target,
live-data latency/availability, alert burden and fallback. Roll out by the validated population rather than
claiming universal coverage. State the main-site effect separately from the research-page effect.

## Preserve ongoing evaluations and shared data

- Keep lead calibration B, ensemble rain, live-status shadow, A8, upgraded-overflow option B, winter calibration
  and the 2027 primary evaluation on their stated windows and rules. Add separately labelled candidates/logs;
  never rewrite an issued forecast, retrospectively backfill a prospective prediction, or silently replace a
  primary comparator. A formal prospective amendment must identify the original analysis and separate any
  secondary work; it must not make exposed outcomes unseen again.
- Reuse the existing satellite artifacts before any imagery download. Record sources, versions, hashes,
  processing settings and output schema. Put a request/byte/time ceiling and stop behaviour on each fetch.
  Separate satellite/EA costs from Open-Meteo quota accounting. No expanded API allocation, new account, paid plan
  or outside enquiry follows automatically from this workflow.
- Set scratch `DIPCAST_ROOT`, `DIPCAST_STATE` and outputs before imports. Inventory the functions a run will call;
  some save processed inputs as a side effect. Copy/link only inputs required for the task, with writes directed
  elsewhere. Fingerprint shared inputs and model artifacts before and after. A worktree or ignored file is not a
  backup or a write barrier. Never replace a source cache to make a preview build succeed.
- A merge is not a deployment. Check successful publishing and the actual public artifact/version; record the
  public URL and scope, or state exactly what remains only in a PR, cache or shadow log.

## Why this policy is needed

The [25 October noise audit](NOISE-AUDIT-2026-10.md) already identified brittle point comparisons. PR #407 also
classified satellite chlorophyll as “promising, not validated”. Those were useful corrections, but the satellite
forward plan was still withdrawn and no observation product followed. This workflow supplies the missing delivery
decision and ownership. It supplements that audit; its route-specific criteria replace any interpretation that
every new research activity or observation display must first pass a main-model superiority test.
