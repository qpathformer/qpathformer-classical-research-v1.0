import ast, importlib.util, json, os, platform, socket, sys, unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
def denied(*a,**kw):raise RuntimeError('Network disabled during bounded startup')
socket.create_connection=denied
socket.socket.connect=denied
socket.socket.connect_ex=denied
q=root/'payload/study/quantum'
sys.path.insert(0,str(q));sys.path.insert(0,str(q/'tests'))
for p in (root/'payload').rglob('*.py'):ast.parse(p.read_text('utf-8'),filename=str(p))
import numpy, scipy, circuits, models, routers, study, verification
import test_models
suite=unittest.TestSuite(test_models.ModelTests(name) for name in ['test_shapes_and_paired_initial_predictions','test_moments_and_state_against_independent_matrices'])
if (q/'deployment_compiler.py').exists():
 sys.path.insert(0,str(q/'deployment_checks'));import test_compiler
 suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_compiler))
result=unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({'status':'PASS' if result.wasSuccessful() else 'FAIL','python':sys.version,'platform':platform.platform(),'numpy':numpy.__version__,'scipy':scipy.__version__,'methods':list(models.METHODS),'tests_run':result.testsRun,'scope':'AST parse all selected Python; numeric imports; registered model shapes and independent state/moment parity; v0.6 coefficient-conversion tests where supplied. No training, official scoring, shot sampling, QPU job or network.'}))
sys.exit(0 if result.wasSuccessful() else 1)
