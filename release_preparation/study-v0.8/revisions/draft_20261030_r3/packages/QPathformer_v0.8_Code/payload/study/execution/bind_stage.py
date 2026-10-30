"""Prepare immutable execution manifest; never approve or launch it."""
import argparse
from pathlib import Path
from durable import HERE, MANIFEST_SCHEMA, AUTHORIZATION_SCHEMA, binding, read, require, write_new, stage_jobs

EXECUTION_FILES = ["durable.py", "worker.py", "launcher.py", "process_identity.py",
                   "resource_probe.py", "bind_stage.py", "vendor/etel/core.py", "vendor/etel/__init__.py"]


def prepare(root, stage, interpreter, authorization, max_parallel, deadline, environment_path):
    root = Path(root).resolve()
    require(root == HERE.parent, "Manifest root must match this v0.8 execution copy")
    matrix, protocol = root/"governance/RUN_MATRIX.json", root/"governance/STUDY_PLAN.json"
    auth = read(authorization)
    require(auth.get("schema") == AUTHORIZATION_SCHEMA, "Scientific freeze schema mismatch")
    require(auth.get("review_status") == "approved_by_root", "Scientific freeze must be prepared first")
    require(auth.get("stage") == stage, "Authorization stage mismatch")
    numerical = read(environment_path)
    files = [root/"quantum"/name for name in auth["scientific_source_hashes"]]
    files += [HERE/name for name in EXECUTION_FILES]
    files += [root/"quantum/data/DATA_SEAL.json", Path(environment_path).resolve(),
              Path(numerical["openblas_dll"])]
    jobs = stage_jobs(read(matrix), stage)
    populations = {j["population_id"] for j in jobs}
    for pop in sorted(populations):
        files.extend([root/"quantum/data"/f"{pop}_{split}.npz" for split in ("train", "validation")])
        files.append(root/"quantum/data"/f"{pop}_router.json")
    return {"schema": MANIFEST_SCHEMA, "mode": "OFFICIAL_STUDY", "study_root": str(root),
            "stage": stage, "max_parallel_tasks": max_parallel, "deadline_seconds": deadline,
            "interpreter": binding(interpreter), "trainer": binding(root/"quantum/study.py"),
            "authorization": binding(authorization), "matrix": binding(matrix), "protocol": binding(protocol),
            "numerical_environment": numerical, "bindings": [binding(p) for p in files], "jobs": jobs}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--stage", choices=("engineering", "A", "B"), required=True)
    parser.add_argument("--interpreter", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--max-parallel", type=int, required=True)
    parser.add_argument("--deadline-seconds", type=float, required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_new(args.output, prepare(args.root, args.stage, args.interpreter, args.authorization,
                                  args.max_parallel, args.deadline_seconds, args.environment))
