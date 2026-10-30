"""Registered v0.9 descriptive metrics and population-level contrasts.

This module has no data loader. It is also used with synthetic qualification data.
"""
from __future__ import annotations
import numpy as np
from scipy.stats import t

CLIP = 1e-7
SCALARS = ('bce', 'macro_f1', 'accuracy', 'brier', 'ece10',
           'positive_precision', 'positive_recall', 'average_precision',
           'native_bce', 'clipping_frequency')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def losses(y, p, z):
    q = np.clip(p, CLIP, 1-CLIP)
    return (-y*np.log(q)-(1-y)*np.log1p(-q),
            np.maximum(z, 0)-y*z+np.log1p(np.exp(-np.abs(z))))


def average_precision(y, p):
    positives = int(y.sum())
    if not positives:
        return None
    order = np.argsort(-p, kind='stable')
    yy, pp = y[order], p[order]
    ends = np.r_[np.flatnonzero(pp[1:] != pp[:-1]), len(pp)-1]
    tp = np.cumsum(yy)[ends]
    recall = tp/positives
    precision = tp/(ends+1)
    return float(np.sum(np.diff(np.r_[0., recall])*precision))


def metrics(y, p, z):
    y = np.asarray(y); p = np.asarray(p, dtype=np.float64); z = np.asarray(z, dtype=np.float64)
    require(y.ndim == 1 and p.shape == z.shape == y.shape, 'Matching vectors required')
    require(np.isin(y, [0, 1]).all(), 'Binary labels required')
    require(np.isfinite(p).all() and np.isfinite(z).all() and np.all((p >= 0) & (p <= 1)), 'Invalid probabilities or logits')
    n = len(y)
    if not n:
        return dict(n=0, **{key: None for key in SCALARS}, confusion=[[0, 0], [0, 0]],
                    reliability10=[], limitation='Empty diagnostic slice; metrics undefined.')
    pred = p >= .5
    confusion = [[int(np.sum((y == a) & (pred == b))) for b in (0, 1)] for a in (0, 1)]
    f1 = []
    for k in (0, 1):
        tp, fp, fn = confusion[k][k], confusion[1-k][k], confusion[k][1-k]
        f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.)
    tp, fp, fn = confusion[1][1], confusion[0][1], confusion[1][0]
    edges = np.linspace(0, 1, 11)
    bins = np.minimum(np.searchsorted(edges, p, side='right')-1, 9)
    reliability = []; ece = 0.
    for k in range(10):
        ix = bins == k; count = int(ix.sum())
        mp = float(p[ix].mean()) if count else None
        my = float(y[ix].mean()) if count else None
        if count:
            ece += count/n*abs(mp-my)
        reliability.append(dict(bin=k, lower=float(edges[k]), upper=float(edges[k+1]),
                                count=count, mean_probability=mp, fraction_positive=my))
    common, native = losses(y, p, z)
    clipped = (p < CLIP) | (p > 1-CLIP)
    return dict(n=n, positives=int(y.sum()), negatives=int(n-y.sum()),
                bce=float(common.mean()), native_bce=float(native.mean()),
                macro_f1=float(np.mean(f1)), per_class_f1=f1,
                accuracy=float(np.mean(pred == y)), brier=float(np.mean((p-y)**2)),
                ece10=float(ece), reliability10=reliability, confusion=confusion,
                positive_precision=float(tp/(tp+fp)) if tp+fp else 0.,
                positive_recall=float(tp/(tp+fn)) if tp+fn else 0.,
                average_precision=average_precision(y, p),
                clipped_count=int(clipped.sum()), clipping_frequency=float(clipped.mean()),
                clipped_wrong_prediction_count=int(np.sum(clipped & (pred != y))),
                minimum_raw_probability=float(p.min()), maximum_raw_probability=float(p.max()),
                minimum_native_logit=float(z.min()), maximum_native_logit=float(z.max()),
                limitation='Single-class slice; registered two-class macro F1 still includes both classes.' if np.unique(y).size < 2 else None)


def distribution(values):
    observed = [float(v) for v in values if v is not None]
    return dict(n=len(values), defined_n=len(observed), values=values,
                mean=float(np.mean(observed)) if observed else None,
                minimum=min(observed) if observed else None, maximum=max(observed) if observed else None,
                sample_sd=float(np.std(observed, ddof=1)) if len(observed) > 1 else None)


