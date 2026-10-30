"""Synthetic scheduling checks only, with inert numerical and lease callbacks."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import ast
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
import run_audit_in_process_v02 as wrapper


class AuditCoordinationTests(unittest.TestCase):
    def exercise(self,fail=False,mismatch=False,preexisting=False,late_failure=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'execution').mkdir()
            env=root/'environment.json';plan=root/'plan.json';frozen=root/'frozen.json';coord=root/'coord.json'
            expected={'python':'3.12.14','interpreter':'fixture','numpy_version':'2.5.4','openblas_dll_sha256':'fixture',
                'openblas_config':'fixture','effective_blas_threads':1,'gpu_used':False}
            env.write_text(json.dumps(expected),encoding='utf-8')
            for path in (plan,frozen,coord):path.write_text('{}',encoding='utf-8')
            preparation={'runtime_environment':wrapper.binding(env),'study_plan':wrapper.binding(plan)}
            args=SimpleNamespace(stage='A',output=root/'audit.json',log=root/'audit.log',coordination_receipt=root/'receipt.json')
            state={'active':False,'released':False,'calls':0};identity={'pid':os.getpid(),'creation_token':'synthetic','identity_source':'synthetic_only'}
            actual=dict(expected)
            if mismatch:actual['effective_blas_threads']=2
            @contextmanager
            def lease(received_root,kind):
                self.assertEqual((received_root,kind),(root,'audit'));state['active']=True
                try:yield
                finally:state['active']=False;state['released']=True
            def audit_stage(stage):
                self.assertTrue(state['active']);self.assertEqual(os.getpid(),identity['pid']);state['calls']+=1
                print('inert endpoint callback');print('inert stderr',file=sys.stderr)
                if fail:raise RuntimeError('synthetic endpoint audit failure')
                return {'status':'PASS','stage':stage,'verified_endpoints':80,'test_model_outcomes_accessed':False}
            modules={'durable':SimpleNamespace(auxiliary_lease=lease),'resource_probe':SimpleNamespace(inspect=lambda:actual),
                'process_identity':SimpleNamespace(identity=lambda:identity),'audit_endpoints_v08':SimpleNamespace(audit_stage=audit_stage)}
            if preexisting:args.output.write_text('preserve',encoding='utf-8')
            preparations=[preparation,RuntimeError('synthetic final preparation changed')] if late_failure else [preparation,preparation]
            with patch.multiple(wrapper,ROOT=root,FROZEN=frozen,COORDINATION=coord),patch.object(wrapper,'verify_preparation',side_effect=preparations),\
                 patch.dict(sys.modules,modules),patch.object(sys,'path',list(sys.path)),patch.dict(os.environ,clear=False):
                if fail or mismatch or preexisting or late_failure:
                    with self.assertRaises(RuntimeError):wrapper.run_leased(args)
                else:
                    result=wrapper.run_leased(args)
                    self.assertEqual(result['status'],'PASS');self.assertEqual(result['process_identity'],identity)
                    self.assertEqual(result['audit'],wrapper.binding(args.output));self.assertEqual(result['log'],wrapper.binding(args.log))
                    self.assertEqual(result['bindings']['numerical_source_freeze'],wrapper.binding(frozen))
            if preexisting:
                self.assertEqual(args.output.read_text(),'preserve');self.assertFalse(args.log.exists())
                self.assertFalse(args.coordination_receipt.exists());self.assertEqual(state['calls'],0)
            else:
                self.assertTrue(state['released']);self.assertFalse(state['active'])
                receipt=json.loads(args.coordination_receipt.read_text())
                self.assertEqual(receipt['status'],'FAIL_PRESERVED' if fail or mismatch or late_failure else 'PASS')
                if fail:
                    self.assertEqual(json.loads(args.output.read_text())['status'],'FAIL')
                    self.assertIn('synthetic endpoint audit failure',args.log.read_text())
                if late_failure:
                    self.assertEqual(json.loads(args.output.read_text())['status'],'FAIL')
                    self.assertIn('synthetic final preparation changed',args.log.read_text())
                if mismatch:self.assertFalse(args.output.exists());self.assertEqual(state['calls'],0)
                else:self.assertEqual(state['calls'],1)

    def test_same_pid_lease_and_companion_binding(self):self.exercise()
    def test_failure_is_preserved_and_lease_released(self):self.exercise(fail=True)
    def test_runtime_mismatch_prevents_numerical_callback(self):self.exercise(mismatch=True)
    def test_existing_output_prevents_all_mutation(self):self.exercise(preexisting=True)
    def test_final_binding_failure_cannot_leave_pass_audit(self):self.exercise(late_failure=True)

    def test_no_child_process_api(self):
        tree=ast.parse(Path(wrapper.__file__).read_text(encoding='utf-8'))
        imported={node.names[0].name for node in ast.walk(tree) if isinstance(node,ast.Import)}
        self.assertTrue(imported.isdisjoint({'subprocess','multiprocessing'}))

    def test_registration_rejects_modified_frozen_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);here=root/'analysis/independent_audit';here.mkdir(parents=True);(root/'governance').mkdir()
            names=('audit_endpoints_v08.py','audit_sampling_trace.py','reference_v08.py','sampler_reference.py','run_audit_leased.py','AUDIT_NUMERICAL_PROTOCOL.json')
            for name in names:(here/name).write_text('inert source fixture',encoding='utf-8')
            frozen=here/'frozen.json'
            frozen.write_text(json.dumps({'schema':'qpath-v08-independent-endpoint-source-freeze-1','sources':[wrapper.binding(here/name) for name in names]}),encoding='utf-8')
            for name in ('NUMERICAL_ENVIRONMENT.json','STUDY_PLAN.json'):(root/'governance'/name).write_text('{}',encoding='utf-8')
            coord=here/'coord.json'
            coord.write_text(json.dumps({'schema':'qpath-v08-endpoint-coordination-source-freeze-2','sources':[wrapper.binding(wrapper.__file__)],
                'numerical_source_freeze':wrapper.binding(frozen),'runtime_environment':wrapper.binding(root/'governance/NUMERICAL_ENVIRONMENT.json'),
                'study_plan':wrapper.binding(root/'governance/STUDY_PLAN.json')}),encoding='utf-8')
            with patch.multiple(wrapper,ROOT=root,HERE=here,FROZEN=frozen,COORDINATION=coord):
                wrapper.verify_preparation()
                (here/names[0]).write_text('changed fixture',encoding='utf-8')
                with self.assertRaisesRegex(RuntimeError,'Frozen numerical source changed'):wrapper.verify_preparation()


if __name__=='__main__':unittest.main(verbosity=2)
