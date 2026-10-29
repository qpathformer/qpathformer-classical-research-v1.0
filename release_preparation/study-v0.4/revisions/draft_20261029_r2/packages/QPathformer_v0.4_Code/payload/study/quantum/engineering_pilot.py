"""Explicit engineering-only 3-round pilot; never an official experiment."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
import argparse
from pathlib import Path
import time
import study


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(exist_ok=False,parents=True);rows=[];start=time.perf_counter()
    for population in study.ENGINEERING:
        for method in study.METHODS:
            r=study.train(method,9701,'A',population,a.output/population/'seed_9701'/method,rounds=3,engineering=True)
            row={'population':population,'method':method,'rounds':3,'updates':225,'training_seconds':r['training_seconds'],
                 'projected_full_training_seconds_linear':r['training_seconds']*200/3,'endpoint_total_seconds':r['endpoint_total_seconds']}
            rows.append(row);study.write_json(a.output/'progress.json',rows);print(row,flush=True)
    study.write_json(a.output/'PILOT_COMPLETE.json',{'status':'completed','scope':'Engineering train/validation only; 18 reduced endpoints, no official or test outcomes',
          'rows':rows,'elapsed_seconds':time.perf_counter()-start,'source_hashes':study.source_hashes(),'finished_utc':study.now()},True)


if __name__=='__main__':main()
