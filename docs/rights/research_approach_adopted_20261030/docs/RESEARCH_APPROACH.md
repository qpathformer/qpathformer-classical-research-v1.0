# Q Pathformer research approach

Draft release helper document for owner review. This approach describes participation, research evidence and the transition between public and private editions. It is separate from the v1.0 main paper and must not be appended to or treated as an amendment of that paper. The current main-paper candidate is the unchanged Architecture Update Research Proposal v0.3, pending its own revision.

## Public foundation and private research

The public v1.0 research edition will present the approved main paper, the supporting study collection and helper documents. Historical study reports remain individually identified and retain their original scientific limitations. A consolidated archive is a reading and provenance aid; it does not combine unlike experiments into a single new benchmark or establish additional results.

Q-Pathformer Lab is the proposed private environment for v2.0. Researchers may become eligible after at least two substantive merged public contributions that improve the repository with documented, reproducible findings. An organisation owner then reviews rights, reproducibility, safety and participation scope before granting access. Eligibility is not automatic admission. Useful classical runs, simulator work, physical QPU experiments and independent reproductions can all contribute.

Enterprise materials are accessible to approved Lab participants. Strategic materials are restricted to organisation owners and held separately. These audiences are defined by actual permissions, not labels. Enterprise and Strategic participation do not grant a commercial or production software licence; applicable code terms and any separate agreements still govern that use. Every proposed asset is reviewed and classified before merge, including code, adapters, weights, datasets and documentation. The full rules are in [Governance](../GOVERNANCE.md) and [Asset review](ASSET_REVIEW.md).

## Evidence required for research claims

Begin each study with a named question, feasible protocol, comparison methods, declared data splits and resource budget. Freeze final evaluation and selection rules before examining test outcomes. Record implementation versions and preserve failed, rejected, negative and inconclusive outcomes. Report uncertainty and the limits of any sample or numerical coverage.

For classical work, report the hardware, software environment, seeds, precision, batch policy, trainable modules, timing boundary, memory and data access. Separate routing, sampling and execution effects. Fair comparisons need explicit exposure, parameter, quality and resource conditions; a count reduction alone does not demonstrate a runtime improvement.

For quantum work, distinguish exact simulation, shot-based simulation and physical QPU execution. Record backend identity, transpilation settings, circuit and job identities, qubits, depth, shots and calibration context where available. Use independent correctness checks and information-matched classical controls where the claim requires them. State precisely what finite testing establishes. Physical advantage is a claim requiring measured evidence, not a consequence of using a quantum interface.

The supplied architecture draft proposes classical and bounded quantum research tracks. Proposed settings and schedules remain hypotheses and protocol choices until implemented and tested. Adoption of this participation approach authorizes no training run, paid compute job or publication of results. The main paper's research scope will be settled during its separate revision.

## Readiness and release cycle

1. Define the next edition's research questions and candidate assets privately. Owners set the scope and record unresolved decisions.
2. Review provenance, permissions, data access and execution risks before running a candidate. Use bounded pilots to estimate feasibility and resource costs.
3. Complete the registered runs, preserve reproducibility evidence and review claims against actual outcomes. Correctness, reproducibility and scientific benefit are separate findings.
4. Review every artifact for public disclosure, scientific support, rights and safety. Prepare a curated public release with a clear statement of omissions and limitations.
5. Publish the approved edition when ready. Owners define the next private edition, such as v3.0 after v2.0, and repeat the contribution and review process. Reassess access for that edition; earlier membership does not promise automatic access.

Not all research materials will be made available. Some may be retained for the next edition or withheld because of rights, privacy, safety, reproducibility or strategic considerations. Explain material omissions when possible without exposing restricted content. Public licences already granted are unaffected by later access decisions. See the [publication notice](PUBLICATION_NOTICE.md) and [release policy](RELEASE_POLICY.md).

## Licence and attribution

© 2026 Anthony Siljeg. The original prose in this standalone Q-Pathformer Research Approach is licensed under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/). The grant was adopted on 30 October 2026. See [rights and scope](RESEARCH_APPROACH_RIGHTS.md) and the [exact edition record](RESEARCH_APPROACH_LICENSE_SCOPE.json).

This scope excludes the main architecture paper as a document, code, adapters, weights, datasets, restricted Lab materials and third-party expression. Existing applicable grants remain unchanged. Alnotrea Labs and Q-Pathformer Initiative identify affiliation; no ownership transfer is stated.
