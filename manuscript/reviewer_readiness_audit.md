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
| Reproducibility depends on files outside Git. | Medium | Fixture rebuild, public-source commands, artifact manifest template, and checksums policy are documented. | Publish the L3 artifact release and link it in submission metadata. |
| Final upload may mismatch journal system fields. | High | A submission-system checklist records file, metadata, PDF, and artifact checks. | Confirm target journal, author metadata, template, and live system fields. |

## Claim-Evidence Check

| Claim class | Evidence status | Review stance |
| --- | --- | --- |
| Identity-agenda confusion is a concrete false-merge pathway. | Supported within Open-v2 hard-negative stress evidence. | Accept as a targeted failure-mode claim. |
| IAD-Risk suppresses hard-negative false merges in the reported setting. | Supported by the current evidence snapshot and bounded by artifact requirements. | Accept only under the stated Open-v2 scope. |
| IAD-Bench is a provenance-aware benchmark contract. | Supported by schema, label-stratum separation, fixture rebuild, and documentation. | Accept as a benchmark-contract contribution, not as human gold. |
| The method is broadly superior to all baselines. | Not claimed. | Keep absent unless all baselines share released prediction scope and stronger evidence. |
| The method is threshold-stable. | Not claimed. | Add only after threshold-grid artifact evidence exists. |
| Human validation is complete. | Not claimed. | Add only after reviewed slice, adjudication log, and agreement report exist. |

## Audit Cycle 1: Claim Discipline

Outcome: pass with residual artifact requirements.

The manuscript avoids unsupported broad-superiority, human-gold, and threshold-stability claims. The remaining risk is not wording but evidence availability: full numerical audit still depends on external artifacts with predictions, logs, tables, and checksums.

## Audit Cycle 2: Submission Readiness

Outcome: blocked for final upload.

The template-independent package is internally consistent, but final upload remains blocked until the target journal, journal template, author metadata, corresponding-author metadata, final template-specific PDFs, live submission-system fields, and artifact release link are completed.

## Minimum Gate Before Final Upload

The manuscript should not be uploaded to a journal system until all of the following are true:

1. `submission_metadata.yml` contains the selected target journal and completed author metadata.
2. `main.tex` is converted to the selected journal template and rebuilt.
3. `supplementary_material.tex` is rebuilt after any final source edits.
4. The artifact release has a real URL or DOI and validates against its checksum file.
5. `python manuscript/scripts/validate_manuscript.py --strict-latex` passes.
6. `python manuscript/scripts/validate_submission_package.py --final-upload` passes.
7. `submission_system_checklist.md` has been checked against the live journal system.
