"""v0.9 fixed geometric routing and train-only Banknote preprocessing."""
from __future__ import annotations
import hashlib
import numpy as np
K=5
RESTARTS=20
MAX_ITER=500

def canonical_features(x):
    a = np.asarray(x, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] != 2 or not np.isfinite(a).all():
        raise ValueError("Expected finite [N,2] numeric input features")
    a = np.array(a, dtype="<f8", order="C", copy=True)
    a[a == 0] = 0.0
    return a


def feature_keys(x):
    return [row.tobytes() for row in canonical_features(x)]


def _distance(x, centers):
    distance = np.sum((x[:, None, :] - centers[None, :, :]) ** 2, axis=2)
    if not np.isfinite(distance).all():
        raise ValueError("Feature magnitude overflows squared Euclidean distance")
    return distance


def _canonical_order(centers):
    return np.lexsort((centers[:, 1], centers[:, 0]))


def _initial_centers(x, rng):
    chosen = [int(rng.integers(len(x)))]
    nearest = _distance(x, x[chosen])[:, 0]
    for _ in range(1, K):
        total = float(nearest.sum())
        if total <= 0:
            raise ValueError("Insufficient distinct coordinates for k-means++")
        cumulative = np.cumsum(nearest)
        index = min(int(np.searchsorted(cumulative, float(rng.random()) * total, side="right")), len(x) - 1)
        if index in chosen:
            positive = np.flatnonzero(nearest > 0)
            index = int(positive[0])
        chosen.append(index)
        nearest = np.minimum(nearest, _distance(x, x[[index]])[:, 0])
    return x[chosen].copy()


def _lloyd(x, initial, max_iter=MAX_ITER):
    centers = initial[_canonical_order(initial)].copy()
    for iteration in range(1, max_iter + 1):
        distances = _distance(x, centers)
        labels = distances.argmin(axis=1)
        counts = np.bincount(labels, minlength=K)
        updated = centers.copy()
        for bank in range(K):
            if counts[bank]:
                updated[bank] = x[labels == bank].mean(axis=0)
        # Sorted x makes the first index a lexicographic coordinate tie break.
        residual = distances[np.arange(len(x)), labels]
        candidates = np.argsort(-residual, kind="stable")
        used = set()
        for bank in np.flatnonzero(counts == 0):
            index = next(int(i) for i in candidates if int(i) not in used)
            used.add(index)
            updated[bank] = x[index]
        updated = updated[_canonical_order(updated)]
        new_labels = _distance(x, updated).argmin(axis=1)
        centers = updated
        if np.array_equal(new_labels, labels) and np.all(counts > 0):
            centers = centers[_canonical_order(centers)]
            labels = _distance(x, centers).argmin(axis=1)
            return centers, labels, iteration, True
    centers = centers[_canonical_order(centers)]
    labels = _distance(x, centers).argmin(axis=1)
    return centers, labels, max_iter, False


def residual_raw(x):
    a=canonical_features(x)
    return np.column_stack([a[:,0]**(degree-k)*a[:,1]**k for degree in (2,3,4) for k in range(degree+1)])


def fit_route_policy(x,seed,hash_salt=None):
    """Inherited 20-restart k-means, with train-only temperature/residual scales."""
    a=canonical_features(x)
    if len(set(feature_keys(a)))<K or int(seed)<0:raise ValueError('At least five unique training coordinates and nonnegative seed required')
    ordered=a[np.lexsort((a[:,1],a[:,0]))]
    candidates=[];records=[]
    for restart in range(RESTARTS):
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([int(seed),restart])))
        centers,labels,iterations,converged=_lloyd(ordered,_initial_centers(ordered,rng))
        inertia=float(np.sum((ordered-centers[labels])**2));counts=np.bincount(labels,minlength=K)
        eligible=bool(converged and np.all(counts>0))
        records.append({'restart':restart,'iterations':iterations,'converged':converged,'eligible':eligible,'inertia':inertia,'counts':counts.tolist()})
        if eligible:candidates.append((inertia,tuple(centers.ravel()),restart,centers,counts))
    if not candidates:raise RuntimeError('No nonempty converged k-means candidate')
    inertia,_,restart,centers,counts=min(candidates,key=lambda c:c[:3])
    d=np.sort(_distance(a,centers),axis=1)
    policy={'schema':'qpath-v09-input-route-1','banks':K,'seed':int(seed),'centroids':centers.tolist(),'tau':float(max(.001,np.median(d[:,1]-d[:,0]))),'residual_scale':np.maximum(1,np.max(np.abs(residual_raw(a)),axis=0)).tolist(),'training_n':len(a),'training_ordered_features_sha256':hashlib.sha256(a.tobytes()).hexdigest(),'training_feature_set_sha256':hashlib.sha256(ordered.tobytes()).hexdigest(),'centroid_order':'lexicographic x0 then x1','kmeans':{'initialization':'k-means++','restarts':RESTARTS,'max_iterations':MAX_ITER,'selected_restart':restart,'selected_inertia':inertia,'restart_records':records,'selection':'minimum eligible inertia; ties center tuple then restart','distance_ties':'lowest canonical center index','empty_cluster':'farthest assigned input with canonical coordinate tie order'},'kmeans_training_counts':counts.tolist(),'fit_scope':'training coordinates only; no labels, IDs or held-out records','preprocessing':{'kind':'identity2'}}
    policy['margin_bins']=fit_margin_bins(a,policy)
    return policy


