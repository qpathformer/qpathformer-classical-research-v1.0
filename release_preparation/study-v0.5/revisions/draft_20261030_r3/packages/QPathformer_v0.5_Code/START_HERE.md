# Q-Pathformer Study v0.5 Code

**Flexible Readouts and Classical Controls**

Q-Pathformer v0.5 examines how learned output heads change shallow circuit classifiers when compared with strong classical controls. Eleven recipes were evaluated on two independently generated circle populations and a rotated ellipse, using five paired training seeds and one fixed split per confirmation population. All circuit execution used classical compute.

The study completed 22 short engineering endpoints, 66 full development endpoints and 165 full confirmation endpoints. Every full endpoint completed 200 rounds and 15,000 optimizer updates. All eleven recipes continued to confirmation; early stopping was not used.

Common clipped BCE was the primary endpoint; macro-F1 was secondary. The learned-readout recipes substantially improved on the same-study Legacy recipe. Scalar changes the probability link, head parameters, capacity and native training loss together, so this comparison does not isolate the readout's contribution. Five-moment Multi adds a smaller, task-dependent benefit over Scalar: both circle adjusted seed intervals include zero; the ellipse loss reduction is below the registered 0.01 practical reference. The random frozen-core control performed substantially worse.

Routed Trig25 had the lowest mean common clipped BCE on all three confirmation populations. Its advantage over Multi was unresolved by the adjusted seed intervals on the circles and resolved on the ellipse. Trig25 controls combined high mean accuracy with much lower measured local execution time than the circuit recipes. These are measurements of the retained CPU implementations, not general hardware-efficiency or monetary-cost claims.

Study v0.5 and repository edition v1.0 are separate. Read the adopted [rights](RIGHTS.md), [verification guidance](VERIFY.md) and selected [source origins](provenance/SOURCE_MAP.json).

Start with the [quickstart](QUICKSTART.md), [source selection](SOURCE_SELECTION.json), [dependency inventory](DEPENDENCY_INVENTORY.json) and [inherited permissions](INHERITED_LICENSE_COVERAGE.json).

The bounded startup helper checks package integrity before scientific imports and after its checks, parses all 52 selected Python files, imports the selected numerical modules and runs two selected tests: model parameter shapes/paired initialization, and independent circuit-state/moment agreement. It does not run training, official scoring, shot sampling, noise experiments or QPU jobs. Success does not establish a clean installation, every optional dependency or full historical reproduction.

Datasets, checkpoints, installed environments and the complete retained archive are excluded. Selected scientific Python remains unchanged; current package helpers and guidance are separate from the historical experiment. No ETEL implementation is supplied.
