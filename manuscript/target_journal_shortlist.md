# Target Journal Shortlist

Updated: 2026-06-18

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

Official guide rechecked: 2026-06-18.

| Requirement area | DKE preparation status | Remaining action before final upload |
| --- | --- | --- |
| Scope fit | The manuscript is positioned around data engineering, knowledge engineering, entity matching, benchmark construction, and reproducible data-processing contracts. | Keep the paper framed as a data/knowledge-engineering method paper during template conversion. |
| Review model | DKE uses single anonymized review. The current anonymous package is only an internal preflight and hygiene check. | Replace placeholders with real author metadata before final upload unless the live system requests anonymization. |
| Abstract | The current abstract is checked against a 250-word limit by `validate_manuscript.py`. | Recheck after any target-template edits. |
| Keywords | `keywords.md` currently contains 1--7 semicolon-separated keywords. | Recheck if journal-specific keyword wording is changed. |
| Highlights | `highlights.md` currently contains 3--5 highlights and is checked against the 85-character limit. | Upload as a separate editable file if required by the Elsevier system. |
| LaTeX route | The generic article draft remains the editable pre-template source. | Convert to Elsevier `elsarticle` only after the authors confirm DKE as the target. |
| Research data statement | The manuscript states that raw third-party data are not redistributed and that full numerical audit requires an external artifact release. | Add the real artifact URL or DOI before final upload. |
| Submission checklist | The project already tracks corresponding-author details, uploaded files, reference consistency, permissions, and artifact release status. | Complete all checklist fields inside the live submission system. |

## Official Source Audit

This audit records the publisher-facing constraints that determine the next manuscript pass. It does not replace author confirmation of institutional rankings, journal class, or final submission-system fields.

| Candidate | Officially verified constraints | Project implication |
| --- | --- | --- |
| Data & Knowledge Engineering | Elsevier lists 6.4 CiteScore and 2.6 Impact Factor, describes the journal as covering data engineering, knowledge engineering, and their interface, and uses single anonymized review. The author guide requests editable source files, supports LaTeX, limits the abstract to 250 words, requires 1--7 keywords, encourages 3--5 highlights with a maximum of 85 characters each, and applies research-data deposit/linking or an explanatory data statement. | Keep DKE as the primary practical route. The current DKE package is a preflight artifact only; final upload still needs author metadata, target-template binding, and a real artifact URL or DOI. |
| Information Systems | Elsevier lists 9.8 CiteScore and 3.4 Impact Factor. Its scope covers data-intensive applications, data models, algorithms, data mining/machine learning, information retrieval with structured data, web semantics, scientific computing, and data science. The guide emphasizes serious experimentation and reproducibility for systems papers, uses single anonymized review, and follows the same editable-source, abstract, keyword, highlight, and data-statement requirements as the Elsevier route. | Treat this as a stretch route. Do not target it until the L3 artifact release, same-scope baseline files, threshold logs, and stronger reproducibility evidence are complete. |
| Scientometrics | Springer identifies the journal as covering quantitative aspects of the science of science, communication in science, and science policy, and reports a 2024 Impact Factor of 3.5. The journal uses single-blind review, requests title-page author information, recommends ORCID, requires a 150--250 word abstract and 4--6 keywords, allows LaTeX for mathematical content, and requires a data availability statement for original research. | Keep it as a domain backup. Selecting this route would require a stronger science-of-science framing, de-anonymized title-page metadata, Springer formatting, and a repository or artifact link that supports the data availability statement. |

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
7. Prepare data availability and artifact-release statements before final upload.

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
