# Reviewer Readiness Audit

Updated: 2026-06-19

## Scope

This audit evaluates whether the template-independent manuscript package is ready for target-journal selection and final-format conversion. It is not a manuscript file for journal upload. It should be used before binding the paper to a journal template and again before final submission.

Current decision: conditionally ready for target-journal selection; not ready for final upload.

## Audit Iteration Summary

Completed audit cycles: 50.

Highest current reviewer-facing risks: final-upload metadata, target-journal template binding, DKE author biography and photograph materials, external artifact release, artifact source directory completeness, artifact release validation bypass, final-upload artifact-dir omission bypass, zero-observed HNFMR overread, L2 public-source rebuild chain-of-custody gap, selective-decision workload evidence, anonymous cover-letter declaration confirmation, preflight metadata declaration placeholders, preflight manuscript declaration boundary, introduction row-scope comparison overread, artifact release README completeness, artifact release commit validity, artifact README/manifest commit mismatch, final package/artifact commit mismatch, final-upload artifact-dir instruction drift, prediction artifact schema drift, generative AI declaration consistency, fixture/live evidence confusion, live submission-system text consistency, Git-only full-numerical audit overread, source-to-PDF package consistency, final-upload source-control package binding, and stronger evidence gates.

Current stopping rule: do not claim Q2/B completion or final-upload readiness until `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release` passes and a real artifact URL or DOI is recorded.

Non-code external inputs still required: author metadata, DKE author biography and photograph materials if that route is selected, target-journal confirmation, funding statement, author contribution statement, permissions statement, generative AI declaration, live submission-system fields, and artifact release URL or DOI.

Next revision trigger: repeat the editorial desk check after target-journal template binding, cover-letter customization, or artifact-link insertion.

## Audit Dimensions

| Dimension | Current status | Evidence in the package | Residual requirement before final upload |
| --- | --- | --- | --- |
| Contribution | Pass with bounded claims | The manuscript defines identity-agenda confusion, IAD-Bench, HNFMR, and risk-aware merge gating. | Keep the contribution framed as false-merge control, not broad method superiority. |
| Writing clarity | Pass for template-independent draft | The manuscript contains explicit problem formulation, notation, method details, result boundaries, limitations, and threats to validity. | Recheck section length and formatting after journal-template conversion. |
| Experimental strength | Conditional | Open-v2 evidence reports baseline HNFMR 0.790--0.999 and zero observed IAD-Risk HNFMR on the reported held-out scope. | Release same-scope prediction files, threshold logs, checksums, and result tables before relying on full numerical audit. |
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
| Experimental strength self-review | Are the reported gains meaningful against strong baselines under a fair interpretation? | needs new experiment | Open-v2 evidence reports representation baseline HNFMR 0.790--0.999, RoBERTa FMR 0.001/HNFMR 0.0001, and zero observed IAD-Risk HNFMR on the reported held-out scope. | Release same-scope prediction files, threshold logs, checksums, and bootstrap intervals before claiming stronger comparative advantage. |
| Evaluation completeness self-review | Are ablations, metrics, datasets, and label strata sufficient for the claimed scope? | needs new experiment | The manuscript reports F1, FMR, HNFMR, label strata, scope compatibility, threshold-status boundaries, and manual-validation requirements. | Add artifact-backed ablations, threshold grid, manual-validation slice, and source-heldout package before stronger robustness or component-causality claims. |
| Method design soundness self-review | Does the method have realistic assumptions and a positive net benefit despite added complexity? | pass | The method exposes thresholds, cannot-link behavior, audit metadata, explicit label-boundary rules, and workload evidence requirements for selective decisions. | Reassess threshold transfer, deployment complexity, automatic merge coverage, defer rate, and manual-review capacity after the selected journal route and external artifact are fixed. |

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

This cycle checks whether the external result package can support a row-by-row reviewer audit of the main Open-v2 result table. The release validator treats `open_v2_main_results` as a schema-bearing artifact rather than a generic file: `tables/open_v2_main_results.csv` must include per-row denominator counts, per-row threshold source, scope label used in the main table, automatic merge count, block count, defer count, automatic merge coverage, defer rate, and capacity-normalized review load. This prevents a release from passing only because the CSV exists and has a matching checksum.

The reviewer-facing interpretation is narrow. A valid `open_v2_main_results` file lets reviewers trace each reported row to its denominator, operating-point source, evaluated scope, and selective-decision coverage. It does not by itself establish broad method ranking, confidence intervals, threshold stability, component causality, human-gold validation, or cluster-level deployment quality. Those stronger claims remain gated by the optional artifact rows and their checksums.

