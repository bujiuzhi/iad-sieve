# Reviewer Readiness Audit

Updated: 2026-06-19

## Scope

This audit evaluates whether the template-independent manuscript package is ready for target-journal selection and final-format conversion. It is not a manuscript file for journal upload. It should be used before binding the paper to a journal template and again before final submission.

Current decision: conditionally ready for target-journal selection; not ready for final upload.

## Audit Iteration Summary

Completed audit cycles: 21.

Highest current reviewer-facing risks: final-upload metadata, target-journal template binding, DKE author biography and photograph materials, external artifact release, artifact release README completeness, artifact release commit validity, prediction artifact schema drift, generative AI declaration consistency, fixture/live evidence confusion, live submission-system text consistency, Git-only fixture reproducibility, source-to-PDF package consistency, final-upload source-control package binding, and stronger evidence gates.

Current stopping rule: do not claim Q2/B completion or final-upload readiness until `python manuscript/scripts/validate_submission_package.py --final-upload` passes and a real artifact URL or DOI is recorded.

Non-code external inputs still required: author metadata, DKE author biography and photograph materials if that route is selected, target-journal confirmation, funding statement, author contribution statement, permissions statement, generative AI declaration, live submission-system fields, and artifact release URL or DOI.

Next revision trigger: repeat the editorial desk check after target-journal template binding, cover-letter customization, or artifact-link insertion.

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
| Result rows use different pair scopes. | Medium | The Open-v2 table is framed as a scope-bounded evidence snapshot, not a comparative ranking. | Release matched prediction scopes before any stricter ranking claim. |
| Threshold results may be sensitive. | Medium | Fixed operating points and threshold-sensitivity evidence status are documented. | Release threshold grid files before claiming threshold stability. |
| Confidence intervals and statistical significance may be overread. | Medium | The manuscript reports point estimates and adds a statistical interpretation boundary that reserves bootstrap intervals, significance tests, and model-ranking claims for artifact-backed evidence. | Release bootstrap intervals, predefined tests, resampling logs, random seeds, and checksums before claiming interval-supported superiority. |
| First-screen submission materials may drift in claim scope. | Medium | Title, abstract, conclusion, cover letter, highlights, and keywords are checked for editorial claim alignment around the same problem, method, evidence snapshot, and claim boundary. | Re-run the editorial alignment gate after template conversion or journal-specific cover-letter edits. |
| Live submission-system text may drift from source files. | Medium | The final-upload information request and submission-system checklist require title, abstract, keywords, and highlights to be copied from source files and previewed in the live submission system. | Mark `submission_system_files_verified` true only after these fields match `main.tex`, `keywords.md`, and `highlights.md` in the live system. |
| Generative AI declaration may be missing or inconsistent with the publisher policy. | Medium | Submission metadata, final-upload information request, target-journal shortlist, and submission-system checklist now require AI-tool use status, author responsibility confirmation, AI authorship exclusion, and machine-generated figure/artwork status. | Complete the final journal-specific declaration wording and keep it consistent across the manuscript, metadata, and live submission system. |
| DKE author biographies and photographs may be missing at upload. | Medium | The target-journal shortlist, final-upload information request, submission metadata, and submission-system checklist now track author biographies and passport-type photographs as DKE-specific final-upload materials. | Collect author-approved biography text and photograph files after author order is confirmed and keep them out of anonymous preflight packages. |
| Test fixtures may be mistaken for current Q2/B evidence. | Medium | The manuscript and audit package distinguish fixture-level code-path checks from live result artifacts and final-upload metadata. | Treat test fixtures, example summaries, and generated fixture rows as validator coverage only unless they are regenerated from current live artifacts, current commit metadata, and the selected target-journal route. |
| Reproducibility depends on files outside Git. | Medium | Fixture rebuild, public-source commands, artifact manifest template, and checksums policy are documented. | Publish the L3 artifact release and link it in submission metadata. |
| Final upload may mismatch journal template or system fields. | High | A submission-system checklist records file, metadata, PDF, artifact, source-archive, and template-binding checks. | Confirm target journal, set `target_journal_template_bound`, rebuild the final template source and PDFs, and verify the live system fields. |

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
| Are the result rows comparable if pair scopes differ? | Interpret the table as a scope-bounded evidence snapshot rather than a single comparative ranking. | Scope compatibility table, operating-point disclosure, and result audit trail. | Do not claim broad method ranking until same released prediction scope is available. |
| Does the method beat strong supervised baselines? | Present RoBERTa as a strong baseline and keep the main claim at transparent false-merge control. | Main Open-v2 results, baseline section, and claim-evidence boundary. | Do not claim SOTA or universal superiority. |
| Are the reported differences statistically significant? | Treat the Open-v2 values as point estimates for a fixed evidence snapshot. | Statistical interpretation boundary and supplementary uncertainty requirements. | Do not claim confidence intervals, significance, or interval-supported ranking until bootstrap and test artifacts are released. |
| Is the mechanism causal without full ablation output? | State that current evidence is mechanism-consistent and that causal ablation claims require artifacts. | Mechanism evidence table and supplementary uncertainty and ablation requirements. | Do not claim completed component causality before no-gate, no-ANI, and single-space variants are released. |
| Can readers reproduce the reported numbers without raw data in Git? | Separate fixture-level code reproduction from L2/L3 result-level artifact reproduction. | Data and Code Availability, supplementary reproduction levels, artifact manifest template, and checksums policy. | Do not imply full numerical audit without external artifact release. |

