# Study v0.4 preparation

Nine combinations of model family and routing were evaluated: two-qubit depth-two circuits, raw-input ReLU MLPs and 25-feature trigonometric logit models, each with global, coordinate-hash or train-only k-means routing. All 54 development and 135 confirmation endpoints completed 200 rounds and 15000 optimizer updates. Confirmation covered two independent circle populations and a rotated ellipse.

Q2 k-means mean macro-F1 was 98.32%, 97.16% and 94.41% across the three confirmation populations. Spatial routing substantially improved Q2 relative to hash routing, but trigonometric k-means models had lower BCE throughout. Global MLP and trigonometric controls also outperformed Q2 k-means in mean F1 and BCE. Q2 versus the small routed MLP was unresolved across training seeds.

Five seeds, synthetic tasks, fixed routers and unequal capacities do not isolate a circuit-specific benefit or establish quantum advantage, equivalence, speed or real-world generalization. Seed intervals and conditional record bootstraps answer different questions. Local readiness covered 45 quantum checkpoints, 1440 validation fixture circuits and 720 measured Aer experiments totaling 737280 simulated shots; 199065600 represented binomial trials are separate. Illustrative noise is not device calibration.

Original source: `C:\Q2\Improvement_Study_v0.4`. Report: `docs/QPATH-RPT-005_Routing_and_Circuit_Contribution_Study_v0.4.docx`. The retained archive records 19,263 payload files and 1,204,159,807 logical payload bytes. This is neither a curated ZIP size nor a hardware minimum.

No ETEL is supplied in this study. Source evidence remains read only. The curated code excludes datasets, checkpoints, full operational archives and installed environments. Full reproduction requires retained evidence and separately reviewed new working paths.

- [x] Confirm authentic report and selected source identities
- [x] Preserve and render report edition
- [ ] Prepare three curated packages and exact adopted scope records
- [x] Seal, extract and run bounded startup
- [ ] Root review and GitHub draft upload

The owner adopted the earlier scoped licensing scheme during preparation; exact final scope identities will be supplied in each package.

Scoped licensing was adopted by the owner during preparation under the same earlier scheme. All final assets reflect that adoption; earlier unsealed report candidates remain in QA history.

Scoped licensing was adopted by the owner during preparation under the same earlier scheme. All final assets reflect that adoption; earlier unsealed report candidates remain in QA history.