The mandatory command for this gate is `python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release`. The gate should be run after `populate_artifact_release.py` and `finalize_artifact_release.py`, because the finalizer refreshes manifest SHA256 values and `validate_artifact_release.py` checks both checksums and the `open_v2_main_results` row-level schema.

## Audit Cycle 10: Final Template Binding and System Metadata Gate

Outcome: pass for validator coverage; blocked for final upload until the selected journal template is bound to the final manuscript source.

This cycle checks whether final-upload readiness is coupled to the selected journal template rather than only to a generated PDF. The submission metadata, final-upload checklist, and submission-system checklist require `target_journal_template_bound`, `target_journal_template_applied`, rebuilt main and supplementary PDFs after template conversion, and a source archive rebuilt after template conversion. The gate prevents a template-independent PDF or DKE/Elsevier preflight package from being treated as final upload evidence.

The reviewer-facing boundary is narrow. Template binding is a publication-format and submission-system consistency gate; it does not strengthen the scientific evidence. The manuscript should not be uploaded until the selected journal template matches the final manuscript source, `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release` passes, and the cover letter, metadata, and availability statements all name the same target journal and artifact release.

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

This cycle separates publisher-required AI-tool disclosure from removable process notes. Formal manuscript files, cover-letter text, highlights, keywords, and submission packages must not contain development logs, development work summaries, or unexplained process traces. At the same time, the final upload workflow must record the actual AI-tool use status required by the selected publisher, confirm author review and responsibility, confirm that AI tools are not listed as authors, and confirm whether machine-generated figures, images, or artwork are included.

The reviewer-facing boundary is compliance rather than scientific evidence. A completed generative AI declaration does not strengthen the method or experiments, but a missing or inconsistent declaration can trigger desk-check or production-stage issues. The declaration must therefore match `submission_metadata.yml`, `final_upload_information_request.md`, the manuscript declaration section if required by the target journal, and the live submission-system field before `generative_ai_declaration_complete` can be set to true.

## Audit Cycle 20: Fixture Evidence Isolation Gate

Outcome: pass for documentation and validator coverage; blocked for Q2/B completion until live artifacts replace example fixture evidence.

This cycle prevents test fixtures from being mistaken for current manuscript evidence. Unit-test fixtures, example JSONL summaries, and generated fixture reports verify that audit builders, validators, and CLI paths behave correctly. They do not prove that the current manuscript has completed the external artifact release, live submission-system checks, same-scope prediction package, author metadata, target-journal template binding, or Q2/B completion gate.

The reviewer-facing boundary is strict: fixture rows can support software reliability and reproducibility-path claims, but they cannot be cited as scientific result evidence or final-upload readiness evidence. A Q2/B or final-upload claim requires live outputs regenerated from the current repository commit, tied to the selected target-journal route, and linked to the external artifact release and final `submission_metadata.yml`.

## Audit Cycle 21: DKE Author Biography and Photograph Gate

Outcome: pass for checklist and metadata-validator coverage; blocked for final upload until author-approved biography text and photograph files are collected when the DKE route is selected.

This cycle checks a non-scientific but submission-critical DKE requirement. The publisher guide requests a short biography for each author and a passport-type photograph as a separate figure. The current anonymous preflight package must not include these identity-bearing files, but the final-upload workflow must collect them after author order and corresponding-author details are confirmed.

The reviewer-facing boundary is administrative rather than evidential. Author biographies and photographs do not strengthen the method, experiments, or reproducibility claims. They are tracked because missing author-material files can block or delay journal-system upload even when the manuscript PDF, source archive, and artifact release are otherwise ready.

## Audit Cycle 22: Method Execution Traceability Gate

Outcome: pass for method-writing clarity; blocked for result-level audit until external prediction, threshold, metric, and checksum artifacts are populated and linked.

This cycle checks whether the Method section gives reviewers a reproducible execution path rather than only a conceptual model description. The manuscript now states the training and inference trace from schema loading through masked supervision, threshold fixation, pair scoring, decision emission, and metric export. This closes a writing-clarity risk: reviewers can see how relation-head predictions, fixed thresholds, cannot-link evidence, merge/block/defer decisions, and metric denominators should align in a result artifact.

