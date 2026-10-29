"""Complete synthetic135-endpoint replay from an unchanged relocated package.

The subprocess executes the actual copied CLI with1600 synthetic records per
population. Python's audit hook rejects all open operations under the actual
working study outside the relocated package. This is a source/IO/statistics
fixture, not a training experiment or a scientific finding.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

from evidence_io import digest, inventory, require
from synthetic_fixture import make_fixture, write, HERE, REAL_STUDY


def tree_hashes(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in root.rglob('*') if p.is_file()}


def main():
    started = time.perf_counter()
    fixture = make_fixture(1600)
    attempt, original = fixture['attempt'], fixture['root']
    copied = attempt / 'relocated_package'
    print('SYNTHETIC relocation fixture: ' + str(attempt), flush=True)
    try:
        original_hashes = tree_hashes(original)
        shutil.copytree(original, copied)
        require(tree_hashes(copied) == original_hashes, 'Copied fixture differs before execution')
        wrapper = attempt / 'run_copied_cli_with_open_guard.py'
        wrapper.write_text('''import os, pathlib, runpy, sys
sys.dont_write_bytecode = True
copy = pathlib.Path(sys.argv[1]).resolve()
blocked_root = pathlib.Path(sys.argv[2]).resolve()
reads = {"copied": 0, "outside_study": 0, "blocked": 0}
def guard(event, args):
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path = pathlib.Path(os.fsdecode(args[0])).resolve()
        if path.is_relative_to(blocked_root) and not path.is_relative_to(copy):
            reads["blocked"] += 1
            raise RuntimeError("ORIGINAL-STUDY FILE ACCESS BLOCKED: " + str(path))
        reads["copied" if path.is_relative_to(copy) else "outside_study"] += 1
sys.addaudithook(guard)
here = copy / "analysis/independent_replay"
sys.path.insert(0, str(here))
sys.argv = [str(here / "replay_and_analyse.py"), "--release", str(copy / "quantum/EVALUATION_RELEASE.json"), "--output", str(here / "synthetic_relocated_replay")]
runpy.run_path(sys.argv[0], run_name="__main__")
print("OPEN_GUARD_COUNTS=" + repr(reads), flush=True)
if reads["blocked"] != 0 or reads["copied"] == 0:
    raise RuntimeError("Unexpected file access guard evidence")
''', encoding='utf-8')
        log = attempt / 'RELOCATED_CLI.log'
        env = os.environ.copy()
        env.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
        with log.open('x', encoding='utf-8') as handle:
            process = subprocess.run([sys.executable, '-B', str(wrapper), str(copied), str(REAL_STUDY)],
                                     cwd=copied, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=600, check=False)
        require(process.returncode == 0, 'Relocated actual CLI failed; preserve log: ' + str(log))
        replay = copied / 'analysis/independent_replay/synthetic_relocated_replay'
        commit = json.loads((replay / 'REPLAY_COMMIT.json').read_text())
        summary = json.loads((replay / 'summary.json').read_text())
        verified = inventory(replay, commit['files'], exclude=('REPLAY_COMMIT.json',))
        require(summary['status'] == 'PASS' and summary['prediction_pairs_replayed'] == 216000,
                'Incomplete full synthetic replay')
        require(tree_hashes(original) == original_hashes, 'Original fixture was changed')
        after = tree_hashes(copied)
        require({name: after[name] for name in original_hashes} == original_hashes, 'Copied evidence was rewritten')
        extra = set(after) - set(original_hashes)
        require(all(name.startswith('analysis/independent_replay/synthetic_relocated_replay/') for name in extra),
                'Unexpected copied-package mutation')
        evidence = {'status': 'PASS', 'synthetic_only': True, 'real_confirmation_outcomes_accessed': False,
                    'fixture_scope': 'Artificial metadata/checkpoints and1600 synthetic records per population; no training experiment claim.',
                    'current_source_hashes': fixture['source_hashes'], 'fixture_root': str(attempt),
                    'original_fixture_files_unchanged': len(original_hashes), 'copied_evidence_files_unchanged': len(original_hashes),
                    'registered_absolute_paths_retained': True, 'metadata_rewritten': False,
                    'guard': 'Actual copied CLI; every Python file open under real study outside relocated package raises. Zero blocked attempts required.',
                    'subprocess_exit_code': process.returncode, 'log_sha256': digest(log),
                    'summary_sha256': digest(replay / 'summary.json'), 'replay_commit_sha256': digest(replay / 'REPLAY_COMMIT.json'),
                    'verified_replay_inventory': verified, 'endpoint_count': summary['endpoint_count'],
                    'prediction_pairs_replayed': summary['prediction_pairs_replayed'], 'population_count': summary['population_count'],
                    'maximum_probability_error': summary['maximum_probability_error'],
                    'maximum_aggregate_bce_error': summary['maximum_aggregate_bce_error'],
                    'numerical_totals': summary['numerical_totals'],
                    'bootstrap_count_hashes': {name: value['statistics']['bootstrap_counts_sha256'] for name, value in summary['populations'].items()},
                    'elapsed_seconds': time.perf_counter() - started}
        write(attempt / 'PREFLIGHT_RESULT.json', evidence)
        write(HERE / 'RELOCATED_PREFLIGHT_RESULT.json', evidence)
        with (HERE / 'RELOCATED_PREFLIGHT_CLI.log').open('xb') as handle:
            handle.write(log.read_bytes())
        print(json.dumps(evidence, indent=2), flush=True)
        return evidence
    except BaseException as error:
        write(attempt / 'PREFLIGHT_FAILURE.json', {'status': 'FAIL', 'synthetic_only': True,
              'error': str(error), 'traceback': traceback.format_exc(), 'preserved': str(attempt)})
        raise


if __name__ == '__main__':
    main()
