"""One-time source adaptation; no model/data/phase execution."""
from pathlib import Path
root=Path(__file__).resolve().parent
for name in ('compiler.py','fixtures.py','support.py','producer.py','timing.py','tests/test_deployment.py'):
    p=root/name;s=p.read_text()
    s=s.replace('v0.7','v0.8').replace('qpath-v07','qpath-v08')
    if name=='compiler.py':
        s=s.replace("METHODS=('qscalar_kmeans','qmulti_kmeans','qmulti_hash')","METHODS=('qmulti_kmeans','qmulti_hash')")
        s=s.replace('approved Scalar/Multi','approved Multi')
        s=s.replace("count=1 if method=='qscalar_kmeans' else 5;width=9+count","count=5;width=14")
        s=s.replace("('trig_global','trig_kmeans','trig_hash','trig121_global')","('trig_kmeans','trig_hash','trig121_global')")
    if name=='support.py':
        s=s.replace('"analysis/official"','"analysis/official_evaluation"')
        s=s.replace('"compiler.py", "joint.py", "fixtures.py"','"compiler.py", "fixtures.py"')
        s=s.replace('("ScalarK", "MultiK", "MultiHash")','("MultiK_U", "MultiK_P", "MultiHash_U", "MultiHash_P")')
        s=s.replace('== 192','== 256').replace('conversion/shot identity','conversion identity')
        s=s.replace('    gate.require(release.get("phase") == phase,', '    gate.require(phase in ("conversion","timing"), "Unregistered deployment phase")\n    gate.require(release.get("phase") == phase,')
        s=s.replace('"Wrong deployment phase")','"Wrong deployment phase")')
    if name=='producer.py':
        s=s.replace('circuit conversion and ideal finite-shot diagnostics','circuit conversion; no finite-shot campaign')
        s=s.replace('CIRCUIT_ARMS = ("ScalarK", "MultiK", "MultiHash")','CIRCUIT_ARMS = ("MultiK_U", "MultiK_P", "MultiHash_U", "MultiHash_P")')
        s=s.replace('TRIG_ARMS = ("TrigK", "TrigHash", "TrigG25", "TrigG121")','TRIG_ARMS = ("TrigK_U", "TrigK_P", "TrigHash_U", "TrigHash_P", "TrigG121_U", "TrigG121_P")')
        s=s.replace('512','640').replace('192','256')
        s=s.replace('(*CIRCUIT_ARMS, *TRIG_ARMS, "MLPG129")','(*CIRCUIT_ARMS, *TRIG_ARMS)')
        s=s.replace('    import joint\n','')
        start=s.index('    streams = []')
        end=s.index('    return {"schema":',start)
        s=s[:start]+s[end:]
        s=s.replace('            "shot_streams": streams,\n','')
        s=s.replace('"fixtures": {"shot_selection": "Lowest 32 numeric validation IDs, ascending, no labels",\n                         "conversion_offgrid"', '"fixtures": {"conversion_offgrid"')
        s=s.replace('256 learned Trig tables','384 learned Trig tables')
        s=s.replace('            "shot_scope": "Conditional classical multinomial simulation; no hardware, no heldout F1"}','            "out_of_scope": "No new finite-shot/noise/Aer campaign, physical hardware or cloud"}')
        s=s.replace('len(records) == 448','len(records) == 640')
        s=s.replace('"learned_trig_same_checkpoint_transforms": 256','"learned_trig_same_checkpoint_transforms": 384')
        start=s.index('\ndef analytic_logit_variance')
        end=s.index('\ndef run(',start)
        s=s[:start]+s[end:]
        s=s.replace('    root, output = Path(root).resolve(), Path(output).resolve()\n    sys.path', '    gate.require(phase == "conversion", "Only conversion is registered in this producer")\n    root, output = Path(root).resolve(), Path(output).resolve()\n    sys.path')
        s=s.replace('(convert if phase == "conversion" else shots)(root, output, verified)','convert(root, output, verified)')
        s=s.replace('("registration", "conversion", "shots")','("registration", "conversion")')
        s=s.replace(', "shot_streams": len(value["shot_streams"])','')
        s=s.replace('"seed": job["training_seed_id"],\n                  "transform"', '"seed": job["training_seed_id"], "base_model": job["base_model"], "sampling_policy": job["sampling_policy"],\n                  "transform"')
    if name=='timing.py':
        s=s.replace('== 512','== 640').replace('"selected_models": 512','"selected_models": 640')
        s=s.replace('== 192','== 256').replace('== 448','== 640')
        s=s.replace('audit.get("learned_trig_exact_repacks") == 256','audit.get("learned_trig_exact_repacks") == 384')
        s=s.replace('("ScalarK", "MultiK", "MultiHash")','("MultiK_U", "MultiK_P", "MultiHash_U", "MultiHash_P")')
        s=s.replace('[2112, 31680, 4224, 576]','[2688, 40320, 5376, 768]')
        s=s.replace('"conditions": 2112, "representations": 704','"conditions": 2688, "representations": 896')
        s=s.replace('if job["arm"] != "MLPG129":','if True:  # Every v0.8 selected model has an exact table representation.')
        s=s.replace('all(p["process_identity"] != identity for p in prior_records)',
                    'all(process_key(p["process_identity"]) != process_key(identity) for p in prior_records)')
        s=s.replace('def run(root, authorization, output, session):',"""def process_key(identity):
    return int(identity["pid"]), identity["creation_token"]


def run(root, authorization, output, session):""")
    if name=='tests/test_deployment.py':
        s=s.replace('import joint\n','')
        s=s.replace('STREAMS = {"paired_circuit_core_initialization": 92731, "mlp_initialization": 92732}','STREAMS = {"paired_circuit_core_initialization": 92731}')
        s=s.replace('(512, 32, 192)','(640, 32, 256)')
        s=s.replace('range(0, 64, 16)','range(0, 80, 20)').replace('start + 16','start + 20')
        s=s.replace('        self.assertEqual(len(value["shot_streams"]), 12800)\n        self.assertEqual(len({s["uint128_decimal"] for s in value["shot_streams"]}), 12800)',
                    '        self.assertEqual(len(value["circuit_run_ids"]),256)\n        self.assertEqual(len(value["all_run_ids"]),640)\n        self.assertNotIn("shot_streams",value)')
        start=s.index('                joints, heads =')
        end=s.index('\n    def ',start)
        s=s[:start]+s[end:]
        start=s.index('    def test_count_conservation')
        end=s.index('    def test_decision_tie_band',start)
        s=s[:start]+s[end:]
        s=s.replace('"circuit_endpoints": 192','"circuit_endpoints": 256').replace('"representations_replayed": 448','"representations_replayed": 640')
        s=s.replace('"learned_trig_exact_repacks": 256','"learned_trig_exact_repacks": 384')
        s=s.replace('range(192)','range(256)').replace('"arm": "ScalarK"','"arm": "MultiK_U"')
    p.write_text(s,encoding='utf-8',newline='\n')