The reviewer-facing boundary remains unchanged. A clear execution trace improves method reproducibility from the manuscript text, but it does not by itself prove the Open-v2 numbers. Result-level audit still requires populated prediction files, threshold logs, metric summaries, manifests, checksums, and the external artifact URL or DOI.

## Audit Cycle 23: First-Screen Claim Lockdown Gate

Outcome: pass for final-upload checklist coverage; blocked for final upload until target-journal wording edits, artifact links, and live system fields are checked against the same source package.

This cycle checks the materials that editors and submission systems see before a reviewer reads the PDF. The submission checklist now requires `cover_letter.md`, `highlights.md`, `keywords.md`, the abstract, and the conclusion to describe the same problem, method, Open-v2 evidence snapshot, and claim boundary. It also blocks first-screen upgrades to broad method superiority, SOTA ranking, statistical superiority, threshold stability, human-gold validation, Q2/B completion, final-upload readiness, or cluster-level deployment quality.

The reviewer-facing boundary is practical. A consistent first screen reduces desk-check and scope-drift risk, but it does not add empirical evidence. Artifact URL or DOI insertion must remain a traceability update unless the released artifact validates the optional evidence needed for stronger claims, such as bootstrap intervals, threshold grids, ablations, manual-validation slice, or cluster artifacts.

## Audit Cycle 24: Final-Upload Claim-Lock Metadata Gate

Outcome: pass for metadata-validator coverage; blocked for final upload until `first_screen_claim_lockdown_confirmed` is true after live system preview.

This cycle turns the first-screen claim lockdown from a checklist instruction into a final-upload metadata gate. The tracked `submission_metadata.yml` now keeps `final_upload_checklist.first_screen_claim_lockdown_confirmed` false by default, and the final-upload metadata validator requires it to be true before upload. The final-upload information request also asks authors to confirm that the cover letter, highlights, keywords, abstract, and conclusion preserve the same Open-v2 evidence boundary and avoid unsupported first-screen upgrades.

The reviewer-facing boundary remains conservative. Setting this field to true confirms text consistency and claim discipline; it does not confirm target-journal acceptance, Q2/B completion, artifact evidence, or stronger empirical claims.

## Audit Cycle 25: Artifact README-Manifest Commit Consistency Gate

Outcome: pass for artifact-validator and commit-consistency coverage; blocked for final numerical audit until the external artifact release is populated, finalized, validated, and linked.

This cycle closes a traceability gap in the external artifact release. The artifact release validator now requires `README.md` to record a parseable `Repository commit` value and requires that value to match `manifest.json` field `repository.commit`. The README template also states that the repository commit must match the manifest and the final manuscript package commit.

The reviewer-facing boundary is source traceability. A matching README and manifest commit prevents reviewers from receiving two different source anchors for the same artifact release. It does not prove that the result files were generated from that commit; that stronger guarantee still depends on command logs, checksums, prediction files, threshold logs, and the final package metadata naming the same source revision.

## Audit Cycle 26: Final Package-Artifact Commit Binding Gate

Outcome: pass for submission-package validator coverage; blocked for final upload until the external artifact release is populated, finalized, validated, and checked with `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release`.

This cycle links the final manuscript package to the external result release. The submission package validator now accepts an optional artifact release directory in final-upload mode, reads the artifact `manifest.json`, and checks that artifact manifest `repository.commit` matches `submission_metadata.yml` field `repository_commit` and, when available, `submission_manifest.json` source-control commit. This prevents a final-upload package from naming one source revision while the external artifact release names another.

The reviewer-facing boundary remains traceability. Passing the package-artifact commit gate means the final source package and external result release share the same source anchor; it does not prove numerical correctness unless the artifact release itself validates, its checksums pass, and the prediction, threshold, metric, and command-log artifacts were generated from the same final source revision.

## Audit Cycle 27: Final-Upload Artifact-Dir Instruction Consistency Gate

Outcome: pass for final-upload instruction coverage; blocked for final upload until the real artifact release directory is available.

This cycle removes a workflow inconsistency introduced by the stronger package-artifact binding gate. The final-upload information request and submission-system checklist now both instruct authors to run `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release`, and the final-upload information request collects the artifact release directory path used for that validation. The manuscript validator also rejects these documents if they revert to the older command without `--artifact-dir`.

The reviewer-facing boundary is procedural. This gate ensures that authors do not accidentally validate only the manuscript package while skipping the external artifact commit binding. It does not replace artifact release validation, target-journal template binding, live submission-system checks, or the external artifact URL or DOI.

