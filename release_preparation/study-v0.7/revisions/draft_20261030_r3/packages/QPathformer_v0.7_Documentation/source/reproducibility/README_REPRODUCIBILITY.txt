Q-Pathformer v0.7 — internal reproducibility and evidence verification

This folder is the entry point for checking the delivered evidence package.
It does not grant test access, launch jobs, publish code or contact a service.
Keep the original manifests and recorded absolute paths unchanged.

What can be verified offline
1. Every payload listed in DELIVERY_MANIFEST.json, including source, data,
   router policies, logs, checkpoint states, prediction arrays and analyses.
   File count, byte count, SHA256 and unexpected files are checked.
2. After the archived root test release and successful evaluation are present,
   reconstruct principal validation/test metrics from all512 archived model
   prediction files and compare the20 registered population-level contrasts.
   Prediction record IDs and observed labels are checked against the archived
   validation/test data. No latent clean/noise diagnostic arrays are loaded.
3. Resolve recorded original absolute paths to their package-relative location
   explicitly, without editing any frozen protocol, release, commit or audit.

The verifier uses only Python's standard library; it does not import NumPy,
Qiskit, a trainer, ETEL or the official evaluator. It reads strictly bounded
numeric one-dimensional NPY arrays inside NPZ files without pickle. It writes
only its JSON result to standard output. Its own synthetic tests were run using
the scientific Python installation; the t-critical-value test additionally
uses SciPy. Hash verification is independent of the scientific runtime.

Commands on the original computer, AFTER final delivery
PowerShell:

& 'C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe' -B `
  'C:\Q2\Improvement_Study_v0.7\reproducibility\verify_package.py' `
  --package 'C:\Q2\Improvement_Study_v0.7'

To also replay the archived prediction metrics and primary statistics:

& 'C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe' -B `
  'C:\Q2\Improvement_Study_v0.7\reproducibility\verify_package.py' `
  --package 'C:\Q2\Improvement_Study_v0.7' --replay-scores `
  --release 'governance/EVALUATION_RELEASE.json'

Use the actual retained release path if the final package names it differently.
The command refuses absent/incomplete release, dual audits or evaluation.
Redirect standard output to a NEW file OUTSIDE the package if a receipt is
wanted. A new file inside the package changes its inventory and should not be
mistaken for part of the frozen delivery.

On a relocated package
Use a Python3.10+ interpreter with the same script and --package set to the
extracted package directory. This standard-library verification path was tested
with synthetic relocation fixtures on Windows/Python3.12.14; execution on every
operating system has not been tested.

The script first verifies the delivery inventory and then reads the original
working_root from DELIVERY_MANIFEST.json. The frozen STUDY_PLAN.json does not
need or receive a new working_root field. If the delivery manifest has no
working_root, supply an explicit --map-root for the recorded original root.
For this study it is C:\Anthony Siljeg\Q2_improvement_study_v07. Recorded paths
under that exact root are mapped to the same relative files under --package.
If a retained binding was deliberately recorded against another root that
refers to THIS SAME package, add --map-root 'that exact original root'.
Do not map C:\Q2 or a parent directory indiscriminately. External baseline
archives and unrelated paths are never silently redirected into this package.
The JSON result reports each mapping used.

Accepted delivery inventories are files lists using relative_path/size_bytes/
sha256 (the historical final-delivery convention), or path/bytes/sha256.
Conflicting duplicate key forms are rejected. A files dictionary keyed by
relative path with bytes/sha256 values is also supported. The final package
writer must choose one of these explicit schemas and include working_root;
the verifier never rewrites a manifest to make its schema fit.

Paths are mapped only during reading. Original JSON bytes, absolute path text,
SHA256 records and provenance remain intact. Hash agreement proves consistency
with the retained manifest, not a digital signature or an independent date of
creation. Keep any separate archive/seal hash as an external trust anchor.

Scientific environment actually used
- Windows CPU execution, Python3.12.14.
- NumPy2.5.4 and SciPy1.18.1.
- One effective OpenBLAS thread per scientific worker.
- Six numerical thread variables set to1: OMP_NUM_THREADS,
  OPENBLAS_NUM_THREADS, MKL_NUM_THREADS, NUMEXPR_NUM_THREADS,
  VECLIB_MAXIMUM_THREADS and BLIS_NUM_THREADS.
- The recorded OpenBLAS configuration is
  OpenBLAS0.3.34.106.0 USE64BITINT DYNAMIC_ARCH NO_AFFINITY SkylakeX
  MAX_THREADS=24. Effective worker threads, not the library maximum, were1.
- Exact interpreter/DLL identity is retained in
  execution/RESOURCE_ENVIRONMENT_CHECK.json and the bound stage manifests.
- The original interpreter is
  C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe.
  Its installed environment was reused read-only; it is not a relocatable
  virtual environment embedded in this package.

requirements-scientific.txt records the two scientific library versions. It
is not a complete machine/environment lock, a wheel bundle or proof that those
builds can be installed on another platform. Python and wheel availability,
the BLAS binary, numerical identity and installed simulator dependencies must
be checked separately before a new scientific execution. No installation or
network access is performed by the verifier.

Three different reproduction scopes
A. Portable read-only evidence/score verification
   The commands above recompute metrics from retained predictions and replay
   the declared paired-population t intervals. They hash-check model/data files
   but do not regenerate model predictions or repeat training. No study claims
   should describe this as a new independent experimental replication.

B. Full independent model prediction/statistics replay in the original tree
   analysis/independent_audit/README_INDEPENDENT_REPLAY.txt documents the frozen
   reference implementation and run_replay_leased.py. It uses the exact raw
   inputs, policies and selected checkpoint and separately reconstructs
   predictions, metrics and analyses. It requires all512 B endpoints plus
   author/independent audits, root hash-bound evaluation release, a complete
   official evaluation and an external ETEL auxiliary lease. Do not invoke it
   during training or isolated timing. It remains original-root execution;
   this package does not claim that every frozen runtime path is relocatable.

C. Future fresh-root scientific reproduction
   A new reproduction needs a separate unsealed working tree and new execution
   metadata/authorizations. Preserve this delivered tree and all original
   protocols. Reuse the delivered frozen data/router policies for an exact
   task replication, or explicitly preregister new populations for a new study.
   Do not rerun official jobs in the existing ledger or overwrite endpoints.

   A future environment setup would have the following general shape:
     <verified Python3.12.14> -m venv <new reproduction root>\.venv
     <new venv Python> -m pip install -r requirements-scientific.txt
   These are preparation examples, not verified portable execution commands.
   Prefer locally archived compatible wheels; no wheel archive is asserted
   here. Validate actual NumPy/SciPy/BLAS identities, run synthetic checks,
   implement/review path bindings for the new root, register its resources,
   and only then create fresh stage authorizations and a separate ledger.

   The original data-generation code also references historical source trees
   for freshness checks. A relocated training run cannot simply execute that
   generator and assume those external datasets exist. Reusing archived data
   and generating scientifically fresh data are distinct reproduction tasks.
   Fully relocatable training has not been verified and is not claimed.

Limits and retained external provenance
The delivered package contains this study's evidence. A prior-version seal
receipt can be checked as a file, but it does not magically include every
external baseline archive it references. Verification of those original
archives requires their separately retained files/seals. The final report
must distinguish full repeated training, independent prediction replay,
metric replay and file-integrity checks.

All materials remain internal. Physical quantum testing belongs to the
separately authorized later release; this verification tool cannot start it.
