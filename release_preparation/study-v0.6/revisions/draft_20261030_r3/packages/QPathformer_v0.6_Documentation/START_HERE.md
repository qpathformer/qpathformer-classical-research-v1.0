# Q-Pathformer Study v0.6 Documentation

**Harder Tasks and Faster Inference**

Q-Pathformer v0.6 asks whether richer circuit readouts help on harder classification boundaries, and whether the same trained circuit can run faster through an equivalent classical representation. Six recipes were compared on checkerboard, spiral, noisy annulus and rare-positive disks, using five paired training seeds on one fixed confirmation split per task family. All circuit execution used classical compute.

The completed design includes 48 development and 120 confirmation endpoints, plus 24 separate engineering endpoints. Every full endpoint completed 200 rounds and 15,000 optimizer updates. All six models train using stable native-logit BCE; checkpoint selection and registered comparisons use common clipped BCE.

Common clipped BCE was the primary endpoint; macro-F1 was secondary. Multi improves on Scalar on checkerboard and spiral, while routed Trig25 achieves lower mean common clipped BCE on both. Noisy-annulus and rare-disk results do not establish a general improvement from the richer readout. Small or unresolved differences are not equivalence results.

Forty selected circuit checkpoints were converted to equivalent classical coefficients. The checks found no classification differences and numerical agreement within the declared tolerances. Conversion reduced measured CPU inference time. It is another representation of the same fitted predictor, not an additional trained model.

An equally optimized routed Trig25 control uses the same coefficient inference kernel and has comparable inference cost; the global MLP is faster in the displayed tables. Conversion improves the retained circuit implementation without establishing a speed advantage over equally optimized classical controls or quantum speedup.

Study v0.6 and repository edition v1.0 are separate. Read the adopted [rights](RIGHTS.md), [verification guidance](VERIFY.md) and selected [source origins](provenance/SOURCE_MAP.json).

Read the [research guide](RESEARCH_GUIDE.md), [release notes](RELEASE_NOTES.md), [original study overview](source_guidance/README.txt) and [reproduction guide](source_guidance/REPRODUCTION_GUIDE.txt). Historical commands require the full retained evidence and are not an instruction to run the study from these curated downloads. The companion Study package provides the report in PDF and Word; Code provides the selected implementation and bounded checks.
