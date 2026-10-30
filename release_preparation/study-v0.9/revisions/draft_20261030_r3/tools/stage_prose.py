"""Current v0.9 guidance and retained-source editorial checks; no experiment runs."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,zipfile
OUT=Path(__file__).resolve().parent
OLD=Path(r'C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.9\draft_20261029_r2')
SCI=Path(r'C:\Q2\Improvement_Study_v0.9\evidence')
def load(p):return json.loads(p.read_text('utf-8'))
def info(p):
    b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def need(ok,msg):
    if not ok:raise RuntimeError(msg)
def write(p,t):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t.rstrip()+'\n',encoding='utf-8',newline='\n')
paths=[SCI/'governance/ANALYSIS_PROTOCOL.json',SCI/'analysis/official_evaluation_v01/STATISTICAL_ANALYSIS.json',SCI/'governance/RUN_MATRIX.json',SCI/'analysis/conversion_v01/CONVERSION_SUMMARY.json',SCI/'analysis/independent_conversion_v02/INDEPENDENT_DERIVED_REPLAY.json',SCI/'analysis/reproduction_v01/REPRODUCTION_SUMMARY.json',SCI/'analysis/independent_derived_recovery03/README_RECOVERY.txt',SCI/'analysis/independent_derived_recovery04/README_RECOVERY04.txt',SCI/'analysis/independent_audit_recovery03/SEMANTIC_DIFF.patch',SCI/'quantum/models.py',SCI/'quantum/study.py',SCI/'quantum/prepare_data.py',SCI/'execution/VENDOR_PROVENANCE.json',SCI/'analysis/independent_audit/replay_analysis_v09.py']
protocol,analysis,matrix,conversion,independent,reproduction=map(load,paths[:6])
primary=analysis['primary_contrasts']
need(protocol['family_size']==12 and len(primary)==12 and protocol['confirmation_count']==636,'Primary design differs')
need(all(c['first']=='C_L' and c['second'] in ('C_S','C_R','G121') and c['n_independent_populations']==8 and c['paired_seeds_per_population']==2 and c['df']==7 and c['confidence']==1-.05/12 for c in primary),'Primary contrast interpretation differs')
counts=Counter('favorable' if c['interval'][1]<0 else 'unfavorable' if c['interval'][0]>0 else 'inconclusive' for c in primary)
need(counts==dict(favorable=5,unfavorable=3,inconclusive=4),'Primary direction counts differ')
practical={(c['family'],c['second']) for c in primary if c['interval'][1]<-.01}
need(practical=={('spiral','C_S'),('annulus','G121'),('disks','C_S')},'Practical-reference findings differ')
need(matrix['counts']==dict(A=72,B=636,engineering=48) and Counter(r['stage'] for r in matrix['runs'])==matrix['counts'],'Run matrix differs')
need(conversion['models']==276 and conversion['bank_cores']==1380 and independent['status']=='PASS' and independent['result']['models']==276 and reproduction['fits']==4,'Historical conversion/reproduction counts differ')
bank=next(x for x in analysis['banknote_descriptive'] if x['arm']=='MLP4')
need(round(bank['metrics']['bce']['mean'],4)==.0165 and round(100*bank['metrics']['macro_f1']['mean'],2)==99.12 and len(bank['seeds'])==5,'Banknote values differ')
omitted=['analysis/independent_audit_recovery03/','analysis/independent_derived_recovery03/','analysis/independent_derived_recovery04/','governance/DEPLOYMENT_PROTOCOL.json','governance/REPRODUCTION_PROTOCOL.json','analysis/reproduction/tests/test_reproduction.py']
with zipfile.ZipFile(OLD/'dist/QPathformer_v0.9_Code.zip') as z:
    members={n.removeprefix('QPathformer_v0.9_Code/payload/study/') for n in z.namelist()}
need(all(not any(n==p or n.startswith(p) for n in members) for p in omitted),'Expected reproduction exclusions differ')
need('ref.sigmoid(z)' in paths[-1].read_text('utf-8') and 'diagnostic_expit(z)' in paths[8].read_text('utf-8'),'Historical diagnostic lineage differs')
rows=['| Task | C_L versus fixed-soft C_S | C_L versus residual C_R | C_L versus global G121 |','| --- | --- | --- | --- |']
for f,label in [('checkerboard','Checkerboard'),('spiral','Spiral'),('annulus','Noisy annulus'),('disks','Rare disks')]:
    cells=[]
    for control in ('C_S','C_R','G121'):
        c=next(c for c in primary if c['family']==f and c['second']==control)
        cells.append('Lower BCE' if c['interval'][1]<0 else 'Higher BCE' if c['interval'][0]>0 else 'Inconclusive')
    rows.append('| '+label+' | '+' | '.join(cells)+' |')
table='\n'.join(rows)
opening='Q-Pathformer v0.9 tests whether learning how inputs are shared among small experts improves prediction beyond fixed routing and an equally sized output correction. It compares circuit emulation and classical models on four synthetic classification tasks, with a separate Banknote Authentication check.'
finding='Across twelve registered comparisons against fixed-soft routing (C_S), a parameter-count-matched output residual (C_R) and the global G121 control, the learned-soft circuit model (C_L) had lower common clipped binary cross-entropy (BCE; lower is better) in five, higher loss in three and inconclusive differences in four.'
practical_text='Three favorable intervals established an absolute reduction greater than 0.01 BCE: C_L versus C_S on spiral and rare disks, and C_L versus G121 on noisy annulus. The annulus result compares model families; its direct routing-control comparisons remained inconclusive. Neither favorable C_L-versus-C_R interval establishes improvement greater than 0.01 throughout the interval.'
interpretation='G121 remained substantially stronger on checkerboard and spiral and held a smaller BCE advantage on rare disks. A four-feature MLP led the descriptive Banknote check, where most other models received two PCA-derived inputs. The results support task-dependent choices and further work on routing and representation.'
design='Confirmation included 636 fits: 576 across four synthetic families and 60 on Banknote. Synthetic inference uses eight independent populations per task, with two paired optimizer seeds. Banknote uses one grouped split with five optimizer seeds. Four additional retrains check selected results in the historical environment; they do not add independent populations.'
etel='This study includes the study-specific execution adapter for **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**. Its retained vendor source records version **0.2.0**. ETEL coordinates complete training fits; the learned router controls expert mixture weights within a predictor.'
bounded='Bounded startup verifies exact package integrity before and after execution, parses all 57 Python files, checks two in-memory circuit inputs and a sigmoid calculation, and requires three successful CLI help paths. It does not exercise all model variants, Banknote preprocessing, complete accepted replay, conversion parity or ETEL recovery.'
replay='Full historical replay also requires the accepted versioned recovery entrypoints, supporting contracts and protocols, qualification sources and operational bindings retained with the complete study evidence. Some included entrypoints preserve earlier historical implementations. The curated Code ZIP supports source inspection and bounded startup; it does not contain every component used by the final accepted replay.'
limits='All results use classical CPU computation. No physical-QPU performance, quantum advantage, universally superior model or broad real-world generalization is established. v0.9 includes no new finite-shot campaign.'
rights='CC BY 4.0 applies to identified controlled original report content and listed explanatory prose. The unchanged Q-Pathformer Platform License 1.0 applies to exact selected Python files, including the retained ETEL files and package helpers; these are source available. Adopted scopes identify covered content and exclusions. Earlier permissions and separate third-party terms remain in force; datasets, trained models, architecture documents and full archives retain separate treatment.'
attribution='Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains licensor; affiliations do not transfer ownership.'
release=f'''**Draft for owner review · Private repository · Study · Documentation · Code**

{opening}

### Historical findings

{finding} Table entries describe C_L relative to the named control.

{table}

{practical_text}

{interpretation}

Synthetic primary comparisons use paired population-mean differences and nominal 99.5833% Bonferroni t intervals (df = 7). Native training loss is a separate diagnostic; macro-F1 is secondary.

### What changed in this study

{design}

{etel} v0.9 uses uniform sampling with replacement; v0.8's priority intervention is historical context. Repository v1.0, study v0.9 and the ETEL versions identify different things.

### Historical verification and limitations

Conversion covered 276 circuit predictors and 1,380 expert cores while retaining routing, gates, residuals and preprocessing. Checked predictions agreed to floating-point tolerance, and conversion reduced local inference latency relative to the original emulators. It does not establish the fastest overall model or compression.

The four clean retrains copied frozen source, data and protocols into new directories and reused the historical environment. Timing conditions are technical comparisons, not independent accuracy replications.

{limits}

### Downloads and release-packaging checks

Download each ZIP with its matching `.seal.json`, verify it, then open `START_HERE.md`.

| Download | Contents |
| --- | --- |
| `QPathformer_v0.9_Study.zip` | Preserved PDF/Word report, edition note, current introduction, rights and provenance |
| `QPathformer_v0.9_Documentation.zip` | Updated study overview, research context and reproduction boundaries |
| `QPathformer_v0.9_Code.zip` | Selected scientific sources, ETEL adapter, dependency inventory and corrected startup tools |

Datasets, checkpoints, installed environments and full archives are excluded. Complete historical replay also requires separately retained accepted recovery implementations, supporting protocols and reviewed environment/path bindings.

{bounded} Release preparation runs no training, official scoring, timing, sampling or QPU jobs. [Report preservation review](report/REPORT_REVIEW_BOUNDARIES.json) records unchanged report identities and the applicable v0.9 disclosure context. Seals are integrity records, not digital signatures.

[Exact package identities](PACKAGE_INDEX.json) · [Fresh startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json) · [Package verification](receipts/ROOT_PACKAGE_VERIFICATION.json) · [Source inventory](receipts/SOURCE_INVENTORY.json).

### Scoped licensing

{rights} [Owner licensing record](OWNER_LICENSE_AUTHORIZATION.json).

{attribution}

This remains a draft in the private repository. **Study v0.9.5 remains Latest.**
'''
write(OUT/'RELEASE_BODY.md',release);write(OUT/'RELEASE_TITLE.txt','Q-Pathformer Study v0.9 — Learned Routing and Classical Controls')
replay_detail=f'''{replay}

Excluded versioned directories include `analysis/independent_audit_recovery03/`, `analysis/independent_derived_recovery03/` and `analysis/independent_derived_recovery04/`. Selected entrypoints also require excluded `governance/DEPLOYMENT_PROTOCOL.json`, `governance/REPRODUCTION_PROTOCOL.json` and `analysis/reproduction/tests/test_reproduction.py`.

The included original `analysis/independent_audit/replay_analysis_v09.py` uses `ref.sigmoid` for the postfit argmax diagnostic. Accepted scoring recovery03 uses installed SciPy `expit` there and retains the earlier common-expert-BCE diagnostic arithmetic correction. Independent model, metric and statistical calculations retain their disclosed separate implementations. The narrow shared diagnostic primitive limits independence at that operation; it does not erase all independent verification.

Derived recovery03 adapts dependencies to the accepted scoring lineage. Recovery04 addresses runtime-metadata schema mismatch without changing numerical algorithms, tolerances, models or producer outputs. Historical preparation READMEs predate later accepted runs and are not final completion statuses. This package keeps its selected historical sources unchanged; no omitted recovery implementation is silently added. A fuller reproduction distribution would require its own exact lineage and scope. This revision checks selection boundaries and retained records, not a complete accepted replay.
'''
guide=f'''# Study v0.9 research overview

{opening}

## Primary findings and inference

{finding} Table entries describe C_L relative to each control.

{table}

{practical_text}

The clearest routing-specific evidence is on spiral and rare disks, where C_L beats both C_S and C_R. C_L versus hard routing is secondary. The twelve primary comparisons are three controls across four tasks, not twelve isolated gate interventions. {interpretation}

Primary common clipped natural-log BCE clips probabilities to `[1e-7, 1-1e-7]`. Native Bernoulli-mixture/logit training loss is separately reported. Do not substitute the native-BCE primary outcome of the later v0.9.5 allocation study. Two paired optimizer-seed differences are averaged within each synthetic population before inference across eight population means. Nominal 99.5833% two-sided Bonferroni t intervals use seven degrees of freedom and small-sample assumptions. Sixteen endpoints are not sixteen independent populations. The 0.01 reference is absolute BCE, not a relative percentage or an F1 change. Crossing zero is inconclusive, not equivalence. Secondary nominal 95% intervals remain separate; there is no pooled task score.

## Model mechanism and training

Nine synthetic arms comprise circuit and trigonometric families, each with hard (H), fixed soft (S), learned soft (L) and fixed soft plus residual (R), plus G121. Banknote adds MLP2, MLP4 and LR2. Circuit H/S have 70 predictor parameters and L/R 82; Trig H/S have 125 and L/R 137. L adds twelve gate coefficients, while R adds twelve output-correction coefficients. Equal counts do not make their function classes, optimization paths or costs identical.

Soft mixtures combine probabilities, not logits. Fixed soft routing remains input dependent. Dense S/L/R evaluate all five experts; hard routing selects one. Centroids and preprocessing are fitted on training inputs. S/L/R share expert initialization and minibatch draws; extra coefficients begin at zero and remain frozen for 750 updates before their own optimizer starts.

v0.9 uses uniform sampling with replacement, not v0.8 priority training. Full fits complete 200 rounds and 15,000 updates. Each round is a fixed budget of 75 minibatches, not an epoch over Banknote. Validation F1 milestones do not cause early stopping. The postfit learned-argmax diagnostic is not a separately trained hard-routing arm. Effective experts summarizes routing weights; it neither counts invoked experts nor demonstrates execution savings.

The registered matrix contains 48 short engineering, 72 development and 636 confirmation fits: 756 in total. Four separate retrains bring the overall count to 760. Synthetic confirmation is 4 tasks × 8 populations × 2 seeds × 9 arms = 576; Banknote contributes 12 arms × 5 seeds = 60. {design}

## Banknote interpretation and attribution

Banknote uses one fixed split grouped by identical raw feature vectors before splitting. Specimen and capture-session identifiers are unavailable, so this grouping does not establish independence at those acquisition levels. Five optimizer seeds describe optimization variability on that one split, not five independent datasets.

Most arms receive two PCA-derived inputs. MLP4 receives all four transformed features; MLP2 uses two. Preprocessing is fitted only on training data. MLP4's reported mean BCE is 0.0165 and macro-F1 is 99.12%. Its stronger result compares different input information and architecture; the synthetic population-level inference does not transfer to this fixed split.

The upstream dataset contains 1,372 instances and four features and has its own CC BY 4.0 attribution: Volker Lohweg, Banknote Authentication, UCI Machine Learning Repository, DOI 10.24432/C55P57. [Official dataset record](https://archive.ics.uci.edu/dataset/267/banknote+authentication). Its terms are separate from Anthony's original-content grant. Dataset bytes are not bundled in the curated downloads.

## Reproduction and accepted replay prerequisites

The four clean retrains are checkerboard C_L seed 1801, spiral C_R seed 1801, noisy-annulus T_L seed 1801 and Banknote MLP4 seed 1901. Frozen source, data and protocols were copied into new directories; datasets and routers were not freshly regenerated as in v0.8. Trained checkpoints were not copied as initialization. Original endpoint evidence was later read for comparison. The report displays zero validation/test probability differences for these selected checks. This is same-environment implementation reproducibility, not new populations, a fresh installation, arbitrary relocation or different-hardware replay.

{replay_detail}

## Conversion and timing

The study converted 276 circuit predictors and 1,380 expert cores to 25-term trigonometric representations. Routing, learned gates, residuals and Banknote preprocessing remain; a mixture of five converted experts does not become one global 25-term model. Reported maximum Laurent-coefficient discrepancy is 2.132e−14 and maximum complete-pipeline probability discrepancy is 8.382e−15. Exact conversion describes algebraic equivalence with finite floating-point checks, not bitwise equality, another trained efficacy arm or a fresh conversion run during packaging.

Converted predictors were faster than their original emulators in all 2,484 matched endpoint/batch/session conditions. This does not say every raw timing call was faster. Tables use complete-call microseconds, including preprocessing where applicable, routing and residual work, with loading excluded. Three sessions and fifteen timed calls per endpoint condition are technical repetitions; figure spans are observed session ranges, not confidence intervals. All arms and sessions remain included.

Conversion does not establish the fastest overall model. Banknote batch-one means are 21.4 microseconds for MLP4 and 149.6 microseconds for converted C_L. Dense expert evaluation retains its cost. Serialized coefficient/policy sizes are distinct from raw coefficient sizes and do not establish compression. Measurement-setting work counters are simulator accounting; no v0.8 speedup ranges or new finite-shot campaign are imported.

## ETEL naming and resource accounting

{etel}

At most five fit workers ran, with one BLAS thread each. Logical blocks of 64 slots are bookkeeping, not physical workers, extra model capacity or demonstrated 64× acceleration. Worker CPU, nested training CPU and stage wall time have different scopes: subtraction does not isolate ETEL overhead and addition can double-count work. Model routing is separate from the later v0.9.5 allocation study.

Repository v1.0, study v0.9, component ETEL v0.1, vendor source 0.2.0 and future qpu-prep-v0.1 are distinct. Historical source version strings, vendor provenance and future v1.1 report language remain unchanged. This selection is not a standalone ETEL release.

## Packaging, reports and limits

{bounded}

The numerical smoke imports NumPy/SciPy and selected modules; importing `reference_v03` is not independent matrix parity. Required help targets are `quantum/study.py`, `execution/launcher.py` and `execution/bind_stage.py`. Final receipts record actual versions and exact package identity outside the entire extracted package. All 55 scientific Python files and original protocols remain unchanged. SOURCE_SELECTION lists 59 implementation/protocol files plus a separately mapped/scoped execution README: 60 retained payload files. Historical Windows observations are Python 3.12.14, NumPy 2.5.4 and SciPy 1.18.1; bounded startup is not fresh-install or Windows process-recovery validation.

Both report formats are preserved. The supplied PDF has 40 pages, including the edition note. The owner-supplied review reports a compatible alternate DOCX rendering without v0.8's missing-row issue; this revision makes no replacement export or universal rendering claim. The v0.9 page-37 operational usage disclosure applies to this report. Historical token equivalents, account debit and operational multipliers are not billed study-specific prices or current pricing. Exact balances are not repeated in current release prose.

Historical internal labels and future recommendations remain source chronology. The old top-level READ_ME is a preserved preparation notice; current START_HERE, the findings report and release evidence guide the reader. No cross-study disclosure correction or automatic redaction is introduced.

The retained archive records 34,582,760,206 logical payload bytes, excluding its manifest and reserved sidecars. That is archival accounting, not download size, model size, RAM requirement or tested hardware minimum. Selected sources and manifest identities are checked; the excluded full archive is not rescanned.

{limits}

{rights}

{attribution}
'''
old=(OLD/'assembly/QPathformer_v0.9_Documentation/OVERVIEW.md').read_text('utf-8')
guide+='\n## Retained source guidance\n\n'+old[old.index('- [Original README_EVALUATION'):]
write(OUT/'QPathformer_v0.9_Documentation/OVERVIEW.md',guide)
for kind in ('Code','Documentation','Study'):
    root=OUT/f'QPathformer_v0.9_{kind}'
    links=('[quickstart](QUICKSTART.md), [selection](SOURCE_SELECTION.json), [dependencies](DEPENDENCY_INVENTORY.json) and [earlier permissions](INHERITED_LICENSE_MAP.json)' if kind=='Code' else '[overview](OVERVIEW.md), [release notes](RELEASE_NOTES.md) and [reproduction boundaries](REPRODUCTION_BOUNDARIES.md)' if kind=='Documentation' else '[report PDF](reports/QPathformer_v0.9_Report_Edition_1.pdf), [Word report](reports/QPathformer_v0.9_Report_Edition_1.docx) and [edition changes](provenance/EDITION_CHANGES.md)')
    write(root/'START_HERE.md',f'# Q-Pathformer study v0.9 {kind}\n\n{opening}\n\n{finding}\n\n{practical_text}\n\n{interpretation}\n\n{etel}\n\nRead the {links}, [rights](RIGHTS.md), [verification guidance](VERIFY.md) and [source map](SOURCE_MAP.json). Repository edition v1.0 and study v0.9 are separate identifiers.\n\n{replay}\n\n{limits}\n\n{attribution}')
    if kind!='Study':
        for name in ('VERIFY.md','RIGHTS.md'):
            text=(OUT.parent/'v08_r3_prose'/f'QPathformer_v0.8_{kind}'/name).read_text('utf-8').replace('v0.8','v0.9')
            if name=='VERIFY.md':text+='\nBounded startup does not test Banknote preprocessing or complete accepted recovery replay. Consult the companion Documentation reproduction boundaries for omitted prerequisites.\n'
            write(root/name,text)
write(OUT/'QPathformer_v0.9_Documentation/RELEASE_NOTES.md',f'# Study v0.9 release notes\n\n{opening}\n\n## Historical findings\n\n{finding}\n\n{table}\n\n{practical_text}\n\n{interpretation}\n\n{design}\n\n{etel}\n\n## Verification and limits\n\n{bounded}\n\n{replay}\n\nAll three wrapper packages have revised identities. Scientific sources, protocols, reports, historical provenance and legal texts remain unchanged. No earlier page-37 or alternate-render defect is carried over.\n\n{limits}\n\nRead the [overview](OVERVIEW.md), [reproduction boundaries](REPRODUCTION_BOUNDARIES.md) and [rights](RIGHTS.md).\n\n{rights}\n\n{attribution}')
write(OUT/'QPathformer_v0.9_Documentation/REPRODUCTION_BOUNDARIES.md',f'# Reproduction boundaries\n\n{bounded}\n\n## Required separately retained material\n\nDatasets, trained checkpoints, installed environments and the full operational archive are excluded. Full replay also needs the recorded native-library configuration and reviewed environment/path bindings. The archive is evidence, not a relocatable live scheduler. Historical commands and guards remain unchanged; do not interpret their presence as a complete curated replay distribution.\n\n{replay_detail}\n\n## Historical versus current verification\n\nFour selected retrains copied frozen source, data and protocols into clean directories and reused the historical environment. They add no independent populations or installation/portability proof. Banknote remains one grouped split with five optimizer seeds and differing feature inputs. No training, official scoring, ETEL execution/recovery, timing, conversion, sampling, dependency installation or QPU work is part of release startup. Final receipts distinguish their actual environment from historical and supplied-review environments.\n\n{etel}\n\n{limits}\n\nSee the [overview](OVERVIEW.md), [source map](SOURCE_MAP.json) and [rights](RIGHTS.md).')
changes=[]
for p in sorted(OUT.glob('QPathformer*/**/*')):
    if p.is_file():
        rel=p.relative_to(OUT);previous=OLD/'assembly'/rel;need(previous.is_file(),'Unexpected package member')
        changes.append(dict(path=rel.as_posix(),previous=info(previous),current=info(p)))
record=dict(status='PASS_RETAINED_PRIMARY_RECORD_CROSSCHECK',created_at_utc=datetime.now(timezone.utc).isoformat(),evidence=[info(p) for p in paths],primary_contrasts=[{k:c[k] for k in ('family','first','second','mean_difference','interval')} for c in primary],primary_directions=counts,omitted_replay_prerequisites=omitted,banknote=dict(bce=bank['metrics']['bce']['mean'],macro_f1=bank['metrics']['macro_f1']['mean'],optimizer_seeds=5,fixed_splits=1),dataset_source=dict(url='https://archive.ics.uci.edu/dataset/267/banknote+authentication',checked_on='2026-10-30',instances=1372,features=4,upstream_license='CC BY 4.0',creator='Volker Lohweg',doi='10.24432/C55P57'),changed_files=changes,reviewer='Preparing agent; retained-source and selection checks, not a second reviewer or full replay',no_experiments_run=True)
write(OUT/'SCIENTIFIC_PROSE_REVIEW.json',json.dumps(record,ensure_ascii=False,indent=2));write(OUT/'PROSE_CHANGES.json',json.dumps(dict(status='STAGED',changed_files=changes,study_assets_reused=False,report_bytes_unchanged=True),indent=2))
print(json.dumps(dict(status=record['status'],changed_files=len(changes),release_words=len(release.split()),directions=counts)))
