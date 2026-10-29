"""Record independent author-evaluator source review; never open outcomes."""
import audit_endpoints_v09 as a
from datetime import datetime,timezone

root=a.ROOT;qualification_path=root/'governance/AUTHOR_EVALUATOR_QUALIFICATION_v03.json';q=a.read(qualification_path)
a.need(q['status']=='PASS' and q['tests']==10 and q['official_test_outcomes_accessed'] is False,'Qualification incomplete')
for name,digest in q['source_hashes'].items():a.need(a.sha(root/name)==digest,'Reviewed source changed')
a.check_binding(q['test_log'])
report={'schema':'qpath-v09-author-evaluator-independent-source-review-1','status':'PASS','utc':datetime.now(timezone.utc).isoformat(),
 'reviewer':'/root/v09_execution','qualification':a.binding(qualification_path),'source_hashes':q['source_hashes'],
 'analysis_protocol':a.binding(root/'governance/ANALYSIS_PROTOCOL.json'),
 'official_test_outcomes_accessed':False,'official_scoring_performed':False,
 'review_scope':'Independent source review and retained synthetic test evidence; later separately gated numerical prediction/statistics replay remains required.',
 'checks':['Complete636B author+independent+root exact endpoint and selectedcheckpoint maps; both no-test-access declarations and common fullBmanifest; seven frozen scientific sources and analysis/data protocols rehashed.',
 'No model/test array read before all636 release gate passes; evaluation output exclusivecreate, failuresretained, sources/consumeddata/latentdiagnostics rehashed at commit.',
 'ClippedBCE1e-7, stable nativeBCE, p>=.5, two-classmacroF1, rawBrier, fixedlinspaceECErightbins, tie-groupedstepwiseAP and no-positiveAPnull matchprotocol.',
 'All12primaryBCEcontrasts use eight populationmeans of two pairedseed differences, df7 Studentt and Bonferroni99.583333percent intervals; practicalreference0.01 and no equivalenceclaim from intervalcrossingzero.',
 'Secondary contrasts nominal95percent; Banknote five optimizationseeds on one split descriptiveonly; no synthetic/real or crossfamilyheadlinepooling.',
 'Selectedbank diagnostics distinguished from actualtrainingexposure; learnedgate historicalpreupdateweights replay all15000minibatches with activation751 and retainedroundchecks; validationmilestones descriptive.',
 'Cost metadata joins exactPIDcreationidentity and ownershipjournal/request/terminalbindings; native lifetimepeakthroughsample includespreflighttrainingverification, missing samplesunknown, elapsedchildsum notstagewall.'],
 'resolved_findings':['Independent audit no-testaccess declaration and sharedmanifestbinding added.','Final rehash of consumedannuluslatentdiagnostics added.','Perattemptresourceidentity/terminal validation and precisepeak semantics added.'],
 'remaining_required_work':'Separate independent636prediction/allmetrics/populationstatistics replay after root evaluation release and committed official scoring.'}
a.write_new(a.HERE/'AUTHOR_EVALUATOR_SOURCE_REVIEW_v01.json',report)
print(a.binding(a.HERE/'AUTHOR_EVALUATOR_SOURCE_REVIEW_v01.json'))
