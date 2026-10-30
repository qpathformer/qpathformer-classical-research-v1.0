# Study v0.5 release notes

Q-Pathformer v0.5 examines how learned output heads change shallow circuit classifiers when compared with strong classical controls. Eleven recipes were evaluated on two independently generated circle populations and a rotated ellipse, using five paired training seeds and one fixed split per confirmation population. All circuit execution used classical compute.

The study completed 22 short engineering endpoints, 66 full development endpoints and 165 full confirmation endpoints. Every full endpoint completed 200 rounds and 15,000 optimizer updates. All eleven recipes continued to confirmation; early stopping was not used.

## Historical findings

Common clipped BCE was primary; macro-F1 was secondary. These are mean losses over five confirmation seeds:

| Recipe | Mean common clipped BCE: circle 1 | Circle 2 | Rotated ellipse |
| --- | ---: | ---: | ---: |
| Legacy | 0.22279 | 0.17937 | 0.21335 |
| Scalar | 0.01362 | 0.01676 | 0.02599 |
| Multi | 0.01315 | 0.01298 | 0.02096 |
| Trig25 routed | 0.01054 | 0.01201 | 0.01399 |

The learned-readout recipes substantially improved on the same-study Legacy recipe. Scalar changes the probability link, head parameters, capacity and native training loss together, so this comparison does not isolate the readout's contribution. Five-moment Multi adds a smaller, task-dependent benefit over Scalar: both circle adjusted seed intervals include zero; the ellipse loss reduction is below the registered 0.01 practical reference. The random frozen-core control performed substantially worse.

Routed Trig25 had the lowest mean common clipped BCE on all three confirmation populations. Its advantage over Multi was unresolved by the adjusted seed intervals on the circles and resolved on the ellipse. Trig25 controls combined high mean accuracy with much lower measured local execution time than the circuit recipes. These are measurements of the retained CPU implementations, not general hardware-efficiency or monetary-cost claims.

## Verification and research boundaries

These results concern small synthetic classifiers, fixed routers and unequal capacities. The ellipse changes the label boundary under the same uniform input distribution; it is not an out-of-distribution benchmark. Five training seeds and one fixed split per population do not establish broad task or real-world generalization. Historical scores from earlier studies provide context, not paired improvement evidence. No physical-QPU result, quantum advantage, ETEL implementation or full language-model benchmark is supplied.

The report's independent replay and local simulator checks are historical evidence. Current package verification is separate. The bounded startup helper checks package integrity before scientific imports and after its checks, parses all 52 selected Python files, imports the selected numerical modules and runs two selected tests: model parameter shapes/paired initialization, and independent circuit-state/moment agreement. It does not run training, official scoring, shot sampling, noise experiments or QPU jobs. Success does not establish a clean installation, every optional dependency or full historical reproduction.

## Packages and rights

The three companion downloads contain the preserved report in PDF and Word, readable guidance, and selected implementation. Reports, scientific source and historical records retain their reviewed bytes. Current helper and explanation changes require refreshed package identities and seals; no new experiment or report correction is claimed. Consult [START_HERE.md](START_HERE.md), the [research guide](RESEARCH_GUIDE.md), [verification guidance](VERIFY.md) and [source origins](provenance/SOURCE_MAP.json).

The identified original report content and explanatory prose are licensed under **CC BY 4.0**. Selected Python source and package helpers are **source available under the unchanged Q-Pathformer Platform License 1.0**. Each package includes its adopted scope; applicable earlier grants remain in force and excluded material retains its separate terms.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains the licensor; company affiliation does not transfer ownership.

The owner adopted the scheme on 29 October 2026. Existing licence texts and the adoption decision are preserved. Package identity updates are distinct from publication and repository visibility. The corresponding GitHub release records its current draft/publication status.