## Audit Cycle 1: Claim Discipline

Outcome: pass with residual artifact requirements.

The manuscript avoids unsupported broad-superiority, human-gold, and threshold-stability claims. The remaining risk is not wording but evidence availability: full numerical audit still depends on external artifacts with predictions, logs, tables, and checksums.

## Audit Cycle 2: Submission Readiness

Outcome: blocked for final upload.

The template-independent package is internally consistent, but final upload remains blocked until the target journal, journal template, author metadata, corresponding-author metadata, funding statement, author contribution statement, third-party material permission statement, generative AI declaration, final template-specific PDFs, live submission-system fields, and artifact release link are completed.

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
| The paper is ready for final upload. | `do_not_answer_as_claim` | State that the anonymous pre-submission package validates, but final upload is still gated. | Do not state final-upload readiness until target journal, author metadata, funding statement, author contribution statement, permissions statement, generative AI declaration, final PDFs, live system fields, and artifact release link are complete. |

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

This cycle checks whether the external result package can support a row-by-row reviewer audit of the main Open-v2 result table. The release validator now treats `open_v2_main_results` as a schema-bearing artifact rather than a generic file: `tables/open_v2_main_results.csv` must include per-row denominator counts, per-row threshold source, scope label used in the main table, automatic merge count, block count, defer count, automatic merge coverage, and defer rate. This prevents a release from passing only because the CSV exists and has a matching checksum.

The reviewer-facing interpretation is narrow. A valid `open_v2_main_results` file lets reviewers trace each reported row to its denominator, operating-point source, evaluated scope, and selective-decision coverage. It does not by itself establish broad method ranking, confidence intervals, threshold stability, component causality, human-gold validation, or cluster-level deployment quality. Those stronger claims remain gated by the optional artifact rows and their checksums.

The mandatory command for this gate is `python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release`. The gate should be run after `populate_artifact_release.py` and `finalize_artifact_release.py`, because the finalizer refreshes manifest SHA256 values and `validate_artifact_release.py` checks both checksums and the `open_v2_main_results` row-level schema.

## Audit Cycle 10: Final Template Binding and System Metadata Gate

Outcome: pass for validator coverage; blocked for final upload until the selected journal template is bound to the final manuscript source.

This cycle checks whether final-upload readiness is coupled to the selected journal template rather than only to a generated PDF. The submission metadata, final-upload checklist, and submission-system checklist require `target_journal_template_bound`, `target_journal_template_applied`, rebuilt main and supplementary PDFs after template conversion, and a source archive rebuilt after template conversion. The gate prevents a template-independent PDF or DKE/Elsevier preflight package from being treated as final upload evidence.

