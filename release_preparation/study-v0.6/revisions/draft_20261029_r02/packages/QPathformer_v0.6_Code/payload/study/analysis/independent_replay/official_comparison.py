"""Canonical official-output checks without importing official computations."""
import numpy as np
from evidence_io import compare_structure, require
from statistics_reference import class_metrics, metrics, calibration, native_logit_bce, class_quality
from threshold_reference import CASES


def metric_shape(y, p):
    result = metrics(y, p)
    calibrated = calibration(y, p)
    result['ece10'] = calibrated['ece']
    result['reliability10'] = [{'bin': i, 'lower': row['lower'], 'upper': row['upper'],
        'count': row['count'], 'mean_probability': row['mean_probability'],
        'fraction_positive': row['positive_fraction']} for i, row in enumerate(calibrated['bins'])]
    return result


def check_metrics(actual, recorded, tolerance=2e-12):
    required = ("bce", "macro_f1", "accuracy", "brier", "n", "clipped", "confusion", "ece10", "reliability10")
    return compare_structure({key: actual[key] for key in required},
                             {key: recorded[key] for key in required}, tolerance)


def check_population_summary(independent, official, protocol_sha256, statistics_sha256):
    require(official["protocol_sha256"] == protocol_sha256, "Official analysis protocol differs")
    require(official["statistics_source_sha256"] == statistics_sha256, "Official statistics source differs")
    require(official["numpy_version"] == "2.5.4", "Official bootstrap runtime differs")
    fields = ("population", "n", "seeds", "methods", "bootstrap_replicates", "primary_family_size",
              "bootstrap_counts_sha256", "aggregate", "contrasts", "limits")
    return compare_structure({key: independent[key] for key in fields}, {key: official[key] for key in fields})


