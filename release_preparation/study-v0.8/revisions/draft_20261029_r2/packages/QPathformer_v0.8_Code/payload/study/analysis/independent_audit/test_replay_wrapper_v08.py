"""Inert dependency mocks only; never obtain a real lease or invoke replay."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import ast
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
import run_replay_leased as wrapper


class ReplayWrapperTests(unittest.TestCase):
    def fixture(self,directory,fail=False,mismatch=False):
        directory=Path(directory)
        args=SimpleNamespace(release=directory/'release.json',output=directory/'output',log=directory/'log.txt')
        state={'lease_active':False,'calls':0,'released':False}
        expected={'python':'fixture','interpreter':'fixture','numpy_version':'2.5.4',
            'openblas_dll_sha256':'fixture','openblas_config':'fixture','effective_blas_threads':1,'gpu_used':False}
        actual=dict(expected)
        if mismatch:actual['effective_blas_threads']=2
        @contextmanager
        def lease(root,kind):
            self.assertEqual(kind,'audit');state['lease_active']=True;state['owner_pid']=os.getpid()
            try:yield
            finally:state['lease_active']=False;state['released']=True
        def require(condition,message):
            if not condition:raise RuntimeError(message)
        def replay(release,output):
            self.assertTrue(state['lease_active'])
            self.assertEqual(os.getpid(),state['owner_pid'])
            self.assertEqual((release,output),(args.release,args.output))
            self.assertTrue(all(os.environ.get(name)=='1' for name in wrapper.THREAD_VARIABLES))
            state['calls']+=1
            print('synthetic replay stdout');print('synthetic replay stderr',file=sys.stderr)
            if fail:raise RuntimeError('preserved synthetic replay failure')
            return {'status':'SYNTHETIC_ONLY','pid':os.getpid()}
        durable=SimpleNamespace(auxiliary_lease=lease,require=require,verify_binding=lambda value:'runtime-fixture',
            read=lambda path: {'runtime_environment':{'path':'runtime-fixture'}} if path==args.release else expected)
        modules={'durable':durable,'resource_probe':SimpleNamespace(inspect=lambda:actual),
            'replay_evaluation_v08':SimpleNamespace(replay=replay)}
        return args,state,modules

    def test_same_process_lease_spans_callback_and_both_output_streams(self):
        with tempfile.TemporaryDirectory() as directory:
            args,state,modules=self.fixture(directory)
            with patch.dict(sys.modules,modules),patch.object(sys,'path',list(sys.path)),patch.dict(os.environ,clear=False):
                result=wrapper.run_leased(args)
            self.assertEqual(result['pid'],state['owner_pid']);self.assertEqual(state['calls'],1)
            self.assertTrue(state['released']);self.assertFalse(state['lease_active'])
            content=args.log.read_text(encoding='utf-8')
            self.assertIn('synthetic replay stdout',content);self.assertIn('synthetic replay stderr',content)
            self.assertIn('lease_owner_and_replay_pid',content)

    def test_exception_preserved_in_log_and_lease_released(self):
        with tempfile.TemporaryDirectory() as directory:
            args,state,modules=self.fixture(directory,fail=True)
            with patch.dict(sys.modules,modules),patch.object(sys,'path',list(sys.path)),patch.dict(os.environ,clear=False):
                with self.assertRaisesRegex(RuntimeError,'preserved synthetic'):wrapper.run_leased(args)
            self.assertEqual(state['calls'],1);self.assertTrue(state['released'])
            self.assertIn('Traceback',args.log.read_text(encoding='utf-8'))
            self.assertIn('preserved synthetic replay failure',args.log.read_text(encoding='utf-8'))

    def test_runtime_mismatch_prevents_callback(self):
        with tempfile.TemporaryDirectory() as directory:
            args,state,modules=self.fixture(directory,mismatch=True)
            with patch.dict(sys.modules,modules),patch.object(sys,'path',list(sys.path)),patch.dict(os.environ,clear=False):
                with self.assertRaisesRegex(RuntimeError,'runtime differs'):wrapper.run_leased(args)
            self.assertEqual(state['calls'],0);self.assertTrue(state['released'])

    def test_existing_log_is_never_overwritten_and_callback_never_started(self):
        with tempfile.TemporaryDirectory() as directory:
            args,state,modules=self.fixture(directory);args.log.write_text('preserve this',encoding='utf-8')
            with patch.dict(sys.modules,modules),patch.object(sys,'path',list(sys.path)),patch.dict(os.environ,clear=False):
                with self.assertRaises(FileExistsError):wrapper.run_leased(args)
            self.assertEqual(state['calls'],0);self.assertTrue(state['released'])
            self.assertEqual(args.log.read_text(encoding='utf-8'),'preserve this')

    def test_wrapper_has_no_child_process_api(self):
        tree=ast.parse(Path(wrapper.__file__).read_text(encoding='utf-8'))
        imported={node.names[0].name for node in ast.walk(tree) if isinstance(node,ast.Import)}
        self.assertTrue(imported.isdisjoint({'subprocess','multiprocessing'}))
        called={node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)}
        self.assertTrue(called.isdisjoint({'Popen','spawn','fork','system'}))


if __name__=='__main__':unittest.main(verbosity=2)
