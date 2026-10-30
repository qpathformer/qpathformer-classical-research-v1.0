# Q Pathformer research governance

Proposed policy for owner adoption. Q-Pathformer publishes reviewed research editions while developing the next edition privately. Public access, research validity, licensing and eligibility for private participation are separate decisions. The [research approach](docs/RESEARCH_APPROACH.md) is a standalone release document; repository governance does not alter the scientific paper.

## Editions and authority

The v1.0 research edition is intended for public release when its main paper, supporting studies, rights and repository contents are ready. Q-Pathformer Lab is the working name for private v2.0 research. Its release requires internal checks, documented runs, independent review where feasible, rights clearance and the safety checks in [Asset review](docs/ASSET_REVIEW.md). Organisation owners approve access, classification, merges and releases, and set the scope of v3.0 and later work.

The [architecture companion](docs/papers/QPathformer_Architecture_and_Experimental_Specification_v1.0.pdf) is a new editorial edition derived from the preserved architecture proposal v0.3, with identified specification patch v0.3.1 clarifications and links to completed component evidence. [Routed States](docs/papers/QPathformer_Main_Paper_v1.0.pdf) is the separate main findings paper, consolidating the completed studies. Both remain drafts pending final review. Participation and publication procedures remain in release documentation. A version label does not establish an experimental result or grant permission to publish.

## Audiences

| Classification | Audience | Intended location |
| --- | --- | --- |
| Public | Anyone | Approved public research repository and release |
| Enterprise | All approved Lab participants and organisation owners | Private Q-Pathformer Lab repository or approved private asset store |
| Strategic | Q-Pathformer organisation owners only | Separate private owner-controlled repository or asset store |

Enterprise is a project access tier, not a GitHub product subscription or GitHub `internal` visibility. Enterprise and Strategic access labels also do not grant the separate production or commercial permissions described by the Q-Pathformer Platform License; those require their own applicable agreement. Lab participation does not grant organisation ownership or access to Strategic materials. Owners already have administrative access; audit installed applications, service identities and any elevated organisation roles for equivalent access.

Repository visibility applies to its contents, branches, PRs and release assets. A public PR cannot contain private Enterprise or Strategic attachments. Labels, directories, CODEOWNERS and private branch names do not provide an access boundary. Keep restricted material in a separate private location with explicit grants. Base organisation permission should be None before admitting Lab participants; review existing repository, team, app and collaborator permissions as part of that change.

## Eligibility for Lab access

At least two distinct, substantive contributions merged into the public v1.0 research repository establish eligibility for an owner review. Each qualifying merge must enhance the repository and include suitable findings, documentation and reproducibility evidence. Classical results, QPU runs, simulator studies, useful reproductions, documented negative results and evidence-based corrections can qualify. Access does not depend on buying QPU time.

The owner records why each merge qualifies. Trivial edits, duplicate results, artificial splitting of one change and unreviewed submissions do not automatically qualify. Useful small corrections remain welcome without a promise of eligibility credit. Contributions must comply with the existing incoming-contribution and redistribution terms; this policy does not open a blanket code submission licence.

After two qualifying merges, an owner reviews provenance, reproducibility, rights, safety, conduct and the proposed participation scope. Access is granted only after that approval and acceptance of the Lab's access conditions. Record the approved repositories, role, start date, review date and owner. Record a reason if access is deferred and allow the applicant to provide missing evidence. A merger, review count or bot never grants membership automatically.

Read access is the default Lab participant role. Additional write or maintainer authority requires a separate owner decision. Do not add a participant as an organisation owner merely to satisfy a review requirement. Recheck access periodically and when roles change; remove access when participation ends. Revocation cannot recall downloaded copies or revoke previously granted public licences.

## Findings and asset review

Contributors propose findings and supporting evidence through the [contribution process](CONTRIBUTING.md). Treat every proposed change, adapter, checkpoint, weight file, dataset, script and document as a candidate asset before merge. Record immutable identity, provenance, rights, intended audience and review outcome. Only an owner may approve classification and a transition to a wider audience.

An owner reviews the proposed diff and the actual assets together. A public findings PR contains only material already safe to disclose publicly; restricted evidence goes through a private intake arranged by an owner. An owner imports approved findings into the appropriate repository PR with contributor attribution. A PR cannot make already disclosed material private retrospectively.

Independent review is preferred for substantive research, safety and rights decisions. With one owner, owner-authored substantive work needs a second qualified reviewer before an independent approval can be claimed. If work must proceed without that review, record a named exception, its scope and reason and keep the independent-review requirement unresolved for publication. Never describe self-review as independent approval.

## Merges and publication

Require a reviewed PR, resolved discussions, current evidence and owner approval for protected branches. Use enforceable GitHub rules where the plan supports them; while private branch protection is unavailable, restrict write/admin to owners and maintain a manual review record. A written rule alone does not enforce access or merge controls.

Public release uses a curated, approved snapshot and asset manifest. Review all reachable history, branches, tags, releases and Actions material before making an existing repository public. Preserve private development history if it contains withheld material. The [release policy](docs/RELEASE_POLICY.md) defines the public transition and the next private cycle.

Not all materials will be published. Owners may retain material for a later version or withhold it because of rights, privacy, safety, reproducibility or strategic considerations. Access does not promise a release date, access to future versions, paper authorship or disclosure of every artifact. Existing applicable licences remain in force.
