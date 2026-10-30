"""One-time preparation of fresh-study data sources; never generates data."""
from pathlib import Path
root=Path(__file__).resolve().parent
for name in ('prepare_data.py','routers.py','tests/test_routers_data.py'):
    p=root/name;s=p.read_text()
    s=s.replace('v0.7','v0.8').replace('v07','v08').replace('V07','V08')
    s=s.replace('7000000000000000000','8000000000000000000').replace('7000000000001000000','8000000000001000000')
    if name=='prepare_data.py':
        s=s.replace('HISTORICAL_REGISTERED_EXPECTED = 264000','HISTORICAL_REGISTERED_EXPECTED = 584000')
        s=s.replace('== 664','== 548').replace('range(2, 7)','range(2, 8)').replace('== 608','== 760')
        s=s.replace('historical264000','historical584000')
        s=s.replace('or key == "proposed_streams"', 'or key in ("proposed_streams", "paired_streams")')
        s=s.replace('"PROPOSED_PROTOCOL.json", "ENGINEERING_FREEZE.json"', '"PROPOSED_PROTOCOL.json", "ENGINEERING_FREEZE.json", "RUN_MATRIX.json"')
        s=s.replace('import numpy as np',"""import os
import sys
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[_key]='1'
import numpy as np""")
    if name=='tests/test_routers_data.py':
        s=s.replace('"boundary_diagnostic", "shot_fixture", "deployment_order"', '"boundary_diagnostic", "deployment_order"')
        s=s.replace('        self.assertEqual({v for _, v in values}, {1, 2, 7})',"""        self.assertEqual({v for _, v in values}, {1, 2, 7})
        nested=d.declared_seeds({'paired_streams':{'training_order':make_stream('test-historical-paired')}})
        self.assertIn(int(make_stream('test-historical-paired')['uint128_decimal']),{v for _,v in nested})

    def test_active_registration_inventory_metadata_only(self):
        _,matrix,_=d.active_inputs()
        self.assertEqual(len(d.all_matrix_streams(matrix)),548)
        self.assertEqual(len(matrix['populations']),40)
        self.assertEqual(len(matrix['runs']),760)
        self.assertEqual(d.HISTORICAL_REGISTERED_EXPECTED,584000)
        self.assertTrue(any(version=='v0.7' for version,_ in d.historical_roots()))""")
    p.write_text(s,encoding='utf-8',newline='\n')
