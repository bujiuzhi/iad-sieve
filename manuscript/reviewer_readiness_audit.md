# Reviewer Readiness Audit

Updated: 2026-06-18

## Scope

This audit evaluates whether the template-independent manuscript package is ready for target-journal selection and final-format conversion. It is not a manuscript file for journal upload. It should be used before binding the paper to a journal template and again before final submission.

Current decision: conditionally ready for target-journal selection; not ready for final upload.

## Audit Dimensions

| Dimension | Current status | Evidence in the package | Residual requirement before final upload |
| --- | --- | --- | --- |
| Contribution | Pass with bounded claims | The manuscript defines identity-agenda confusion, IAD-Bench, HNFMR, and risk-aware merge gating. | Keep the contribution framed as false-merge control, not broad method superiority. |
| Writing clarity | Pass for template-independent draft | The manuscript contains explicit problem formulation, notation, method details, result boundaries, limitations, and threats to validity. | Recheck section length and formatting after journal-template conversion. |
| Experimental strength | Conditional | Open-v2 evidence reports baseline HNFMR 0.790--0.999 and IAD-Risk HNFMR=0.000 on the reported held-out scope. | Release same-scope prediction files, threshold logs, checksums, and result tables before relying on full numerical audit. |
| Evaluation completeness | Conditional | The paper reports gold/proxy/silver strata, FMR, HNFMR, operating-point disclosure, scope compatibility, and claim-evidence boundaries. | Add full artifact-backed threshold grid, ablation suite, and manual-validation slice before stronger robustness or component-causality claims. |
| Method design soundness | Pass with stated boundaries | The method separates identity, agenda, and agenda-non-identity signals and exposes risk thresholds and cannot-link behavior. | Recheck threshold transfer and source-heldout behavior under the selected target journal's evidence expectations. |

## Reviewer Risk Register

| Reviewer concern | Risk level | Current mitigation | Remaining action |
| --- | --- | --- | --- |
| The paper overclaims beyond its evidence. | Medium | Abstract, introduction, results, limitations, and supplementary material explicitly restrict broad method-ranking and human-gold claims. | Keep unsupported claims out during template conversion and cover-letter customization. |
| Silver hard negatives may not be true non-identity labels. | Medium | The manuscript separates gold, proxy, silver, and future manual-validation layers. | Complete or release a manual-validation slice before claiming stronger label precision. |
| Result rows use different pair scopes. | Medium | The Open-v2 table is framed as a scope-bounded evidence snapshot, not a leaderboard. | Release matched prediction scopes before any stricter ranking claim. |
| Threshold results may be sensitive. | Medium | Fixed operating points and threshold-sensitivity evidence status are documented. | Release threshold grid files before claiming threshold stability. |
| Confidence intervals and statistical significance may be overread. | Medium | The manuscript reports point estimates and adds a statistical interpretation boundary that reserves bootstrap intervals, significance tests, and model-ranking claims for artifact-backed evidence. | Release bootstrap intervals, predefined tests, resampling logs, random seeds, and checksums before claiming interval-supported superiority. |
| First-screen submission materials may drift in claim scope. | Medium | Title, abstract, conclusion, cover letter, highlights, and keywords are checked for editorial claim alignment around the same problem, method, evidence snapshot, and claim boundary. | Re-run the editorial alignment gate after template conversion or journal-specific cover-letter edits. |
| Reproducibility depends on files outside Git. | Medium | Fixture rebuild, public-source commands, artifact manifest template, and checksums policy are documented. | Publish the L3 artifact release and link it in submission metadata. |
| Final upload may mismatch journal system fields. | High | A submission-system checklist records file, metadata, PDF, and artifact checks. | Confirm target journal, author metadata, funding statement, author contribution statement, permissions statement, template, and live system fields. |

## Claim-Evidence Check