The reviewer-facing boundary is narrow. Template binding is a publication-format and submission-system consistency gate; it does not strengthen the scientific evidence. The manuscript should not be uploaded until the selected journal template matches the final manuscript source, `python manuscript/scripts/validate_submission_package.py --final-upload` passes, and the cover letter, metadata, and availability statements all name the same target journal and artifact release.

## Audit Cycle 11: Live Submission Text Consistency Gate

Outcome: pass for checklist and validator coverage; blocked for final upload until the live submission-system preview is checked.

This cycle checks whether the text entered into the journal system remains synchronized with the repository sources after template conversion and metadata insertion. The final-upload information request now requires the title and abstract to be checked against `main.tex`, keywords to be copied exactly from `keywords.md`, highlights to be copied exactly from `highlights.md`, and the live submission system preview to show the same title, abstract, keywords, and highlights.

The reviewer-facing boundary is practical rather than scientific. A clean PDF is not enough if the submission system displays stale or manually edited first-screen text. Therefore `submission_system_files_verified` should remain false until title, abstract, keywords, highlights, uploaded files, and live system preview all match the final source package.

## Audit Cycle 12: Git-Only Fixture Reproducibility Gate

Outcome: pass for no-network code-path evidence; blocked for full numerical reproduction until the external artifact release is populated and linked.

This cycle checks whether the public repository can demonstrate executable data-processing paths without committing raw third-party data or full experiment outputs. The required command is `python manuscript/scripts/verify_fixture_rebuild.py`, which rebuilds DeepMatcher, SciRepEval-style, OpenAlex/OpenCitations, and assembled IAD-Bench fixture outputs in a temporary directory. The companion public-release command is `python scripts/check_public_release.py`, which verifies that `data/`, `outputs/`, caches, credentials, and large local artifacts remain outside the public package.

The reviewer-facing boundary is explicit. Passing the fixture rebuild proves that the data adapters, CLI entry points, schema contracts, and IAD-Bench assembly path execute on small public fixtures. It does not prove the Open-v2 numerical table, threshold choices, model predictions, or bootstrap intervals. Those result-level claims remain tied to the L2/L3 public-source rebuild or external artifact release with manifests and checksums.

## Audit Cycle 13: Submission Package Source-PDF Consistency Gate

Outcome: pass for package-level validator coverage; blocked for final upload until the selected journal source and PDFs are rebuilt after all final source edits.

This cycle checks whether the generated submission package can detect stale compiled files rather than relying on manual rebuild discipline. The package validator now compares packaged PDFs against their packaged source dependencies: the main PDF is checked against `main.tex` and `references.bib`, the supplementary PDF is checked against `supplementary_material.tex`, and the DKE/Elsevier preflight PDF is checked against `iad-risk-manuscript-elsevier.tex`, `keywords.md`, and `references.bib`. If a packaged PDF is older than any required source dependency, the package must be rejected with the action boundary: rebuild PDF before packaging.

The reviewer-facing boundary is procedural but important. A passing package validation shows that the packaged PDFs are not older than the included source files and bibliography. It does not prove final journal-template correctness, author metadata completeness, external artifact availability, or stronger empirical evidence. Those remain gated by template binding, final-upload metadata, artifact release validation, and the Q2/B evidence checks.

## Audit Cycle 14: Source-Control Manifest Binding Gate

Outcome: pass for manifest-level commit traceability; blocked for final upload until the final package is rebuilt from the submitted repository commit.

This cycle checks whether a submission package can be traced back to the exact source revision used to build it. The submission package manifest records a `source_control` object with `repository_commit`, `repository_branch`, `worktree_dirty`, and `tracked_state`. This gives reviewers and editors a concrete commit anchor for the LaTeX source, package checksums, and data-processing code without embedding local absolute paths or author-identifying repository URLs in anonymous packages.

The final-upload boundary is stricter than anonymous preflight. When source-control metadata is available, final-upload validation checks that the manifest `repository_commit` matches `submission_metadata.yml` and that `worktree_dirty` is false. A mismatch means the package was not rebuilt from the committed source state named in the availability statement, and the final upload must be regenerated before submission.

