Q-Pathformer v0.4 - INTERNAL RESEARCH
Study: QPATH-ROUTING-v0.4

Scientific study complete. All work used local CPU simulation. There were no
quantum hardware jobs, cloud submissions or publication actions.

This README is not a final delivery certificate. Final delivery is determined
by DELIVERY_MANIFEST.json together with matching PASS records in
DELIVERY_VERIFICATION.json and DELIVERY_VERIFICATION_INDEPENDENT.json.
Final Word QA and delivery verification are separate from this scientific
completion record; neither is claimed here.

Report location in the delivered package:
docs/QPATH-RPT-005_Routing_and_Circuit_Contribution_Study_v0.4.docx

Completed scope
54 development and 135 confirmation endpoints: all 189 completed 200 rounds
and 15,000 optimizer updates each. All nine model/routing combinations were
retained. Full endpoint audits, validation learning/resource summaries, one
root-released confirmation evaluation and independent replay are complete.
The replay checked all 135 selected checkpoints on 1,600 test records per
population: 216,000 checkpoint-record predictions, exact class agreement,
zero numerical-band ambiguities, and matching paired-bootstrap count hashes.

Local readiness is also complete and independently audited: 45 quantum
checkpoints, 1,440 validation fixture circuits, 1,350 conditional binomial
arrays and 720 local measured Aer experiments (737,280 simulated measurement
shots). The 199,065,600 represented binomial trials are a separate probability-
level calculation, not additional Aer or hardware shots. Illustrative noise
settings are not IBM device calibration.

Key results
Means across five training seeds within each population. F1 is a percentage;
BCE is clipped binary cross entropy using natural logs, with lower better.
Model          Circle 1 F1% / BCE   Circle 2 F1% / BCE   Ellipse F1% / BCE
Q2 global       89.95 / 0.28412    89.77 / 0.28430    88.30 / 0.33665
Q2 hash         89.81 / 0.28527    90.13 / 0.28383    85.66 / 0.35660
Q2 k-means      98.32 / 0.17689    97.16 / 0.18280    94.41 / 0.21207
MLP global      99.39 / 0.01546    99.11 / 0.02198    99.16 / 0.01988
MLP hash        70.12 / 0.53071    69.63 / 0.54509    72.42 / 0.51016
MLP k-means     85.15 / 0.26715    83.91 / 0.28028    88.09 / 0.22199
Trig global     99.57 / 0.01348    99.67 / 0.01558    99.56 / 0.01528
Trig hash       99.06 / 0.02125    99.21 / 0.02395    99.16 / 0.02286
Trig k-means    99.75 / 0.01031    99.65 / 0.01319    99.56 / 0.01274

Spatial k-means routing substantially improves Q2 over hash routing on all
three populations. Both separately reported adjusted seed and conditional
record BCE intervals favor that comparison beyond the 0.01 reference.
Trigonometric k-means models have lower BCE than Q2 k-means on all populations.
Q2's lower mean BCE than the small routed MLP is not resolved across training
seeds: all adjusted seed intervals include zero. Global MLP and trigonometric
controls also outperform Q2 k-means on mean F1 and BCE.

Interpretation limits and next local research
These are synthetic tasks with five seeds, fixed routers and specified
architectures/optimizers. Model families have different parameter capacities;
the results do not isolate a unique circuit benefit or establish quantum
advantage, equivalence, hardware speed or real-world generalization. Seed
intervals and conditional record bootstraps answer different questions.
Validation steps-to-97% are descriptive, with nonreachers retained; every run
completed its full budget. Fresh v0.4 scores are not paired version-improvement
estimates against historical v0.3 scores.

Next, preregister a local comparison with matched parameter/operation budgets,
strong classical controls and harder fresh tasks; examine probability quality
and routed-MLP optimization. Use new held-out evaluation populations. Resolve
those questions before considering hardware testing.

Evidence and reproduction
RUN_STATUS.json records completion scope and hashes of existing evidence.
REPRODUCTION_GUIDE.txt explains verification and replay in a separate copy;
never add reproduction outputs to the verified original delivery. The package
contains source/data/evidence, not a copied Python environment.
- governance/: protocols, environment and baseline-preservation checks.
- quantum/stage_A and quantum/stage_B: complete training histories.
- quantum/confirmation_evaluation/: released predictions and statistics.
- analysis/independent_replay/confirmation_replay/: independent verification.
- analysis/learning_resources/: validation milestones and resource summaries.
- quantum/local_readiness_confirmation/ and
  analysis/classical_review/confirmation_readiness_audit/: simulator evidence.

Preservation checks PASS: all 5,192 v0.3 manifest payloads and all 21 tracked
Baseline3 seal artifacts match their recorded baseline identities. No baseline
source, archive or historical result was modified by this study.
