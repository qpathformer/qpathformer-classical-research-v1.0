"""Prepare a concrete Stage B proposal after verified Stage A selection.

Only root may create the separate approved STAGE_B_FREEZE.json. This script
does not start training or read any confirmation population or test outcome.
"""
import qstudy as s


def main():
    output=s.ROOT/"STAGE_B_PROPOSAL.json"
    if output.exists() or (s.ROOT/"STAGE_B_FREEZE.json").exists():
        raise FileExistsError("Preserve existing proposal/freeze for root review")
    original=s.read_json(s.ROOT/"STAGE_A_FREEZE.json")
    audit=s.read_json(s.ROOT/"STAGE_A_ENDPOINT_AUDIT.json")
    selection=s.read_json(s.ROOT/"STAGE_A_SELECTION.json")
    registration=s.read_json(s.ROOT/"EVALUATION_REGISTRATION.json")
    if (audit["status"]!="pass" or audit["count"]!=27 or audit["test_file_read"]
            or selection["stage_a_freeze_sha256"]!=s.digest(s.ROOT/"STAGE_A_FREEZE.json")
            or selection["test_accessed"] or s.source_hashes()!=original["source_hashes"]):
        raise ValueError("Verified complete development evidence and unchanged training source required")
    for path,sha in registration["source_hashes"].items():
        if s.digest(s.ROOT/path)!=sha:
            raise ValueError("Reviewed evaluation package changed")
    for endpoint in audit["endpoints"]:
        folder=s.ROOT/"stage_A"/f"seed_{endpoint['seed']}"/endpoint["method"]
        if (s.digest(folder/"result.json")!=endpoint["result_sha256"]
                or s.digest(folder/"selected_checkpoint.npz")!=endpoint["checkpoint_sha256"]):
            raise ValueError("Audited development endpoint changed")
    proposal=dict(original)
    for field in ("approved_utc","independent_review","proposal_sha256"):
        proposal.pop(field,None)
    proposal.update({"created_utc":s.now(),"review_status":"awaiting_separate_root_approval",
        "stage":"B","methods":selection["proposed_stage_b_methods"],"training_seeds":[401,402,403,404,405],
        "official_training_started":False,"registered_stage_b_runs":5*len(selection["proposed_stage_b_methods"]),
        "selected_candidate":selection["selected_candidate"],"confirmation_purpose":selection["confirmation_purpose"],
        "stage_a_freeze_sha256":s.digest(s.ROOT/"STAGE_A_FREEZE.json"),
        "stage_a_selection_sha256":s.digest(s.ROOT/"STAGE_A_SELECTION.json"),
        "stage_a_endpoint_audit_sha256":s.digest(s.ROOT/"STAGE_A_ENDPOINT_AUDIT.json"),
        "evaluation_registration_sha256":s.digest(s.ROOT/"EVALUATION_REGISTRATION.json"),
        "evaluation_source_sha256":s.digest(s.ROOT/"evaluate_confirmation.py"),
        "evaluation_independent_review_sha256":s.digest(s.ROOT/"EVALUATOR_INDEPENDENT_REVIEW.json"),
        "readiness_protocol_sha256":s.digest(s.ROOT/"READINESS_PROTOCOL.json"),
        "additional_reporting_sources_sha256":{name:s.digest(s.ROOT/name) for name in
            ("propose_stage_b.py","watch_stage_b.py","summarize_quantum.py","plot_confirmation.py","RESOURCE_DEFINITIONS.json")},
        "selected_development_validation_difference":selection["selected_minus_original_validation_bce"],
        "development_promising_flag":selection["development_promising_flag"],
        "test_evaluation_gate":"After all registered Stage B endpoints complete: independent validation replay and endpoint lock, then separate root-issued EVALUATION_RELEASE.json. No automatic evaluation or candidate reselection.",
        "probability_readout_repeats":"Five measurement repeats nested within each training checkpoint; 1024 and4096 budgets use separate RNG draws, not a shared-prefix sample.",
        "readiness_scope":"Local ideal Aer fixtures and RY/RZ/CX simulator basis only; not IBM backend ISA, noise-calibrated evidence or hardware execution.",
        "proposal_source_sha256":s.digest(__file__),
        "next_action":"Root reviews completed development evidence and this concrete proposal, then separately creates approved STAGE_B_FREEZE.json. No Stage B launch until then."})
    s.write_json(output,proposal)
    print("Stage B proposal saved; awaiting root review:",selection["selected_candidate"],proposal["registered_stage_b_runs"],"runs")


if __name__=="__main__":
    main()