## Audit Cycle 28: Final-Upload Artifact Release Validation Gate

Outcome: pass for integrated artifact-release validation coverage; blocked for final upload until the real artifact release validates.

This cycle closes the remaining `--artifact-dir` gap. The submission package validator now calls the artifact release validator whenever final-upload validation receives an artifact release directory, so the final upload gate checks release file membership, checksums, README markers, manifest policy, required artifact IDs, Open-v2 row-level audit columns, prediction JSONL fields, and claim-dependent artifact requirements before applying package-artifact commit binding.

The reviewer-facing boundary is stronger but still procedural. Passing this integrated gate means the manuscript package names an artifact release that is structurally valid and source-bound to the final package; it still does not make stronger empirical claims unless the released files contain the required bootstrap, ablation, manual-validation, threshold-grid, or cluster-level evidence.

## Audit Cycle 29: Final-Upload Artifact-Dir Required Gate

Outcome: pass for missing artifact-directory rejection; blocked for final upload until a real finalized artifact release directory is supplied.

This cycle closes the last command-line bypass in the final-upload validator. In final-upload mode, `validate_submission_package.py` now rejects validation runs that omit `--artifact-dir`, even when the package metadata already contains an artifact URL or DOI and the final-upload checklist marks the release as linked. This prevents a package from passing final validation with only manuscript metadata while skipping local checksum, manifest, row-schema, prediction-schema, and package-artifact commit checks.

The reviewer-facing boundary remains reproducibility discipline rather than new result evidence. The gate proves that the final validation workflow cannot bypass the external release directory; it still requires the real release to be populated, finalized, checksum-verified, publicly linked, and source-bound to the submitted manuscript commit before any final-upload readiness claim is allowed.

## Audit Cycle 30: Main-Manuscript Artifact Validation Text Gate

Outcome: pass for manuscript-level reproducibility wording; blocked for final upload until the real artifact URL or DOI and finalized release directory are available.

This cycle moves the artifact validation requirement into the main manuscript's Data and Code Availability section. The text now states that an external result release supports the Open-v2 numerical table only after `validate_artifact_release.py --artifact-dir /path/to/release` passes and the final manuscript package also passes `validate_submission_package.py --final-upload --artifact-dir /path/to/release`. The paragraph names the release manifest, checksums, result identifiers, row-level schemas, prediction schemas, claim-boundary flags, raw-data exclusions, source-control commit, submission metadata, and artifact manifest as the binding checks.

The reviewer-facing boundary is claim-evidence alignment. The manuscript no longer relies only on supplemental instructions or repository scripts to describe result-level auditability; the main text tells reviewers that a failed artifact or package-binding validation means the external release should not be used to support the Open-v2 numerical table or stronger claims.

## Audit Cycle 31: Zero-Observed HNFMR Wording Gate

Outcome: pass for first-screen zero-risk overread control; blocked for stronger risk claims until broader source-heldout and manual-validation evidence are released.

This cycle revises the abstract, contribution-evidence summary, result interpretation paragraph, cover letter, and highlights so that the IAD-Risk held-out result is described as zero observed HNFMR rather than as wording that can be read as absolute zero risk. The numerical result table still reports the measured HNFMR value, but the first-screen prose now keeps the observational scope visible.

The reviewer-facing boundary is statistical interpretation. The current evidence means no hard-negative false merge was observed under the reported Open-v2 held-out scope and operating point; it does not prove zero risk under all scholarly sources, thresholds, version policies, or cluster-level merge workflows.

## Audit Cycle 32: L2 Public-Source Rebuild Traceability Gate

Outcome: pass for L2 public-source rebuild traceability wording and release-template coverage; blocked for full numerical reproduction until a populated external artifact release records real public input manifests, processing logs, derived-output summaries, and checksums.

This gate checks whether a reader can understand how the project remains reproducible when raw third-party data and full experimental outputs are not committed to Git. The supplementary material now separates no-network fixture rebuilding from L2 public-source rebuilding and requires a release-level `source_input_manifest`, `processing_run_log`, output summaries, and checksum coverage before L2 rebuilds are treated as result evidence. The data-processing documentation records the same boundary for repository users.

The reviewer-facing boundary is chain of custody. The repository can prove that adapters, CLI entry points, fixture rebuilds, schema checks, and release validators are executable; it cannot by itself prove the Open-v2 numerical table without real public-source inputs or an L3 artifact release. Therefore the artifact release template and validator now require `source_input_manifest` and `processing_run_log` alongside result tables, predictions, threshold logs, and split summaries.