## Audit Cycle 15: Artifact Release Commit Validity Gate

Outcome: pass for commit-format validator coverage; blocked for final upload until the external artifact release names the same committed source revision as the final manuscript package.

This cycle checks whether the external result release can be tied to a real source revision rather than a placeholder or free-form label. The artifact release skeleton builder and validator require `repository.commit` to be a 7 to 40 character hexadecimal Git commit. This applies both when creating a release scaffold and when validating a populated release directory.

The reviewer-facing boundary is narrow. A syntactically valid commit makes the artifact manifest auditable, but it does not prove that all result files were generated from that commit. That stronger guarantee still requires checksums, command logs, prediction files, threshold logs, and the final manuscript metadata to reference the same repository commit and artifact URL or DOI.

## Audit Cycle 16: Artifact Release README Reproducibility Gate

Outcome: pass for README validator coverage; blocked for final upload until the external artifact release is populated, finalized, validated, and linked.

This cycle checks whether the release README preserves the minimum instructions a reviewer needs before auditing external results. The artifact release validator now requires `README.md` to retain the data policy, `manifest.json`, `checksums.sha256`, the checksum command, the `validate_artifact_release.py` command, the repository commit field, reproduction levels, and claim boundaries. The same gate keeps raw third-party data exclusions visible in the release package rather than only in repository-side documentation.

The reviewer-facing boundary is procedural. A complete README improves auditability, but it does not replace artifact checksums, result files, threshold logs, command logs, or the final artifact URL or DOI. It only ensures that the external release cannot pass validation after its reproduction instructions have been reduced to an uninformative file.

## Audit Cycle 17: Final-Upload Source-Control Package Binding Gate

Outcome: pass for package-builder coverage; blocked for final upload until target-journal metadata, author metadata, declarations, and artifact URL or DOI are complete.

This cycle closes a source-control binding edge case in the final-upload workflow. A tracked `submission_metadata.yml` file cannot reliably contain the Git commit of the commit that contains itself, because changing the file changes the commit hash. The final-upload package builder therefore keeps the source metadata eligible for anonymous pre-submission, reads `git remote origin`, `git rev-parse HEAD`, and the current branch during `--final-upload`, and writes `repository_url`, `repository_commit`, `repository_branch`, and the matching data/code availability statement into the package copy of `submission_metadata.yml`.

The reviewer-facing boundary is traceability rather than new evidence. This gate ensures that the final package metadata and `submission_manifest.json` agree on the committed source revision used for upload. It does not solve the remaining external blockers: the package still needs confirmed author metadata, target-journal template binding, funding and contribution declarations, permissions wording, generative AI declaration wording, live submission-system verification, and an artifact release URL or DOI before final upload can pass.

## Audit Cycle 18: Prediction Artifact Schema Gate

Outcome: pass for checklist and validator coverage; blocked for final numerical audit until the external artifact release is populated, finalized, validated, and linked.

This cycle checks whether final-upload review instructions match the row-level prediction schema enforced by `validate_artifact_release.py`. The final upload checklist now requires `iad_risk_predictions`, `representation_baseline_scores`, and `supervised_baseline_predictions` JSONL files to expose `pair_id`, `source_document_id`, `target_document_id`, expected labels, label strength, hard-negative level, split identifiers, score or probability fields, `threshold_value` where applicable, threshold source, and `merge_prediction`. It also requires `threshold_selection_logs` to expose system, threshold_name, `threshold_value`, selection_split, selection_metric, selection_rule, applied_scope, and `score_field`.

The reviewer-facing boundary is auditability rather than new empirical strength. A schema-complete prediction artifact lets reviewers recompute row-level decisions, denominators, and fixed operating points from the released files. It does not by itself establish threshold stability, statistical superiority, ablation causality, human-gold validation, or cluster-level quality; those remain gated by the optional artifacts and claim flags.

## Audit Cycle 19: Generative AI Declaration Gate

Outcome: pass for checklist and metadata validator coverage; blocked for final upload until the selected journal's live declaration wording is completed.

