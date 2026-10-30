"""One clean retrain with a child-owned deadline that survives parent loss."""
import os,sys,argparse,json,threading,time,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'execution'))
from process_identity import identity
def write(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
def main():
    p=argparse.ArgumentParser();p.add_argument('--request',required=True);a=p.parse_args();request=json.loads(Path(a.request).read_text());meta=Path(request['metadata']);write(meta,{'process_identity':identity(),'command':request['trainer_arguments'],'phase':'clean_reproduction_fit','child_owned_deadline_seconds':7200});stop=threading.Event()
    def watchdog():
        if not stop.wait(7200):
            write(meta.with_suffix('.TIMEOUT.json'),{'status':'timed_out','partial_artifacts_preserved':True,'automatic_retry':False});os._exit(124)
    thread=threading.Thread(target=watchdog,daemon=True);thread.start();sys.argv=request['trainer_arguments'];sys.path.insert(0,str(Path(sys.argv[0]).parent))
    try:runpy.run_path(sys.argv[0],run_name='__main__')
    finally:stop.set();thread.join(timeout=1)
if __name__=='__main__':main()
