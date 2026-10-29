"""Manually invoked root release after review of completed confirmation evidence.

This creates an authorization manifest only. It never reads test data, runs
models, starts training, or calls the evaluator. Never invoke before root has
reviewed the actual endpoint lock and local-readiness results.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import uuid
ROOT = Path(__file__).resolve().parents[1]
Q = ROOT / 'quantum'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def require(condition, message):
    if not condition:
        raise ValueError(message)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root-reviewed', action='store_true', required=True)
    parser.parse_args()
    out = Q / 'EVALUATION_RELEASE.json'
    require(not out.exists() and (not (Q / 'confirmation_evaluation').exists()), 'Preserve prior release/evaluation')
    freeze = read(Q / 'STAGE_B_FREEZE.json')
    require(sha(Q / 'STAGE_B_FREEZE.json') == 'edcdb0b04f3c7676277ad9fd5f20695ca4792cc1b527530161ca42b95ca0b4c5', "Release validation failed: sha(Q / 'STAGE_B_FREEZE.json') == 'edcdb0b04f3c7676277ad9fd5f20695ca4792cc1b527530161ca42b95ca0b4c5'")
    require(freeze['review_status'] == 'approved_by_root' and freeze['registered_stage_b_runs'] == 40, "Release validation failed: freeze['review_status'] == 'approved_by_root' and freeze['registered_stage_b_runs'] == 40")
    require(freeze['training_seeds'] == list(range(401, 406)) and freeze['selected_candidate'] == 'untied_assigned', "Release validation failed: freeze['training_seeds'] == list(range(401, 406)) and freeze['selected_candidate'] == 'untied_assigned'")
    for hashes in [freeze['source_hashes'], freeze['additional_reporting_sources_sha256'], read(Q / 'EVALUATION_REGISTRATION.json')['source_hashes'], read(Q / 'READINESS_PROTOCOL.json')['source_hashes']]:
        for name, expected in hashes.items():
            require(sha(Q / name) == expected, name)
    for field, name in [('stage_a_selection_sha256', 'STAGE_A_SELECTION.json'), ('stage_a_endpoint_audit_sha256', 'STAGE_A_ENDPOINT_AUDIT.json'), ('evaluation_registration_sha256', 'EVALUATION_REGISTRATION.json'), ('evaluation_source_sha256', 'evaluate_confirmation.py'), ('evaluation_independent_review_sha256', 'EVALUATOR_INDEPENDENT_REVIEW.json'), ('readiness_protocol_sha256', 'READINESS_PROTOCOL.json'), ('data_seal_sha256', 'data/DATA_SEAL.json')]:
        require(freeze[field] == sha(Q / name), field)
    require(freeze['root_analysis_protocol_sha256'] == sha(ROOT / 'governance/ANALYSIS_PROTOCOL.json'), "Release validation failed: freeze['root_analysis_protocol_sha256'] == sha(ROOT / 'governance/ANALYSIS_PROTOCOL.json')")
    stage = read(Q / 'stage_B/stage_status.json')
    require(stage['status'] == 'completed' and {r['seed'] for r in stage['exits']} == set(range(401, 406)), "Release validation failed: stage['status'] == 'completed' and {r['seed'] for r in stage['exits']} == set(range(401, 406))")
    require(len(stage['exits']) == 5 and all((r['exit_code'] == 0 for r in stage['exits'])), "Release validation failed: len(stage['exits']) == 5 and all((r['exit_code'] == 0 for r in stage['exits']))")
    for seed in range(401, 406):
        require(read(Q / 'stage_B' / f'seed_{seed}' / 'failures.json') == [], "Release validation failed: read(Q / 'stage_B' / f'seed_{seed}' / 'failures.json') == []")
    require(not (Q / 'stage_B_watch/failure.json').exists(), "Release validation failed: not (Q / 'stage_B_watch/failure.json').exists()")
    ready = read(Q / 'stage_B_watch/READY_FOR_EVALUATION_REVIEW.json')
    lock_path = Q / 'CONFIRMATION_ENDPOINT_LOCK.json'
    lock = read(lock_path)
    require(ready['registered_endpoints'] == 40 and ready['test_population_read'] is False, "Release validation failed: ready['registered_endpoints'] == 40 and ready['test_population_read'] is False")
    require(ready['endpoint_lock_sha256'] == sha(lock_path), "Release validation failed: ready['endpoint_lock_sha256'] == sha(lock_path)")
    require(lock['status'] == 'pass' and lock['test_file_read'] is False, "Release validation failed: lock['status'] == 'pass' and lock['test_file_read'] is False")
    require(lock['stage_b_freeze_sha256'] == sha(Q / 'STAGE_B_FREEZE.json') == ready['stage_b_freeze_sha256'], "Release validation failed: lock['stage_b_freeze_sha256'] == sha(Q / 'STAGE_B_FREEZE.json') == ready['stage_b_freeze_sha256']")
    require(lock['evaluator_sha256'] == sha(Q / 'evaluate_confirmation.py') == ready['evaluator_sha256'], "Release validation failed: lock['evaluator_sha256'] == sha(Q / 'evaluate_confirmation.py') == ready['evaluator_sha256']")
    require(lock['stage_a_selection_sha256'] == freeze['stage_a_selection_sha256'], "Release validation failed: lock['stage_a_selection_sha256'] == freeze['stage_a_selection_sha256']")
    require(lock['data_seal_sha256'] == freeze['data_seal_sha256'], "Release validation failed: lock['data_seal_sha256'] == freeze['data_seal_sha256']")
    require(lock['root_analysis_protocol_sha256'] == freeze['root_analysis_protocol_sha256'], "Release validation failed: lock['root_analysis_protocol_sha256'] == freeze['root_analysis_protocol_sha256']")
    require(lock['selected_candidate'] == freeze['selected_candidate'], "Release validation failed: lock['selected_candidate'] == freeze['selected_candidate']")
    identities = {(seed, method) for seed in freeze['training_seeds'] for method in freeze['methods']}
    require(len(identities) == len(lock['endpoints']) == 40, "Release validation failed: len(identities) == len(lock['endpoints']) == 40")
    require({(r['seed'], r['method']) for r in lock['endpoints']} == identities, "Release validation failed: {(r['seed'], r['method']) for r in lock['endpoints']} == identities")
    for item in lock['endpoints']:
        folder = Q / 'stage_B' / f"seed_{item['seed']}" / item['method']
        result = read(folder / 'result.json')
        require(result['status'] == 'completed' and read(folder / 'status.json')['status'] == 'completed', "Release validation failed: result['status'] == 'completed' and read(folder / 'status.json')['status'] == 'completed'")
        require(result['completed_rounds'] == 200 and result['optimizer_global_updates'] == 15000, "Release validation failed: result['completed_rounds'] == 200 and result['optimizer_global_updates'] == 15000")
        require(result['test_accessed'] is False and result['engineering'] is False, "Release validation failed: result['test_accessed'] is False and result['engineering'] is False")
        require(result['stage_freeze_sha256'] == sha(Q / 'STAGE_B_FREEZE.json'), "Release validation failed: result['stage_freeze_sha256'] == sha(Q / 'STAGE_B_FREEZE.json')")
        for name, field in [('selected_checkpoint.npz', 'checkpoint_sha256'), ('result.json', 'result_sha256'), ('ledger.jsonl', 'ledger_sha256')]:
            require(item[field] == sha(folder / name), str(folder / name))
        require(item['checkpoint_sha256'] == result['selected_checkpoint_sha256'], "Release validation failed: item['checkpoint_sha256'] == result['selected_checkpoint_sha256']")
        require(item['status'] == 'pass' and item['max_validation_probability_error'] <= 1e-10 and (item['max_validation_metric_error'] <= 1e-10), "Release validation failed: item['status'] == 'pass' and item['max_validation_probability_error'] <= 1e-10 and (item['max_validation_metric_error'] <= 1e-10)")
        ledger = [json.loads(line) for line in (folder / 'ledger.jsonl').read_text().splitlines()]
        require([r['round'] for r in ledger] == list(range(1, 201)), "Release validation failed: [r['round'] for r in ledger] == list(range(1, 201))")
        require(min(ledger, key=lambda r: (r['validation']['bce'], r['round']))['round'] == item['selected_round'] == result['selected_round'], "Release validation failed: min(ledger, key=lambda r: (r['validation']['bce'], r['round']))['round'] == item['selected_round'] == result['selected_round']")
    folder = Q / 'local_readiness_results'
    readiness = read(folder / 'summary.json')
    require(readiness['status'] == 'pass' and readiness['engineering'] is False, "Release validation failed: readiness['status'] == 'pass' and readiness['engineering'] is False")
    require(readiness['test_population_read'] is False and readiness['labels_read'] is False, "Release validation failed: readiness['test_population_read'] is False and readiness['labels_read'] is False")
    require(readiness['hardware_jobs'] == readiness['physical_shots'] == readiness['sampling_failures'] == 0, "Release validation failed: readiness['hardware_jobs'] == readiness['physical_shots'] == readiness['sampling_failures'] == 0")
    require(readiness['fixture_circuits'] == 40 and readiness['independent_matrix_comparisons'] == 120, "Release validation failed: readiness['fixture_circuits'] == 40 and readiness['independent_matrix_comparisons'] == 120")
    require(readiness['aer_sampled_executions'] == 400 and readiness['aer_simulated_shots'] == 1024000, "Release validation failed: readiness['aer_sampled_executions'] == 400 and readiness['aer_simulated_shots'] == 1024000")
    require(readiness['max_matrix_error'] <= 1e-10 and readiness['max_aer_probability_error'] <= 1e-10, "Release validation failed: readiness['max_matrix_error'] <= 1e-10 and readiness['max_aer_probability_error'] <= 1e-10")
    require(ready['readiness_summary_sha256'] == sha(folder / 'summary.json'), "Release validation failed: ready['readiness_summary_sha256'] == sha(folder / 'summary.json')")
    configuration = read(folder / 'configuration.json')
    protocol = read(Q / 'READINESS_PROTOCOL.json')
    seal = read(Q / 'data/DATA_SEAL.json')
    require(configuration['classification'] == 'INTERNAL CIRCUIT READINESS', "Release validation failed: configuration['classification'] == 'INTERNAL CIRCUIT READINESS'")
    require(configuration['protocol_sha256'] == sha(Q / 'READINESS_PROTOCOL.json'), "Release validation failed: configuration['protocol_sha256'] == sha(Q / 'READINESS_PROTOCOL.json')")
    require(configuration['source_hashes'] == protocol['source_hashes'], "Release validation failed: configuration['source_hashes'] == protocol['source_hashes']")
    require(configuration['validation_file_sha256'] == seal['files']['confirmation_validation.npz']['sha256'], "Release validation failed: configuration['validation_file_sha256'] == seal['files']['confirmation_validation.npz']['sha256']")
    require(configuration['test_population_read'] is False and configuration['labels_read'] is False, "Release validation failed: configuration['test_population_read'] is False and configuration['labels_read'] is False")
    require(configuration['credential_accessed'] is False and configuration['hardware_jobs'] == configuration['physical_shots'] == 0, "Release validation failed: configuration['credential_accessed'] is False and configuration['hardware_jobs'] == configuration['physical_shots'] == 0")
    require(len(configuration['fixtures']) == 8 and {r['synthetic_class'] for r in configuration['fixtures']} == set(range(1, 9)), "Release validation failed: len(configuration['fixtures']) == 8 and {r['synthetic_class'] for r in configuration['fixtures']} == set(range(1, 9))")
    manifest = read(folder / 'manifest.json')['files']
    normalized_manifest = {str(Path(name)).replace('\\', '/'): expected for name, expected in manifest.items()}
    required_files = {'configuration.json', 'summary.json', 'numerical_checks.json', 'aer_counts.json'}
    required_files.update((f'circuits/seed_{seed}_untied_assigned_C{c}.qasm' for seed in range(401, 406) for c in range(1, 9)))
    require(required_files <= set(normalized_manifest), 'Incomplete local readiness manifest')
    require(len(normalized_manifest) == len(manifest), 'Duplicate local readiness manifest path')
    for name, expected in manifest.items():
        target = (folder / name).resolve()
        require(target.is_relative_to(folder.resolve()), 'Readiness manifest path escapes its folder')
        require(sha(target) == expected, name)
    numerical = read(folder / 'numerical_checks.json')
    expected = {(f'seed_{seed}_untied_assigned', c) for seed in range(401, 406) for c in range(1, 9)}
    require(len(numerical) == 40 and {(r['identity'], r['fixture_class']) for r in numerical} == expected, "Release validation failed: len(numerical) == 40 and {(r['identity'], r['fixture_class']) for r in numerical} == expected")
    for item in numerical:
        seed = int(item['identity'].split('_')[1])
        audit = next((r for r in lock['endpoints'] if r['seed'] == seed and r['method'] == 'untied_assigned'))
        require(item['checkpoint_sha256'] == audit['checkpoint_sha256'] and item['method'] == 'untied_assigned', "Release validation failed: item['checkpoint_sha256'] == audit['checkpoint_sha256'] and item['method'] == 'untied_assigned'")
    release = {'review_status': 'approved_by_root', 'created_utc': datetime.now(timezone.utc).isoformat(), 'release_id': 'qpath-v02-quantum-' + str(uuid.uuid4()), 'endpoint_lock_sha256': sha(lock_path), 'stage_b_freeze_sha256': sha(Q / 'STAGE_B_FREEZE.json'), 'evaluator_sha256': sha(Q / 'evaluate_confirmation.py'), 'root_release_script_sha256': sha(Path(__file__)), 'readiness_summary_sha256': sha(folder / 'summary.json'), 'registered_endpoints': 40, 'test_outcomes_accessed_before_release': False, 'scope': 'One-time local sealed confirmation evaluation of all40 registered endpoints; independent prediction replay, registered paired analysis and ideal finite-shot sensitivity. No retraining, model reselection, cloud or hardware.', 'next_action': 'Run the separate frozen evaluator once using --evaluate, then inspect its independent replay and complete analysis before reporting.'}
    with out.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(release, indent=2) + '\n')
    print(json.dumps(release, indent=2))
if __name__ == '__main__':
    main()
