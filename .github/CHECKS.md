# Research repository checks and merge rules

The public Research v1.0 `main` branch requires a pull request, resolved review
conversations, an up-to-date branch and these GitHub Actions jobs:

| Required check | Bounded coverage |
| --- | --- |
| Documentation links | Local links/images and Markdown/HTML anchors in the tracked live documents selected by `.github/ci/documentation-scope.json`; exact filename case and repository boundaries |
| Content scope | Byte lengths and SHA256 identities in the current research content scope, licence adoption, scope revision, Research Approach scope and trademark adoption records; revision `before` identities checked at their recorded historical source commit |

The [live rules](https://github.com/qpathformer/qpathformer-classical-research-v1.0/rules)
block force pushes and deletion of `main`, with no bypass actors. Zero approving
reviews are required for this single-maintainer repository. Owner review and a
deliberate merge remain required by [governance](../GOVERNANCE.md); a self-merge
does not establish independent review or automatically grant Lab access.

Both jobs run for every PR to `main`, push to `main` and manual dispatch, without
path filters. They use pinned actions, read-only repository permissions, no
persisted checkout credentials, no repository secrets and GitHub-hosted runners.
They use `pull_request`, not `pull_request_target`, and do not run study software
or model loaders. GitHub may require an owner's approval for external-fork runs.
Workflow/helper changes themselves need review before execution.

## Run locally

Use Python 3.12 and Git from the repository root. Stage intended new files before
checking because the link checker uses the Git-tracked inventory. Preserve exact
published bytes: set `git config core.autocrlf false` before checkout; do not
normalise historical files to repair a hash mismatch.

```sh
python -m pip install --require-hashes -r .github/ci/requirements.txt
python -B -m unittest discover -s .github/ci/tests -v
python -B .github/ci/check_readme_links.py --scope-file .github/ci/documentation-scope.json
python -B .github/ci/check_content_scope.py
```

The content verifier needs the historical source commit named in the revision
record; use a full clone or fetch that history. Local success does not replace
the required GitHub Actions checks on the current PR head. Coordinate job-name
and ruleset changes so PRs do not wait for a removed check.

## Coverage and scope maintenance

The link job is offline: external URLs, paths inside code examples and documents
outside the explicit current selection need separate review. Historical study
READMEs retain their original package-relative context. Add new live entry-point
documents to the selection when appropriate; do not rewrite historical evidence
merely to expand a navigation check.

The identity check validates declared bytes, not authorship, licence authority,
scientific correctness, safety, private-access configuration, release downloads
or completeness of every historical record. Historical record contents refer
to their stated source editions. When changing current scoped prose, preserve
the prior scope/adoption/revision records, refresh current identities and record
the previous source commit. Keep published tags and sealed assets unchanged.

CI helpers have a scoped [MIT notice](ci/LICENSE) and [source record](ci/SOURCE.md).
Original current policy/helper prose is identified in the
[research content scope](../RESEARCH_V1_CONTENT_LICENSE_SCOPE.json); other material
retains its own applicable terms. Passing checks grants no incoming licence,
scientific endorsement or private membership.