## Audit Cycle 33: Main-Text L2 Provenance Alignment Gate

Outcome: pass for main-text L2 provenance alignment; blocked for final numerical reproduction until the real release contains populated `source_input_manifest`, `processing_run_log`, prediction files, threshold logs, metric summaries, and checksums.

This gate checks whether the main manuscript itself names the L2 provenance artifacts introduced in the supplementary material and release template. The reproduction-level table, result audit trail, result artifact crosswalk, and Data and Code Availability section now state that L2 public-source rebuilds require `source_input_manifest` and `processing_run_log` in addition to prediction, threshold, manifest, checksum, and metric artifacts.

The reviewer-facing boundary is source-to-result alignment. Main text, supplementary material, artifact release template, validator, and tests now use the same provenance vocabulary, reducing the risk that reviewers see the artifact rules as supplemental-only instructions. This alignment still does not create the artifact release; it only ensures the submitted manuscript points to the evidence that must exist before full numerical reproduction or final-upload readiness can be claimed.

## Audit Cycle 34: Selective Decision Workload Boundary Gate

Outcome: pass for selective-decision workload wording and validator coverage; blocked for operational throughput or cost-saving claims until the external artifact reports automatic merge coverage, block rate, defer rate, review-load counts, and capacity-normalized review load from the same prediction files.

This gate checks whether low false-merge rates can be overread as evidence that the method reduces human review. The manuscript now treats low FMR or HNFMR with high deferral as a conservative triage outcome rather than a productivity outcome. Operational benefit requires the released artifacts to bind false-merge metrics to automatic merge coverage, block rate, defer rate, a predeclared deferral budget, and manual-review capacity.

The reviewer-facing boundary is workload attribution. The current manuscript can argue safety-oriented false-merge control under fixed operating points, but it should not claim throughput reduction, review-cost savings, or all-pair automatic resolution until the workload evidence is released and validated.

## Audit Cycle 35: Anonymous Cover-Letter Declaration Boundary Gate

Outcome: pass for anonymous preflight cover-letter boundary; blocked for final upload until author-provided metadata confirms originality, author approval, competing-interest status, funding, author contribution, permission, and generative AI declarations.

This gate checks whether the anonymous cover letter prematurely asserts final author declarations. The preflight cover letter now keeps the scientific submission summary and evidence boundaries, but it states that it does not treat author declarations as finalized until the author-provided metadata and live submission-system fields are completed. This prevents the anonymous preflight package from representing unconfirmed author approval or competing-interest statements as final.

The reviewer-facing boundary is compliance discipline. The current package can be used to review the manuscript story, scope, and reproducibility boundaries, but it should not be treated as final-upload-ready until the selected journal, author identities, corresponding author, declarations, artifact release, and live system fields are confirmed.

## Audit Cycle 36: Preflight Metadata Declaration Placeholder Gate

Outcome: pass for tracked metadata declaration placeholders; blocked for final upload until `submission_metadata.yml` is populated with author-confirmed originality, author approval, and competing-interest statements.

This gate checks whether the tracked source metadata prematurely records final author declarations. In the anonymous preflight source, `statements.originality`, `statements.author_approval`, and `statements.competing_interests` remain empty because the author list and corresponding author are not yet confirmed. The manuscript validator rejects those fields when they are filled while the package remains in preflight state.

The reviewer-facing boundary is structured metadata integrity. The tracked metadata file remains useful for package construction and final-upload gating, but it does not assert unconfirmed author declarations before the final journal route and live submission metadata are available.

## Audit Cycle 37: Preflight Manuscript Declaration Boundary Gate

Outcome: pass for anonymous preflight manuscript declaration boundary; blocked for final upload until the listed authors confirm the competing-interest status and the final statement is synchronized with `submission_metadata.yml` and the live submission system.

This gate checks whether the main manuscript prematurely asserts a final competing-interest declaration. In the anonymous preflight manuscript, the Competing Interests section now states that the competing-interest declaration is not finalized and must be confirmed by the listed authors before final upload. This keeps the manuscript source aligned with the blank preflight declaration fields in `submission_metadata.yml`.

The reviewer-facing boundary is declaration authority. The current source package can support scientific review and template preparation, but it must not be treated as an author-approved final declaration package until the selected journal route, author list, competing-interest status, metadata file, and live submission-system fields are synchronized.

## Audit Cycle 38: Introduction Row-Scope Comparison Boundary Gate

