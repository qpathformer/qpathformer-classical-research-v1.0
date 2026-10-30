# Study v0.6 release notes

Q-Pathformer v0.6 asks whether richer circuit readouts help on harder classification boundaries, and whether the same trained circuit can run faster through an equivalent classical representation. Six recipes were compared on checkerboard, spiral, noisy annulus and rare-positive disks, using five paired training seeds on one fixed confirmation split per task family. All circuit execution used classical compute.

The completed design includes 48 development and 120 confirmation endpoints, plus 24 separate engineering endpoints. Every full endpoint completed 200 rounds and 15,000 optimizer updates. All six models train using stable native-logit BCE; checkpoint selection and registered comparisons use common clipped BCE.

## Historical findings

Common clipped BCE was primary; macro-F1 was secondary. These are mean losses over five confirmation seeds:

| Recipe | Checkerboard | Spiral | Noisy annulus | Rare disks |
| --- | ---: | ---: | ---: | ---: |
| Scalar | 0.57805 | 0.50069 | 0.41064 | 0.01345 |
| Multi | 0.52162 | 0.42532 | 0.40911 | 0.01456 |
| Routed Trig25 | 0.30504 | 0.24828 | 0.40317 | 0.01487 |

Multi improves on Scalar on checkerboard and spiral, while routed Trig25 achieves lower mean common clipped BCE on both. Noisy-annulus and rare-disk results do not establish a general improvement from the richer readout. Small or unresolved differences are not equivalence results.

Forty selected circuit checkpoints were converted to equivalent classical coefficients. The checks found no classification differences and numerical agreement within the declared tolerances. Conversion reduced measured CPU inference time. It is another representation of the same fitted predictor, not an additional trained model.

An equally optimized routed Trig25 control uses the same coefficient inference kernel and has comparable inference cost; the global MLP is faster in the displayed tables. Conversion improves the retained circuit implementation without establishing a speed advantage over equally optimized classical controls or quantum speedup.

## Verification and research boundaries

These are small two-dimensional synthetic binary classifiers with fixed routers and unequal capacities. Five paired training seeds on one fixed confirmation split per task family do not establish population-wide or real-world generalization. Historical prior-version scores provide context, not paired improvement evidence. No physical-QPU result, quantum advantage, ETEL implementation or full language-architecture benchmark is supplied.

The report's independent replay and local simulator checks are historical evidence. Current package verification is separate. The bounded startup checks exact package integrity before and after its six required tests, parses all 61 selected Python files, and imports the selected numerical modules. The tests cover model shapes/paired initialization, independent circuit-state/moment agreement, orthogonal conversion nodes, both heads off grid and forced banks, constant logits/invalid contracts, and the learned Trig25 coefficient kernel. Missing compiler or test components fail startup. It does not train, score official data, sample shots, rerun benchmarks or submit QPU jobs. Success is not full scientific reproduction or a clean installation.

## Packages and rights

The three companion downloads contain the preserved report in PDF and Word, readable guidance, and selected implementation. Reports, scientific source and historical records retain their reviewed bytes. Current helper and explanation changes require refreshed package identities and seals; no new experiment or report correction is claimed. Consult [START_HERE.md](START_HERE.md), the [research guide](RESEARCH_GUIDE.md), [verification guidance](VERIFY.md) and [source origins](provenance/SOURCE_MAP.json).

The identified original report content and explanatory prose are licensed under **CC BY 4.0**. Selected Python source and package helpers are **source available under the unchanged Q-Pathformer Platform License 1.0**. Each package identifies its adopted scope and exclusions; applicable earlier grants remain in force.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains the licensor; company affiliation does not transfer ownership.

The owner adopted the scheme on 29 October 2026. Existing licence texts and the adoption decision are preserved. Package identity updates are distinct from publication and repository visibility. The corresponding GitHub release records its current draft/publication status.