| Claim class | Evidence status | Review stance |
| --- | --- | --- |
| Identity-agenda confusion is a concrete false-merge pathway. | Supported within Open-v2 hard-negative stress evidence. | Accept as a targeted failure-mode claim. |
| IAD-Risk suppresses hard-negative false merges in the reported setting. | Supported by the current evidence snapshot and bounded by artifact requirements. | Accept only under the stated Open-v2 scope. |
| IAD-Bench is a provenance-aware benchmark contract. | Supported by schema, label-stratum separation, fixture rebuild, and documentation. | Accept as a benchmark-contract contribution, not as human gold. |
| The method is broadly superior to all baselines. | Not claimed. | Keep absent unless all baselines share released prediction scope and stronger evidence. |
| The method is threshold-stable. | Not claimed. | Add only after threshold-grid artifact evidence exists. |
| The result has statistical significance or interval-supported superiority. | Not claimed. | Add only after bootstrap intervals, predefined tests, and checksum-fixed resampling logs exist. |
| Human validation is complete. | Not claimed. | Add only after reviewed slice, adjudication log, and agreement report exist. |

## Adversarial Self-Review Matrix

This matrix records the current reviewer-facing answer to the five required self-review dimensions. The status values are intentionally strict: `pass` means the present manuscript text and package evidence are sufficient for the bounded claim, `needs revision` means wording or structure must be tightened before final upload, and `needs new experiment` means stronger evidence is required before making the corresponding stronger claim.

| Dimension | Skeptical reviewer question | Status | Current evidence | Required revision or experiment before stronger claim |
| --- | --- | --- | --- | --- |
| Contribution self-review | What new knowledge does the paper give beyond ordinary entity matching or scientific representation scoring? | pass | The manuscript defines identity-agenda confusion, HNFMR, IAD-Bench label-strength separation, and risk-aware merge gating. | Keep the novelty framed as false-merge control and benchmark contract design, not broad model superiority. |
| Writing clarity self-review | Can a knowledgeable reader reproduce the method and understand each module's motivation? | pass | The method section defines identity, agenda, ANI, risk score, thresholds, feature groups, and provenance-aware masking. | Recheck length, figure placement, and title-page formatting after target-journal template conversion. |
| Experimental strength self-review | Are the reported gains meaningful against strong baselines under a fair interpretation? | needs new experiment | Open-v2 evidence reports representation baseline HNFMR 0.790--0.999, RoBERTa FMR 0.001/HNFMR 0.0001, and IAD-Risk HNFMR=0.000 on the reported held-out scope. | Release same-scope prediction files, threshold logs, checksums, and bootstrap intervals before claiming stronger comparative advantage. |
| Evaluation completeness self-review | Are ablations, metrics, datasets, and label strata sufficient for the claimed scope? | needs new experiment | The manuscript reports F1, FMR, HNFMR, label strata, scope compatibility, threshold-status boundaries, and manual-validation requirements. | Add artifact-backed ablations, threshold grid, manual-validation slice, and source-heldout package before stronger robustness or component-causality claims. |
| Method design soundness self-review | Does the method have realistic assumptions and a positive net benefit despite added complexity? | pass | The method exposes thresholds, cannot-link behavior, audit metadata, and explicit boundaries for silver labels and source transfer. | Reassess threshold transfer and deployment complexity after the selected journal route and external artifact are fixed. |

## Reviewer Response Matrix

This matrix anticipates likely reviewer questions and maps each answer to manuscript evidence and a conservative response boundary. It should be used to keep the cover letter, response letter, and final template conversion aligned with the same claim limits.

