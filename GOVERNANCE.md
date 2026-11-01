# Q Pathformer research governance

The original repository policy was adopted on 31 October 2026; the [guidance decision record](docs/GUIDANCE_UPDATE_STATUS.json) identifies the status and effective date of later amendments. Q-Pathformer publishes reviewed research editions while developing the next edition privately. Public access, research validity, licensing and eligibility for private participation are separate decisions. The [research approach](docs/RESEARCH_APPROACH.md) is a standalone release document; repository governance does not alter the scientific paper.

## Editions and authority

Research v1.0 is public. Private Research Lab is the working name for proposed private research v2.0; it is separate from the already-public [Enterprise v2.0 Standards Edition](https://github.com/qpathformer/qpathformer-enterprise-v2.0-standards-release). This policy does not establish a Lab repository or grant membership. Its release requires internal checks, documented runs, independent review where feasible, rights clearance and the safety checks in [Asset review](docs/ASSET_REVIEW.md). Organisation owners approve access, classification, merges and releases, and set the scope of v3.0 and later work.

The [architecture companion](docs/papers/QPathformer_Architecture_and_Experimental_Specification_v1.0.pdf) is a new editorial edition derived from the preserved architecture proposal v0.3, with identified specification patch v0.3.1 clarifications and links to completed component evidence. [Routed States](docs/papers/QPathformer_Main_Paper_v1.0.pdf) is the separate main findings paper, consolidating the completed studies. Both carry the research edition v1.0 label. The replacement removes editorial review labels without changing the scientific claims or limitations. Participation and publication procedures remain in release documentation. A version label does not establish an experimental result or grant permission to publish.

The [research cycle](docs/RESEARCH_CYCLE.md) explains the repeating sequence: public edition n accepts permitted contributions; edition n+1 begins in a private Lab; an approved selection may later become public; retained work and the following private edition remain separately controlled. Strategic is an audience and workstream, not a mandatory separate public version number. Access-PoD document Versions A/B/C and the Enterprise release numbers are independent naming schemes.

## Audiences

Public, Enterprise/Lab and Strategic are participation/access categories independent of the architecture’s States 1, 2 and 3. “Internal development” describes a separately authorised project role, not employment status or organisation-owner privileges.

| Classification | Audience | Intended location |
| --- | --- | --- |
| Public | Anyone | Approved public research repository and release |
| Enterprise — Lab participants | Approved Lab participants and organisation owners, within explicit grants | Proposed private Research Lab repository or approved private asset store |
| Strategic — internal development | Specifically authorised internal Q-Pathformer developers; owners retain approval/admin authority | Proposed separate private owner-controlled repository or asset store |

The proposed research Lab and public Enterprise Standards are separate projects in the wider Q-Pathformer programme. No technical integration, dependency or shared membership is established by these policies. Use Private Research Lab in ordinary prose. The table defines the Enterprise/Lab category; it does not identify the Enterprise Standards project.

Enterprise is a project access tier, not a GitHub product subscription or GitHub `internal` visibility. Enterprise and Strategic access labels also do not grant the separate production or commercial permissions described by the Q-Pathformer Platform License; those require their own applicable agreement. Lab participation does not grant organisation ownership or access to Strategic materials. An approved internal developer need not become an organisation owner; use an explicit restricted team or repository grant for that role. Owners already have administrative access; audit installed applications, service identities and any elevated organisation roles for equivalent access.

Repository visibility applies to its contents, branches, PRs and release assets. A public PR cannot contain private Enterprise or Strategic attachments. Labels, directories, CODEOWNERS and private branch names do not provide an access boundary. Keep restricted material in a separate private location with explicit grants. Base organisation permission should be None before admitting Lab participants; review existing repository, team, app and collaborator permissions as part of that change.

## Eligibility for Lab access

At least two distinct, substantive qualifying contributions merged into public Q-Pathformer research establish eligibility for an owner review. For the initial research v2.0 Lab, the public foundation is Research v1.0. Record the qualifying merges considered for each cycle and reassess access; this does not automatically reset the contribution count or carry membership forward. Each qualifying merge must enhance the repository and include suitable findings, documentation and reproducibility evidence. Classical results, QPU runs, simulator studies, useful reproductions, documented negative results and evidence-based corrections can qualify. Access does not depend on buying QPU time.

The owner records why each merge qualifies. Trivial edits, duplicate results, artificial splitting of one change and unreviewed submissions do not automatically qualify. Useful small corrections remain welcome without a promise of eligibility credit. Contributions must comply with the existing incoming-contribution and redistribution terms; this policy does not open a blanket code submission licence.

After two qualifying merges, an owner reviews provenance, reproducibility, rights, safety, conduct and the proposed participation scope. Access is granted only after that approval and acceptance of the Lab's access conditions. Record the approved repositories, role, start date, review date and owner. Record a reason if access is deferred and allow the applicant to provide missing evidence. A merger, review count or bot never grants membership automatically.

Read access is the default Lab participant role. Additional write or maintainer authority requires a separate owner decision. Do not add a participant as an organisation owner merely to satisfy a review requirement. Recheck access periodically and when roles change; remove access when participation ends. Revocation cannot recall downloaded copies or revoke previously granted public licences.

## Findings and asset review

Contributors propose findings and supporting evidence through the [contribution process](CONTRIBUTING.md). Treat every proposed change, adapter, checkpoint, weight file, dataset, script and document as a candidate asset before merge. Record immutable identity, provenance, rights, intended audience and review outcome. Only an owner may approve classification and a transition to a wider audience.

An owner reviews the proposed diff and the actual assets together. A public findings PR contains only material already safe to disclose publicly; restricted evidence goes through a private intake arranged by an owner. An owner imports approved findings into the appropriate repository PR with contributor attribution. A PR cannot make already disclosed material private retrospectively.

Independent review is preferred for substantive research, safety and rights decisions. With one owner, owner-authored substantive work needs a second qualified reviewer before an independent approval can be claimed. If work must proceed without that review, record a named exception, its scope and reason and keep the independent-review requirement unresolved for publication. Never describe self-review as independent approval.

## Strategic work and agreed retention

Strategic development is optional and may run alongside a Lab cycle. Lab work does not have to pass through this workstream before publication review. Strategic materials are restricted to specifically authorised internal Q-Pathformer developers. Organisation owners retain approval and administrative authority. An internal-development appointment and explicit access grant are separate from Lab admission.

Strategic work is reserved for specifically authorised internal developers and may concern model internals, safety protocols and separately specified cryptographic derivation/re-derivation or evidence-protection mechanisms. This identifies a proposed research scope; it does not assert that those mechanisms exist, are validated, or are disclosed in a public paper.

For contributed private material proposed for Strategic retention or a new Strategic use, record an asset-specific agreement with the contributor or applicable rights holder and the authorised project representative. Identify the permitted purpose, audience, duration and disclosure terms, together with any additional permissions required. Existing public permissions remain unchanged. Identify the actual rights holder where different from the submitter. The [retention review template](templates/STRATEGIC_RETENTION_REVIEW.md) records an agreement; completing it does not create one. Classification, merge and membership imply no assignment, exclusivity, confidentiality, incoming licence or additional restriction on existing public content. If agreement is missing, defer the proposed new use; existing rights and obligations remain applicable.

## Merges and publication

Changes to `main` require a pull request, resolved review conversations, an up-to-date branch and the GitHub Actions checks **Documentation links** and **Content scope**. Force pushes and deletion of `main` are blocked; no bypass actors are configured. See [repository checks](.github/CHECKS.md) for the bounded coverage and [live rules](https://github.com/qpathformer/qpathformer-classical-research-v1.0/rules).

The single-maintainer configuration requires zero approving reviews. An owner inspects the diff, evidence and rights before merging; the merge is the recorded owner decision. This setting permits an owner to merge their own PR once checks pass and discussions are resolved. It does not establish independent review, approve private access or validate a scientific claim. Record any substantive review exception as described above. Reviewers and bots cannot grant Lab membership through a merge.

Future private repositories need their own enforceable controls and access review. Check the applicable GitHub plan before provisioning them; written policy and public-repository rules do not protect another repository.

Public release uses a curated, approved snapshot and asset manifest. The intended recurring route publishes a separate public selection while retaining private Lab history and Strategic work in their restricted locations. Review all reachable history, branches, tags, releases and Actions material before making an existing repository public. Preserve private development history if it contains withheld material. The [release policy](docs/RELEASE_POLICY.md) defines the public transition and the next private cycle.

Not all materials will be published. Owners may retain material for a later version or withhold it because of rights, privacy, safety, reproducibility or strategic considerations. Access does not promise a release date, access to future versions, paper authorship or disclosure of every artifact. Existing applicable licences remain in force.