Outcome: pass for introduction-level row-scope comparison wording; blocked for same-scope ranking claims until all row families share released prediction scopes, threshold logs, metric summaries, and checksums.

This gate checks whether the contribution paragraph can be misread as claiming that all reported baselines and IAD-Risk rows are directly ranked under one identical evaluation scope. The introduction now states that IAD-Risk is evaluated within a shared Open-v2 pair schema while explicitly marking row-scope differences between full-scope baselines and held-out IAD-Risk rows. This keeps the first-page contribution aligned with the Open-v2 table, result interpretation guardrails, and submission-material claim boundary.

The reviewer-facing boundary is ranking interpretation. A shared schema supports auditable row construction and relation semantics, but it does not remove the full-scope versus held-out test distinction or authorize a same-scope ranking implication before the external artifact release supplies matched prediction files and threshold records.

## Audit Cycle 39: Installable CLI Entry-Point Traceability Gate

Outcome: pass for Git-only command discovery and source entry-point binding; blocked for full numerical audit until the external artifact release is populated, finalized, validated, and linked.

This gate checks whether a reviewer can locate the executable project entry point from tracked source files before running fixture rebuilds or artifact commands. The main manuscript now states that the package source lives under `src/iad_sieve`, that `pyproject.toml` exposes `iad-sieve = iad_sieve.cli:main`, and that `python -m iad_sieve.cli --help` verifies argparse command discovery from the repository. The manuscript validator also checks these markers against the tracked source contract rather than treating the data-availability wording as an unverified prose claim.

The reviewer-facing boundary is executable traceability. This gate proves that Git-only reviewers can discover the CLI, inspect the package entry point, and run fixture-level rebuild commands without raw third-party data. It does not prove the Open-v2 numerical table, threshold choices, prediction files, bootstrap intervals, workload metrics, ablations, or cluster-level artifacts; those remain tied to the L2/L3 public-source rebuild or the external artifact release with manifests and checksums.

## Audit Cycle 40: Artifact Source Preflight Gate

Outcome: pass for source artifact completeness preflight coverage; blocked for final numerical audit until the source artifacts are populated, copied, finalized, checksum-validated, and publicly linked.

This gate checks whether the artifact workflow can fail early before copying incomplete result files into a release scaffold. The artifact release workflow now requires `python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only` before the ordinary populate, finalize, and validate commands. The preflight reuses the release manifest copy plan, checks required source artifact paths and optional mapping paths, and returns without copying files, writing `artifact_population_log.jsonl`, or running finalization.

The reviewer-facing boundary is source-package readiness. A passing preflight means the source artifact directory contains the required files named by the release manifest and that path mappings are safe. It does not prove row-level schemas, checksums, source-control commit binding, public accessibility, or numerical correctness; those remain enforced by `finalize_artifact_release.py`, `validate_artifact_release.py`, `validate_submission_package.py --final-upload --artifact-dir /path/to/release`, and the final artifact URL or DOI.

## Audit Cycle 41: Main-Text Schema Density Gate

Outcome: pass for main-text schema-density reduction; blocked for final numerical audit until the external artifact release remains populated, finalized, checksum-validated, and publicly linked.

This gate checks whether schema-contract details make the main manuscript harder to read than necessary for a journal reviewer. The main manuscript now summarizes the IAD-Bench document and pair fields in prose, while the supplementary material preserves the full document-schema and pair-schema tables with their field groups, interpretation roles, and HNFMR audit boundary.

The reviewer-facing boundary is readability without loss of reproducibility. Moving the detailed schema tables out of the main text reduces table density and improves first-pass readability, but it does not relax the schema contract. The validator now checks both the main-text field summary and the supplementary schema tables so that reviewers can still audit fixture rebuilding, public-source rebuilding, and artifact validation against the same required fields.

## Audit Cycle 42: Related-Work Positioning Density Gate

Outcome: pass for Related Work table-density reduction; blocked for final numerical audit until the external artifact release remains populated, finalized, checksum-validated, and publicly linked.

This gate checks whether the closest-work positioning matrix interrupts the Related Work narrative. The main manuscript now states the four closest work families and the novelty boundary in prose, while the supplementary material preserves the full positioning table with optimization targets, limitations, and IAD-Risk distinctions.

The reviewer-facing boundary is novelty clarity without table overload. The edit keeps the Related Work section focused on mechanism differences rather than table scanning, while the validator still requires both the main-text novelty boundary and the supplementary positioning matrix.