| Likely reviewer question | Response stance | Evidence location | Boundary to keep |
| --- | --- | --- | --- |
| Is identity-agenda confusion a new problem or only ordinary semantic similarity? | Treat it as a targeted false-merge failure mode in scholarly work deduplication. | Introduction, Problem Formulation, HNFMR definition, and contribution-evidence summary. | Do not claim a universal prevalence estimate across all scholarly corpora. |
| Why are silver hard negatives acceptable without complete human gold labels? | Use them as stress-test evidence and keep them separate from DeepMatcher gold identity labels. | IAD-Bench label layers, Open-v2 composition, limitations, and supplementary manual-validation protocol. | Do not call OpenAlex or OpenCitations labels human gold. |
| Are the result rows comparable if pair scopes differ? | Interpret the table as a scope-bounded evidence snapshot rather than a single leaderboard. | Scope compatibility table, operating-point disclosure, and result audit trail. | Do not claim broad method ranking until same released prediction scope is available. |
| Does the method beat strong supervised baselines? | Present RoBERTa as a strong baseline and keep the main claim at transparent false-merge control. | Main Open-v2 results, baseline section, and claim-evidence boundary. | Do not claim SOTA or universal superiority. |
| Are the reported differences statistically significant? | Treat the Open-v2 values as point estimates for a fixed evidence snapshot. | Statistical interpretation boundary and supplementary uncertainty requirements. | Do not claim confidence intervals, significance, or interval-supported ranking until bootstrap and test artifacts are released. |
| Is the mechanism causal without full ablation output? | State that current evidence is mechanism-consistent and that causal ablation claims require artifacts. | Mechanism evidence table and supplementary uncertainty and ablation requirements. | Do not claim completed component causality before no-gate, no-ANI, and single-space variants are released. |
| Can readers reproduce the reported numbers without raw data in Git? | Separate fixture-level code reproduction from L2/L3 result-level artifact reproduction. | Data and Code Availability, supplementary reproduction levels, artifact manifest template, and checksums policy. | Do not imply full numerical audit without external artifact release. |

## Audit Cycle 1: Claim Discipline

Outcome: pass with residual artifact requirements.

The manuscript avoids unsupported broad-superiority, human-gold, and threshold-stability claims. The remaining risk is not wording but evidence availability: full numerical audit still depends on external artifacts with predictions, logs, tables, and checksums.

## Audit Cycle 2: Submission Readiness

Outcome: blocked for final upload.

The template-independent package is internally consistent, but final upload remains blocked until the target journal, journal template, author metadata, corresponding-author metadata, funding statement, author contribution statement, third-party material permission statement, final template-specific PDFs, live submission-system fields, and artifact release link are completed.

## Audit Cycle 3: Q2/B Acceptance Gate

Outcome: blocked for Q2/B completion; acceptable for conservative target-journal selection.

From a skeptical reviewer perspective, the manuscript can be considered for a conservative target-journal route only if its claims remain bounded to the current Open-v2 evidence snapshot. It should not be described as Q2/B-complete until the remote reproducibility, strong model matrix, model superiority, innovation depth, novelty and prior-art positioning, and claim lockdown gates are all closed with artifact-backed evidence.

The current manuscript therefore keeps its strongest claims limited to identity-agenda false-merge control under stratified evidence. It does not claim SOTA performance, complete threshold stability, complete human gold validation, or broad source-heldout generalization.

## Audit Cycle 4: Final Package Hygiene

Outcome: pass for anonymous pre-submission package hygiene; blocked for final upload metadata.

The anonymous package hygiene gate checks that generated submission packages exclude raw data, experiment outputs, local caches, credentials, author email addresses, ORCID values, personal account URLs, local absolute paths, and development process notes. This closes a common desk-check risk for anonymous review, but it does not replace the final-upload metadata gate because the target journal, authors, corresponding author, final template-specific PDFs, and artifact release URL or DOI remain unresolved.

## Audit Cycle 5: Editorial Desk Check

Outcome: pass for template-independent first-screen claim alignment; must be repeated after journal-specific edits.

The editorial desk check compares the title, abstract, conclusion, cover letter, highlights, and keywords against the same core story: IAD-Risk addresses identity-agenda confusion in scholarly work deduplication; IAD-Bench separates gold, proxy, and silver evidence; the Open-v2 evidence snapshot supports targeted false-merge suppression; and the paper does not claim broad method ranking, statistical superiority, threshold stability, cluster-level deployment quality, or human-gold validation. This keeps the editorial claim alignment consistent before the manuscript reaches external review.

## Audit Cycle 6: Reviewer Rebuttal Boundary

Outcome: pass for conservative response planning; blocked for stronger evidence claims.

This cycle separates reviewer questions that can be answered from the current manuscript from questions that require additional artifact-backed evidence. The status labels are: `ready_to_answer` when the manuscript already contains direct evidence, `limited_answer` when the response must stay within the present Open-v2 evidence snapshot, and `do_not_answer_as_claim` when the answer would require new experiments, public artifact files, author declarations, permission declarations, or target-journal confirmation before it can appear as a manuscript claim.

