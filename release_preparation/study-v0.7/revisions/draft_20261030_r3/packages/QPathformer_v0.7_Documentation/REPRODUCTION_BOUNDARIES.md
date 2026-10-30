# Reproduction boundaries

Bounded startup verifies exact package integrity before and after execution, parses all 52 Python files, imports NumPy/SciPy and selected modules, checks two inputs through a zero-angle circuit plus a sigmoid comparison, and requires successful `--help` from `quantum/study.py`, `execution/launcher.py` and `execution/bind_stage.py`. It does not test all eight model families, independently compare matrices, run conversion parity, execute ETEL fits/recovery, score official data or rerun timing/sampling.

No training, ETEL fit launch, cancellation/recovery exercise, official evaluation, shot sampling, timing benchmark, QPU preparation or installation is part of release verification. The downloads exclude data, checkpoints, installed environments and the complete retained archive. Full replay needs those separately retained inputs and reviewed environment/path bindings. Original commands and absolute paths are history, not the curated quickstart.

The original Windows resource APIs, OpenBLAS binary and recovery behavior are not validated by imports/help. Recorded historical dependency versions remain observations, while new receipts record the actual runtime.

The Code package includes the study-specific execution integration for **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**, using retained ETEL source version **0.2.0**. It schedules complete registered fits in isolated local processes. The component label, historical source version, study v0.7 and repository edition v1.0 identify different things. This selection is not a standalone ETEL component release.

The findings concern four small synthetic binary task families on classical CPU hardware. Eight population differences per task and small-sample t assumptions limit generalization. Historical cross-version scores are context, not paired improvement evidence. No physical-QPU performance, device-noise tolerance, full language-architecture benchmark or quantum advantage is established.

See the [overview](OVERVIEW.md), [source map](SOURCE_MAP.json) and [rights](RIGHTS.md).