def validate_policy(policy):
    if policy.get('schema')!='qpath-v09-input-route-1' or policy.get('banks')!=5:raise ValueError('Unsupported router')
    centers=canonical_features(policy['centroids'])
    if centers.shape!=(5,2) or not np.array_equal(_canonical_order(centers),np.arange(5)):raise ValueError('Invalid center order')
    if not np.isfinite(policy['tau']) or policy['tau']<.001:raise ValueError('Invalid fixed temperature')
    return centers


def route(x,policy,kind='kmeans'):
    if kind!='kmeans':raise ValueError('v0.9 has only geometric routing')
    return _distance(canonical_features(x),validate_policy(policy)).argmin(axis=1).astype(np.int64)


def geometric_scores(x,policy):
    return -_distance(canonical_features(x),validate_policy(policy))/float(policy['tau'])


def soft_weights(x,policy):
    score=geometric_scores(x,policy);score-=score.max(axis=1,keepdims=True)
    q=np.exp(score);return q/q.sum(axis=1,keepdims=True)


def residual_features(x,policy):
    scale=np.asarray(policy['residual_scale'],dtype=np.float64)
    if scale.shape!=(12,) or not np.isfinite(scale).all() or (scale<1).any():raise ValueError('Invalid frozen residual scale')
    return residual_raw(x)/scale


def geometric_margin(x,policy):
    d=np.sort(_distance(canonical_features(x),validate_policy(policy)),axis=1)
    return d[:,1]-d[:,0]


def fit_margin_bins(training_x,policy):
    raw=np.quantile(geometric_margin(training_x,policy),[0,.1,.25,.5,1],method='linear');edges=np.unique(raw)
    return {'schema':'qpath-v09-fixed-margin-bins-1','quantiles':[0,.1,.25,.5,1],'quantile_method':'linear','raw_edges':raw.tolist(),'unique_edges':edges.tolist(),'bins':max(1,len(edges)-1),'fit_scope':'training coordinates and frozen geometry only'}


def margin_bins(x,policy,bins=None):
    bins=policy['margin_bins'] if bins is None else bins
    if bins['schema']!='qpath-v09-fixed-margin-bins-1':raise ValueError('Unsupported boundary bins')
    edges=np.asarray(bins['unique_edges'],dtype=np.float64)
    if edges.ndim!=1 or len(edges)<1 or not np.isfinite(edges).all() or (np.diff(edges)<=0).any():raise ValueError('Invalid boundary edges')
    return np.searchsorted(edges[1:-1],geometric_margin(x,policy),side='right').astype(np.int64)


def fit_preprocessing(raw_training_x):
    a=np.asarray(raw_training_x,dtype=np.float64)
    if a.ndim!=2 or a.shape[1]!=4 or len(a)<5 or not np.isfinite(a).all():raise ValueError('Expected finite training[N,4]')
    mean=a.mean(axis=0);std=a.std(axis=0,ddof=0);std=np.where(std>0,std,1.)
    z=(a-mean)/std
    center=z.mean(axis=0)
    _,s,vt=np.linalg.svd(z-center,full_matrices=False)
    components=vt[:2].copy()
    for row in components:
        j=int(np.argmax(np.abs(row)))
        if row[j]<0:row*=-1
    pcs=(z-center)@components.T;pcmean=pcs.mean(axis=0);pcstd=pcs.std(axis=0,ddof=0);pcstd=np.where(pcstd>0,pcstd,1.)
    total=float(np.sum(s*s))
    return {'kind':'banknote_standardize_pca2_standardize_arctan','input_features':4,'output_features':2,'training_n':len(a),'mean4':mean.tolist(),'scale4':std.tolist(),'pca_center4':center.tolist(),'components2x4':components.tolist(),'pc_mean2':pcmean.tolist(),'pc_scale2':pcstd.tolist(),'retained_variance':float(np.sum(s[:2]**2)/total) if total else 0.,'retained_variance_by_component':(s[:2]**2/total).tolist() if total else [0.,0.],'svd_sign_rule':'largest absolute loading positive; lowest index breaks ties','std_ddof':0,'constant_feature_scale':1.,'bounding':'(2/pi)*arctan(z)','fit_scope':'training raw four features only'}


def preprocess(raw_x,policy,dimensions=2):
    prep=policy.get('preprocessing',policy)
    if prep['kind']=='identity2':
        if dimensions!=2:raise ValueError('Synthetic data are two-dimensional')
        return canonical_features(raw_x)
    a=np.asarray(raw_x,dtype=np.float64)
    if a.ndim!=2 or a.shape[1]!=4 or not np.isfinite(a).all():raise ValueError('Expected finite raw[N,4]')
    z=(a-np.asarray(prep['mean4']))/np.asarray(prep['scale4'])
    if dimensions==4:return (2/np.pi)*np.arctan(z)
    if dimensions!=2:raise ValueError('Only two or four coordinates supported')
    pc=(z-np.asarray(prep['pca_center4']))@np.asarray(prep['components2x4']).T
    return (2/np.pi)*np.arctan((pc-np.asarray(prep['pc_mean2']))/np.asarray(prep['pc_scale2']))


