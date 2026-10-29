"""Bounded offline package startup. No training, scoring, shots or QPU submission."""
import argparse,ast,hashlib,json,os,platform,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output).resolve()
    if out.is_relative_to(ROOT.resolve()):raise ValueError('Receipt must be outside the entire package')
    if out.exists():raise FileExistsError('Preserve existing receipts')
    checks=[]
    for f in ROOT.rglob('*.py'):ast.parse(f.read_text('utf-8-sig'),filename=str(f))
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1');env.pop('PYTHONOPTIMIZE',None)
    def run(label,args,cwd):
        r=subprocess.run([sys.executable,'-B',*args],cwd=cwd,env=env,capture_output=True,text=True,timeout=90)
        checks.append(dict(label=label,command=[sys.executable,'-B',*args],cwd=str(cwd),returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
        return r.returncode==0
    q=ROOT/'payload/study/quantum'
    ok=run('numeric imports and in-memory predictions',['-c','import json, numpy as np; import qstudy as s\nx=np.array([[0.,0.],[.1,-.3],[-.6,.7],[.9,.9]]); d=np.array([1,2,3,4]); route=np.array([0,1,2,3]); counts={}\nfor method in s.METHODS:\n m=s.Model(method,902); p=m.predict(x,d,route); assert p.shape==(4,) and np.isfinite(p).all() and ((p>=0)&(p<=1)).all(); counts[method]=len(m.parameters)\nprint(json.dumps({"model_parameter_counts":counts,"finite_in_memory_predictions":True}))'],q)
    ok=run('training CLI argument help',['qstudy.py','--help'],q) and ok
    ok=run('independent matrix or initialization invariant',['-m','unittest','test_models.ModelChecks.test_all_circuit_arm_predictions_against_matrix_oracle'],q/'tests') and ok
    if (ROOT/'payload/study/classical').exists():
        code="import json, torch; from dataclasses import replace; from qpath.classical import ModelConfig,QPathTextModel; torch.set_num_threads(1); c=replace(ModelConfig.smoke(),dropout=0.,labels=14); m=QPathTextModel(c).eval(); m.route_mode='shared'; x=torch.tensor([[2,3,0],[4,5,6]]); mask=x!=0; result=m(x,mask)['logits']; assert result.shape==(2,14) and torch.isfinite(result).all(); print(json.dumps({'torch':torch.__version__,'shape':list(result.shape),'training_updates':0}))"
        ok=run('classical CPU forward without updates',['-c',code],ROOT/'payload/study/classical') and ok
    result=dict(status='PASS' if ok else 'FAIL',recorded_at_utc=datetime.now(timezone.utc).isoformat(),python=sys.executable,python_version=sys.version,platform=platform.platform(),checks=checks,scope='All selected Python parsed; source-specific imports and deterministic in-memory predictions, CLI help and one explicit nontraining invariant; v0.2 additionally a CPU text forward. No official input files used.',not_verified=['Clean-room dependency installation','Full training or official scoring','Datasets and selected checkpoints','Full-archive relocation','Shot sampling or noise experiments','Hardware or QPU execution'])
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':result['status'],'checks':len(checks)}));return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