def check_official_numerical(y, canonical, ids, routes, official, independent, numerical):
    """Check canonical facts fully, plus disclosed author-reference consistency.

    The separate author oracle does not publish every reference probability.
    Its raw class metrics can be rebuilt from the exhaustive disagreement list.
    Reference-near counts and raw-reference BCE receive bounded consistency
    checks, whereas our own complete oracle probabilities are fully replayed.
    """
    y, p, ids = np.asarray(y), np.asarray(canonical), np.asarray(ids)
    n = len(y)
    require(official["band_half_width"] == numerical["band"], "Official numerical band differs")
    for key, tolerance in (("maximum_probability_error", numerical["probability_abs_tolerance"]),
                           ("independent_bce_error", numerical["independent_aggregate_bce_abs_tolerance"])):
        require(np.isfinite(official[key]) and 0 <= official[key] <= tolerance, "Official numerical tolerance failed")
    canonical_metrics = metric_shape(y, p)
    check_metrics(canonical_metrics, official["canonical_metrics"])
    compare_structure(independent["sensitivity"], official["sensitivity"])
    require(set(official["sensitivity"]) == set(CASES), "Official sensitivity cases differ")
    actual_near = np.abs(p - .5) <= numerical["band"]
    counts = official["counts"]
    require(counts["n"] == n and counts["canonical_near_band"] == int(actual_near.sum()), "Canonical numerical counts differ")
    require(counts["outside_band_class_disagreements"] == 0, "Official outside-band disagreement")
    records = official["disagreements"]
    require(counts["class_disagreements"] == len(records)
            and counts["exact_class_agreement"] == (len(records) == 0), "Official disagreement counts differ")
    positions = {int(record_id): index for index, record_id in enumerate(ids)}
    seen = set()
    reconstructed_raw = (p >= .5).astype(np.int64)
    for row in records:
        identity = row["record_id"]
        require(type(identity) is int and identity in positions and identity not in seen, "Unknown/duplicate disagreement ID")
        seen.add(identity)
        index = positions[identity]
        require(row["label"] == int(y[index]) and row["hash_route"] == int(routes["hash"][index])
                and row["kmeans_route"] == int(routes["kmeans"][index]), "Disagreement metadata differs")
        cp, rp = row["canonical_probability"], row["reference_probability"]
        require(cp == float(p[index]) and np.isfinite(rp) and 0 <= rp <= 1,
                "Disclosed canonical probability differs or invalid raw probability")
        require(abs(cp - rp) <= numerical["probability_abs_tolerance"]
                and abs(cp - .5) <= numerical["band"] and abs(rp - .5) <= numerical["band"],
                "Disclosed difference violates numerical band/tolerance")
        require(row["canonical_prediction"] == int(cp >= .5) and row["reference_prediction"] == int(rp >= .5)
                and row["canonical_prediction"] != row["reference_prediction"], "Disclosed classes inconsistent")
        reconstructed_raw[index] = row["reference_prediction"]
    raw_classes = class_metrics(y, reconstructed_raw)
    compare_structure(raw_classes, {key: official["raw_reference_metrics"][key] for key in raw_classes})
    raw_bce = official["raw_reference_metrics"]["bce"]
    require(np.isfinite(raw_bce) and raw_bce >= 0
            and abs(raw_bce - canonical_metrics["bce"]) <= numerical["independent_aggregate_bce_abs_tolerance"],
            "Disclosed raw-reference BCE inconsistent")
    require(abs(abs(raw_bce - official["canonical_metrics"]["bce"]) - official["independent_bce_error"]) <= 2e-12,
            "Official BCE error field inconsistent")
    reference_count, union_count = counts["reference_near_band"], counts["union_near_band"]
    require(type(reference_count) is int and type(union_count) is int
            and len(records) <= reference_count <= n
            and max(counts["canonical_near_band"], reference_count) <= union_count
            <= min(n, counts["canonical_near_band"] + reference_count - len(records)),
            "Undisclosed author reference-near counts violate set bounds")
    require(type(official["raw_reference_metrics"]["clipped"]) is int
            and 0 <= official["raw_reference_metrics"]["clipped"] <= n, "Invalid raw clipped count")
    raw = official['raw_reference_metrics']
    require(np.isfinite(raw['brier']) and 0 <= raw['brier'] <= 1
            and abs(raw['brier']-canonical_metrics['brier']) <= 2*numerical['probability_abs_tolerance']+2e-12,
            'Author raw Brier inconsistent with probability tolerance')
    # Full reference probability bins are unavailable: check partition/ranges and
    # aggregate arithmetic, without claiming exact bin membership reconstruction.
    bins=raw['reliability10'];edges=np.linspace(0,1,11)
    require(len(bins)==10, 'Author reference calibration bin count differs')
    count_total=0; positive_total=0.; probability_total=0.; ece=0.
    for i, row in enumerate(bins):
        require(row['bin']==i and row['lower']==edges[i] and row['upper']==edges[i+1]
                and type(row['count']) is int and 0 <= row['count'] <= n, 'Invalid reference calibration bin')
        count_total+=row['count']
        if row['count']:
            mp, fy=row['mean_probability'], row['fraction_positive']
            require(np.isfinite(mp) and np.isfinite(fy) and edges[i]-2e-12 <= mp <= edges[i+1]+2e-12
                    and 0 <= fy <= 1, 'Invalid reference calibration mean')
            positive_total+=row['count']*fy;probability_total+=row['count']*mp
            ece+=row['count']/n*abs(mp-fy)
        else: require(row['mean_probability'] is None and row['fraction_positive'] is None, 'Empty reference bin differs')
    require(count_total==n and abs(positive_total-int(y.sum())) <= 2e-12*n
            and abs(probability_total/n-float(np.mean(p))) <= numerical['probability_abs_tolerance']+2e-12
            and np.isfinite(raw['ece10']) and abs(ece-raw['ece10']) <= 2e-12,
            'Author reference calibration aggregate inconsistent')
    return {"status": "PASS", "canonical_metrics_and_sensitivities_reconstructed": True,
            "author_raw_class_metrics_reconstructed_from_disagreement_rows": True,
            "author_disagreements": len(records), "independent_disagreements": independent["counts"]["class_disagreements"],
            "limitation": "Author-reference full probabilities/logits are not stored; reference-near membership, raw clipping/BCE/Brier/calibration and native loss receive bounded consistency checks only. Independent oracle full probabilities/logits and diagnostics are separately reconstructed."}


