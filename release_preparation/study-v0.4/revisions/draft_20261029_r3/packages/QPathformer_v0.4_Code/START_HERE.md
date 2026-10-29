# Q-Pathformer study v0.4 Code

This completed study crosses a two-qubit, depth-two circuit model (Q2), a raw-coordinate ReLU MLP and a 25-feature trigonometric sigmoid-logit model with global, coordinate-hash and training-only k-means routing. Routed examples activate one of five parameter banks; the fixed k-means router is fitted to training coordinates without labels.

All 54 development and 135 confirmation endpoints completed 200 rounds and 15,000 optimizer updates per endpoint. Confirmation used five training seeds per model/population combination across two independent circle populations and a rotated ellipse. All circuit execution was simulated on classical compute. Companion Study and Documentation downloads explain the primary BCE results, stronger classical controls and uncertainty.

Start with [QUICKSTART.md](QUICKSTART.md), [DEPENDENCIES.md](DEPENDENCIES.md), [source selection](SOURCE_SELECTION.json) and [exact code licence scope](CODE_LICENSE_SCOPE.json). The selected Python files and package helpers are source available under the unchanged Q-Pathformer Platform License 1.0. This selection contains no ETEL implementation. Original scientific Python files are copied unchanged. [Inherited licence mapping](INHERITED_LICENSE_MAP.json) preserves earlier grants.

Bounded startup checks use in-memory predictions for the nine model/routing combinations, training CLI help and the selected full-matrix agreement invariant. They do not run training, historical scientific replay, shot sampling or QPU jobs. Datasets, checkpoints, full operational archives, installed dependencies and credentials are excluded. Historical full-study commands remain evidence and need separate inputs and reviewed path bindings. [Rights](RIGHTS.md) · [Verification](VERIFY.md).
