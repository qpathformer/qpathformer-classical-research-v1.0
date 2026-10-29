"""Internal v0.2 quantum mechanism study. Training never opens a test partition.

Official training requires a separately reviewed stage freeze. Engineering runs
are explicitly separate and are never eligible for candidate selection.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor"))
import numpy as np
from qpath import quantum, reference
from qpath.data import array_hash

METHODS = ("scheduled", "min_depth2", "untied_assigned", "untied_balanced",
           "untied_all_records", "fixed4", "mlp129", "mlp17", "mlp41",
           "min_depth2_mlp129")
CANDIDATES = ("min_depth2", "untied_assigned", "untied_balanced")
STAGE_A_METHODS = METHODS[:-1]
UNTIED = ("untied_assigned", "untied_balanced", "untied_all_records")
OFFSETS = (0, 4, 12, 24, 40)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def source_hashes():
    files = [ROOT / "qstudy.py", ROOT / "prepare_study.py", ROOT / "tests/test_v02.py",
             ROOT / "launch_stage.py", ROOT / "select_candidate.py"]
    files += sorted((ROOT / "vendor/qpath").glob("*.py"))
    return {str(p.relative_to(ROOT)): digest(p) for p in files}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_population(name, split):
    if split not in ("train", "validation"):
        raise ValueError("Training loader accepts only train/validation; test access is separate")
    path = ROOT / "data" / f"{name}_{split}.npz"
    manifest = read_json(ROOT / "data/DATA_SEAL.json")
    if digest(path) != manifest["files"][path.name]["sha256"]:
        raise ValueError(f"Population hash mismatch: {path}")
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    pred = p >= .5
    f1 = []
    for label in (0, 1):
        tp = np.sum((y == label) & (pred == label))
        fp = np.sum((y != label) & (pred == label))
        fn = np.sum((y == label) & (pred != label))
        f1.append(float(2*tp/(2*tp+fp+fn)) if 2*tp+fp+fn else 0.)
    return {"bce": quantum.binary_cross_entropy(y, p), "macro_f1": float(np.mean(f1)),
            "accuracy": float(np.mean(pred == y)), "n": len(y),
            "clipped": int(np.sum((p < quantum.CLIP) | (p > 1-quantum.CLIP))),
            "confusion": [[int(np.sum((y == a) & (pred == b))) for b in (0, 1)] for a in (0, 1)]}


def sigmoid(x):
    result = np.empty_like(x, dtype=float)
    positive = x >= 0
    result[positive] = 1 / (1 + np.exp(-x[positive]))
    exp = np.exp(x[~positive])
    result[~positive] = exp / (1 + exp)
    return result


class Model:
    def __init__(self, method, seed):
        if method not in METHODS:
            raise ValueError(method)
        self.method = method
        self.is_mlp = "mlp" in method
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, 1])))
        if self.is_mlp:
            n = int(method.split("mlp")[-1])
            self.hidden = {17: 2, 41: 5, 129: 16}[n]
            h = self.hidden
            a, b = np.sqrt(6/(6+h)), np.sqrt(6/(h+1))
            self.parameters = np.concatenate((rng.uniform(-a,a,6*h), np.zeros(h),
                                               rng.uniform(-b,b,h), [0.]))
        else:
            bank = rng.uniform(-.1,.1,(4,2,2))
            self.parameters = (np.concatenate([bank[:d].ravel() for d in range(1,5)])
                               if method in UNTIED else bank.ravel().copy())

    def effective_depth(self, depth):
        depth = np.asarray(depth)
        if self.method == "fixed4":
            return np.full_like(depth,4)
        if self.method.startswith("min_depth2"):
            return np.maximum(depth,2)
        return depth

    def bank(self, d):
        if self.method in UNTIED:
            return self.parameters[OFFSETS[d-1]:OFFSETS[d]].reshape(d,2,2)
        return self.parameters.reshape(4,2,2)

    def features(self, x, depth):
        return np.column_stack((x, np.eye(4)[self.effective_depth(depth)-1]))

    def unpack(self):
        h, p = self.hidden, self.parameters
        return p[:6*h].reshape(6,h), p[6*h:7*h], p[7*h:8*h], p[-1]

    def predict(self, x, depth):
        if self.is_mlp:
            f = self.features(x,depth)
            a,b,c,d = self.unpack()
            return sigmoid(np.maximum(f@a+b,0)@c+d)
        depth = self.effective_depth(depth)
        if self.method not in UNTIED:
            return quantum.predict_proba(x,self.bank(4),depth)
        p = np.empty(len(x))
        for d in range(1,5):
            chosen = np.flatnonzero(depth == d)
            if len(chosen):
                p[chosen] = quantum.predict_proba(x[chosen],self.bank(d),d)
        return p

    def gradient(self, x, y, depth):
        """Mean loss over these exact rows; return loss, gradient, p, work."""
        if self.is_mlp:
            f = self.features(x,depth)
            a,b,c,d = self.unpack()
            z = f@a+b
            act = np.maximum(z,0)
            p = sigmoid(act@c+d)
            g = (p-y)/len(y)
            g[(p < quantum.CLIP) | (p > 1-quantum.CLIP)] = 0
            g1 = g[:,None]*c[None,:]*(z > 0)
            grad = np.concatenate(((f.T@g1).ravel(),g1.sum(0),act.T@g,[g.sum()]))
            return quantum.binary_cross_entropy(y,p),grad,p,{"circuit_examples":0,"layer_applications":0}
        depth = self.effective_depth(depth)
        if self.method not in UNTIED:
            loss,g,p,count = quantum.loss_gradient(x,y,self.bank(4),depth)
            work = {"circuit_examples":count,"layer_applications":int(np.sum(depth*(1+8*depth)))}
            return loss,g.ravel(),p,work
        grad, p = np.zeros_like(self.parameters),np.empty(len(y))
        count = 0
        for d in range(1,5):
            chosen = np.flatnonzero(depth == d)
            if len(chosen):
                loss,g,pd,work = quantum.loss_gradient(x[chosen],y[chosen],self.bank(d),d)
                # Original mixture objective: sum(group loss * group fraction).
                grad[OFFSETS[d-1]:OFFSETS[d]] = g.ravel()*len(chosen)/len(y)
                p[chosen] = pd
                count += work
        return quantum.binary_cross_entropy(y,p),grad,p,{
            "circuit_examples":count,"layer_applications":int(np.sum(depth*(1+8*depth)))}


class CyclicSampler:
    """Repeated permutations of one fixed subset; never adds new record IDs."""
    def __init__(self, indices, seed, depth):
        self.indices = np.asarray(indices)
        if not len(self.indices):
            raise ValueError("Every depth group must contain training rows")
        self.rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,3,depth])))
        self.queue = np.empty(0,dtype=int)
        self.position = 0

    def draw(self,n):
        result = []
        while n:
            if self.position == len(self.queue):
                self.queue = self.rng.permutation(self.indices)
                self.position = 0
            take = min(n,len(self.queue)-self.position)
            result.extend(self.queue[self.position:self.position+take])
            self.position += take
            n -= take
        return np.asarray(result,dtype=int)


def expanded_gradient(model, train, batch, samplers, weights):
    """64 rows per bank, same global update count; 4x record visits."""
    gradient = np.zeros(40)
    total_loss, clips, count, layer_work = 0.,0,0,0
    observed = []
    for d in range(1,5):
        ids = samplers[d].draw(len(batch)) if model.method == "untied_balanced" else batch
        loss,g,p,c = quantum.loss_gradient(train["x"][ids],train["y"][ids],model.bank(d),d)
        gradient[OFFSETS[d-1]:OFFSETS[d]] = g.ravel()*weights[d-1]
        total_loss += loss*weights[d-1]
        clips += int(np.sum((p < quantum.CLIP) | (p > 1-quantum.CLIP)))
        count += c
        layer_work += len(ids)*d*(1+8*d)
        observed.append(ids)
    return total_loss,gradient,clips,{"circuit_examples":count,"layer_applications":layer_work},observed


def verify_freeze(stage,seed,method):
    path = ROOT / f"STAGE_{stage}_FREEZE.json"
    if not path.is_file():
        raise RuntimeError("Official training is prohibited without the independently reviewed stage freeze")
    freeze = read_json(path)
    if freeze.get("review_status") != "approved_by_root":
        raise RuntimeError("Independent approval field missing")
    if seed not in freeze["training_seeds"] or method not in freeze["methods"]:
        raise ValueError("Unregistered seed/method")
    if freeze["source_hashes"] != source_hashes():
        raise RuntimeError("Frozen training source changed")
    if freeze["data_seal_sha256"] != digest(ROOT / "data/DATA_SEAL.json"):
        raise RuntimeError("Frozen data seal changed")
    return freeze


def save_checkpoint(path,model,opt,round_number):
    np.savez(path,parameters=model.parameters,adam_m=opt.m,adam_v=opt.v,
             adam_t=opt.t,round=round_number)


def save_predictions(path,population,p):
    with Path(path).open("w",newline="",encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("record_id","original_depth","label","probability","prediction"))
        writer.writerows(zip(population["ids"],population["depth"],population["y"],p,(p >= .5).astype(int)))


def train(method,seed,stage,output,rounds=200,limit=None,engineering=False):
    if output.exists():
        raise FileExistsError("Output exists; preserve earlier runs and failures")
    freeze = None if engineering else verify_freeze(stage,seed,method)
    if not engineering and (rounds != 200 or limit is not None):
        raise ValueError("Official runs require 200 rounds and all 4,800 records")
    dataset = "engineering" if engineering else ("development" if stage == "A" else "confirmation")
    train_data = load_population(dataset,"train")
    validation = load_population(dataset,"validation")
    if limit is not None:
        train_data = {key:value[:limit] for key,value in train_data.items()}
        validation = {key:value[:min(160,len(value))] for key,value in validation.items()}
    output.mkdir(parents=True)
    config = {"classification":"INTERNAL - NOT FOR PUBLICATION", "stage":stage,"engineering":engineering,
              "dataset":dataset,"method":method,"seed":seed,"rounds":rounds,"batch_size":64,
              "train_records":len(train_data["y"]),"validation_records":len(validation["y"]),
              "test_accessed":False,"started_utc":now(),"source_hashes":source_hashes(),
              "data_seal_sha256":digest(ROOT/"data/DATA_SEAL.json"),
              "stage_freeze_sha256":digest(ROOT/f"STAGE_{stage}_FREEZE.json") if freeze else None,
              "environment":{"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),
                             "executable":sys.executable,"threads":{k:os.getenv(k) for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")}},
              "optimizer":{"name":"Adam","lr":.01,"betas":[.9,.999],"epsilon":1e-8,"weight_decay":0},
              "selection":"lowest full validation BCE across 200 rounds, earliest exact tie"}
    write_json(output/"config.json",config)
    model = Model(method,seed)
    opt = quantum.Adam(model.parameters.shape)
    initial = model.parameters.copy()
    np.savez(output/"initial_state.npz",parameters=initial)
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,2])))
    groups = {d:np.flatnonzero(train_data["depth"] == d) for d in range(1,5)}
    weights = np.asarray([len(groups[d])/len(train_data["y"]) for d in range(1,5)])
    samplers = {d:CyclicSampler(groups[d],seed,d) for d in range(1,5)}
    orders, expanded_orders, gradient_means = [],[],[]
    work = {"training_circuit_examples":0,"training_layer_applications":0,
            "validation_circuit_examples":0,"validation_layer_applications":0,
            "training_record_visits":0,"training_clipped_probabilities":0}
    layer_exposure = np.zeros(4,dtype=np.int64)
    bank_visits = np.zeros(4,dtype=np.int64)
    nonempty_depth_batches = np.zeros(4,dtype=np.int64)
    best,selected_round,selected = float("inf"),None,None
    start = time.perf_counter()
    r = 0
    try:
        with (output/"ledger.jsonl").open("w",encoding="utf-8") as ledger:
            for r in range(1,rounds+1):
                order = rng.permutation(len(train_data["y"]))
                orders.append(order)
                total_loss,grad_norm_sum,grad_norm_max = 0.,0.,0.
                gradient_sum = np.zeros_like(model.parameters)
                round_expanded = []
                batches = 0
                for off in range(0,len(order),64):
                    ids = order[off:off+64]
                    if method in ("untied_balanced","untied_all_records"):
                        loss,g,clips,w,observed = expanded_gradient(model,train_data,ids,samplers,weights)
                        bank_visits += len(ids)
                        nonempty_depth_batches += 1
                        layer_exposure += len(ids)*np.arange(4,0,-1)
                        work["training_record_visits"] += 4*len(ids)
                        if method == "untied_balanced":
                            round_expanded.extend(np.stack(observed,axis=1).tolist())
                    else:
                        loss,g,p,w = model.gradient(train_data["x"][ids],train_data["y"][ids],train_data["depth"][ids])
                        clips = int(np.sum((p < quantum.CLIP) | (p > 1-quantum.CLIP)))
                        effective = model.effective_depth(train_data["depth"][ids])
                        if not model.is_mlp:
                            layer_exposure += [np.sum(effective >= d) for d in range(1,5)]
                            bank_visits += [np.sum(effective == d) for d in range(1,5)]
                            nonempty_depth_batches += [np.any(effective == d) for d in range(1,5)]
                        work["training_record_visits"] += len(ids)
                    if not np.isfinite(g).all() or not np.isfinite(loss):
                        raise FloatingPointError("Nonfinite gradient or loss")
                    norm = float(np.linalg.norm(g))
                    grad_norm_sum += norm
                    grad_norm_max = max(norm,grad_norm_max)
                    gradient_sum += g
                    batches += 1
                    opt.step(model.parameters,g)
                    total_loss += loss*len(ids)
                    work["training_circuit_examples"] += w["circuit_examples"]
                    work["training_layer_applications"] += w["layer_applications"]
                    work["training_clipped_probabilities"] += clips
                if method == "untied_balanced":
                    expanded_orders.append(np.asarray(round_expanded,dtype=np.int32))
                gradient_means.append(gradient_sum/batches)
                p = model.predict(validation["x"],validation["depth"])
                vm = metrics(validation["y"],p)
                if not model.is_mlp:
                    work["validation_circuit_examples"] += len(p)
                    work["validation_layer_applications"] += int(np.sum(model.effective_depth(validation["depth"])))
                is_best = vm["bce"] < best
                if is_best:
                    best,selected_round,selected = vm["bce"],r,model.parameters.copy()
                    save_checkpoint(output/"selected_checkpoint.npz",model,opt,r)
                row = {"round":r,"optimizer_updates":opt.t,"training_loss":total_loss/len(order),
                       "validation":vm,"selected":is_best,"mean_batch_gradient_norm":grad_norm_sum/batches,
                       "maximum_batch_gradient_norm":grad_norm_max,"work_cumulative":dict(work),
                       "elapsed_seconds":time.perf_counter()-start}
                ledger.write(json.dumps(row,allow_nan=False)+"\n")
                ledger.flush()
                write_json(output/"status.json",{"status":"running","round":r,"seed":seed,"method":method})
        training_seconds = time.perf_counter()-start
        save_checkpoint(output/"last_checkpoint.npz",model,opt,rounds)
        np.savez_compressed(output/"record_orders.npz",orders=np.asarray(orders,dtype=np.int32),record_ids=train_data["ids"])
        if expanded_orders:
            np.savez_compressed(output/"expanded_record_orders.npz",orders=np.asarray(expanded_orders),record_ids=train_data["ids"])
        np.savez(output/"epoch_gradient_means.npz",gradients=np.asarray(gradient_means))
        model.parameters[:] = selected
        p = model.predict(validation["x"],validation["depth"])
        work["selected_validation_replay_circuit_examples"] = 0 if model.is_mlp else len(p)
        work["selected_validation_replay_layer_applications"] = 0 if model.is_mlp else int(np.sum(model.effective_depth(validation["depth"])))
        save_predictions(output/"validation_predictions.csv",validation,p)
        diag = selected_training_diagnostics(model,train_data,output)
        result = {"status":"completed","method":method,"seed":seed,"stage":stage,"engineering":engineering,
                  "selected_round":selected_round,"selected_validation":metrics(validation["y"],p),
                  "completed_rounds":rounds,"optimizer_global_updates":opt.t,
                  "parameter_count":int(model.parameters.size),"training_seconds":training_seconds,
                  "total_seconds":time.perf_counter()-start,"work":work,
                  "layer_training_record_exposure":layer_exposure.tolist(),
                  "executed_depth_training_record_visits":bank_visits.tolist(),
                  "nonempty_executed_depth_batches":nonempty_depth_batches.tolist(),
                  "training_depth_population_weights":weights.tolist(),"diagnostics":diag,
                  "selected_checkpoint_sha256":digest(output/"selected_checkpoint.npz"),
                  "data_seal_sha256":config["data_seal_sha256"],"stage_freeze_sha256":config["stage_freeze_sha256"],
                  "test_accessed":False,"finished_utc":now()}
        write_json(output/"result.json",result)
        write_json(output/"status.json",{"status":"completed","round":rounds,"seed":seed,"method":method})
        return result
    except BaseException as exc:
        failure = {"status":"failed","method":method,"seed":seed,"utc":now(),"error":str(exc),
                   "type":type(exc).__name__,"traceback":traceback.format_exc()}
        save_checkpoint(output/"failed_checkpoint.npz",model,opt,r)
        write_json(output/"failure.json",failure)
        write_json(output/"status.json",failure)
        raise


def selected_training_diagnostics(model,train_data,output):
    gradients,counts,losses,clipped = [],[],[],[]
    total_work = {"circuit_examples":0,"layer_applications":0,"record_visits":len(train_data["y"])}
    for d in range(1,5):
        ids = np.flatnonzero(train_data["depth"] == d)
        loss,g,p,work = model.gradient(train_data["x"][ids],train_data["y"][ids],train_data["depth"][ids])
        gradients.append(g)
        counts.append(len(ids))
        losses.append(loss)
        clipped.append(int(np.sum((p < quantum.CLIP) | (p > 1-quantum.CLIP))))
        total_work["circuit_examples"] += work["circuit_examples"]
        total_work["layer_applications"] += work["layer_applications"]
    np.savez(output/"selected_training_gradients_by_depth.npz",gradients=np.asarray(gradients),
             counts=np.asarray(counts),original_depths=np.arange(1,5))
    cosines = []
    if model.method in ("scheduled","min_depth2","fixed4"):
        for a in range(1,5):
            for b in range(a+1,5):
                n = int(min(model.effective_depth(np.asarray([a]))[0],model.effective_depth(np.asarray([b]))[0]))*4
                ga,gb = gradients[a-1][:n],gradients[b-1][:n]
                denom = np.linalg.norm(ga)*np.linalg.norm(gb)
                cosines.append({"depths":[a,b],"common_coordinates":n,"cosine":float(ga@gb/denom) if denom else None})
    return {"population":"all training records grouped by original assigned depth",
            "losses":losses,"gradient_norms":[float(np.linalg.norm(g)) for g in gradients],
            "clipped_probabilities":clipped,"common_prefix_cosines":cosines,
            "work_separate_from_training":total_work,
            "interpretation":"Prespecified local raw gradient diagnostic, not Adam update direction or causal attribution"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",choices=("A","B"),default="A")
    parser.add_argument("--method",choices=METHODS,required=True)
    parser.add_argument("--seed",type=int,required=True)
    parser.add_argument("--engineering",action="store_true")
    parser.add_argument("--rounds",type=int,default=200)
    parser.add_argument("--train-limit",type=int)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    result = train(args.method,args.seed,args.stage,args.output,args.rounds,args.train_limit,args.engineering)
    print(json.dumps({k:result[k] for k in ("status","method","seed","selected_round","selected_validation","training_seconds")}))


if __name__ == "__main__":
    main()
