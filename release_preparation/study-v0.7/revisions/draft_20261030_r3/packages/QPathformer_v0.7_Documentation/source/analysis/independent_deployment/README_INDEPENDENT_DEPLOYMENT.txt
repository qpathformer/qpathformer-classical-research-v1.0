Q-Pathformer v0.7 independent conversion and shot audit (internal)

Preparation has used only synthetic arrays, source text and metadata. No official
test population, selected checkpoint, model outcome, conversion or timing has
been accessed or performed by this implementation before root release.

Independent numerical implementation
- reference.py uses explicit dense Kronecker matrices for the two-qubit core.
- State amplitude Laurent polynomials are propagated algebraically through gates;
  bra/ket convolution gives frequencies -2..2. A complex-to-real change of basis
  yields the25coefficients. No interpolation, grid projection, fitting, producer
  circuit, compiler or Model calls enter this coefficient reconstruction.
- Real feature order is x0 then x1, rowmajor tensor product of
  [1,cos(pi*x),sin(pi*x),cos(2*pi*x),sin(2*pi*x)].
- Immutable geometric/hash routes are separately reconstructed from raw inputs.
- Clipped Voronoi edges are reconstructed by feasible polygon vertices rather
  than the producer's halfspace-interval algorithm. The same frozen stream
  reconstructs128offgrid probes. All actual boundary and forced-bank probes stay.
- Shot audit derives XX/ZZ probabilities from independent states, then replays
  exact registered multinomial streams against retained normalized probabilities
  after verifying those probabilities. This avoids claiming count discrepancies
  caused solely by harmless tiny floating-point state differences.
- Joint count covariance is preserved. Independent moments, logits, probabilities,
  MAE/MSE/bias/variance, count conservation, head norms and analytic logit variance
  are checked, along with the producer's descriptive delta-method approximation.

Pre-outcome source snapshot (metadata only)
  python -B -X utf8 analysis/independent_deployment/audit_artifacts.py
    --phase freeze --output ABSOLUTE_NEW_SOURCE_FREEZE.json
  Never creates a release. Root must bind and review the snapshot before access.

Separate root authorization for each independent audit phase
  {
    "schema": "qpath-v07-independent-deployment-release-1",
    "review_status": "approved_by_root",
    "phase": "conversion" or "shots",
    "test_access_authorized": true,
    "max_parallel_tasks": 1,
    "required_blas_threads": 1,
    "output": ABSOLUTE_FRESH_DIRECTORY_UNDER_STUDY_ANALYSIS,
    "source_freeze": binding of independent source snapshot,
    "evaluation_release": binding of original root test release,
    "evaluation_commit": binding of completed official EVALUATION_COMMIT.json,
    "producer_commit": binding of CONVERSION_COMMIT.json or SHOTS_COMMIT.json
  }
  Binding is {path:absolute path,sha256:SHA256,bytes:integer}.

Execution (only after root approval and complete producer output)
  C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe -B -X utf8
    analysis/independent_deployment/audit_artifacts.py
    --phase conversion|shots --authorization AUTHORIZATION --output OUTPUT

The CLI acquires the existing ETEL audit lease itself, excludes training/timing,
and uses the historical one-thread scientific environment. It rechecks all512
original B endpoints, both audits, source/data/protocol hashes, and every official
evaluation payload before input/model loading. It also validates the completed
producer commit and its root authorization/source registration. Never wrap it in
another copy of the same exclusive lease (that would deadlock/fail acquisition).

Conversion output
- summary.json: statusPASS,phaseconversion,circuit_endpoints192,
  representations_replayed448,learned_trig_exact_repacks256,conversion_commit
  exactbinding,authorizationbinding.
- Independent reference validation/test prediction NPZs for every transformed
  representation; conversion_replay.json records all errors and disagreements.
- Timing must bind this successful independent conversion summary and its
  INDEPENDENT_DEPLOYMENT_COMMIT before isolated sessions. Root can name these
  independent_conversion_audit and independent_conversion_commit.

Shot output
- summary.json: statusPASS,phase shots,checkpoints192,count_arrays12800,
  count_vectors409600,prediction_values245760,represented_measurement_outcomes
  1132462080,producer_commit exactbinding.
- Independent reconstructed sampled probabilities and shot_replay.json preserve
  technical diagnostics; these are classical conditional simulations, never
  heldout F1, physical shots or independent learned-model replicates.

Both phases write START,summary and INDEPENDENT_DEPLOYMENT_COMMIT with complete
hash inventories. Failed runs retain FAILURE.json and partial evidence, never
overwrite outputs. Root must record a fresh same-recipe audit recovery.
Numerical tolerances before outcomes: coefficient2e-11, probability2e-12,
native-logit1e-9; class disagreement requires both probabilities within32float64
eps of0.5 and all disagreements remain retained. These are representation parity
checks, not accuracy improvements or proof of physical hardware readiness.

Remaining steps at handoff
1. Finish producer source review/registration and bind independent source freeze.
2. Complete registered A/B and all dual audits; root releases official testing.
3. Official evaluation and separate independent prediction/statistics replay.
4. Root-authorized conversion; independent conversion audit above.
5. Three fresh isolated timing sessions with available-host-memory snapshots and
   independent conversion proof; independent timing inventory/statistics review.
6. Root-authorized joint-shot producer; independent shot audit above.
7. Root combines findings/limitations/costs, renders and verifies internal report,
   reverifies sealed baseline and delivers evidence. These preflight tests do not
   constitute completed study delivery.
