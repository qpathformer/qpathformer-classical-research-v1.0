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
import readout_reference_v06 as ref

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'analysis/independent_replay'))
from evidence_io import contained, digest, inventory, map_original_absolute, read_bound, recheck, require

REGISTRY = 'c03c1f46fdf5a658ac7a5aabda64a2c56990fdefaddceb30bf74d031899d8876'
POPULATIONS = ('confirmation_checkerboard', 'confirmation_spiral', 'confirmation_annulus', 'confirmation_disks')
SEEDS = (1201, 1202, 1203, 1204, 1205)
METHODS = ('qscalar_kmeans', 'qmulti_kmeans')
ALL_METHODS = METHODS + ('mlp8tanh_kmeans','trig_kmeans','trig_global','mlp_global')


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
            and release.get('study_id') == 'QPATH-GENERALIZATION-v0.6'
            and release.get('scope') == 'all_120_registered_confirmation_endpoints_once'
            and isinstance(release.get('release_id'), str) and release['release_id'], 'Root release required')
    paths = {
        'registration_sha256': q / 'EVALUATION_REGISTRATION.json',
        'endpoint_lock_sha256': q / 'CONFIRMATION_ENDPOINT_LOCK.json',
        'independent_endpoint_review_sha256': q / 'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json',
        'stage_freeze_sha256': q / 'STAGE_B_FREEZE.json',
        'data_seal_sha256': q / 'data/DATA_SEAL.json',
        'analysis_protocol_sha256': root / 'governance/ANALYSIS_PROTOCOL.json',
        'readiness_protocol_sha256': root / 'governance/LOCAL_READINESS_PROTOCOL.json',
        'deployment_protocol_sha256': root / 'governance/DEPLOYMENT_PROTOCOL.json',
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
    for key in ('data_seal_sha256', 'analysis_protocol_sha256', 'readiness_protocol_sha256', 'deployment_protocol_sha256'):
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
    require(lock['status'] == 'PASS' and lock['stage'] == 'B' and lock['endpoint_count'] == 120
            and lock['engineering'] is False, 'Completed author audit required')
    for key in ('data_seal_sha256', 'analysis_protocol_sha256', 'stage_freeze_sha256'):
        require(lock[key] == release[key], 'Author lock binding differs')
    require(lock['source_hashes'] == freeze['source_hashes'] == reg['training_source_hashes'], 'Training sources differ')
    for name, expected in lock['source_hashes'].items():
        bound_file(contained(q, name), expected, watched)
    for name, expected in lock['audit_source_hashes'].items():
        bound_file(map_original_absolute(name, original, root), expected, watched)
    require(review['status'] == 'PASS' and review['stage'] == 'B' and review['endpoint_count'] == 120
            and review['endpoint_lock_sha256'] == release['endpoint_lock_sha256'], 'Independent review required')
    audit_path = contained(root, review['independent_audit_path'])
    audit = read_bound(audit_path, watched)
    require(watched[str(audit_path.resolve())] == review['independent_audit_sha256'], 'Independent audit changed')
    require(audit['status'] == 'PASS' and audit['stage'] == 'B' and audit['endpoint_count'] == 120
            and audit['engineering'] is False and audit['validation_rounds_replayed'] == 24000
            and audit['validation_predictions_replayed'] == 38400000
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
    require(len(lock['endpoints']) == len(audit['endpoints']) == 120
            and {(r['population'], r['seed'], r['method']) for r in lock['endpoints']} == identities
            and {(r['population'], r['seed'], r['method']) for r in audit['endpoints']} == identities, 'Exact120 endpoint identities required')
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
            and stage['committed_endpoints'] == stage['expected_endpoints'] == 120
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
    # Audit-only prerequisite. No test payload is opened or parsed, and the
    # producer was not required to watch this separate completion record.
    official=read_bound(q/'confirmation_evaluation/EVALUATION_COMMIT.json',watched)
    require(official.get('status')=='completed' and official.get('study_id')=='QPATH-GENERALIZATION-v0.6'
            and official.get('report_count')==120 and official.get('prediction_file_count')==120
            and official.get('population_count')==4 and official.get('payload_count')==250,
            'Complete official evaluation metadata required')
    require(official['release_sha256']==watched[str(release_path.resolve())]
            and official['registration_sha256']==rh and official['endpoint_lock_sha256']==release['endpoint_lock_sha256']
            and official['release_id']==release['release_id'],'Official evaluation completion identity differs')
    require(set(official['files'])==set(reg['expected_output_paths']) and len(official['files'])==250,'Official evaluation declared inventory differs')
    require(timestamp(release['created_utc'])<=timestamp(official['completed_utc'])<=timestamp(report['created_utc']),
            'Capsule must follow official evaluation completion')
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
    """All numerical inputs are opened only after gate; synthetic contexts are explicit."""
    report,protocol,folder=context['report'],context['protocol'],context['folder']
    populations,seeds,methods=protocol['populations'],protocol['training_seeds'],protocol['methods']
    require(methods==list(METHODS),'Only registered Scalar/Multi capsule methods')
    groups=[(p,s,m) for p in populations for s in seeds for m in methods]
    rows=report['circuits']; require(len(rows)==32*len(groups),'Full32 fixtures per checkpoint required')
    require([(r['population'],r['training_seed'],r['method'],r['fixture_index']) for r in rows]==[(*g,i) for g in groups for i in range(32)],'Fixture tuple/order differs')
    vals={};parameters={};checkpoints={}
    # Require producer bindings before even the first validation NPZ load.
    for pop in populations:
        for filename,expected in ((f'{pop}_validation.npz',context['seal']['files'][f'{pop}_validation.npz']['sha256']),
                                  (f'{pop}_router.json',context['seal']['routers'][pop]['sha256'])):
            recorded=PureWindowsPath(context['original_root'])/'quantum'/'data'/filename
            matches=[h for n,h in report['watched_input_hashes'].items() if PureWindowsPath(n)==recorded]
            require(matches==[expected],'Missing original validation/router binding: '+filename)
    for pop in populations:
        path=context['q']/'data'/f'{pop}_validation.npz';bound_file(path,context['seal']['files'][path.name]['sha256'],context['watched'])
        data=load_arrays(path);indices=np.argsort(data['ids'],kind='stable')[:32]
        require(len(set(data['ids'].tolist()))==1600,'Validation record identity count differs')
        policy_path=context['q']/'data'/f'{pop}_router.json';bound_file(policy_path,context['seal']['routers'][pop]['sha256'],context['watched']);policy=read_bound(policy_path,context['watched'])
        centers=np.asarray(policy['centroids']);xy=data['x'][indices]
        route=np.array([min(range(5),key=lambda j:float(sum((x[k]-centers[j,k])**2 for k in range(2)))) for x in xy])
        require(np.array_equal(route,data['kmeans_route'][indices]),'Independent raw-input routing differs')
        require(report['fixture_ids'][pop]==data['ids'][indices].tolist(),'Smallest-ID selection differs')
        vals[pop]=(xy,data['ids'][indices],route)
    for identity in groups:
        pop,seed,method=identity;entry=context['endpoints'][identity]
        path=context['q']/'stage_B'/pop/f'seed_{seed}'/method/'selected_checkpoint.npz'
        expected=entry['files']['selected_checkpoint.npz']['sha256'];bound_file(path,expected,context['watched'])
        data=load_arrays(path);v=data['parameters'];require(v.shape==((50 if method=='qscalar_kmeans' else 70),) and np.isfinite(v).all(),'Checkpoint shape/values differ')
        require(data['core_parameters'].size==0,'Unexpected separate frozen core')
        parameters[identity]=v;checkpoints[identity]=expected
    tables=read_bound(folder/'snapshot_channel_tables.json',context['watched']);noise=read_bound(folder/'snapshot_noise_model.json',context['watched'])
    saved=load_arrays(folder/'snapshot_quantum_channels.npz');channels={};readout={};maxima={}
    def compare(a,b,label,limit=2e-12):
        error=vector_close(a,b,label,limit);maxima[label]=max(maxima.get(label,0.),error);return error
    for error in noise['errors']:
        if error['type']=='roerror':
            matrix=np.asarray(error['probabilities']);require(matrix.shape==(2,2) and np.isfinite(matrix).all() and (matrix>=0).all(),'Readout matrix invalid')
            compare(matrix.sum(axis=1),[1.,1.],'readout_row_sum')
            for (q,) in error['gate_qubits']:require(q not in readout,'Duplicate readout channel');readout[q]=matrix
        else:
            require(error['type']=='qerror','Unknown noise type');channel=ref.reconstruct_superop(error)
            for qs in error['gate_qubits']:
                for operation in error['operations']:
                    matches=[a for a in tables['channels'] if a['operation']==operation and a['physical_qubits']==qs]
                    require(len(matches)==1,'Serialized native channel mapping differs');item=matches[0]
                    compare(channel,saved[item['array_key']],'exported_superop');key=(operation,tuple(qs));require(key not in channels,'Duplicate native channel');channels[key]=channel
    require(len(channels)==len(tables['channels']) and set(saved)=={v['array_key'] for v in tables['channels']},'Exact channel inventory differs')
    require(set(readout)==set(range(5)) and set(tables['readout_matrices'])==set(map(str,range(5))),'Exact five readout inventory differs')
    for q,matrix in readout.items():compare(matrix,tables['readout_matrices'][str(q)],'exported_readout',0.)
    settings=[];disagreements=[];bygroup={g:[] for g in groups};bykey={}
    for row in rows:
        identity=row['population'],row['training_seed'],row['method'];pop,seed,method=identity;i=row['fixture_index']
        xy,ids,routes=vals[pop];require(row['record_id']==int(ids[i]) and row['bank']==int(routes[i]),'Fixture record/bank differs')
        compare(row['x'],xy[i],'input_identity',0.);key=f'{pop}__seed{seed}__{method}__id{int(ids[i])}'
        require(row['key']==key and row['checkpoint_sha256']==checkpoints[identity],'Fixture checkpoint/key differs')
        require(key not in bykey,'Duplicate fixture key');bykey[key]=row;bygroup[identity].append(row)
        width=10 if method=='qscalar_kmeans' else 14;theta=parameters[identity][width*row['bank']:width*(row['bank']+1)];core=theta[:8].reshape(2,2,2)
        compare(theta[8:],row['head'],'head_identity',0.)
        required=['XX'] if method=='qscalar_kmeans' else ['XX','ZZ'];require(row['required_settings']==required and set(row['settings'])==set(required),'Measurement settings differ')
        require(row['core_operations']=={'ry':8,'rz':4,'cx':2},'Core operations differ')
        require(math.isfinite(row['source_unitary_error']) and 0<=row['source_unitary_error']<=2e-12,'Recorded core matrix residual outside protocol')
        rho=ref.core_density(xy[i],core);moments=ref.moments(rho);p=ref.apply_head(method,theta,moments)[0]
        for field in ('reference_moments','production_moments','aer_core_moments'):
            compare(moments,[row[field][k] for k in ('X0','X1','Z0','Z1','Z0Z1')],field)
        for field in ('production_probability','reference_probability','aer_core_probability','compiled_aer_probability'):compare(p,row[field],field)
        cl=classification(row['production_probability'],p)
        if cl['class_disagreement']:disagreements.append({'key':key,'canonical_probability':row['production_probability'],'independent_probability':p,**cl})
        require(row['numerical_classification']==classification(row['production_probability'],row['reference_probability']),'Saved core class diagnostic differs')
        require(row['compiled_numerical_classification']==classification(row['production_probability'],row['compiled_aer_probability']),'Saved compiled class diagnostic differs')
        predicted={name:{} for name in ('ideal','illustrative_mild','archived_manila')}
        for setting in required:
            settings.append((row,setting));record=row['settings'][setting]
            operations=ref.parse_native_qasm((folder/'circuits'/f'{key}__{setting}__compiled.qasm').read_text())
            counts={name:sum(op[0]==name for op in operations) for name in {op[0] for op in operations}}
            require(record['compiled_operations']==counts and record['compiled_width']==5,'Compiled gate counts/width differ')
            require(record['logical_operations']=={'ry':10 if setting=='XX' else 8,'rz':4,'cx':2},'Logical setting operations differ')
            mapping=record['physical_mapping'];require(mapping=={'logical_wire_to_physical':[0,1],'logical_q0_physical':1,'logical_q1_physical':0,'classical_bit_to_physical':[0,1],'count_order':['00','01','10','11'],'physical_width':5,'active_physical_qubits':[0,1],'routing_method':'none'},'Physical/wire/count mapping differs')
            ideal=ref.native_density(operations);native=ref.native_density(operations,channels)
            ij=np.maximum(np.real(np.diag(ideal)),0);ij/=ij.sum();nj=np.maximum(np.real(np.diag(native)),0);nj/=nj.sum()
            compare(ij,ref.setting_distribution(rho,setting),'native_ideal_joint');compare(ij,record['reference_joint'],'reference_joint');compare(ij,record['compiled_aer_joint'],'aer_joint')
            mildrho=ref.core_density(xy[i],core,.001,.01);mildpre=ref.setting_distribution(mildrho,setting,.001,0.)
            distributions={'ideal':(ij,ij),'illustrative_mild':(mildpre,ref.bit_flip_joint(mildpre,.01)),
                           'archived_manila':(nj,ref.asymmetric_readout(nj,readout))}
            for scenario,(pre,observed) in distributions.items():
                target=row['scenarios'][scenario]['settings'][setting]
                compare(pre,target['premeasurement_joint'],scenario+'_premeasurement');compare(observed,target['observed_joint'],scenario+'_observed')
                predicted[scenario][setting]=observed
            for field in ('source_unitary_error','compiled_unitary_error','compiled_aer_joint_error'):
                require(math.isfinite(record[field]) and 0<=record[field]<=2e-12,'Recorded matrix residual outside protocol')
        for scenario,joints in predicted.items():
            m=ref.grouped_moments(joints['XX'],joints.get('ZZ',np.full(4,.25)));expected=ref.apply_head(method,theta,m)[0];target=row['scenarios'][scenario]
            compare(expected,target['observed_probability'],scenario+'_head')
            keys=('X0','X1') if method=='qscalar_kmeans' else ('X0','X1','Z0','Z1','Z0Z1')
            compare([target['observed_moments'][k] for k in keys],m[:len(keys)],scenario+'_grouped_moments')
            close(target['absolute_distortion_from_ideal'],abs(target['observed_probability']-row['reference_probability']),'Distortion arithmetic differs')
            require(target['classification_disagreement_from_ideal']==bool((target['observed_probability']>=.5)!=(row['reference_probability']>=.5)),'Noise class comparison differs')
    records=read_bound(folder/'finite_shot_records.json',context['watched']);counts=load_arrays(folder/'finite_shot_counts.npz');predictors=load_arrays(folder/'finite_shot_probabilities.npz')
    scenarios=['ideal','illustrative_mild','archived_manila'];expected_tuples=[(p,s,m,sc,shots,repeat) for p,s,m in groups for sc in scenarios for shots in (1024,8192) for repeat in range(5)]
    require([(v['population'],v['training_seed'],v['method'],v['scenario'],v['shots_per_setting'],v['repeat_index']) for v in records]==expected_tuples,'Sampling semantic tuple/order differs')
    expected_counts=set();expected_predictors=set();represented=0
    for item,identity in zip(records,expected_tuples):
        pop,seed,method,scenario,shots,repeat=identity;require(type(item['repeat_index']) is int,'Repeat must be integer');key=f'{pop}__seed{seed}__{method}__{scenario}__shots{shots}__repeat{repeat}'
        require(item['key']==key,'Shot key differs');expected_predictors.add(key)
        cells=bygroup[(pop,seed,method)];required=cells[0]['required_settings'];require(item['settings']==required and item['record_ids']==[r['record_id'] for r in cells],'Shot settings/fixtures differ')
        drawn={}
        for setting in required:
            seq=[690101,populations.index(pop),seed,methods.index(method),scenarios.index(scenario),shots,repeat,('XX','ZZ').index(setting)]
            require(item['seed_sequences'][setting]==seq,'Sampling RNG identity differs')
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(seq)))
            actual=counts[key+'__'+setting];expected_counts.add(key+'__'+setting)
            require(actual.dtype==np.int64 and actual.shape==(32,4) and (actual>=0).all() and np.all(actual.sum(1)==shots),'Joint counts invalid')
            replay=np.array([rng.multinomial(shots,r['scenarios'][scenario]['settings'][setting]['observed_joint']) for r in cells],dtype=np.int64)
            require(np.array_equal(actual,replay),'Exact canonical-probability joint draw differs');drawn[setting]=actual/shots
        values=[]
        for i,row in enumerate(cells):
            m=ref.grouped_moments(drawn['XX'][i],drawn.get('ZZ',np.full((32,4),.25))[i]);values.append(ref.apply_head(method,np.r_[np.zeros(8),row['head']],m)[0])
        compare(values,predictors[key],'joint_sample_predictor');target=np.array([r['scenarios'][scenario]['observed_probability'] for r in cells]);values=np.asarray(predictors[key])
        close(item['mean_signed_probability_error'],np.mean(values-target),'Sampling signed error differs');close(item['mean_absolute_probability_error'],np.mean(abs(values-target)),'Sampling absolute error differs')
        close(item['classification_disagreement_from_density'],np.mean((values>=.5)!=(target>=.5)),'Sampling class fraction differs')
        require(item['total_shots']==shots*32*len(required),'Represented shots differ');represented+=item['total_shots']
    require(set(counts)==expected_counts and set(predictors)==expected_predictors,'Exact finite-shot NPZ inventory differs')
    summaries=read_bound(folder/'finite_shot_summary.json',context['watched']);summary_tuples=[(*g,sc,n) for g in groups for sc in scenarios for n in (1024,8192)]
    require([(v['population'],v['training_seed'],v['method'],v['scenario'],v['shots_per_setting']) for v in summaries]==summary_tuples,'Nested summary order differs')
    for item,(pop,seed,method,scenario,shots) in zip(summaries,summary_tuples):
        cells=bygroup[(pop,seed,method)];require(item['replicates']==5 and item['fixture_ids']==[r['record_id'] for r in cells],'Nested summary fixture identity differs')
        a=np.array([predictors[f'{pop}__seed{seed}__{method}__{scenario}__shots{shots}__repeat{j}'] for j in range(5)])
        target=np.array([r['scenarios'][scenario]['observed_probability'] for r in cells]);bias=a.mean(0)-target;variance=((a-a.mean(0))**2).sum(0)/4
        compare(item['empirical_bias_per_fixture'],bias,'nested_bias');compare(item['sample_variance_per_fixture'],variance,'nested_variance')
        for field,value in (('mean_signed_bias',bias.mean()),('mean_absolute_bias',abs(bias).mean()),('mean_sample_variance',variance.mean())):close(item[field],value,'Nested aggregate differs')
    measured=read_bound(folder/'measured_aer_counts.json',context['watched']);expected_measured=[(r['key'],setting,scenario) for scenario in ('ideal','archived_manila') for r,setting in settings if r['fixture_index']<8]
    require([(m['key'],m['setting'],m['scenario']) for m in measured]==expected_measured,'Measured execution tuple/order differs')
    for item in measured:
        require(item['shots']==1024 and item['seed_simulator']==690103 and item['count_order']==['00','01','10','11'],'Measured shot/seed/wire identity differs')
        c=np.asarray(item['counts']);require(c.dtype.kind in 'iu' and c.shape==(4,) and (c>=0).all() and c.sum()==1024,'Measured counts invalid')
        joint=np.array(bykey[item['key']]['scenarios'][item['scenario']]['settings'][item['setting']]['observed_joint']);compare(joint,item['density_expected_joint'],'measured_expectation')
        compare([c@ref.Q0/1024,c@ref.Q1/1024,c@(ref.Q0*ref.Q1)/1024],item['observed_moments'],'measured_moment_arithmetic')
        variance=1024*joint*(1-joint)
        for j in range(4):
            if variance[j]>0:close(item['standardized_count_residuals'][j],(c[j]-1024*joint[j])/np.sqrt(variance[j]),'Measured standardized residual differs')
            else:require(item['standardized_count_residuals'][j] is None,'Degenerate measured residual must be null')
    for pop in populations:
        for method in methods:
            cells=[r for r in rows if r['population']==pop and r['method']==method]
            for scenario in scenarios:
                item=report['summaries'][pop][method][scenario];values=[r['scenarios'][scenario] for r in cells]
                require(item['checkpoint_fixture_pairs']==len(cells),'Noise summary denominator differs')
                for field,v in (('mean_absolute_distortion',np.mean([a['absolute_distortion_from_ideal'] for a in values])),('maximum_absolute_distortion',max(a['absolute_distortion_from_ideal'] for a in values)),('classification_disagreement_fraction',np.mean([a['classification_disagreement_from_ideal'] for a in values]))):close(item[field],v,'Noise aggregate differs')
    totals={'checkpoint_count':len(groups),'checkpoint_fixture_pairs':len(rows),'required_measurement_circuits':len(settings),'additional_original_legacy_circuits':0,'core_ideal_aer_evaluations':len(rows),'compiled_ideal_aer_evaluations':len(settings),'production_model_forward_statevector_examples':len(rows),'additional_full_moment_statevector_examples':len(rows),'density_evaluations':3*len(settings),'logical_two_qubit_density_evaluations':len(settings),'compiled_five_qubit_density_evaluations':2*len(settings),'measured_aer_circuit_experiments':len(measured),'actual_simulated_measurement_shots':1024*len(measured),'finite_shot_count_array_count':len(counts),'finite_shot_predictor_array_count':len(predictors),'represented_multinomial_trials':represented}
    for field,value in totals.items():require(report[field]==value,'Capsule work total differs: '+field)
    recorded_maxima={'maximum_core_unitary_error':max(r['source_unitary_error'] for r in rows),
        'maximum_compiled_unitary_error':max(v['compiled_unitary_error'] for r in rows for v in r['settings'].values()),
        'maximum_aer_moment_error':max(r['maximum_aer_moment_error'] for r in rows),
        'maximum_production_moment_error':max(r['maximum_production_moment_error'] for r in rows)}
    for field,value in recorded_maxima.items():close(report[field],value,'Recorded aggregate residual differs')
    resources=report['checkpoint_resources']
    require([(v['population'],v['training_seed'],v['method']) for v in resources]==groups,'Checkpoint resource order differs')
    for item,identity in zip(resources,groups):
        pop,seed,method=identity;result=read_bound(context['q']/'stage_B'/pop/f'seed_{seed}'/method/'result.json',context['watched'])
        require(item['inference']==result['inference'] and item['frozen_cache']==result['frozen_cache'] and item['trainable_parameters']==result['parameter_count']==(50 if method=='qscalar_kmeans' else 70) and item['fixed_core_parameters']==result['fixed_core_parameter_count']==0,'Checkpoint resource evidence differs')
    files={'report.json','snapshot_noise_model.json','snapshot_channel_tables.json','snapshot_quantum_channels.npz','finite_shot_counts.npz','finite_shot_probabilities.npz','finite_shot_records.json','finite_shot_summary.json','measured_aer_counts.json'}
    files.update(f'circuits/{r["key"]}__core.qasm' for r in rows)
    files.update(f'circuits/{r["key"]}__{setting}__{kind}.qasm' for r,setting in settings for kind in ('logical','compiled'))
    files.update(f'circuits/{r["key"]}__{setting}__measured.qasm' for r,setting in settings if r['fixture_index']<8)
    require(set(context['commit']['files'])==files,'Full capsule payload inventory differs')
    require(all(math.isfinite(v) and v>=0 for v in report['timings_seconds'].values()) and math.isfinite(report['elapsed_seconds']) and report['elapsed_seconds']>=0,'Timing must be finite and nonnegative')
    return {**totals,'selected_checkpoints_checked':len(checkpoints),'native_channel_mappings_reconstructed':len(channels),'readout_matrices_reconstructed':len(readout),'maximum_independent_errors':maxima,'all_exact_joint_multinomial_arrays_reproduced':True,'five_repeat_bias_variance_reconstructed':True,'independent_class_disagreements':len(disagreements),'independent_class_disagreement_records':disagreements,'outside_band_independent_class_disagreements':0,'payload_count':len(files)}


