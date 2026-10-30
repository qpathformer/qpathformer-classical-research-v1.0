# Q-Pathformer Study v0.6 Study

**Harder Tasks and Faster Inference**

Q-Pathformer v0.6 asks whether richer circuit readouts help on harder classification boundaries, and whether the same trained circuit can run faster through an equivalent classical representation. Six recipes were compared on checkerboard, spiral, noisy annulus and rare-positive disks, using five paired training seeds on one fixed confirmation split per task family. All circuit execution used classical compute.

The completed design includes 48 development and 120 confirmation endpoints, plus 24 separate engineering endpoints. Every full endpoint completed 200 rounds and 15,000 optimizer updates. All six models train using stable native-logit BCE; checkpoint selection and registered comparisons use common clipped BCE.

Common clipped BCE was the primary endpoint; macro-F1 was secondary. Multi improves on Scalar on checkerboard and spiral, while routed Trig25 achieves lower mean common clipped BCE on both. Noisy-annulus and rare-disk results do not establish a general improvement from the richer readout. Small or unresolved differences are not equivalence results.

Forty selected circuit checkpoints were converted to equivalent classical coefficients. The checks found no classification differences and numerical agreement within the declared tolerances. Conversion reduced measured CPU inference time. It is another representation of the same fitted predictor, not an additional trained model.

An equally optimized routed Trig25 control uses the same coefficient inference kernel and has comparable inference cost; the global MLP is faster in the displayed tables. Conversion improves the retained circuit implementation without establishing a speed advantage over equally optimized classical controls or quantum speedup.

Study v0.6 and repository edition v1.0 are separate. Read the adopted [rights](RIGHTS.md), [verification guidance](VERIFY.md) and selected [source origins](provenance/SOURCE_MAP.json).

Read the preserved report in [PDF](reports/QPathformer_v0.6_Report.pdf) or [Word](reports/QPathformer_v0.6_Report.docx). The [edition record](provenance/EDITION_CHANGES.md) explains the appended note and metadata. All original scientific content, three figures and 39 tables remain preserved; current wrapper clarification does not reissue the report.

These are small two-dimensional synthetic binary classifiers with fixed routers and unequal capacities. Five paired training seeds on one fixed confirmation split per task family do not establish population-wide or real-world generalization. Historical prior-version scores provide context, not paired improvement evidence. No physical-QPU result, quantum advantage, ETEL implementation or full language-architecture benchmark is supplied.

Historical full-delivery paths refer to retained evidence, not files in this curated download. Companion Documentation and Code packages provide explanation and selected source. Packaging adds no experiments.
