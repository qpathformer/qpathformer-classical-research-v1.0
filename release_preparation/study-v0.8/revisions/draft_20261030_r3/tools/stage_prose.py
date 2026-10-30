"""Current v0.8 guidance, with retained primary-record cross-checks."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
OUT=Path(__file__).resolve().parent
OLD=Path(r'C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.8\draft_20261029_r2')
SCI=Path(r'C:\Q2\Improvement_Study_v0.8')
def load(p):return json.loads(p.read_text('utf-8'))
def info(p):
    b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def need(ok,msg):
    if not ok:raise RuntimeError(msg)
def write(p,t):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t.rstrip()+'\n',encoding='utf-8')
paths=[SCI/'governance/ANALYSIS_PROTOCOL.json',SCI/'analysis/official_results/stage_B_v01/primary_analysis.json',SCI/'analysis/deployment_results/conversion_v01/summary.json',SCI/'analysis/independent_deployment_results/conversion_v01/summary.json',SCI/'analysis/reproduction_results/full_v01/summary.json',SCI/'execution/VENDOR_PROVENANCE.json',SCI/'quantum/sampling.py',SCI/'quantum/study.py',SCI/'quantum/routers.py',SCI/'analysis/official_evaluation/statistics_core.py']
protocol,primary,conversion,independent,reproduction,vendor=map(load,paths[:6])
need(protocol['family_size']==20 and protocol['nominal_per_contrast_confidence']==.9975 and protocol['populations_per_family']==8 and protocol['seeds_per_population']==2,'Design differs')
contrasts=primary['contrasts'];need(len(contrasts)==20,'Primary family differs')
direct=[c for c in contrasts if c['contrast_name'] in ('priority_MultiK','priority_TrigK')]
need(len(direct)==8 and sum(c['interval'][1]<0 for c in direct)==4 and not any(c['interval'][1]<-.01 for c in direct),'Direct findings differ')
wins={(c['family'],c['contrast_name']) for c in direct if c['interval'][1]<0}
need(wins=={('checkerboard','priority_TrigK'),('spiral','priority_TrigK'),('disks','priority_MultiK'),('disks','priority_TrigK')},'Winning comparisons differ')
need(all(c['n_independent_populations']==8 and c['paired_seeds_per_population']==2 and c['degrees_of_freedom']==7 and c['nominal_confidence']==.9975 for c in contrasts),'Inference differs')
need(conversion['circuit_conversions']==256 and conversion['learned_trig_same_checkpoint_transforms']==384 and independent['representations_replayed']==640 and reproduction['count']==4,'Historical verification counts differ')
rows=['| Task | Circuit MultiK | Routed TrigK |','| --- | --- | --- |']
for family,label in [('checkerboard','Checkerboard'),('spiral','Spiral'),('annulus','Noisy annulus'),('disks','Rare disks')]:
    rows.append('| '+label+' | '+' | '.join('Lower BCE with priority' if (family,'priority_'+arm) in wins else 'Inconclusive' for arm in ('MultiK','TrigK'))+' |')
table='\n'.join(rows)
opening='Q-Pathformer v0.8 asks whether giving higher-loss training examples more sampling opportunities helps models with fixed input routing. It compares uniform and priority sampling across five circuit and classical model designs on checkerboard, spiral, noisy-annulus and rare-disk tasks.'
finding='Four of eight prespecified direct comparisons supported lower common clipped binary cross-entropy (BCE; lower is better) with priority sampling. The other four were inconclusive. None established an absolute reduction greater than 0.01 BCE across its entire adjusted interval.'
interpretation='Priority did not close the routed circuit’s gap to the wider global trigonometric baseline on checkerboard or spiral. Macro-F1 is descriptive; a higher F1 need not imply lower BCE. The findings support further work on representation and routing, with priority retained as an optional training policy.'
design='The study completed 40 short engineering fits, 80 development fits and 640 confirmation fits. Five base models—MultiK, MultiHash, TrigK, TrigHash and TrigG121—each have uniform and priority arms. Confirmation uses eight independent populations per task and two paired optimizer seeds within each population.'
etel='The included adapter belongs to **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1** and retains historical vendor source version **0.2.0**. Priority sampling chooses training examples; model routing chooses the predictor bank for an input; ETEL coordinates complete training fits.'
limits='All results use classical CPU computation; v0.8 includes no physical-QPU run or new finite-shot experiment. Four synthetic binary task families and eight independent populations per task limit generalization. No quantum advantage or universal training benefit is established.'
bounded='Bounded startup verifies package integrity before and after execution, parses all 85 selected Python files, checks two inputs through a zero-angle circuit plus a sigmoid comparison, and requires successful help output from three CLI paths. It does not run training, official scoring, conversion parity, timing, ETEL fits/recovery or QPU work.'
viewing='Use the supplied PDF for the reviewed page layout. The Word edition preserves the editable report content, but pagination and table rendering can vary by application. Check all table rows before exporting a replacement PDF.'
rights='Identified original report content and explanatory prose use **CC BY 4.0**. Exact selected Python files, including retained ETEL files and package helpers, are **source available under the unchanged Q-Pathformer Platform License 1.0**. Existing applicable grants remain in force. Dependencies, datasets, trained models, architecture documents and full archives retain separate terms; package scopes identify covered content and exclusions.'
attribution='Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains licensor; affiliations do not transfer ownership.'
release=f'''**Draft for owner review · Private repository · Study · Documentation · Code**

{opening}

### Historical findings

{finding}

{table}

{interpretation}

The twenty primary comparisons use paired population-mean differences and nominal 99.75% Bonferroni t intervals (df = 7). Two seed differences are averaged within each population; sixteen endpoints are not sixteen independent populations. Native-logit BCE used for training is a separate diagnostic.

### What changed in this study

{design}

{etel} At most five fit processes ran concurrently; 64 logical slots are bookkeeping, not a measured speedup. Repository v1.0, study v0.8 and ETEL versions identify different things.

### Historical verification and limitations

Four preselected clean-directory retrains reproduced earlier configurations in the historical environment; they add no independent populations. Conversion checked 256 circuit coefficient tables and 384 trigonometric repacks, with maximum independent probability discrepancy below 2.62e−14 and no checked class changes. These are representations of existing predictors, not additional efficacy arms.

Reported paired CPU latency ratios favored compiled circuits, but all three timing sessions varied and loading was excluded. Conversion adds no accuracy or compression claim. Detailed results and boundaries remain in the report and Documentation overview.

{limits}

### Downloads and release-packaging checks

Download each ZIP with its matching `.seal.json`, verify it, then open `START_HERE.md`.

| Download | Contents |
| --- | --- |
| `QPathformer_v0.8_Study.zip` | Preserved PDF/Word report, viewing guidance, rights and provenance |
| `QPathformer_v0.8_Documentation.zip` | Updated overview, findings, original guidance and reproduction boundaries |
| `QPathformer_v0.8_Code.zip` | Selected scientific implementation, ETEL adapter and corrected bounded verification tools |

{viewing} The [current clarification](report/VISUAL_REVIEW_CLARIFICATION.json) corrects a cross-study reference in preserved visual-review metadata. Report PDF/DOCX bytes remain unchanged.

{bounded} Raw data, checkpoints, environments and the complete archive are excluded. Full replay needs separately retained inputs. Seals are integrity records, not digital signatures.

[Exact package identities](PACKAGE_INDEX.json) · [Fresh startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json) · [Package verification](receipts/ROOT_PACKAGE_VERIFICATION.json) · [Source inventory](receipts/SOURCE_INVENTORY.json).

### Scoped licensing

{rights} [Owner licensing record](OWNER_LICENSE_AUTHORIZATION.json).

{attribution}

This remains a draft in the private repository. **Study v0.9.5 remains Latest.**
'''
write(OUT/'RELEASE_BODY.md',release);write(OUT/'RELEASE_TITLE.txt','Q-Pathformer Study v0.8 — Priority Training and Routed Models')
guide=f'''# Study v0.8 research overview

{opening}

{design}

## Metrics and primary findings

{finding}

{table}

{interpretation}

The primary metric is common clipped natural-log BCE, with probabilities clipped to `[1e-7, 1-1e-7]`. Training and priority scores use native-logit BCE, separately reported as a diagnostic. For spiral TrigK priority, native BCE is 0.250964 while common clipped BCE is 0.240354. The later v0.9.5 native-BCE primary outcome must not be substituted here.

The twenty-comparison family comprises eight direct priority-minus-uniform contrasts, eight geometric-versus-hash priority interactions, and four MultiK-priority versus TrigG121-priority contrasts. Two paired seed differences are averaged within each population before inference across eight population differences. Nominal 99.75% two-sided Bonferroni t intervals use seven degrees of freedom, with small-sample distributional assumptions. No record bootstrap is used. The 0.01 reference is absolute BCE, not a percentage, F1 change or equivalence test; crossing zero means inconclusive.

The two Trig interaction intervals favor geometric routing on checkerboard and spiral, but an interaction alone does not establish absolute priority benefit. Rare-disk MultiK priority has the highest descriptive mean F1 while the global control has lower BCE. F1 plot whiskers are population sample standard deviations, not confidence intervals. There is no universal F1 improvement claim.

## Sampling and model routing

Both policies draw training records with replacement. The first ten rounds are uniform. Subsequent priority probabilities use training-record native losses and remain fixed within a round; inverse-probability weights `1/(N*p_i)` correct raw gradients before the batch mean. The frozen input router is not refitted from priority scores, labels or held-out outcomes. The conditional raw-gradient target remains ordinary empirical BCE; this does not guarantee identical Adam trajectories or improved generalization.

The uniform control also performs scheduled diagnostic refreshes. All full fits use 200 rounds and 15,000 updates, with no early stopping; engineering fits use 12 rounds and 900 updates. Validation-selected predictors are compared after full budgets. The study does not demonstrate end-to-end training savings against an uninstrumented uniform baseline. v0.7 used shuffled passes, so cross-version values remain historical context rather than a paired population pool.

MultiK and MultiHash each have 70 learned predictor scalars, routed TrigK and TrigHash 125, and global TrigG121 121. Router metadata, optimizer state and audit traces are additional. Similar totals do not make function classes or computational costs identical.

## ETEL naming and execution scope

{etel}

At most five fit processes ran concurrently. The 64 logical slots describe bookkeeping, not 64 physical workers, model banks, qubits or a 64× speedup. This study does not establish the later ETEL suitability-allocation policy or distributed provisioning. Component ETEL v0.1, incorporated source 0.2.0, study v0.8, repository edition v1.0 and future qpu-prep-v0.1 are distinct identifiers.

The original vendor `__version__ = "0.2.0"`, vendor archive/provenance and original guides remain unchanged. This is a study-specific adapter, not a standalone ETEL component release. CLI help is not a Windows execution, recovery, cancellation or resource-supervision test.

## Historical reproduction and conversion

Four preselected clean-directory retrains cover checkerboard MultiK priority, spiral TrigK priority, annulus MultiHash uniform and rare-disk TrigG121 uniform, each population 01 and seed 1601. Data and routers were regenerated using unchanged code in new output directories; the fits were not initialized from trained checkpoints. Historical environment/path bindings and original coordinates were reused, with earlier endpoint evidence used for comparison. These are same-environment reproductions, not new populations, fresh installations or portability tests.

The study converted 256 circuit predictors to coefficient tables and repacked 384 learned Trig predictors. The 640 representations are existing fitted models, not extra efficacy arms. The independent maximum probability discrepancy was 2.615e−14 and every checked class remained unchanged. Algebraic equivalence and finite floating-point checks do not promise bitwise equality or efficient conversion of arbitrary deeper circuits. Release startup does not freshly verify excluded checkpoints.

Group medians of paired original/compiled CPU latency ratios were 4.33–4.59× for batch 1, 11.82–16.03× for batch 32 and 2.33–5.36× for batch 1,024. Timings cover complete resident-model calls, including routing, features and heads, with loading excluded. They are not per-record times or ratios reconstructed from aggregate cells. All three sessions remain included: session three was substantially faster and the cause was not isolated. Technical repetitions are not population replications or hardware-independent guarantees. Several classical controls remain faster in relevant conditions.

The bare circuit payload is 560 bytes, compiled coefficients 1,000 bytes and retaining both 1,560 bytes before router/container overhead. Conversion is not compression, an accuracy gain or quantum hardware acceleration.

## Packaging, viewing and boundaries

{limits}

{bounded} The numerical smoke imports NumPy/SciPy and selected modules; importing `reference_v03` does not constitute an independent matrix comparison. Required help paths are `quantum/study.py`, `execution/launcher.py` and `execution/bind_stage.py`. Receipts record actual versions, exit status and exact final package identities, outside the complete package. All 83 retained scientific Python files and original protocols remain unchanged.

Historical Windows observations include Python 3.12.14, NumPy 2.5.4 and SciPy 1.18.1. The supplied review's Linux runtime used different numerical-library versions; neither its checks nor current bounded startup establish a fresh installation or full historical replay. Code SOURCE_SELECTION identifies 87 implementation/protocol files, with an additional execution README separately mapped and scoped.

{viewing}

The supplied report PDF has 45 pages. Both original and edition DOCX contain all ten Appendix F Spiral cost rows, which appear on supplied-PDF page 38. The review notes report seven rows omitted by LibreOfficeDev 26.8.0.0.alpha0 export; this preparation preserves the complete supplied PDF and does not reproduce that alternative export or infer a Word defect. The cause is unestablished. Historical visual-review metadata includes a v0.9/page-37 sentence that does not describe v0.8; a current external clarification binds the unchanged report. This is provenance correction, not a scientific erratum. Historical source labels and pending workflow statements remain evidence, not instructions to rerun jobs.

The archive's 64,335,733,380 logical payload bytes exclude its manifest and reserved sidecars. This is retained archival accounting, not download size, model size, RAM requirement or a tested hardware minimum. Selected sources and manifest identities are checked; the full excluded archive is not rescanned.

{rights}

{attribution}
'''
old=(OLD/'assembly/QPathformer_v0.8_Documentation/OVERVIEW.md').read_text('utf-8')
guide+='\n## Retained source guidance\n\n'+old[old.index('- [Original README_PREPARATION'):]
write(OUT/'QPathformer_v0.8_Documentation/OVERVIEW.md',guide)
for kind in ('Code','Documentation'):
    root=OUT/f'QPathformer_v0.8_{kind}'
    links=('[quickstart](QUICKSTART.md), [source selection](SOURCE_SELECTION.json), [dependencies](DEPENDENCY_INVENTORY.json) and [earlier permissions](INHERITED_LICENSE_MAP.json)' if kind=='Code' else '[overview](OVERVIEW.md), [release notes](RELEASE_NOTES.md) and [reproduction boundaries](REPRODUCTION_BOUNDARIES.md)')
    write(root/'START_HERE.md',f'# Q-Pathformer study v0.8 {kind}\n\n{opening}\n\n{finding}\n\n{interpretation}\n\n{etel}\n\nRead the {links}, [rights](RIGHTS.md), [verification guidance](VERIFY.md) and [source map](SOURCE_MAP.json). The companion Study package contains the preserved report in PDF and Word.\n\n{viewing}\n\n{bounded}\n\n{attribution}')
    # Reuse reviewed generic verification/rights wording with study naming changed.
    for name in ('VERIFY.md','RIGHTS.md'):
        text=(OUT.parent/'v07_r3_prose'/f'QPathformer_v0.7_{kind}'/name).read_text('utf-8').replace('v0.7','v0.8')
        write(root/name,text)
write(OUT/'QPathformer_v0.8_Documentation/RELEASE_NOTES.md',f'# Study v0.8 release notes\n\n{opening}\n\n{design}\n\n## Historical findings\n\n{finding}\n\n{table}\n\n{interpretation}\n\n{etel}\n\n## Verification and limits\n\n{limits}\n\n{bounded}\n\nAll three package pairs have revised wrapper identities; the report PDF/DOCX, scientific source, historical provenance and legal texts remain unchanged.\n\n{viewing}\n\nRead the [overview](OVERVIEW.md) and [rights](RIGHTS.md).\n\n{rights}\n\n{attribution}')
write(OUT/'QPathformer_v0.8_Documentation/REPRODUCTION_BOUNDARIES.md',f'# Reproduction boundaries\n\n{bounded}\n\nNo training, ETEL fit launch, recovery/cancellation exercise, official scoring, sampling, timing, QPU preparation or dependency installation is part of release verification. Data, checkpoints, installed environments and the full archive are excluded. Full replay needs separately retained inputs and reviewed environment/path bindings. Historical commands are provenance, not the curated quickstart.\n\nThe four historical retrains used the original environment and configurations; they are not fresh population replications or clean installations. Windows resource APIs and recovery behavior are not validated by help screens. New receipts identify their actual runtime.\n\n{etel}\n\n{limits}\n\n{viewing}\n\nSee the [overview](OVERVIEW.md), [source map](SOURCE_MAP.json) and [rights](RIGHTS.md).')
study=(OLD/'assembly/QPathformer_v0.8_Study/START_HERE.md').read_text('utf-8')
study=study.replace('Priority improved four of eight direct registered BCE comparisons','Priority improved four of eight direct registered common clipped BCE comparisons')
study=study.replace('Read [scoped rights]',viewing+'\n\nRead [scoped rights]')
write(OUT/'QPathformer_v0.8_Study/START_HERE.md',study)
changes=[]
for p in sorted(OUT.glob('QPathformer*/**/*')):
    if p.is_file():
        rel=p.relative_to(OUT);previous=OLD/'assembly'/rel;need(previous.is_file(),'Unexpected package member')
        changes.append(dict(path=rel.as_posix(),previous=info(previous),current=info(p)))
record=dict(status='PASS_RETAINED_PRIMARY_RECORD_CROSSCHECK',created_at_utc=datetime.now(timezone.utc).isoformat(),evidence=[info(p) for p in paths],direct_contrasts=[{k:c[k] for k in ('family','contrast_name','mean_difference','interval')} for c in direct],changed_files=changes,reviewer='Preparing agent; retained source cross-check, not a second reviewer',no_experiments_run=True)
write(OUT/'SCIENTIFIC_PROSE_REVIEW.json',json.dumps(record,ensure_ascii=False,indent=2));write(OUT/'PROSE_CHANGES.json',json.dumps(dict(status='STAGED',changed_files=changes,study_assets_reused=False,report_bytes_unchanged=True),indent=2))
print(json.dumps(dict(status=record['status'],changed_files=len(changes),release_words=len(release.split()))))