def contrast(rows, family, first, second, confidence, primary):
    selected = [r for r in rows if r['family'] == family]
    populations = sorted({r['population'] for r in selected})
    require(len(populations) == 8, 'Eight independent synthetic populations required')
    parts = []
    for population in populations:
        paired = {}
        for arm in (first, second):
            rr = [r for r in selected if r['population'] == population and r['arm'] == arm]
            require(len(rr) == 2 and len({r['seed'] for r in rr}) == 2, 'Two unique paired seeds required')
            paired[arm] = {r['seed']: r['test']['bce'] for r in rr}
        require(set(paired[first]) == set(paired[second]), 'Unpaired training seeds')
        differences = [dict(seed=s, first=paired[first][s], second=paired[second][s],
                            difference=paired[first][s]-paired[second][s]) for s in sorted(paired[first])]
        parts.append(dict(population=population, seed_pairs=differences,
                          mean_difference=float(np.mean([d['difference'] for d in differences]))))
    d = np.array([part['mean_difference'] for part in parts])
    mean = float(d.mean()); sd = float(d.std(ddof=1)); se = sd/np.sqrt(8)
    critical = float(t.ppf((1+confidence)/2, 7)); low, high = mean-critical*se, mean+critical*se
    if se == 0:
        statistic = None; pvalue = 1. if mean == 0 else 0.
    else:
        statistic = mean/se; pvalue = float(2*t.sf(abs(statistic), 7))
    return dict(family=family, first=first, second=second, metric='bce',
                direction='first minus second; negative favors first', primary=primary,
                populations=parts, n_independent_populations=8, paired_seeds_per_population=2,
                mean_difference=mean, population_sample_sd=sd, standard_error=float(se), df=7,
                confidence=confidence, critical_t=critical, interval=[float(low), float(high)],
                t_statistic=statistic, two_sided_p_unadjusted=pvalue,
                bonferroni_p=min(1., 12*pvalue) if primary else None,
                favors_first=bool(high < 0), favors_second=bool(low > 0),
                first_exceeds_practical_reference=bool(high < -.01) if primary else None,
                interpretation=('Interval is below zero.' if high < 0 else 'Interval is above zero.' if low > 0 else
                                'Interval includes zero; this does not demonstrate equivalence.'),
                multiplicity='Bonferroni family of 12 primary BCE contrasts' if primary else 'Nominal 95% secondary exploratory interval')


def analyze(rows, protocol):
    require(len(rows) == 636 and len({r['job_id'] for r in rows}) == 636, 'Complete unique confirmation results required')
    require(protocol['family_size'] == 12 and protocol['populations_per_family'] == 8 and protocol['seeds_per_population'] == 2,
            'Unexpected registered analysis')
    primary = [contrast(rows, c['family'], c['first'], c['second'],
                        protocol['nominal_per_contrast_confidence'], True) for c in protocol['primary_contrasts']]
    families = sorted({c['family'] for c in protocol['primary_contrasts']})
    secondary = [contrast(rows, f, c['first'], c['second'], .95, False)
                 for f in families for c in protocol['secondary_contrasts']]
    synthetic = []
    for family in families:
        rr = [r for r in rows if r['family'] == family]
        for arm in sorted({r['arm'] for r in rr}):
            ar = [r for r in rr if r['arm'] == arm]
            require(len(ar) == 16, 'Each synthetic arm needs 8 populations by 2 seeds')
            population_rows = []
            for population in sorted({r['population'] for r in ar}):
                pr = [r for r in ar if r['population'] == population]
                population_rows.append(dict(population=population, seeds=[r['seed'] for r in pr],
                                            metrics={k: distribution([r['test'][k] for r in pr]) for k in SCALARS}))
            synthetic.append(dict(family=family, arm=arm, population_results=population_rows,
                                  across_population_means={k: distribution([p['metrics'][k]['mean'] for p in population_rows]) for k in SCALARS}))
    real = []
    rr = [r for r in rows if r['family'] == 'banknote']
    require(len(rr) == 60, 'Banknote requires 12 arms by 5 optimizer seeds')
    for arm in sorted({r['arm'] for r in rr}):
        ar = sorted((r for r in rr if r['arm'] == arm), key=lambda r: r['seed'])
        require(len(ar) == 5, 'Five Banknote optimization seeds required')
        real.append(dict(arm=arm, seeds=[r['seed'] for r in ar],
                         metrics={k: distribution([r['test'][k] for r in ar]) for k in SCALARS},
                         limitation='Descriptive optimization variation on one fixed grouped split; not independent datasets.'))
    return dict(primary_contrasts=primary, secondary_contrasts=secondary,
                synthetic_by_family_and_arm=synthetic, banknote_descriptive=real,
                pooling='No headline average across task families or across synthetic and Banknote data.')
