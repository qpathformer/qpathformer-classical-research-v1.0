"""Independent audit of the complete, root-released local confirmation capsule.

The public CLI reads no test arrays or official test metrics. It requires the
completed readiness commit, full Stage B audits and the root release first.
Density channels are reconstructed with NumPy; actual Aer measurement draws
are checked as recorded, never rerandomized or treated as hardware results.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path, PureWindowsPath
import sys
import traceback

import numpy as np
import readout_reference_v05 as ref

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'analysis/independent_replay'))
from evidence_io import contained, digest, inventory, map_original_absolute, read_bound, recheck, require

REGISTRY = '401e8ebed00499a82bdd4e392a33f97269d0ee4078f5bb7c8653b11287b4cbf0'
POPULATIONS = ('confirmation_circle_1', 'confirmation_circle_2', 'confirmation_ellipse')
SEEDS = (1001, 1002, 1003, 1004, 1005)
METHODS = ('q2_kmeans', 'qscalar_kmeans', 'qmulti_kmeans', 'qfrozen_kmeans')
ALL_METHODS = METHODS + ('mlp4relu_kmeans','mlp8relu_kmeans','mlp4tanh_kmeans','mlp8tanh_kmeans','trig_kmeans','trig_global','mlp_global')


def now():
    return datetime.now(timezone.utc).isoformat()


def timestamp(text):
    result = datetime.fromisoformat(text)
    require(result.tzinfo is not None, 'Timezone-aware evidence required')
    return result.astimezone(timezone.utc)


def bound_file(path, expected, watched):
    path = Path(path).resolve()
    require(str(path) not in watched or watched[str(path)] == expected,
            'Previously bound input identity differs: ' + str(path))
    require(digest(path) == expected, 'Bound input changed: ' + str(path))
    watched[str(path)] = expected


def gate(root, *, expected_registry=REGISTRY):
    """Metadata and hashes only. No np.load, test arrays or test reports."""
    require(np.__version__ == '2.5.4', 'Registered NumPy2.5.4 required for exact joint multinomial replay')
    root = Path(root).resolve(); q = root / 'quantum'
    folder = q / 'local_readiness_confirmation'
    watched = {}
    release_path = q / 'EVALUATION_RELEASE.json'
    release = read_bound(release_path, watched)
    require(release.get('status') == 'released_by_root'
            and release.get('study_id') == 'QPATH-READOUT-v0.5'
            and release.get('scope') == 'all_165_registered_confirmation_endpoints_once'
            and isinstance(release.get('release_id'), str) and release['release_id'], 'Root release required')
    paths = {
        'registration_sha256': q / 'EVALUATION_REGISTRATION.json',
        'endpoint_lock_sha256': q / 'CONFIRMATION_ENDPOINT_LOCK.json',
        'independent_endpoint_review_sha256': q / 'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json',
        'stage_freeze_sha256': q / 'STAGE_B_FREEZE.json',
        'data_seal_sha256': q / 'data/DATA_SEAL.json',
        'analysis_protocol_sha256': root / 'governance/ANALYSIS_PROTOCOL.json',
        'readiness_protocol_sha256': root / 'governance/LOCAL_READINESS_PROTOCOL.json',
        'independent_replay_ready_sha256': root / 'analysis/independent_replay/ANALYSIS_READY.json',
    }
    objects = {}
    for key, path in paths.items():
        objects[key] = read_bound(path, watched)
        require(release.get(key) == watched[str(path.resolve())], 'Root release binding differs: ' + key)
    reg = objects['registration_sha256']; lock = objects['endpoint_lock_sha256']
    review = objects['independent_endpoint_review_sha256']; ready = objects['independent_replay_ready_sha256']
    freeze = objects['stage_freeze_sha256']; protocol = objects['readiness_protocol_sha256']
    seal = objects['data_seal_sha256']; rh = watched[str(paths['registration_sha256'].resolve())]
    require(rh == expected_registry and reg['status'] == 'REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS', 'Registered evaluator changed')
    require(reg['methods'] == list(ALL_METHODS) and reg['training_seeds'] == list(SEEDS)
            and reg['populations'] == list(POPULATIONS), 'Registered scope differs')
    original = reg['original_working_root']
    for key in ('data_seal_sha256', 'analysis_protocol_sha256', 'readiness_protocol_sha256'):
        require(reg[key] == release[key], 'Registered data/protocol differs')
    require(ready['status'] == 'READY_BEFORE_CONFIRMATION_TEST_ACCESS'
            and ready['registration_sha256'] == rh
            and ready['analysis_protocol_sha256'] == release['analysis_protocol_sha256'], 'Independent replay readiness differs')
    for hashes in (reg['source_hashes'], ready['source_hashes'], ready['evidence_hashes']):
        require(bool(hashes), 'Empty registered hash inventory')
        for name, expected in hashes.items():
            bound_file(contained(root, name), expected, watched)
    require(freeze['review_status'] == 'approved_by_root'
            and freeze['methods'] == list(ALL_METHODS) and freeze['populations'] == list(POPULATIONS)
            and freeze['training_seeds'] == list(SEEDS), 'Root full Stage B freeze missing')
    require(lock['status'] == 'PASS' and lock['stage'] == 'B' and lock['endpoint_count'] == 165
            and lock['engineering'] is False, 'Completed author audit required')
    for key in ('data_seal_sha256', 'analysis_protocol_sha256', 'stage_freeze_sha256'):
        require(lock[key] == release[key], 'Author lock binding differs')
    require(lock['source_hashes'] == freeze['source_hashes'] == reg['training_source_hashes'], 'Training sources differ')
    for name, expected in lock['source_hashes'].items():
        bound_file(contained(q, name), expected, watched)
    for name, expected in lock['audit_source_hashes'].items():
        bound_file(map_original_absolute(name, original, root), expected, watched)
    require(review['status'] == 'PASS' and review['stage'] == 'B' and review['endpoint_count'] == 165
            and review['endpoint_lock_sha256'] == release['endpoint_lock_sha256'], 'Independent review required')
    audit_path = contained(root, review['independent_audit_path'])
    audit = read_bound(audit_path, watched)
    require(watched[str(audit_path.resolve())] == review['independent_audit_sha256'], 'Independent audit changed')
    require(audit['status'] == 'PASS' and audit['stage'] == 'B' and audit['endpoint_count'] == 165
            and audit['engineering'] is False and audit['validation_rounds_replayed'] == 33000
            and audit['validation_predictions_replayed'] == 52800000
            and audit['model_test_outcomes_accessed'] is False, 'Full independent audit required')
    for key in ('endpoint_lock_sha256', 'analysis_protocol_sha256', 'data_seal_sha256'):
        require(audit[key] == release[key], 'Independent audit binding differs')
    auditor = contained(root, reg['independent_auditor_path'])
    require(digest(auditor) == audit['auditor_sha256'] == reg['source_hashes'][reg['independent_auditor_path']], 'Independent auditor differs')
    for name, expected in audit['independent_source_sha256'].items():
        require(Path(name).name == name, 'Unsafe independent source name')
        p = auditor.parent / name
        require(expected == reg['source_hashes'][p.relative_to(root).as_posix()], 'Independent source registry differs')
        bound_file(p, expected, watched)
    identities = {(pop, seed, method) for pop in POPULATIONS for seed in SEEDS for method in ALL_METHODS}
    require(len(lock['endpoints']) == len(audit['endpoints']) == 165
            and {(r['population'], r['seed'], r['method']) for r in lock['endpoints']} == identities
            and {(r['population'], r['seed'], r['method']) for r in audit['endpoints']} == identities, 'Exact165 endpoint identities required')
    checked = {(r['population'], r['seed'], r['method']): r for r in audit['endpoints']}
    endpoints = {}
    for row in lock['endpoints']:
        identity = row['population'], row['seed'], row['method']
        pop, seed, method = identity; ar = checked[identity]
        endpoint = q / 'stage_B' / pop / f'seed_{seed}' / method
        require(map_original_absolute(row['path'], original, root).resolve() == endpoint.resolve(), 'Endpoint original identity differs')
        require(ar['endpoint_commit_sha256'] == row['endpoint_commit_sha256']
                and ar['rounds_verified'] == 200 and ar['validation_predictions_replayed'] == 320000
                and ar['selected_round'] == row['selected_round']
                and ar['selected_checkpoint_sha256'] == row['files']['selected_checkpoint.npz']['sha256'], 'Full endpoint audit differs')
        endpoint_commit = read_bound(endpoint / 'endpoint_commit.json', watched)
        require(watched[str((endpoint / 'endpoint_commit.json').resolve())] == row['endpoint_commit_sha256']
                and endpoint_commit['status'] == 'completed' and endpoint_commit['test_accessed'] is False
                and endpoint_commit['files'] == row['files'] and not (endpoint / 'failure.json').exists(), 'Endpoint commit differs')
        inventory(endpoint, row['files'], exclude=('endpoint_commit.json',))
        for name, metadata in row['files'].items():
            bound_file(contained(endpoint, name), metadata['sha256'], watched)
        endpoints[identity] = row
    stage = read_bound(q / 'stage_B/stage_status.json', watched)
    require(stage['status'] == 'completed' and stage['stage'] == 'B'
            and stage['committed_endpoints'] == stage['expected_endpoints'] == 165
            and sorted((r['seed'], r['exit_code']) for r in stage['exits']) == [(s, 0) for s in SEEDS], 'All five workers must have closed')
    require(timestamp(release['created_utc']) >= max(timestamp(lock['created_utc']), timestamp(audit['created_utc'])), 'Release predates audits')
    require(protocol['populations'] == list(POPULATIONS) and protocol['training_seeds'] == list(SEEDS)
            and protocol['methods'] == list(METHODS), 'Readiness protocol scope differs')
    commit_path = folder / 'READINESS_COMMIT.json'
    commit = read_bound(commit_path, watched)
    require(commit['status'] == 'completed' and commit['engineering'] is False
            and commit['test_accessed'] is False and not (folder / 'FAILURE.json').exists(), 'Actual complete confirmation capsule required')
    inventory(folder, commit['files'], exclude=('READINESS_COMMIT.json',))
    for name, metadata in commit['files'].items():
        bound_file(contained(folder, name), metadata['sha256'], watched)
    report = read_bound(folder / 'report.json', watched)
    require(report['status'] == 'PASS' and report['engineering'] is False and report['test_accessed'] is False
            and report['populations'] == list(POPULATIONS) and report['training_seeds'] == list(SEEDS)
            and report['methods'] == list(METHODS) and report['protocol_sha256'] == release['readiness_protocol_sha256'], 'Readiness report identity differs')
    require(timestamp(release['created_utc']) <= timestamp(report['created_utc']) <= timestamp(commit['created_utc']), 'Readiness chronology differs')
    # The producer records every pre-capsule bound input. Remap provenance, never
    # dereference original-tree paths or a sealed test/outcome payload.
    recorded_watched = {}
    for name, expected in report['watched_input_hashes'].items():
        path = map_original_absolute(name, original, root) if PureWindowsPath(name).is_absolute() else contained(q, name.replace('\\', '/'))
        relative = path.relative_to(root).as_posix()
        require('_SEALED_test' not in relative and not relative.startswith('quantum/confirmation_evaluation/'), 'Readiness must not watch test outcomes')
        bound_file(path, expected, watched); recorded_watched[str(path.resolve())] = expected
    # All root-approved evidence and selected endpoint inventories must have
    # been watched by the original capsule, not merely by this later audit.
    own_prefix = str(folder.resolve()) + '\\'
    for name, expected in watched.items():
        if not name.startswith(own_prefix):
            require(recorded_watched.get(name) == expected, 'Capsule omitted bound pre-execution evidence: ' + name)
    recheck(watched)
    return {'root': root, 'q': q, 'folder': folder, 'release': release, 'report': report,
            'commit': commit, 'seal': seal, 'protocol': protocol, 'endpoints': endpoints,
            'watched': watched, 'registry_sha256': rh, 'original_root': original}


def load_arrays(path):
    require('_SEALED_test' not in str(path), 'Test arrays are outside this audit')
    with np.load(path, allow_pickle=False) as z:
        return {key: z[key] for key in z.files}


def close(actual, expected, label, tol=2e-12):
    require(math.isfinite(float(actual)) and abs(float(actual) - float(expected)) <= tol, label)


def vector_close(actual, expected, label, tol=2e-12):
    a,b=np.asarray(actual),np.asarray(expected)
    require(a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all(),label+' shape/nonfinite')
    error=float(np.max(np.abs(a-b))) if a.size else 0.
    require(error<=tol,label);return error


def classification(actual, reference):
    band=32*np.finfo(np.float64).eps
    different=bool((actual>=.5)!=(reference>=.5))
    require(not different or (abs(actual-.5)<=band and abs(reference-.5)<=band),'Class disagreement outside numerical band')
    return {'canonical_prediction':int(actual>=.5),'reference_prediction':int(reference>=.5),
            'class_disagreement':different,'canonical_near_band':bool(abs(actual-.5)<=band),
            'reference_near_band':bool(abs(reference-.5)<=band),'band_half_width':float(band)}


def verify_numerics(context):
    """Only called after gate; internally reusable on explicitly synthetic fixtures."""
    report,protocol,folder=context['report'],context['protocol'],context['folder']
    populations,seeds,methods=protocol['populations'],protocol['training_seeds'],protocol['methods']
    groups=[(p,s,m) for p in populations for s in seeds for m in methods]
    require(report['populations']==populations and report['training_seeds']==seeds and report['methods']==methods,'Numerical scope differs')
    rows=report['circuits'];nfixture=protocol['fixtures']['n_per_population']
    require(nfixture==32 and len(rows)==len(groups)*32,'Every checkpoint requires32 fixtures')
    expected_rows=[(*g,i) for g in groups for i in range(32)]
    require([(r['population'],r['training_seed'],r['method'],r['fixture_index']) for r in rows]==expected_rows,'Fixture order/identity differs')
    # Require producer pre-execution coverage before any numerical payload load.
    for pop in populations:
        for filename,expected in [(f'{pop}_validation.npz',context['seal']['files'][f'{pop}_validation.npz']['sha256']),
                                  (f'{pop}_router.json',context['seal']['routers'][pop]['sha256'])]:
            recorded=PureWindowsPath(context['original_root'])/'quantum'/'data'/filename
            matches=[h for name,h in report['watched_input_hashes'].items() if PureWindowsPath(name)==recorded]
            require(matches==[expected],'Capsule omitted sealed validation/router pre-execution binding: '+filename)
    validate={};checkpoints={};parameters={};resources=[]
    for pop in populations:
        path=context['q']/'data'/f'{pop}_validation.npz'
        bound_file(path,context['seal']['files'][path.name]['sha256'],context['watched'])
        val=load_arrays(path);indices=np.argsort(val['ids'],kind='stable')[:32]
        require(len(set(val['ids'].tolist()))==len(val['ids']) and len(indices)==32,'Validation identities invalid')
        policy_path=context['q']/'data'/f'{pop}_router.json';policy=read_bound(policy_path,context['watched'])
        bound_file(policy_path,context['seal']['routers'][pop]['sha256'],context['watched'])
        centers=np.asarray(policy['centroids']);require(centers.shape==(5,2),'Router centroids invalid')
        xy=val['x'][indices]
        route=np.array([min(range(5),key=lambda j:float((x[0]-centers[j,0])**2+(x[1]-centers[j,1])**2)) for x in xy])
        require(np.array_equal(route,val['kmeans_route'][indices]),'Independent fixture routing differs')
        require(report['fixture_ids'][pop]==val['ids'][indices].tolist(),'Smallest-ID fixture selection differs')
        validate[pop]=(xy,val['ids'][indices],route)
    widths={'q2_kmeans':8,'qscalar_kmeans':10,'qmulti_kmeans':14,'qfrozen_kmeans':6}
    for identity in groups:
        pop,seed,method=identity;endpoint=context['endpoints'][identity]
        ep=map_original_absolute(endpoint['path'],context['original_root'],context['root'])
        path=ep/'selected_checkpoint.npz';bound_file(path,endpoint['files']['selected_checkpoint.npz']['sha256'],context['watched'])
        checkpoint=load_arrays(path);theta=checkpoint['parameters'];core=checkpoint['core_parameters']
        require(theta.shape==(5*widths[method],) and theta.dtype==np.float64 and np.isfinite(theta).all(),'Checkpoint parameter shape/value differs')
        if method=='qfrozen_kmeans':
            initial=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,1]))).uniform(-.1,.1,(5,4,2,2))[:,:2]
            require(core.dtype==np.float64 and np.array_equal(core,initial),'Fixed random core identity differs')
        else:require(core.shape==(0,),'Unexpected fixed core payload')
        parameters[identity]=(theta.reshape(5,widths[method]),core);checkpoints[identity]=digest(path)
        er=read_bound(ep/'result.json',context['watched'])
        resources.append({'population':pop,'training_seed':seed,'method':method,'inference':er['inference'],
            'frozen_cache':er['frozen_cache'],'trainable_parameters':er['parameter_count'],'fixed_core_parameters':er['fixed_core_parameter_count']})
    require(report['checkpoint_resources']==resources,'Checkpoint cost/cache metadata differs')
    names=('X0','X1','Z0','Z1','Z0Z1');maxima={'ideal_probability':0.,'independent_moments':0.,'premeasurement_joint':0.,'observed_joint':0.,'noisy_probability':0.}
    saved_maxima={'maximum_core_unitary_error':0.,'maximum_compiled_unitary_error':0.,'maximum_aer_moment_error':0.,'maximum_production_moment_error':0.}
    row_by_key={};head_by_key={};required_entries=[];legacy_entries=[];distributions=0;independent_class_differences=[]
    for row in rows:
        identity=row['population'],row['training_seed'],row['method'];pop,seed,method=identity;i=row['fixture_index']
        xy,ids,routes=validate[pop];bank=int(routes[i]);theta,core=parameters[identity];bank_theta=theta[bank]
        require(row['record_id']==int(ids[i]) and row['x']==xy[i].tolist() and row['bank']==bank,'Fixture raw input/route differs')
        key=f'{pop}__seed{seed}__{method}__id{int(ids[i])}'
        require(row['key']==key and key not in row_by_key and row['checkpoint_sha256']==checkpoints[identity],'Fixture key/checkpoint differs')
        angles=core[bank] if method=='qfrozen_kmeans' else bank_theta[:8].reshape(2,2,2)
        head=[] if method=='q2_kmeans' else (bank_theta if method=='qfrozen_kmeans' else bank_theta[8:]).tolist()
        require(row['head']==head,'Stored head differs')
        ideal=ref.core_density(xy[i],angles);moments=ref.moments(ideal);prob,_=ref.apply_head(method,bank_theta,moments)
        for field in ('reference_moments','production_moments','aer_core_moments'):
            require(set(row[field])==set(names),'Missing full Pauli moments')
            maxima['independent_moments']=max(maxima['independent_moments'],vector_close([row[field][n] for n in names],moments,'Independent full moments differ'))
        for field in ('production_probability','reference_probability','aer_core_probability','compiled_aer_probability'):
            error=abs(float(row[field])-prob);close(row[field],prob,'Independent ideal predictor differs');maxima['ideal_probability']=max(maxima['ideal_probability'],error)
        own_class=classification(row['production_probability'],prob)
        if own_class['class_disagreement']:
            independent_class_differences.append({'key':key,'canonical_probability':row['production_probability'],'independent_probability':prob,**own_class})
        require(row['numerical_classification']==classification(row['production_probability'],row['reference_probability']) and
            row['compiled_numerical_classification']==classification(row['production_probability'],row['compiled_aer_probability']),'Ideal class diagnostics differ')
        settings=['XX'] if method in ('q2_kmeans','qscalar_kmeans') else ['XX','ZZ']
        require(row['required_settings']==settings and set(row['settings'])==set(settings+(['legacy'] if method=='q2_kmeans' else [])),'Measurement settings differ')
        require(row['core_operations']=={'ry':8,'rz':4,'cx':2},'Core logical gates differ')
        for field in ('source_unitary_error','maximum_aer_moment_error','maximum_production_moment_error'):
            require(math.isfinite(row[field]) and 0<=row[field]<=2e-12,'Recorded ideal matrix residual invalid')
        for field,saved in (('maximum_aer_moment_error','aer_core_moments'),('maximum_production_moment_error','production_moments')):
            close(row[field],max(abs(row[saved][n]-row['reference_moments'][n]) for n in names),'Moment error summary differs')
            saved_maxima[field]=max(saved_maxima[field],row[field])
        saved_maxima['maximum_core_unitary_error']=max(saved_maxima['maximum_core_unitary_error'],row['source_unitary_error'])
        for setting,item in row['settings'].items():
            joint=ref.setting_distribution(ideal,'legacy_q0' if setting=='legacy' else setting)
            vector_close(item['reference_joint'],joint,'Ideal setting joint differs');vector_close(item['compiled_aer_joint'],joint,'Compiled Aer joint differs')
            close(item['compiled_aer_joint_error'],np.max(abs(np.asarray(item['compiled_aer_joint'])-item['reference_joint'])),'Compiled Aer error summary differs')
            require(item['logical_operations']=={'ry':8+(2 if setting=='XX' else 1 if setting=='legacy' else 0),'rz':4,'cx':2},'Logical setting operations differ')
            require(item['logical_depth']==(8 if setting=='ZZ' else 9),'Logical circuit depth differs')
            require(type(item['compiled_depth']) is int and item['compiled_depth']>0 and math.isfinite(item['compiled_global_phase']),'Invalid compiled resource metadata')
            require(set(item['compiled_operations'])<=set(protocol['compile']['basis_gates']) and all(type(v) is int and v>0 for v in item['compiled_operations'].values()),'Compiled operation metadata invalid')
            for field in ('source_unitary_error','compiled_unitary_error','compiled_aer_joint_error'):
                require(math.isfinite(item[field]) and 0<=item[field]<=2e-12,'Compiled residual outside fixed tolerance')
            saved_maxima['maximum_compiled_unitary_error']=max(saved_maxima['maximum_compiled_unitary_error'],item['compiled_unitary_error'])
            (legacy_entries if setting=='legacy' else required_entries).append((row,setting))
        require(set(row['scenarios'])=={s['name'] for s in protocol['noise_scenarios']},'Noise scenario inventory differs')
        for scenario in protocol['noise_scenarios']:
            density=ref.core_density(xy[i],angles,scenario['one_qubit_depolarizing'],scenario['cx_depolarizing'])
            record=row['scenarios'][scenario['name']];require(set(record['settings'])==set(row['settings']),'Noise setting inventory differs')
            joints={}
            for setting,item in record['settings'].items():
                translated='legacy_q0' if setting=='legacy' else setting
                pre=ref.setting_distribution(density,translated,scenario['one_qubit_depolarizing'],0.)
                observed=ref.bit_flip_joint(pre,scenario['symmetric_readout_flip'])
                maxima['premeasurement_joint']=max(maxima['premeasurement_joint'],vector_close(item['premeasurement_joint'],pre,'Independent premeasurement joint differs'))
                maxima['observed_joint']=max(maxima['observed_joint'],vector_close(item['observed_joint'],observed,'Independent observed joint differs'))
                joints[setting]=observed;distributions+=1
            grouped=ref.grouped_moments(joints['XX'],joints.get('ZZ',np.ones(4)/4))
            visible=names if 'ZZ' in settings else names[:2]
            require(set(record['observed_moments'])==set(visible),'Noisy moment inventory differs')
            vector_close([record['observed_moments'][n] for n in visible],grouped[:len(visible)],'Noisy grouped moments differ')
            noisy,_=ref.apply_head(method,bank_theta,grouped)
            error=abs(noisy-record['observed_probability']);close(record['observed_probability'],noisy,'Independent noisy head differs');maxima['noisy_probability']=max(maxima['noisy_probability'],error)
            close(record['absolute_distortion_from_ideal'],abs(record['observed_probability']-row['reference_probability']),'Noise distortion differs')
            require(record['classification_disagreement_from_ideal']==bool((record['observed_probability']>=.5)!=(row['reference_probability']>=.5)),'Noise class flip differs')
            if method=='q2_kmeans':close(record['original_legacy_probability'],sum(joints['legacy'][2:]),'Legacy marginal differs');close(record['original_legacy_probability'],record['observed_probability'],'Legacy and XX noisy marginal differ')
        row_by_key[key]=row;head_by_key[key]=bank_theta
    counts=load_arrays(folder/'finite_shot_counts.npz');probabilities=load_arrays(folder/'finite_shot_probabilities.npz')
    records=read_bound(folder/'finite_shot_records.json',context['watched'])
    expected_tuples=[(*g,sc['name'],shots,rep) for g in groups for sc in protocol['noise_scenarios'] for shots in protocol['finite_shot']['shots_per_setting'] for rep in range(protocol['finite_shot']['replicates'])]
    require(all(type(r['repeat_index']) is int for r in records) and
            [(r['population'],r['training_seed'],r['method'],r['scenario'],r['shots_per_setting'],r['repeat_index']) for r in records]==expected_tuples,
            'Finite-shot semantic tuple order differs')
    expected_keys=[f'{p}__seed{s}__{m}__{sc["name"]}__shots{shots}__repeat{rep}' for p,s,m in groups for sc in protocol['noise_scenarios'] for shots in protocol['finite_shot']['shots_per_setting'] for rep in range(protocol['finite_shot']['replicates'])]
    require([r['key'] for r in records]==expected_keys and set(probabilities)==set(expected_keys),'Finite-shot prediction inventory/order differs')
    count_keys=set();represented=0
    for item in records:
        identity=item['population'],item['training_seed'],item['method'];selected=[r for r in rows if (r['population'],r['training_seed'],r['method'])==identity]
        shots=item['shots_per_setting'];scenario=item['scenario'];settings=selected[0]['required_settings']
        require(item['record_ids']==[r['record_id'] for r in selected] and item['settings']==settings and set(item['seed_sequences'])==set(settings),'Shot identities/settings differ')
        per_setting={}
        for setting in settings:
            sequence=[590101,populations.index(identity[0]),identity[1],methods.index(identity[2]),[s['name'] for s in protocol['noise_scenarios']].index(scenario),shots,item['repeat_index'],('XX','ZZ').index(setting)]
            require(item['seed_sequences'][setting]==sequence,'Joint RNG seed differs')
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(sequence)))
            expected=np.array([rng.multinomial(shots,r['scenarios'][scenario]['settings'][setting]['observed_joint']) for r in selected],dtype=np.int64)
            key=item['key']+'__'+setting;count_keys.add(key);actual=counts[key]
            require(actual.dtype==np.int64 and actual.shape==(32,4) and np.array_equal(actual,expected),'Exact joint multinomial array differs')
            per_setting[setting]=actual/shots
        expected=np.array([ref.apply_head(identity[2],head_by_key[r['key']],ref.grouped_moments(per_setting['XX'][i],per_setting['ZZ'][i] if 'ZZ' in settings else np.ones(4)/4))[0] for i,r in enumerate(selected)])
        actual=probabilities[item['key']];require(actual.dtype==np.float64,'Sampled predictor dtype differs');vector_close(actual,expected,'Joint sampled head predictor differs')
        target=np.array([r['scenarios'][scenario]['observed_probability'] for r in selected])
        for field,value in [('mean_signed_probability_error',np.mean(actual-target)),('mean_absolute_probability_error',np.mean(abs(actual-target))),('classification_disagreement_from_density',np.mean((actual>=.5)!=(target>=.5)))]:close(item[field],value,'Shot summary differs')
        require(item['total_shots']==shots*32*len(settings),'Shot work differs');represented+=item['total_shots']
    require(set(counts)==count_keys,'Joint count inventory differs')
    summaries=read_bound(folder/'finite_shot_summary.json',context['watched']);summary_ids=[(*g,sc['name'],shots) for g in groups for sc in protocol['noise_scenarios'] for shots in protocol['finite_shot']['shots_per_setting']]
    require([(r['population'],r['training_seed'],r['method'],r['scenario'],r['shots_per_setting']) for r in summaries]==summary_ids,'Bias/variance summary inventory differs')
    for item in summaries:
        p,s,m,sc,shots=item['population'],item['training_seed'],item['method'],item['scenario'],item['shots_per_setting']
        selected=[r for r in rows if (r['population'],r['training_seed'],r['method'])==(p,s,m)]
        target=np.array([r['scenarios'][sc]['observed_probability'] for r in selected]);sample=np.array([probabilities[f'{p}__seed{s}__{m}__{sc}__shots{shots}__repeat{j}'] for j in range(5)])
        bias=sample.mean(axis=0)-target;variance=sample.var(axis=0,ddof=1)
        require(item['replicates']==5 and item['fixture_ids']==[r['record_id'] for r in selected],'Bias/variance scope differs')
        vector_close(item['empirical_bias_per_fixture'],bias,'Shot empirical bias differs');vector_close(item['sample_variance_per_fixture'],variance,'Shot sample variance differs')
        for field,v in [('mean_signed_bias',bias.mean()),('mean_absolute_bias',abs(bias).mean()),('mean_sample_variance',variance.mean())]:close(item[field],v,'Shot bias/variance aggregate differs')
    measured=read_bound(folder/'measured_aer_counts.json',context['watched']);sm=protocol['aer_measured_smoke']
    expected_measured=[(r['key'],setting,sc['name']) for sc in protocol['noise_scenarios'] if sc['name'] in sm['scenarios'] for r,setting in required_entries if r['fixture_index']<sm['records_per_checkpoint']]
    require([(r['key'],r['setting'],r['scenario']) for r in measured]==expected_measured,'Measured experiment order/inventory differs')
    for item in measured:
        counts4=np.array(item['counts']);require(counts4.dtype.kind in 'iu' and counts4.shape==(4,) and (counts4>=0).all() and counts4.sum()==item['shots']==sm['shots_per_setting'],'Measured joint counts invalid')
        require(item['count_order']==['00','01','10','11'] and item['seed_simulator']==sm['seed_simulator'],'Measured wire/seed metadata differs')
        joint=np.array(row_by_key[item['key']]['scenarios'][item['scenario']]['settings'][item['setting']]['observed_joint'])
        vector_close(item['density_expected_joint'],joint,'Measured expectation differs')
        vector_close(item['observed_moments'],[counts4@ref.Q0/item['shots'],counts4@ref.Q1/item['shots'],counts4@(ref.Q0*ref.Q1)/item['shots']],'Measured moment arithmetic differs')
        variance=item['shots']*joint*(1-joint)
        for j in range(4):
            if variance[j]>0:close(item['standardized_count_residuals'][j],(counts4[j]-item['shots']*joint[j])/np.sqrt(variance[j]),'Measured residual differs')
            else:require(item['standardized_count_residuals'][j] is None,'Degenerate residual must be absent')
    for pop in populations:
        for method in methods:
            selected=[r for r in rows if r['population']==pop and r['method']==method]
            for sc in protocol['noise_scenarios']:
                summary=report['summaries'][pop][method][sc['name']];v=[r['scenarios'][sc['name']] for r in selected]
                require(summary['checkpoint_fixture_pairs']==len(selected),'Noise summary denominator differs')
                for field,value in [('mean_absolute_distortion',np.mean([a['absolute_distortion_from_ideal'] for a in v])),('maximum_absolute_distortion',max(a['absolute_distortion_from_ideal'] for a in v)),('classification_disagreement_fraction',np.mean([a['classification_disagreement_from_ideal'] for a in v]))]:close(summary[field],value,'Noise summary arithmetic differs')
    totals={'checkpoint_count':len(groups),'checkpoint_fixture_pairs':len(rows),'required_measurement_circuits':len(required_entries),'additional_original_legacy_circuits':len(legacy_entries),
        'core_ideal_aer_evaluations':len(rows),'compiled_ideal_aer_evaluations':len(required_entries)+len(legacy_entries),'production_model_forward_statevector_examples':len(rows),'additional_full_moment_statevector_examples':len(rows),
        'logical_density_evaluations':distributions,'measured_aer_circuit_experiments':len(measured),'actual_simulated_measurement_shots':sum(r['shots'] for r in measured),
        'finite_shot_count_array_count':len(counts),'finite_shot_predictor_array_count':len(probabilities),'represented_multinomial_trials':represented}
    for field,value in totals.items():require(report[field]==value,'Capsule work total differs: '+field)
    for field,value in saved_maxima.items():close(report[field],value,'Recorded maximum summary differs')
    files={'report.json','finite_shot_counts.npz','finite_shot_probabilities.npz','finite_shot_records.json','finite_shot_summary.json','measured_aer_counts.json'}
    files.update(f'circuits/{r["key"]}__core.qasm' for r in rows)
    files.update(f'circuits/{r["key"]}__{setting}__{kind}.qasm' for r,setting in required_entries+legacy_entries for kind in ('logical','compiled'))
    files.update(f'circuits/{r["key"]}__{setting}__measured.qasm' for r,setting in required_entries if r['fixture_index']<sm['records_per_checkpoint'])
    require(set(context['commit']['files'])==files,'Complete QASM/payload inventory differs')
    require(all(math.isfinite(v) and v>=0 for v in report['timings_seconds'].values()) and math.isfinite(report['elapsed_seconds']) and report['elapsed_seconds']>=0,'Nonfinite/negative timing')
    return {'selected_checkpoints_checked':len(checkpoints),**totals,'maximum_independent_errors':maxima,
        'all_exact_joint_multinomial_arrays_reproduced':True,'measured_count_residuals_checked':len(measured),'qasm_payload_count':len(files)-6,
        'noise_probabilities_reconstructed':True,'five_repeat_bias_variance_reconstructed':True,
        'independent_class_disagreements':len(independent_class_differences),'independent_class_disagreement_records':independent_class_differences,
        'outside_band_independent_class_disagreements':0}

def run(root, output):
    output = Path(output).resolve(); require(not output.exists(), 'Preserve prior audit output')
    context = gate(root)
    for path in (Path(__file__), Path(ref.__file__)):
        bound_file(path, digest(path), context['watched'])
    output.mkdir(parents=True, exist_ok=False)
    def write(name, value):
        with (output / name).open('x', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, allow_nan=False); handle.write('\n')
    write('ACCESS_EVENT.json', {'created_utc': now(), 'scope': 'Root-released completed local validation-only readiness capsule audit; no test arrays.',
          'release_id': context['release']['release_id'], 'readiness_commit_sha256': digest(context['folder'] / 'READINESS_COMMIT.json')})
    try:
        checks = verify_numerics(context); recheck(context['watched'])
        result = {'status': 'PASS', 'created_utc': now(), 'study_id': 'QPATH-READOUT-v0.5', 'engineering': False,
                  'test_arrays_accessed': False, 'model_test_outcomes_accessed': False, 'checks': checks,
                  'release_id': context['release']['release_id'], 'release_sha256': digest(context['q'] / 'EVALUATION_RELEASE.json'),
                  'readiness_commit_sha256': digest(context['folder'] / 'READINESS_COMMIT.json'),
                  'registration_sha256': context['registry_sha256'],
                  'auditor_sources': {str(p.relative_to(ROOT).as_posix()): digest(p) for p in (Path(__file__), Path(ref.__file__))},
                  'watched_input_hashes': context['watched'],
                  'scope': 'Independent per-logical-gate density/noise/readout reconstruction and exact joint multinomial replay; recorded actual Aer count arithmetic checked without rerandomization. 60 selected quantum checkpoints, label-independent validation fixtures only.',
                  'limits': 'QASM payload identities and completeness, recorded matrix residuals and independently reconstructed probabilities are checked; this auditor does not independently compile or parse QASM unitaries. No hardware/calibration, test accuracy, seed independence from repeated shots, or stochastic pass/fail inference.'}
        write('summary.json', result)
        recheck(context['watched'])
        write('AUDIT_COMMIT.json', {'status': 'completed', 'created_utc': now(), 'files': {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size} for p in output.iterdir() if p.is_file()},
              'readiness_commit_sha256': result['readiness_commit_sha256']})
        return result
    except BaseException as error:
        write('FAILURE.json', {'status': 'FAIL', 'created_utc': now(), 'error': str(error), 'traceback': traceback.format_exc(), 'recovery': 'Preserve all outputs; root review before any separate retry.'})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    require(args.output.resolve().parent == HERE, 'Output must be a new child of classical_review')
    result = run(ROOT, args.output)
    print(json.dumps({'status': result['status'], 'output': str(args.output), 'checks': result['checks']}))


if __name__ == '__main__':
    main()