## Audit Cycle 43: Method Design Boundary Density Gate

Outcome: pass for Method table-density reduction; blocked for final numerical audit until the external artifact release remains populated, finalized, checksum-validated, and publicly linked.

This gate checks whether operational net-benefit and version-identifier policy tables make the Method section heavier than necessary for first-pass review. The main manuscript now states the cost, workload, threshold-governance, version-policy, and adjudication boundaries in prose, while the supplementary material preserves the full operational net-benefit and version-identifier matrices.

The reviewer-facing boundary is design soundness without table overload. The edit keeps the Method section focused on the algorithm and decision policy, while the validator still requires both main-text boundary statements and supplementary method-design tables.

## Audit Cycle 44: Experiment Reporting Boundary Density Gate

Outcome: pass for Experiments table-density reduction; blocked for final numerical audit until the external artifact release remains populated, finalized, checksum-validated, and publicly linked.

This gate checks whether threshold-governance and statistical-interpretation matrices make the Experiments section heavier than necessary for first-pass review. The main manuscript now states the fixed threshold-selection protocol, uncertainty requirements, point-estimate boundary, confidence-interval requirement, statistical-significance requirement, zero-observed HNFMR interpretation, and model-ranking boundary in prose, while the supplementary material preserves the full threshold and uncertainty reporting protocol table and the full statistical interpretation boundary table.

The reviewer-facing boundary is experimental interpretability without table overload. The edit keeps the Experiments section focused on what the reported Open-v2 snapshot can and cannot support, while the validator still requires the main-text boundary statements and both supplementary experiment-reporting tables.

## Audit Cycle 45: Result Artifact Crosswalk Density Gate

Outcome: pass for result-audit table-density reduction; blocked for final numerical audit until the external artifact release remains populated, finalized, checksum-validated, and publicly linked.

This gate checks whether the Open-v2 result artifact crosswalk belongs in the main manuscript or the supplementary material. The main manuscript now states the row-level audit requirements, prediction-file requirements, threshold-log requirements, public-source provenance requirements, and L3 artifact boundary in prose, while the supplementary material preserves the full result artifact crosswalk with row-family artifact IDs.

The reviewer-facing boundary is numerical-audit traceability without main-text table overload. The edit keeps the main result section focused on the Open-v2 evidence snapshot and its interpretation boundary, while the validator still requires the complete supplementary crosswalk and its required artifact IDs.

## Audit Cycle 46: Manual Validation Boundary Density Gate

Outcome: pass for manual-validation table-density reduction; blocked for final label-precision claims until a reviewed slice, adjudication log, agreement report, pair-level notes, and checksums are released.

This gate checks whether the manual-validation boundary matrix is needed in the main result section. The main manuscript now states that manual validation is not completed, that silver hard negatives are stress-test evidence rather than human-gold non-identity labels, and that stronger label-precision claims require a 500--1,000 pair reviewed slice with blinded independent review and adjudication artifacts. The supplementary material preserves the full manual validation boundary table and the full manual validation protocol table.

The reviewer-facing boundary is label-evidence clarity without main-text table overload. The edit keeps the Open-v2 result section focused on the reported evidence snapshot while the validator still requires the supplementary manual-validation boundary, protocol, reviewer process, adjudication artifacts, and human-gold wording limits.

## Audit Cycle 47: Scope Compatibility Matrix Density Gate

Outcome: pass for mixed-scope comparison table-density reduction; blocked for broad ranking claims until all row families share released prediction scopes, threshold logs, checksums, interval estimates, and a manual-validation slice.

This gate checks whether the Open-v2 scope compatibility matrix belongs in the main result section. The main manuscript now states that the Open-v2 table is a scope-bounded evidence table, not a single comparative ranking, and that full pair-scope representation baselines and held-out IAD-Risk rows support a mechanistic comparison rather than a broad ranking. The supplementary material preserves the full scope compatibility matrix with row-family scopes, supported interpretations, and unsupported stronger comparisons.

The reviewer-facing boundary is mixed-scope interpretation clarity without main-text table overload. The edit keeps the main result section focused on the conservative false-merge-control claim while the validator still requires the supplementary scope compatibility matrix and the explicit stronger-comparison boundary.

## Audit Cycle 48: Result Interpretation Guardrails Density Gate

Outcome: pass for result-interpretation table-density reduction; blocked for stronger result readings until same-scope prediction files, interval estimates, threshold-stability evidence, and artifact checksums are released.

