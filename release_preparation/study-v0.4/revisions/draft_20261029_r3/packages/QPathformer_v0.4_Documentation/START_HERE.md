# Q-Pathformer study v0.4 Documentation

This completed study asks what shallow circuit models contribute when conventional models have access to the same routing choices. It crosses a two-qubit, depth-two circuit model (Q2), a raw-coordinate ReLU MLP and a 25-feature trigonometric sigmoid-logit model with global, coordinate-hash and training-only k-means routing. Routed examples activate one of five parameter banks; the fixed k-means router is fitted to training coordinates without labels.

All 54 development and 135 confirmation endpoints completed 200 rounds and 15,000 optimizer updates per endpoint. Confirmation used five training seeds per model/population combination on two independent circle populations and a rotated ellipse. All circuit execution was simulated on classical compute.

Binary cross-entropy (BCE; lower is better) was primary. Spatial routing improved Q2 over hash routing, while global MLP and global trigonometric controls achieved lower mean BCE and higher mean macro-F1 on every confirmation population. Routed trigonometric models also had lower BCE than routed Q2. The Q2-versus-small-routed-MLP BCE comparison remains unresolved across training seeds.

Read the [research guide](RESEARCH_GUIDE.md) for results, capacities, uncertainty and local-readiness accounting; the [reproduction boundaries](REPRODUCIBILITY.md) explain the curated selection. Also see the [release notes](RELEASE_NOTES.md) and original [study guidance](historical/REPRODUCTION_GUIDE.txt). Repository edition v1.0 is separate from study v0.4. [Rights](RIGHTS.md) · [Verification](VERIFY.md).
