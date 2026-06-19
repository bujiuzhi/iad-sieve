# Target Journal Shortlist

Updated: 2026-06-19

## Selection Boundary

This shortlist supports pre-submission planning for the manuscript "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication." It is not a final submission record. The final upload metadata should remain incomplete until the authors confirm the target journal, author list, corresponding author, journal template, and artifact release link.

Rank-sensitive labels such as JCR quartile, Chinese Academy of Sciences zone, and CCF class must be reconfirmed in the authors' institutional ranking system before final upload. The evidence below uses publisher pages for scope, metrics, and formatting requirements.

## Recommendation

Primary practical target: Data & Knowledge Engineering.

Rationale: the manuscript is about entity matching, data integration, benchmark construction, and reproducible data-processing contracts. Data & Knowledge Engineering directly covers the interface of data engineering and knowledge engineering, provides an Elsevier LaTeX route, and has a lower evidence burden than Information Systems. The main risk is that the paper must keep the contribution framed as a data/knowledge-engineering method rather than as a broad scientometric study.

Stretch target: Information Systems.

Rationale: Information Systems has stronger database and data-intensive systems positioning and is appropriate if the manuscript is upgraded with a stronger same-scope experimental package, threshold grid, ablations, and artifact release. The current manuscript is close in topic but still conservative in evidence, so this route has higher desk-rejection risk unless the L3 artifact package is completed.

Domain backup: Scientometrics.

Rationale: Scientometrics is a strong thematic fit for scholarly metadata and science-of-science evaluation, especially because the manuscript uses OpenAlex/OpenCitations and studies scholarly work identity. The risk is that the current manuscript is primarily a data-engineering/entity-resolution method paper, while Scientometrics reviewers may expect a stronger bibliometric research question and domain interpretation.

## Data & Knowledge Engineering Preflight

Status: provisional preparation only; final upload metadata remains incomplete until author confirmation.

Official guide rechecked: 2026-06-19.

| Requirement area | DKE preparation status | Remaining action before final upload |
| --- | --- | --- |
| Scope fit | The manuscript is positioned around data engineering, knowledge engineering, entity matching, benchmark construction, and reproducible data-processing contracts. | Keep the paper framed as a data/knowledge-engineering method paper during template conversion. |
| Review model | DKE uses single anonymized review. The current anonymous package is only an internal preflight and hygiene check. | Replace placeholders with real author metadata before final upload unless the live system requests anonymization. |
| Abstract | The current abstract is checked against a 250-word limit by `validate_manuscript.py`. | Recheck after any target-template edits. |
| Keywords | `keywords.md` currently contains 1--7 semicolon-separated keywords. | Recheck if journal-specific keyword wording is changed. |
| Highlights | `highlights.md` currently contains 3--5 highlights and is checked against the 85-character limit. | Upload as a separate editable file if required by the Elsevier system. |
| LaTeX route | The generic article draft remains the editable pre-template source. | Convert to Elsevier `elsarticle` only after the authors confirm DKE as the target. |
| Research data statement | The manuscript states that raw third-party data are not redistributed and that full numerical audit requires an external artifact release. | Add the real artifact URL or DOI before final upload. |
| Generative AI declaration | Elsevier author guidance requires AI-tool use in manuscript preparation to be declared when applicable and prohibits listing AI tools as authors. | Fill the final generative AI declaration only after authors confirm the exact tool-use status and statement wording. |
| Author biographies and photographs | DKE author guidance requests a short biography of each author and a passport-type photograph as a separate figure in editable form. | Collect author-approved biographies and photographs before final upload if DKE remains the selected route. |
| Submission checklist | The project already tracks corresponding-author details, uploaded files, reference consistency, permissions, and artifact release status. | Complete all checklist fields inside the live submission system. |

## Official Source Audit

This audit records the publisher-facing constraints that determine the next manuscript pass. It does not replace author confirmation of institutional rankings, journal class, or final submission-system fields.

Official source snapshot date: 2026-06-19.

- DKE guide verified: 2026-06-19.
- DKE guide source URL: https://www.sciencedirect.com/journal/data-and-knowledge-engineering/publish/guide-for-authors.
- Information Systems guide verified: 2026-06-19.
- Scientometrics guide verified: 2026-06-19.

All publisher-page facts in this shortlist were rechecked on 2026-06-19 from the official source links listed below. These checks support manuscript-preparation decisions only; JCR quartile, Chinese Academy of Sciences zone, CCF class, and local institutional category must still be rechecked in the authors' authorized ranking systems before final upload.

