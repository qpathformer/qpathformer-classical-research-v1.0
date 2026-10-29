# Q-Pathformer study v0.4 Study

This completed study asks what shallow circuit models contribute when conventional models have access to the same routing choices. It crosses a two-qubit, depth-two circuit model (Q2), a raw-coordinate ReLU MLP and a 25-feature trigonometric sigmoid-logit model with global, coordinate-hash and training-only k-means routing. Routed examples activate one of five parameter banks. The fixed k-means router is fitted to training coordinates without labels.

All 54 development and 135 confirmation endpoints completed 200 rounds and 15,000 optimizer updates per endpoint. Confirmation used five training seeds per model/population combination on two independent circle populations and a rotated ellipse. All circuit execution was simulated on classical compute.

Read the [PDF report](reports/QPathformer_v0.4_Report.pdf) or [Word report](reports/QPathformer_v0.4_Report.docx). The historical scientific report is preserved in full; [edition changes](provenance/EDITION_CHANGES.md) identify the appended note and metadata. [Report licence scope](REPORT_LICENSE_SCOPE.json) · [Inherited expression evidence](INHERITED_REPORT_EXPRESSION.json).

Binary cross-entropy (BCE; lower is better) was primary. Spatial routing improved Q2 over hash routing, but global MLP and global trigonometric controls achieved lower mean BCE and higher mean macro-F1 on every confirmation population. Routed trigonometric models also had lower BCE than routed Q2. Q2 versus the small routed MLP remains unresolved across training seeds; the adjusted paired-seed BCE intervals include zero on all three populations.

Five seeds, synthetic tasks, fixed routers and unequal model capacities do not establish a circuit-specific benefit, equivalence, quantum advantage, speed or real-world generalization. Seed intervals and conditional record bootstraps answer different questions. Historical local readiness checks covered all 45 circuit checkpoints and 737,280 simulated Aer measurement shots. Separate conditional binomial diagnostics are documented in the report. No physical shots or hardware jobs are reported, and illustrative noise is not device calibration.

The publisher's public release remains subject to owner review. This does not limit reuse permitted under the adopted CC BY 4.0 grant. Dated publication-status wording in the preserved edition records describes the publisher's review process; it does not add a recipient permission requirement to the adopted licence.

Repository edition v1.0 and study v0.4 are separate identifiers. Companion downloads contain Documentation and selected source-available Code. Packaging adds no experiments, and original future-study recommendations remain historical recommendations. [Rights](RIGHTS.md) · [Verification](VERIFY.md).