This cycle separates publisher-required AI-tool disclosure from removable process notes. Formal manuscript files, cover-letter text, highlights, keywords, and submission packages must not contain development logs, assistant work summaries, or unexplained process traces. At the same time, the final upload workflow must record the actual AI-tool use status required by the selected publisher, confirm author review and responsibility, confirm that AI tools are not listed as authors, and confirm whether machine-generated figures, images, or artwork are included.

The reviewer-facing boundary is compliance rather than scientific evidence. A completed generative AI declaration does not strengthen the method or experiments, but a missing or inconsistent declaration can trigger desk-check or production-stage issues. The declaration must therefore match `submission_metadata.yml`, `final_upload_information_request.md`, the manuscript declaration section if required by the target journal, and the live submission-system field before `generative_ai_declaration_complete` can be set to true.

## Audit Cycle 20: Fixture Evidence Isolation Gate

Outcome: pass for documentation and validator coverage; blocked for Q2/B completion until live artifacts replace example fixture evidence.

This cycle prevents test fixtures from being mistaken for current manuscript evidence. Unit-test fixtures, example JSONL summaries, and generated fixture reports verify that audit builders, validators, and CLI paths behave correctly. They do not prove that the current manuscript has completed the external artifact release, live submission-system checks, same-scope prediction package, author metadata, target-journal template binding, or Q2/B completion gate.

The reviewer-facing boundary is strict: fixture rows can support software reliability and reproducibility-path claims, but they cannot be cited as scientific result evidence or final-upload readiness evidence. A Q2/B or final-upload claim requires live outputs regenerated from the current repository commit, tied to the selected target-journal route, and linked to the external artifact release and final `submission_metadata.yml`.

## Audit Cycle 21: DKE Author Biography and Photograph Gate

Outcome: pass for checklist and metadata-validator coverage; blocked for final upload until author-approved biography text and photograph files are collected when the DKE route is selected.

This cycle checks a non-scientific but submission-critical DKE requirement. The publisher guide requests a short biography for each author and a passport-type photograph as a separate figure. The current anonymous preflight package must not include these identity-bearing files, but the final-upload workflow must collect them after author order and corresponding-author details are confirmed.

The reviewer-facing boundary is administrative rather than evidential. Author biographies and photographs do not strengthen the method, experiments, or reproducibility claims. They are tracked because missing author-material files can block or delay journal-system upload even when the manuscript PDF, source archive, and artifact release are otherwise ready.

## Minimum Gate Before Final Upload

The manuscript should not be uploaded to a journal system until all of the following are true:

1. `submission_metadata.yml` contains the selected target journal, `target_journal_template_bound: true`, completed author metadata, and author biography/photo readiness when the selected route requires it.
2. `main.tex` or the selected journal source is converted to the selected journal template and rebuilt.
3. `supplementary_material.tex` is rebuilt after any final source edits.
4. The artifact release has a real URL or DOI, validates against its checksum file, and records the same repository commit used by the final manuscript package.
5. The funding statement text, author contribution statement, permissions statement, generative AI declaration, data/code availability statement, and journal-specific research data statement are complete and consistent with the live submission system, with CRediT roles covering every listed author and with the repository URL, repository commit, and artifact URL or DOI embedded in the availability statements.
6. `python manuscript/scripts/verify_fixture_rebuild.py` passes from the public source tree without requiring raw third-party data.
7. `python scripts/check_public_release.py` passes and confirms that `data/`, `outputs/`, caches, credentials, and large local artifacts are outside the public package.
8. `python manuscript/scripts/validate_manuscript.py --strict-latex` passes.
9. `python manuscript/scripts/validate_submission_package.py --final-upload` passes.
10. `submission_system_checklist.md` has been checked against the live journal system; the selected journal template matches the final manuscript source; and the title, abstract, keywords, highlights, uploaded files, and live system preview have been verified against the final source package.
11. The Q2/B acceptance gate is either fully ready or the manuscript title, abstract, cover letter, and conclusion avoid any Q2/B-complete or broad-superiority wording.
12. Test fixtures, example summaries, and generated fixture rows are not used as proof of Q2/B completion unless they are regenerated from current live artifacts and current commit metadata.