### DKE Official Guide Evidence

The DKE source check is an official-guide preflight record, not final target selection. It binds the current preflight package to the publisher's guide URL while leaving `selected_author_guide_source`, `selected_author_guide_source_url`, `selected_author_guide_rechecked_date`, and `selected_target_author_confirmed` incomplete until the authors confirm the final route.

| Official DKE guide item | Verified source fact | Project consequence |
| --- | --- | --- |
| Scope and metrics | ScienceDirect lists DKE with 6.4 CiteScore and 2.6 Impact Factor and describes the journal as publishing data engineering, knowledge engineering, and interface work. | Keep DKE as the primary practical candidate, but treat publisher metrics as screening signals rather than JCR, CAS, CCF, or institutional ranking proof. |
| Review and source files | The guide states single anonymized review and requests editable source material, with LaTeX supported. | Keep the current anonymous Elsevier preflight package separate from final upload, and bind the final source only after author confirmation. |
| Front-matter limits | The guide lists a 250-word abstract limit, 1--7 keywords, and 3--5 highlights with an 85-character limit. | Continue validating abstract, keywords, and highlights before package creation and after any template conversion. |
| Data and declarations | The guide requires research data handling or a data statement, CRediT author contribution reporting, and generative AI disclosure when AI tools were used in manuscript preparation. | Keep artifact URL/DOI, CRediT roles, and the target-specific generative AI declaration as final-upload blockers. |
| Author identity materials | The guide requests a short biography for each author and a passport-type photograph as a separate editable figure. | Collect author-approved biographies and photographs only after author order is confirmed; keep them outside anonymous preflight packages. |

| Candidate | Officially verified constraints | Project implication |
| --- | --- | --- |
| Data & Knowledge Engineering | Elsevier lists 6.4 CiteScore and 2.6 Impact Factor, describes the journal as covering data engineering, knowledge engineering, and their interface, and uses single anonymized review. The author guide requests editable source files, supports LaTeX, limits the abstract to 250 words, requires 1--7 keywords, encourages 3--5 highlights with a maximum of 85 characters each, applies research-data deposit/linking or an explanatory data statement, requires a CRediT author contribution statement, requires a generative AI declaration when AI tools were used in manuscript preparation, and requests short author biographies plus passport-type photographs. | Keep DKE as the primary practical route. The current DKE package is a preflight artifact only; final upload still needs author metadata, target-template binding, a CRediT author contribution statement, author biographies and photographs, a generative AI declaration decision, and a real artifact URL or DOI. |
| Information Systems | Elsevier lists 9.8 CiteScore and 3.4 Impact Factor. Its scope covers data-intensive applications, data models, algorithms, data mining/machine learning, information retrieval with structured data, web semantics, scientific computing, and data science. The guide emphasizes serious experimentation and reproducibility for systems papers, uses single anonymized review, follows the same editable-source, abstract, keyword, highlight, research-data, CRediT, and generative AI declaration requirements as the Elsevier route, and states that the Information Systems data statement is required at submission. | Treat this as a stretch route. Do not target it until the L3 artifact release, same-scope baseline files, threshold logs, stronger reproducibility evidence, final data statement wording, and generative AI declaration wording are complete. |
| Scientometrics | Springer identifies the journal as covering quantitative aspects of the science of science, communication in science, and science policy, and reports a 2024 Impact Factor of 3.5. The journal uses single-blind review, requests title-page author information, recommends ORCID, requires a 150--250 word abstract and 4--6 keywords, allows LaTeX for mathematical content, requires a data availability statement for original research, and states that large-language-model use should be documented while copy-editing-only tool use does not need declaration. | Keep it as a domain backup. Selecting this route would require a stronger science-of-science framing, de-anonymized title-page metadata, Springer formatting, a repository or artifact link that supports the data availability statement, and target-specific AI-use wording. |

## Source-to-Decision Audit

The shortlist uses official publisher pages only to decide manuscript preparation steps. Metrics are screening signals, not ranking proof, and rank-sensitive labels still require institutional confirmation before upload. Review model and author metadata rules determine anonymization. Data statement and artifact link requirements determine final-upload blockers. Recheck publisher pages on submission day because journal metrics, review policies, and formatting instructions can change without notice.