This gate checks whether the Open-v2 result interpretation guardrails matrix is needed in the main result section. The main manuscript now states the direct reading boundary in prose: Scope type labels separate full available Open-v2 rows from held-out Open-v2 test rows, scope labels prevent ranking interpretation, and the supported reading is mechanism-oriented rather than a broad method-superiority claim. The supplementary material preserves the full result interpretation guardrails table with row-family readings and unsupported readings.

The reviewer-facing boundary is result-reading clarity without main-text table overload. The edit keeps the main result section focused on the Open-v2 evidence snapshot while the validator still requires the supplementary guardrails table, unsupported-reading boundary, scope labels, and threshold-stability or zero-risk limits.

## Audit Cycle 49: Claim-Evidence Boundary Density Gate

Outcome: pass for claim-evidence table-density reduction; blocked for final numerical audit until same-scope prediction files, interval estimates, manual-validation evidence, and artifact checksums are released.

This gate checks whether the claim-evidence boundary table is needed in the main result section. The main manuscript now states the boundary in prose: identity-agenda confusion is supported only as a false-merge pathway, IAD-Risk support is bounded to the reported Open-v2 setting, IAD-Bench remains a provenance-aware evaluation contract, and repository-level reproduction does not by itself prove full numerical results without public source files or a released artifact package. The supplementary material preserves the full claim-evidence boundary table with required support and unsupported claim classes.

The reviewer-facing boundary is claim-evidence clarity without main-text table overload. The edit keeps the main result section focused on the reported evidence snapshot while the validator still requires the supplementary claim-evidence boundary, including identity-agenda confusion, IAD-Risk support, IAD-Bench evidence, and repository-level reproduction limits.

## Audit Cycle 50: Validity Threats Density Gate

Outcome: pass for validity-threat table-density reduction; blocked for final numerical audit until source-heldout evidence, causal ablations, cluster-level artifacts, and external artifact checksums are released.

This gate checks whether the threats-to-validity matrix is needed in the main manuscript. The main manuscript now states the validity threat model in prose: construct validity is tied to label strata, internal validity to threshold and split separation, external validity to the current source mix, conclusion validity to the absence of complete causal ablations, reproducibility to source and artifact availability, and operational validity to the gap between pair-level decisions and cluster-level deployment. The supplementary material preserves the full validity-threats matrix with each risk, mitigation, and remaining boundary.

The reviewer-facing boundary is validity-threat clarity without main-text table overload. The edit keeps the main threats section readable while the validator still requires the supplementary validity-threat boundary, including construct validity, internal validity, external validity, conclusion validity, reproducibility, operational validity, and the explicit rule that mitigations do not turn proxy or silver evidence into human-adjudicated truth.

## Minimum Gate Before Final Upload

The manuscript should not be uploaded to a journal system until all of the following are true:

1. `submission_metadata.yml` contains the selected target journal, `target_journal_template_bound: true`, completed author metadata, and author biography/photo readiness when the selected route requires it.
2. `main.tex` or the selected journal source is converted to the selected journal template and rebuilt.
3. `supplementary_material.tex` is rebuilt after any final source edits.
4. The artifact release has a real URL or DOI, validates against its checksum file, and records the same repository commit used by the final manuscript package in both `README.md` and `manifest.json`.
5. The funding statement text, author contribution statement, permissions statement, generative AI declaration, data/code availability statement, and journal-specific research data statement are complete and consistent with the live submission system, with CRediT roles covering every listed author and with the repository URL, repository commit, and artifact URL or DOI embedded in the availability statements.
6. `python manuscript/scripts/verify_fixture_rebuild.py` passes from the public source tree without requiring raw third-party data.
7. `python scripts/check_public_release.py` passes and confirms that `data/`, `outputs/`, caches, credentials, and large local artifacts are outside the public package.
8. `python manuscript/scripts/validate_manuscript.py --strict-latex` passes.
9. `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release` passes after the external artifact release is finalized.
10. `submission_system_checklist.md` has been checked against the live journal system; the selected journal template matches the final manuscript source; and the title, abstract, keywords, highlights, uploaded files, and live system preview have been verified against the final source package.
11. The Q2/B acceptance gate is either fully ready or the manuscript title, abstract, cover letter, and conclusion avoid any Q2/B-complete or broad-superiority wording.
12. Test fixtures, example summaries, and generated fixture rows are not used as proof of Q2/B completion unless they are regenerated from current live artifacts and current commit metadata.
