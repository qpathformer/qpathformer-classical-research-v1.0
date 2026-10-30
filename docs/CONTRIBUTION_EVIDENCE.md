# Reproducibility evidence for contributions

Use this checklist for findings submissions. Supply enough information for a reviewer to understand what was run, reproduce it within the permitted access scope and evaluate the claim. If data or equipment prevents an independent rerun, explain the restriction and distinguish inspectable evidence from reproduced results.

| Record | Required evidence |
| --- | --- |
| Question and status | Hypothesis or correction, prior study, new contribution, planned versus completed work |
| Code and environment | Commit, archive hashes, dependency versions, installation and execution commands, operating system |
| Data | Source, version, terms, split hashes, labels, transforms, duplicate/leakage checks and permitted access route |
| Configuration | All seeds, hardware, precision, batch policy, optimisers, stop rule, selection rule and resource cap |
| Comparison | Matched information and access, baselines, tuning budget, exposure and timing boundaries |
| Outcomes | All seeds, failures and retries, selected checkpoint identities, metrics, uncertainty and negative results |
| Cost | Preparation, training, evaluation, compilation and submission costs in named units |
| Provenance | Candidate asset hashes, parents, rights, material AI assistance and human verification |

For classical work record CPU/GPU configuration, memory, acceleration settings and whether wall time includes evaluation and checkpointing. Keep parameter counts, active parameters, FLOPs estimates, memory and measured runtime distinct.

For quantum work record simulator versus physical backend, provider/version, job identifiers where safely shareable, submission time, qubits, logical and compiled circuits, mapping, gates, compiled depth, shots, measurement processing, noise assumptions and calibration context. Count classical optimisation and compilation costs. State whether training used exact probabilities, simulated shots or physical measurements. Repeated shots from one checkpoint are not independent training runs.

Separate numerical implementation checks from predictive quality and claims of advantage. Preserve original logs securely, share only permitted extracts, and link corrections to the prior record. Use the [asset review process](ASSET_REVIEW.md) before distributing data, model artifacts or executable helpers.
