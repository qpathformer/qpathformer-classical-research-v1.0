# Q-Pathformer Study v0.6 Code

**Harder Tasks and Faster Inference**

Q-Pathformer v0.6 asks whether richer circuit readouts help on harder classification boundaries, and whether the same trained circuit can run faster through an equivalent classical representation. Six recipes were compared on checkerboard, spiral, noisy annulus and rare-positive disks, using five paired training seeds on one fixed confirmation split per task family. All circuit execution used classical compute.

The completed design includes 48 development and 120 confirmation endpoints, plus 24 separate engineering endpoints. Every full endpoint completed 200 rounds and 15,000 optimizer updates. All six models train using stable native-logit BCE; checkpoint selection and registered comparisons use common clipped BCE.

Common clipped BCE was the primary endpoint; macro-F1 was secondary. Multi improves on Scalar on checkerboard and spiral, while routed Trig25 achieves lower mean common clipped BCE on both. Noisy-annulus and rare-disk results do not establish a general improvement from the richer readout. Small or unresolved differences are not equivalence results.

Forty selected circuit checkpoints were converted to equivalent classical coefficients. The checks found no classification differences and numerical agreement within the declared tolerances. Conversion reduced measured CPU inference time. It is another representation of the same fitted predictor, not an additional trained model.

An equally optimized routed Trig25 control uses the same coefficient inference kernel and has comparable inference cost; the global MLP is faster in the displayed tables. Conversion improves the retained circuit implementation without establishing a speed advantage over equally optimized classical controls or quantum speedup.

Study v0.6 and repository edition v1.0 are separate. Read the adopted [rights](RIGHTS.md), [verification guidance](VERIFY.md) and selected [source origins](provenance/SOURCE_MAP.json).

Start with the [quickstart](QUICKSTART.md), [source selection](SOURCE_SELECTION.json), [dependency inventory](DEPENDENCY_INVENTORY.json) and [inherited permissions](INHERITED_LICENSE_COVERAGE.json).

The bounded startup checks exact package integrity before and after its six required tests, parses all 61 selected Python files, and imports the selected numerical modules. The tests cover model shapes/paired initialization, independent circuit-state/moment agreement, orthogonal conversion nodes, both heads off grid and forced banks, constant logits/invalid contracts, and the learned Trig25 coefficient kernel. Missing compiler or test components fail startup. It does not train, score official data, sample shots, rerun benchmarks or submit QPU jobs. Success is not full scientific reproduction or a clean installation.

Datasets, checkpoints, installed environments and the complete retained archive are excluded. Selected scientific Python remains unchanged; current package helpers and guidance are separate from the historical experiment. No ETEL implementation is supplied.
