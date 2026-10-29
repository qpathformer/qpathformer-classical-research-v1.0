Q Pathformer v0.5 internal readout study
Prepared for Anthony Siljeg
Study identity: QPATH-READOUT-v0.5
Guide generated: 2026-10-19T04:19:10.924958+00:00

Start with docs/QPATH-RPT-006_Flexible_Readouts_and_Classical_Controls_v0.5.docx.
The Word report explains the measured results, uncertainty, costs, limitations
and recommendations. This is internal research, not a publication or hardware trial.

Scope
Eleven small model recipes compare flexible circuit readouts with neural-network
and trigonometric controls on fresh two-dimensional circle and ellipse tasks.
All training and quantum simulation ran on classical CPU hardware. No GPU,
new language-model training, cloud jobs or physical quantum device was used.
The aim is useful classical implementation and evidence for later circuit tests;
these experiments do not benchmark the complete proposed language architecture.

Completed evidence
22 short engineering endpoints; 66 full development endpoints; 165 full confirmation
endpoints. Each official endpoint completed 200 rounds and 15,000 optimizer updates.
All eleven arms proceeded to confirmation. Both stages passed full saved-validation
replay, followed by a root release, official test scoring and independent prediction
and statistics replay. The local readiness capsule and its independent audit cover
60 quantum checkpoints and 1,920 validation fixture/checkpoint pairs. All shots are
simulated. The Word report passed scientific review and all 33 pages were
visually inspected. Prior v0.4 payloads and the four Baseline4 seal files were rehashed.

Evidence map
governance/                 Plans, frozen rules, runtime, preservation and release tools
quantum/data/               Fresh data, training-only router policies and data seal
quantum/stage_A/            Development logs, every-round evidence and checkpoints
quantum/stage_B/            Confirmation logs, every-round evidence and checkpoints
quantum/confirmation_evaluation/   Official predictions and population statistics
analysis/independent_replay/confirmation_replay/   Independent prediction/statistics replay
analysis/learning_resources/       Validation milestones and measured resource summaries
quantum/local_readiness_confirmation/             QASM, noise, shots and local simulator checks
analysis/classical_review/confirmation_readiness_audit/   Independent capsule audit
report_work/               Retained template, report source, figures and QA records
docs/                      Final internal Word report

Verification and reuse
REPRODUCTION_GUIDE.txt provides safe replay instructions. Keep the delivered package
and all previous seals unchanged. Use a verified writable copy and fresh output
folders for computation. Do not train or rewrite results inside this package.
The exact-byte inventory is DELIVERY_MANIFEST.json. Separate root and independent
delivery verification records must both report PASS before this package is treated
as a verified delivery. The guide itself does not substitute for those records.
Source-data exclusions, uncertainty scopes, numerical tolerances and known limitations
are documented in the report and frozen protocols. Historical v0.4 scores are context,
not paired evidence of a version-to-version improvement.

Final Word SHA256: b08a039280e478710eeae7faa521fd37a41224bfd81100391ba8880f15992fb9
Report input approval SHA256: 43d03e335edac6be6436b8189feb3d21c7e4cd7af01eff96bf34a16fb12b669a
