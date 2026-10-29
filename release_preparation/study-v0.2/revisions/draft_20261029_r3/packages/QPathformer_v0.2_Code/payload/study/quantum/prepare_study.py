"""Prepare disjoint deterministic data partitions before development training.

Sealed test arrays are written and hashed, never evaluated here. The seal is a
protocol/access boundary, not encryption. Training loaders cannot open tests.
"""
from pathlib import Path
import json
import numpy as np
from qstudy import ROOT, now, write_json, digest
from qpath.data import _allocate, array_hash

DATASETS = {"development":(12017,12023,12029),
            "confirmation":(22017,22023,22029),
            "engineering":(32017,32023,32029)}


def generate(seeds):
    features,classes_seed,split_seed = seeds
    x = np.random.Generator(np.random.PCG64(features)).uniform(-1,1,(8000,2))
    y = (np.sum(x*x,axis=1) < 2/np.pi).astype(np.int64)
    classes = np.random.Generator(np.random.PCG64(classes_seed)).integers(1,9,8000)
    depth = 5-(classes+1)//2
    rng = np.random.Generator(np.random.PCG64(split_seed))
    groups = [rng.permutation(np.flatnonzero((y == label) & (classes == c)))
              for label in (0,1) for c in range(1,9)]
    counts = [len(g) for g in groups]
    tn,vn = _allocate(counts,.6,4800),_allocate(counts,.2,1600)
    splits = {s:[] for s in ("train","validation","test")}
    for ids,n,m in zip(groups,tn,vn):
        splits["train"].extend(ids[:n])
        splits["validation"].extend(ids[n:n+m])
        splits["test"].extend(ids[n+m:])
    result = {}
    for name,ids in splits.items():
        ids = rng.permutation(np.asarray(ids,dtype=np.int64))
        result[name] = {"x":x[ids],"y":y[ids],"classes":classes[ids],"depth":depth[ids],"ids":ids}
    return result


def main():
    folder = ROOT/"data"
    folder.mkdir(exist_ok=False)
    seal = {"created_utc":now(),"status":"sealed before official development",
            "visibility":"INTERNAL - NOT FOR PUBLICATION", "outcomes_evaluated":False,
            "generator":"NumPy PCG64","numpy_version":np.__version__,
            "rule":"y=sum(x**2)<2/pi; x uniform[-1,1]^2; independent classes uniform1..8; depth4,4,3,3,2,2,1,1",
            "split":"label-by-class stratified largest remainders 4800/1600/1600; unique records across partitions",
            "datasets":{},"files":{},
            "seal_limitation":"Protocol and loader boundary, not encryption; test labels computed only for generation/stratification, never model evaluation"}
    for name,seeds in DATASETS.items():
        populations = generate(seeds)
        seal["datasets"][name] = {"seeds":{"features":seeds[0],"classes":seeds[1],"split":seeds[2]},
                                   "counts":{s:len(p["y"]) for s,p in populations.items()}}
        for split,data in populations.items():
            filename = f"{name}_{'SEALED_test' if split == 'test' else split}.npz"
            path = folder/filename
            np.savez(path,**data)
            seal["files"][filename] = {"sha256":digest(path),"arrays":{k:array_hash(v) for k,v in data.items()},
                                       "n":len(data["y"]),"dataset":name,"split":split}
    write_json(folder/"DATA_SEAL.json",seal)
    print("Prepared and sealed populations; no model outcome evaluated")


if __name__ == "__main__":
    main()