| Reviewer challenge | Response status | safe response scope | must-not-claim boundary |
| --- | --- | --- | --- |
| The problem may be ordinary semantic similarity rather than a distinct failure mode. | `ready_to_answer` | Point to identity-agenda confusion, HNFMR, and the label-strength separation in IAD-Bench. | Do not claim a universal prevalence estimate across scholarly databases. |
| Silver hard negatives may contain noisy non-identity labels. | `limited_answer` | State that silver labels are stress-test evidence and are not presented as human gold. | Do not claim complete human validation until a reviewed slice, adjudication log, and agreement report are released. |
| The table mixes pair scopes and may not support a ranking. | `limited_answer` | Treat Open-v2 as a scope-bounded evidence snapshot and cite operating-point and scope-compatibility disclosures. | Do not claim method ranking, SOTA performance, or interval-supported superiority without same-scope prediction artifacts and bootstrap logs. |
| The mechanism may not be causal without ablations. | `do_not_answer_as_claim` | Use only the current mechanism-consistent wording. | Do not claim completed component causality before no-gate, no-ANI, single-space, and threshold-grid artifacts are released. |
| The result cannot be fully reproduced from Git alone. | `limited_answer` | Distinguish fixture-level code reproduction from L2/L3 artifact reproduction. | Do not imply full numerical audit until the external artifact release URL or DOI, manifest, and checksums are available. |
| The paper is ready for final upload. | `do_not_answer_as_claim` | State that the anonymous pre-submission package validates, but final upload is still gated. | Do not state final-upload readiness until target journal, author metadata, funding statement, author contribution statement, permissions statement, final PDFs, live system fields, and artifact release link are complete. |

## Revision Trigger Register

This register converts likely reviewer pressure into mandatory edits. Each reviewer concern triggers a concrete manuscript revision rather than a stronger unsupported claim. If the evidence listed in the third column is absent, revise the relevant manuscript text to weaken the claim, add artifact-backed evidence, or keep the limitation explicit. The revision rule is: do not upgrade the abstract, introduction, conclusion, cover letter, or highlights until the required evidence and final-upload metadata are complete.

| Trigger | Required revision action | Evidence required before stronger wording | Claim boundary |
| --- | --- | --- | --- |
| Contribution trigger: reviewers treat identity-agenda confusion as ordinary semantic similarity. | Tighten the problem framing around false-merge control, HNFMR, and label-strength separation. | A clearer novelty comparison against ordinary entity matching and representation-only scoring. | Do not claim universal prevalence or broad task replacement. |
| Writing clarity trigger: reviewers cannot reproduce the method from the paper. | Expand notation, feature construction, thresholding, and artifact pointers in the method and supplementary material. | Runnable commands, schema contracts, fixture rebuilds, and manifest-linked artifacts. | Do not imply full numerical audit from Git-only files. |
| Experimental strength trigger: reviewers ask whether gains over strong baselines are meaningful. | Keep the result as a bounded Open-v2 evidence snapshot or add stronger same-scope baseline evidence. | Same-scope prediction files, metric tables, threshold logs, checksums, and bootstrap intervals. | Do not claim SOTA, broad superiority, or interval-supported ranking before artifacts exist. |
| Evaluation completeness trigger: reviewers request ablations, threshold sensitivity, or manual validation. | Move unsupported mechanism statements to limitations or add the missing experiment artifacts. | Ablation suite, threshold sensitivity grid, manual validation slice, adjudication log, and agreement report. | Do not claim component causality, threshold stability, or human-gold validation without these files. |
| Method design soundness trigger: reviewers argue the gate adds complexity or unrealistic assumptions. | Clarify deployment assumptions, cannot-link behavior, risk thresholds, and the net benefit of false-merge control. | Source-heldout checks, topic-heldout checks, realistic operating points, and failure-case analysis. | Do not claim robust cross-source transfer before split-readiness and source-heldout evidence are defensible. |

## Audit Cycle 7: Journal Fit and Novelty Desk Check

Outcome: pass for a conservative Data & Knowledge Engineering route; blocked for a stronger Information Systems or broad Q2/B claim until artifact-backed evidence is complete.