def native_shape(y, p, z):
    return {'native_bce': metrics(y,p)['bce'] if z is None else native_logit_bce(y,z),
        'has_native_logits': z is not None, 'minimum_raw_probability': float(np.min(p)),
        'maximum_raw_probability': float(np.max(p)), 'minimum_native_logit': None if z is None else float(np.min(z)),
        'maximum_native_logit': None if z is None else float(np.max(z)),
        'clipped_wrong_prediction_count': int(np.sum(((p<1e-7)|(p>1-1e-7))&((p>=.5)!=y)))}


def check_native(y,p,z,recorded,author,numerical):
    actual=native_shape(y,p,z)
    canonical=compare_structure(actual,recorded)
    require(author['has_native_logits'] == (z is not None), 'Author native flag differs')
    if z is None:
        require(set(author)=={'has_native_logits'}, 'Legacy native verification schema differs')
    else:
        require(set(author)=={'has_native_logits','maximum_logit_error','independent_native_loss','native_loss_error'},
                'Author native verification schema differs')
        require(np.isfinite(author['maximum_logit_error']) and 0 <= author['maximum_logit_error'] <= numerical['independent_native_logit_abs_tolerance'],
                'Author logit error exceeds tolerance')
        loss=author['independent_native_loss'];error=author['native_loss_error']
        require(np.isfinite(loss) and loss>=0 and np.isfinite(error) and 0<=error<=numerical['independent_native_aggregate_loss_abs_tolerance']
                and abs(loss-actual['native_bce']) <= numerical['independent_native_aggregate_loss_abs_tolerance']
                and abs(abs(loss-recorded['native_bce'])-error)<=2e-12, 'Author native loss inconsistent')
    return {'status':'PASS','canonical':canonical,'author_reference_scope':'Reported native loss/error consistency only; full independent logits/loss replayed separately.'}


def check_class_quality(y, p, recorded):
    return compare_structure(class_quality(y,p), recorded)


def annulus_oracle_diagnostic(y, clean_y, label_flip):
    """Generator context after release, never a fitted model or selection input."""
    y, clean, flipped = np.asarray(y), np.asarray(clean_y), np.asarray(label_flip)
    require(clean.shape == y.shape and flipped.shape == y.shape and np.isin(clean,(0,1)).all()
            and flipped.dtype == np.bool_ and np.array_equal(y,clean ^ flipped.astype(np.int64)),
            "Invalid annulus noise provenance")
    known = np.asarray([.1 + .8*int(label) for label in clean],dtype=np.float64)
    return {"realized_flip_count":int(np.count_nonzero(flipped)),
            "realized_flip_fraction":int(np.count_nonzero(flipped))/len(y),
            "known_conditional_probability_metrics":metric_shape(y,known),
            "latent_decision_observed_accuracy":int(np.count_nonzero(clean==y))/len(y),
            "scope":"Analytic generator reference, not a learned/deployable arm. Expected Bayes observed-label accuracy is0.90; finite-sample realization may differ. No model reselection."}


def objective(method):
    return 'stable native logit BCE; derivative sigmoid(logit)-label, no clipping zero-gradient rule'


def forward_work(method,n):
    family=method.split('_')[0];quantum=family.startswith('q');legacy=family=='q2';frozen=family=='qfrozen'
    c=n if quantum else 0;moments=0 if legacy or not quantum else 1 if family=='qscalar' else 5
    hidden=32 if family=='mlp' else int(family[3]) if family.startswith('mlp') else 0
    return {'forward_circuit_examples':c,'shift_circuit_examples':0,'circuit_examples':c,'layer_applications':2*c,
        'feature_ry_gates':4*c,'feature_rz_gates':0,'trainable_ry_gates':0 if frozen else 4*c,
        'trainable_rz_gates':0 if frozen else 4*c,'cx_gates':2*c,'readout_ry_gates':c if legacy else 0,
        'fixed_core_ry_gates':4*c if frozen else 0,'fixed_core_rz_gates':4*c if frozen else 0,
        'bank_record_visits':n,'model_record_visits':n,'classical_forward_examples':0 if legacy else n,
        'classical_backward_examples':0,'trig_feature_values':25*n if family=='trig' else 0,
        'mlp_hidden_evaluations':n*hidden,'core_statevector_examples':c,'moment_values_computed':c*moments,
        'frozen_cached_feature_rows':0,'head_feature_values':n*moments,'measurement_settings_equivalent':c*(2 if moments==5 else 1)}
