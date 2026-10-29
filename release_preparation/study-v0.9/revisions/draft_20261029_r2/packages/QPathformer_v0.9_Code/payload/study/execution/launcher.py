"""Root-gated command line for Q-Path Multiplier (ETEL); no implicit approval."""
import argparse
import json
from pathlib import Path
from durable import (current_attempts, new_attempt, read, reconcile, request_cancel, run_stage,
                     validate_manifest, status_summary, request_drain, clear_drain)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--manifest", required=True)
    run.add_argument("--release", required=True)
    status = sub.add_parser("status")
    status.add_argument("--root", required=True)
    status.add_argument("--reconcile", action="store_true", help="Explicitly verify payloads and reconcile dead workers")
    drain = sub.add_parser("drain", help="Finish active fits and admit no new fits")
    drain.add_argument("--root", required=True)
    drain.add_argument("--reason", required=True)
    resume = sub.add_parser("resume", help="Clear drain after root usage review; does not launch")
    resume.add_argument("--root", required=True)
    resume.add_argument("--approval", required=True)
    cancel = sub.add_parser("cancel")
    cancel.add_argument("--root", required=True)
    cancel.add_argument("--attempt", required=True)
    cancel.add_argument("--reason", required=True)
    recover = sub.add_parser("recover")
    recover.add_argument("--manifest", required=True)
    recover.add_argument("--release", required=True)
    recover.add_argument("--job-id", required=True)
    recover.add_argument("--approval", required=True)
    args = parser.parse_args()
    if args.command == "run":
        result = run_stage(args.manifest, args.release)
    elif args.command == "status":
        result = ({"attempts": [reconcile(args.root, row) for row in current_attempts(args.root)]}
                  if args.reconcile else status_summary(args.root))
    elif args.command == "drain":
        result = request_drain(args.root, args.reason)
    elif args.command == "resume":
        result = clear_drain(args.root, args.approval)
    elif args.command == "cancel":
        request_cancel(args.root, args.attempt, args.reason)
        result = {"status": "cancellation_requested", "attempt": args.attempt}
    else:
        manifest, _ = validate_manifest(args.manifest, args.release)
        matches = [j for j in manifest["jobs"] if j["run_id"] == args.job_id]
        if len(matches) != 1:
            raise RuntimeError("Recovery job not registered exactly once")
        result = new_attempt(manifest["study_root"], args.manifest, args.release, matches[0], args.approval)
    print(json.dumps(result, indent=2))
    return 1 if result.get("status") == "failures_present" else 20 if result.get("status") == "drained" else 0


if __name__ == "__main__":
    raise SystemExit(main())
