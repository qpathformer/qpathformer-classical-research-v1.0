"""Bounded offline imports, CLI construction and tiny in-memory circuit check.

Writes only stdout. Invoke with -B; no official data, fitting or scoring is used.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[name]='1'
sys.path.insert(0,str(ROOT/'payload/study/quantum'))
import numpy as np
import scipy
import circuits,models,routers,reference_v03
x=np.array([[0.0,0.0],[0.1,-0.3]],dtype=np.float64)
bank=np.zeros((2,2,2),dtype=np.float64)
moments=circuits.moments(x,bank,count=5)
assert moments.shape==(2,5) and np.isfinite(moments).all()
assert np.all(np.abs(moments)<=1+1e-12)
np.testing.assert_allclose(models.sigmoid(np.array([-1.,0.,1.])),1/(1+np.exp(-np.array([-1.,0.,1.]))),rtol=1e-14,atol=1e-14)
commands=[]
for relative in ('payload/study/quantum/study.py','payload/study/execution/launcher.py','payload/study/execution/bind_stage.py'):
    command=[sys.executable,'-B',str(ROOT/relative),'--help']
    p=subprocess.run(command,cwd=ROOT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=40)
    assert p.returncode==0,(relative,p.stderr)
    assert 'usage:' in p.stdout.lower(),relative
    commands.append({'command':command,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
print(json.dumps({'status':'PASS','scope':'Imports of scientific modules; tiny in-memory 2-input circuit expectation and sigmoid checks; three CLI help paths.','python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'commands':commands,'not_verified':['No training','No official scoring','No shot sampling','No QPU or cloud jobs','No full reproduction','No dependency installation','No original archive verification by this startup helper']},indent=2))
