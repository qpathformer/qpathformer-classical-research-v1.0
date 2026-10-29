# Study v0.4 research guide

Nine combinations of model family and routing were evaluated: two-qubit depth-two circuits, raw-input ReLU MLPs and 25-feature trigonometric logit models, each with global, coordinate-hash or train-only k-means routing. All 54 development and 135 confirmation endpoints completed 200 rounds and 15000 optimizer updates. Confirmation covered two independent circle populations and a rotated ellipse.

## Findings

Q2 k-means mean macro-F1 was 98.32%, 97.16% and 94.41% across the three confirmation populations. Spatial routing substantially improved Q2 relative to hash routing, but trigonometric k-means models had lower BCE throughout. Global MLP and trigonometric controls also outperformed Q2 k-means in mean F1 and BCE. Q2 versus the small routed MLP was unresolved across training seeds.

## Interpretation

Five seeds, synthetic tasks, fixed routers and unequal capacities do not isolate a circuit-specific benefit or establish quantum advantage, equivalence, speed or real-world generalization. Seed intervals and conditional record bootstraps answer different questions. Local readiness covered 45 quantum checkpoints, 1440 validation fixture circuits and 720 measured Aer experiments totaling 737280 simulated shots; 199065600 represented binomial trials are separate. Illustrative noise is not device calibration.

The report preserves all original tables, figures, numerical qualifications and historical recommendations. Read those alongside the original protocols before interpreting comparisons. No ETEL implementation is supplied by this source study.

## Selected evidence

The [original overview](historical/README.txt) and [reproduction guide](historical/REPRODUCTION_GUIDE.txt) describe the full retained archive. Commands and absolute paths in those files are historical; they are not a batch to run in a curated download.
