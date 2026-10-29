"""Registered official summaries. Independent replay must not import this module."""
from pathlib import Path
import hashlib, json
import numpy as np
from scipy.stats import t

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / 'governance/ANALYSIS_PROTOCOL.json'
CLIP = 1e-7

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def metric_arrays(labels, probabilities):
    """Return seed x method x (BCE,F1,accuracy), with F1/accuracy fractions."""
    y = np.asarray(labels, dtype=np.int64)
    p = np.asarray(probabilities, dtype=np.float64)
    if y.ndim != 1 or p.ndim != 3 or p.shape[-1] != len(y):
        raise ValueError('Invalid prediction shapes')
    if not np.isin(y, [0, 1]).all() or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError('Invalid labels or probabilities')
    pc = np.clip(p, CLIP, 1-CLIP)
    loss = -(y*np.log(pc)+(1-y)*np.log1p(-pc))
    pred = p >= .5
    tp = np.sum(pred & (y == 1), axis=-1)
    fp = np.sum(pred & (y == 0), axis=-1)
    fn = np.sum(~pred & (y == 1), axis=-1)
    tn = np.sum(~pred & (y == 0), axis=-1)
    d1, d0 = 2*tp+fp+fn, 2*tn+fp+fn
    f1 = (np.divide(2*tp, d1, out=np.zeros_like(tp, dtype=float), where=d1!=0)
          + np.divide(2*tn, d0, out=np.zeros_like(tn, dtype=float), where=d0!=0))/2
    metrics = np.stack([loss.mean(axis=-1), f1, (tp+tn)/len(y)], axis=-1)
    return metrics, loss

def _interval(values, confidence):
    values = np.asarray(values, dtype=np.float64)
    mean = float(values.mean())
    sd = float(values.std(ddof=1))
    half = float(t.ppf((1+confidence)/2, len(values)-1)*sd/np.sqrt(len(values)))
    return {'mean':mean, 'sample_sd':sd, 'n':len(values), 'confidence':confidence,
            'lower':mean-half, 'upper':mean+half}

def _bootstrap_metrics(labels, probabilities, loss, counts):
    y = np.asarray(labels)
    p = np.asarray(probabilities)
    n = len(y)
    s, m, _ = p.shape
    pred = p.reshape(s*m, n) >= .5
    tp_basis = (pred & (y == 1)).astype(np.float64).T
    fp_basis = (pred & (y == 0)).astype(np.float64).T
    result = np.empty((len(counts), m, 3), dtype=np.float64)
    mean_loss = loss.mean(axis=0).T
    for start in range(0, len(counts), 100):
        stop = min(start+100, len(counts))
        c = counts[start:stop].astype(np.float64)
        tp = c@tp_basis
        fp = c@fp_basis
        pos = (c@y)[:, None]
        fn, tn = pos-tp, n-pos-fp
        d1, d0 = 2*tp+fp+fn, 2*tn+fp+fn
        f1 = (np.divide(2*tp,d1,out=np.zeros_like(tp),where=d1!=0)
              + np.divide(2*tn,d0,out=np.zeros_like(tn),where=d0!=0))/2
        result[start:stop,:,0] = c@mean_loss/n
        result[start:stop,:,1] = f1.reshape(stop-start,s,m).mean(axis=1)
        result[start:stop,:,2] = ((tp+tn)/n).reshape(stop-start,s,m).mean(axis=1)
    return result

def analyse_population(population_name, labels, probabilities, seeds, methods, output_dir):
    """Exclusive output for one population; return its JSON-safe result.

    probabilities has shape(5,9,n), canonical seed/method order from protocol.
    Creates bootstrap_counts.npy and population_summary.json. Does not read data
    or model files itself; caller must enforce the all-endpoint release gate.
    """
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding='utf-8-sig'))
    if list(seeds) != protocol['training_seeds'] or list(methods) != protocol['methods']:
        raise ValueError('Unregistered seeds or method order')
    if population_name not in protocol['population_order']:
        raise ValueError('Unregistered confirmation population')
    p = np.asarray(probabilities, dtype=np.float64)
    if p.shape[:2] != (5,9):raise ValueError('All45 population endpoints required')
    y = np.asarray(labels)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    metrics, loss = metric_arrays(y,p)
    config = protocol['record_bootstrap']
    rng = np.random.Generator(np.random.PCG64(config['seeds'][population_name]))
    raw_counts = rng.multinomial(len(y),np.full(len(y),1.0/len(y)),size=config['replicates'])
    if raw_counts.max() > np.iinfo(np.uint16).max:raise ValueError('Bootstrap count overflow')
    counts = raw_counts.astype(np.uint16)
    del raw_counts
    if not np.all(counts.sum(axis=1)==len(y)):raise ValueError('Invalid bootstrap counts')
    count_path = output/'bootstrap_counts.npy'
    np.save(count_path,counts,allow_pickle=False)
    boot = _bootstrap_metrics(y,p,loss,counts)
    names = ('bce','macro_f1','accuracy')
    aggregate = {}
    for mi,method in enumerate(methods):
        aggregate[method] = {metric:{'mean':float(metrics[:,mi,ki].mean()),
                                    'sample_sd':float(metrics[:,mi,ki].std(ddof=1)),
                                    'seed_values':metrics[:,mi,ki].tolist()}
                             for ki,metric in enumerate(names)}
    def contrast(name,terms,primary):
        indices=[(methods.index(method),weight) for method,weight in terms]
        result={'name':name,'terms':terms,'primary':primary,'metrics':{}}
        for ki,metric in enumerate(names):
            scale = 1.0 if metric=='bce' else 100.0
            seed_delta = sum(metrics[:,index,ki]*weight for index,weight in indices)*scale
            boot_delta = sum(boot[:,index,ki]*weight for index,weight in indices)*scale
            item={'units':'natural_log_loss' if metric=='bce' else 'percentage_points',
                  'seed_values':seed_delta.tolist(), 'seed_interval95':_interval(seed_delta,.95),
                  'record_interval95':np.quantile(boot_delta,[.025,.975],method='linear').tolist()}
            if primary and metric=='bce':
                alpha=.05/protocol['primary_family_size']
                item['seed_interval_adjusted']=_interval(seed_delta,1-alpha)
                item['record_interval_adjusted']=np.quantile(boot_delta,[alpha/2,1-alpha/2],method='linear').tolist()
                item['practical_magnitude']=.01
            result['metrics'][metric]=item
        return result
    comparisons=[]
    for first,second in protocol['primary_contrasts']:
        comparisons.append(contrast(first+' minus '+second,[(first,1),(second,-1)],True))
    for first,second in protocol['secondary_contrasts']:
        comparisons.append(contrast(first+' minus '+second,[(first,1),(second,-1)],False))
    for interaction in protocol['secondary_interactions']:
        comparisons.append(contrast(interaction['name'],interaction['terms'],False))
    result={'population':population_name,'n':len(y),'seeds':list(seeds),'methods':list(methods),
            'protocol_sha256':digest(PROTOCOL_PATH),'statistics_source_sha256':digest(__file__),
            'numpy_version':np.__version__,'bootstrap_counts_sha256':digest(count_path),
            'bootstrap_replicates':len(counts),'primary_family_size':protocol['primary_family_size'],
            'aggregate':aggregate,'contrasts':comparisons,
            'limits':{'seed':protocol['seed_uncertainty']['limits'],
                      'record':protocol['record_bootstrap']['limits'],
                      'secondary':protocol['secondary_limits']}}
    with (output/'population_summary.json').open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    return result