This cycle checks desk-rejection risk before final template binding. The current target-journal scope fit is strongest for Data & Knowledge Engineering because the manuscript is framed around data engineering, knowledge engineering, entity matching, benchmark contracts, and reproducible data-processing. Information Systems remains a stretch route because it would require a stronger same-scope experimental package, released prediction files, threshold logs, and broader systems-oriented evidence. Scientometrics remains a domain backup because it would require stronger science-of-science interpretation and manual-validation evidence.

The novelty beyond ordinary entity matching should be stated as a bounded combination of identity-agenda confusion, HNFMR, label-strength-aware IAD-Bench construction, and risk-aware merge gating. This positioning is stronger than presenting another similarity scorer, but it must not be inflated into broad method superiority, SOTA ranking, or universal scholarly deduplication coverage. The practical decision is therefore to keep the DKE route active, treat Information Systems as blocked until the L3 artifact package and stronger baselines are complete, and treat Scientometrics as a backup that would need a domain-facing rewrite.

## Audit Cycle 8: Pair-to-Cluster Claim Lockdown

Outcome: pass for template-independent first-screen claim lockdown; blocked for cluster-level deployment claims until artifact-backed audits are released.

The pair-to-cluster lockdown prevents pair-level metrics from being read as cluster-level deployment quality. The abstract, method, limitations, conclusion, cover letter, highlights, and supplementary material keep the current claim at pair-level false-merge control under the Open-v2 evidence snapshot. Stronger cluster-level claims require cluster artifacts that include `cluster_metric_summary`, `cannot_link_audit`, cluster assignments, cannot-link coverage, and cluster contamination rate.

The first-screen materials carry the same boundary. The cover letter states that the manuscript does not claim cluster-level deployment quality without cluster artifacts. The highlights state that cluster-level claims require artifact-backed audits. The conclusion states that cluster-level artifact audits are future validation requirements before broad method ranking. This keeps cover letter, highlights, and conclusion aligned with the pair-to-cluster evidence boundary in the main manuscript.

## Audit Cycle 9: Artifact Row-Level Result Audit

Outcome: pass for release-template and validator coverage; blocked for final numerical audit until the external artifact release is populated and linked.

This cycle checks whether the external result package can support a row-by-row reviewer audit of the main Open-v2 result table. The release validator now treats `open_v2_main_results` as a schema-bearing artifact rather than a generic file: `tables/open_v2_main_results.csv` must include per-row denominator counts, per-row threshold source, and scope label used in the main table. This prevents a release from passing only because the CSV exists and has a matching checksum.

The reviewer-facing interpretation is narrow. A valid `open_v2_main_results` file lets reviewers trace each reported row to its denominator, operating-point source, and evaluated scope. It does not by itself establish broad method ranking, confidence intervals, threshold stability, component causality, human-gold validation, or cluster-level deployment quality. Those stronger claims remain gated by the optional artifact rows and their checksums.

The mandatory command for this gate is `python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release`. The gate should be run after `populate_artifact_release.py` and `finalize_artifact_release.py`, because the finalizer refreshes manifest SHA256 values and `validate_artifact_release.py` checks both checksums and the `open_v2_main_results` row-level schema.

## Minimum Gate Before Final Upload

The manuscript should not be uploaded to a journal system until all of the following are true:

1. `submission_metadata.yml` contains the selected target journal and completed author metadata.
2. `main.tex` is converted to the selected journal template and rebuilt.
3. `supplementary_material.tex` is rebuilt after any final source edits.
4. The artifact release has a real URL or DOI, validates against its checksum file, and records the same repository commit used by the final manuscript package.
5. The funding statement, author contribution statement, permissions statement, data/code availability statement, and journal-specific research data statement are complete and consistent with the live submission system, with the repository URL, repository commit, and artifact URL or DOI embedded in the availability statements.
6. `python manuscript/scripts/validate_manuscript.py --strict-latex` passes.
7. `python manuscript/scripts/validate_submission_package.py --final-upload` passes.
8. `submission_system_checklist.md` has been checked against the live journal system.
9. The Q2/B acceptance gate is either fully ready or the manuscript title, abstract, cover letter, and conclusion avoid any Q2/B-complete or broad-superiority wording.