def run(root,output):
    output=Path(output).resolve();require(not output.exists(),'Preserve prior audit output');context=gate(root)
    for path in (Path(__file__),Path(ref.__file__)):bound_file(path,digest(path),context['watched'])
    output.mkdir(parents=True,exist_ok=False)
    def write(name,value):
        with (output/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
    write('ACCESS_EVENT.json',{'created_utc':now(),'release_id':context['release']['release_id'],'readiness_commit_sha256':digest(context['folder']/'READINESS_COMMIT.json'),'scope':'Validation-only released complete capsule; no test arrays or model test metrics.'})
    try:
        checks=verify_numerics(context);recheck(context['watched'])
        result={'status':'PASS','study_id':'QPATH-GENERALIZATION-v0.6','created_utc':now(),'engineering':False,'test_arrays_accessed':False,'model_test_outcomes_accessed':False,'checks':checks,'release_id':context['release']['release_id'],'release_sha256':digest(context['q']/'EVALUATION_RELEASE.json'),'readiness_commit_sha256':digest(context['folder']/'READINESS_COMMIT.json'),'registration_sha256':context['registry_sha256'],'auditor_sources':{p.relative_to(ROOT).as_posix():digest(p) for p in (Path(__file__),Path(ref.__file__))},'watched_input_hashes':context['watched'],'scope':'Independent NumPy logical channels, serialized native-channel reconstruction, native QASM density replay, asymmetric readout, grouped moments/nonlinear heads and exact saved-probability multinomial draws; repeated-shot bias/variance and recorded measured-count arithmetic.','limits':'No independent backend-from-calibration reconstruction, Qiskit transpilation or Aer execution. Native circuits use only physical0/1; inactive target wires remain idle without added noise. Original logical QASM and all payload hashes/inventories are checked; source/compiled unitary residuals are retained producer measurements, not independently rerun unitary calculations. No hardware or current-calibration claim.'}
        write('summary.json',result);recheck(context['watched'])
        write('AUDIT_COMMIT.json',{'status':'completed','created_utc':now(),'readiness_commit_sha256':result['readiness_commit_sha256'],'files':{p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in output.iterdir() if p.is_file()}});return result
    except BaseException as error:
        write('FAILURE.json',{'status':'FAIL','created_utc':now(),'error':str(error),'traceback':traceback.format_exc(),'recovery':'Preserve all output; root review before separate retry.'});raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    require(args.output.resolve().parent==HERE,'Output must be a new child of classical_review')
    result=run(ROOT,args.output);print(json.dumps({'status':result['status'],'checks':result['checks']}))


