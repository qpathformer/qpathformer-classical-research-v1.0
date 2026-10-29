# Included material and rights status

**Private staging, updated 29 October 2026.** The Git tree supplies project documentation and scope records. The [study-v0.9.5 release](https://github.com/qpathformer/qpathformer-classical-research/releases/tag/study-v0.9.5) supplies separately identified study, documentation and code downloads. “Public report edition” identifies an editorial edition; access to this repository and its downloads remains private.

| Reader route | Available material | Rights boundary |
| --- | --- | --- |
| **Study** | QPATH RPT011 public report edition 1, as PDF, Word and report package. | The specified original report content is licensed under CC BY 4.0; see [report scope](REPORT_LICENSE_SCOPE.json). |
| **Documentation** | Current explanations, guides, illustrations, study summary, scope/provenance records and the unchanged QPATH-ARCH-001 PDF; also the preserved original documentation ZIP. | Selected original documentation has a separate [CC BY 4.0 scope](DOCUMENTATION_LICENSE_SCOPE.json) with its own adoption record. The ZIP and current tree contain mixed material, with no blanket grant. See [license scope](LICENSE_SCOPE.md). |
| **Code** | Selected implementation and ETEL sources, package instructions and verification/startup tools, in the named Code and ETEL ZIP. | Platform License 1.0 applies to the listed Python files; supporting files retain their applicable terms. See [code scope](CODE_LICENSE_SCOPE.json). |

The report and implementation files are release downloads rather than contents of this Git tree. GitHub's generated source archives contain the tagged documentation tree; use the named Code and ETEL ZIP for the implementation.

## Study report

Anthony Siljeg adopted CC BY 4.0 on 28 October 2026 for the public report's original prose, table presentation and seven study-result figures, to the extent he has authority over those rights. [REPORT_LICENSE_SCOPE.json](REPORT_LICENSE_SCOPE.json) preserves the decision and identifies the publisher's PDF/Word files.

The public edition retains the scientific findings and records its editorial omissions. Internal report files and private change records remain outside this distribution. Content licensed through the public edition remains reusable under that grant, including the same content appearing in an earlier report; previously omitted material and other surrounding content are not automatically added. Embedded fonts and specifically identified third-party material retain their applicable terms.

## Project documentation and historical ZIP

The original documentation ZIP preserves the 41 tracked files at commit `f9f4723e31b4944ccea16541cb0efc4c74cda841`. Its manifest, seal and bytes remain unchanged. Its proposed CC BY selection was not a package-wide license and remains unadopted.

The Git-tree [proposal](CC_BY_SCOPE_PROPOSAL.md) and [candidate record](cc_scope_proposal.json) are also retained unchanged from scope revision `461ea2383f0e333247ddfe664e187265a444b931`. That record identifies seven Markdown and eleven image candidates at that revision. The current documentation decision uses a new [20-file record](DOCUMENTATION_LICENSE_SCOPE.json) and [rights statement](DOCUMENTATION_RIGHTS.md). It neither rewrites the old proposal nor rebuilds the historical ZIP. Content licensed through the new selection retains that grant where it also appears in an older snapshot; the entire snapshot and older unselected material are not automatically licensed.

QPATH-ARCH-001 remains unchanged with its embedded copyright and [source provenance](docs/architecture/README.md). It is excluded as a document from the separate code, report and documentation grants; expression actually licensed through selected documentation or images remains reusable under that grant. The three-state concept image has separate generated-image/reference provenance; its inclusion in the new selection licenses only controlled expression and does not assert ownership of every generated element. Other architecture sources remain excluded.

## Selected code

The code attachment preserves 36 archived study Python files and adds two package-review tools. On 28 October 2026, the owner adopted the unchanged [Q-Pathformer Platform License 1.0](QPATHFORMER-PLATFORM-1.0.txt) for those 38 files, identified in [CODE_LICENSE_SCOPE.json](CODE_LICENSE_SCOPE.json). This covers the listed implementation/tests, inherited numerical kernels, incorporated ETEL core and review tools.

The grant does not automatically cover supporting Markdown/JSON documents or historical READMEs. The selection is not the complete historical standalone ETEL CLI/fixture/demo package or a turnkey reproduction archive. Its bounded startup and targeted check records do not establish full study reproduction, fresh-install portability or physical-QPU execution.

## Separately retained material

Generated datasets, trained models, weights/checkpoints, runtime trees and complete reproduction archives remain separately retained. They are not supplied or licensed as whole collections by this release. The later repository distribution will require an explicit material inventory and applicable rights for each selected addition.

Dependency records identify NumPy/SciPy and host requirements without redistributing installed packages or native libraries. Third-party material retains its applicable terms. SHA-256 seals verify bytes; they are not digital signatures, ownership certifications or proof of scientific reproduction.
