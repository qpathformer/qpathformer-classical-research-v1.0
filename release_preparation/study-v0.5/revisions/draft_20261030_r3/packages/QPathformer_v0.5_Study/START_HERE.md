# Q-Pathformer Study v0.5 Study

**Flexible Readouts and Classical Controls**

Q-Pathformer v0.5 examines how learned output heads change shallow circuit classifiers when compared with strong classical controls. Eleven recipes were evaluated on two independently generated circle populations and a rotated ellipse, using five paired training seeds and one fixed split per confirmation population. All circuit execution used classical compute.

The study completed 22 short engineering endpoints, 66 full development endpoints and 165 full confirmation endpoints. Every full endpoint completed 200 rounds and 15,000 optimizer updates. All eleven recipes continued to confirmation; early stopping was not used.

Common clipped BCE was the primary endpoint; macro-F1 was secondary. The learned-readout recipes substantially improved on the same-study Legacy recipe. Scalar changes the probability link, head parameters, capacity and native training loss together, so this comparison does not isolate the readout's contribution. Five-moment Multi adds a smaller, task-dependent benefit over Scalar: both circle adjusted seed intervals include zero; the ellipse loss reduction is below the registered 0.01 practical reference. The random frozen-core control performed substantially worse.

Routed Trig25 had the lowest mean common clipped BCE on all three confirmation populations. Its advantage over Multi was unresolved by the adjusted seed intervals on the circles and resolved on the ellipse. Trig25 controls combined high mean accuracy with much lower measured local execution time than the circuit recipes. These are measurements of the retained CPU implementations, not general hardware-efficiency or monetary-cost claims.

Study v0.5 and repository edition v1.0 are separate. Read the adopted [rights](RIGHTS.md), [verification guidance](VERIFY.md) and selected [source origins](provenance/SOURCE_MAP.json).

Read the preserved report in [PDF](reports/QPathformer_v0.5_Report.pdf) or [Word](reports/QPathformer_v0.5_Report.docx). The [edition record](provenance/EDITION_CHANGES.md) explains the appended note and metadata. All original scientific content, four figures and 25 tables remain preserved; current wrapper clarification does not reissue the report.

These results concern small synthetic classifiers, fixed routers and unequal capacities. The ellipse changes the label boundary under the same uniform input distribution; it is not an out-of-distribution benchmark. Five training seeds and one fixed split per population do not establish broad task or real-world generalization. Historical scores from earlier studies provide context, not paired improvement evidence. No physical-QPU result, quantum advantage, ETEL implementation or full language-model benchmark is supplied.

Historical full-delivery paths refer to retained evidence, not files in this curated download. Companion Documentation and Code packages provide explanation and selected source. Packaging adds no experiments.