| Source fact class | Current decision use | Submission-day check |
| --- | --- | --- |
| DKE and Information Systems scope statements | Keep the paper framed around data engineering, knowledge engineering, entity matching, benchmark contracts, and reproducible data processing. | Confirm that the selected journal scope still covers data-intensive methods and knowledge/data engineering. |
| Elsevier review model and title-page rules | Treat the anonymous package as a preflight package; prepare real author metadata for final upload. | Confirm whether the live system requests single anonymized or anonymous files at the upload step. |
| Elsevier abstract, keyword, highlight, source-file, and data-statement rules | Keep the abstract within 250 words, keywords within 1--7 entries, highlights within 3--5 bullets and 85 characters, and source files editable. | Re-run the manuscript and submission-package validators after any template or metadata edit. |
| Elsevier author contribution rules | Require the final author list to support a CRediT author contribution statement before upload. | Fill `submission_metadata.yml`, `final_upload_information_request.md`, and the live submission system with author-order-specific contribution roles. |
| DKE author biography and photograph request | Treat short biographies and passport-type photographs as DKE-specific final-upload materials rather than anonymous preflight files. | Collect author-approved biographies and image files after author order is confirmed. |
| Generative AI policy | Elsevier requires disclosure when AI tools are used in manuscript preparation and prohibits AI authorship; Springer requires large-language-model use to be documented but exempts copy-editing-only tool use. | Fill the generative AI declaration status, author review confirmation, AI authorship exclusion, and any target-specific statement text before final upload. |
| Scientometrics title-page, abstract, keyword, and data availability rules | Keep Scientometrics as a domain backup that would need Springer formatting, 150--250 word abstract, 4--6 keywords, and a stronger science-of-science interpretation. | Confirm Springer submission fields and decide whether a domain-facing rewrite is worth the effort. |
| Artifact and data availability requirements | Keep external artifact release as a final-upload blocker rather than a cosmetic repository link. | Add a real artifact URL or DOI and validate checksums before citing result artifacts. |

## Candidate Matrix

| Candidate | Publisher evidence | Fit to IAD-Risk | Pre-submission action |
| --- | --- | --- | --- |
| Information Systems | Elsevier reports 9.8 CiteScore and 3.4 Impact Factor. Its scope covers data-intensive applications, data models, algorithms, data mining/machine learning, information retrieval with structured data, web semantics, scientific computing, and data science. | Strong but demanding. Best if targeting a B-class database/information-systems route. | Complete full artifact release, threshold grid, ablations, and same-scope baseline files before final upload. |
| Data & Knowledge Engineering | Elsevier reports 6.4 CiteScore and 2.6 Impact Factor. Its scope covers database systems, knowledgebase systems, data engineering, knowledge engineering, and the interface of the two fields. | Best practical match for the current manuscript. | Convert to Elsevier LaTeX, keep highlights at 3--5 bullets with at most 85 characters each, add final author metadata, and link the artifact release. |
| Scientometrics | Springer describes the journal as covering quantitative aspects of the production, communication, and use of scientific and technological information. It reports a 2024 Impact Factor of 3.5. | Good domain backup if the manuscript foregrounds scholarly metadata and science-of-science implications. | Reframe the introduction and discussion toward scholarly communication, add stronger manual-validation/domain interpretation, and check Springer formatting. |

## Template and File Implications

If the selected target is an Elsevier journal, the next manuscript pass should:

1. Convert `main.tex` from generic `article` to the Elsevier LaTeX template.
2. Keep the abstract within 250 words.
3. Keep keywords within the journal's 1--7 keyword requirement.
4. Keep highlights as a separate editable file with 3--5 bullets and no bullet over 85 characters.
5. Upload editable source files rather than relying on PDF alone.
6. Provide title page, author names, affiliations, and corresponding-author contact details.
7. Prepare short author biographies and passport-type photographs if the live DKE/Elsevier route requires them.
8. Prepare data availability and artifact-release statements before final upload.
9. Prepare the generative AI declaration or no-use statement required by the live system.

If the selected target is Scientometrics, the next manuscript pass should:

1. Check Springer Nature submission formatting and title-page requirements.
2. Preserve the current conservative claim boundaries around silver labels and manual validation.
3. Strengthen the domain-facing interpretation for scholarly communication and science-of-science readers.
4. Prepare a de-anonymized title page for single-blind review unless the live submission system explicitly requests anonymization.

## Source Links

- Information Systems guide for authors: https://www.sciencedirect.com/journal/information-systems/publish/guide-for-authors
- Data & Knowledge Engineering guide for authors: https://www.sciencedirect.com/journal/data-and-knowledge-engineering/publish/guide-for-authors
- Scientometrics journal page: https://link.springer.com/journal/11192
- Scientometrics submission guidelines: https://link.springer.com/journal/11192/submission-guidelines
