# Cover Letter

Dear Editor,

We submit the manuscript titled "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication" for consideration as a research article.

This work studies a practical failure mode in scholarly entity matching: semantically related papers can share a research agenda without describing the same scholarly work. Such identity-agenda confusion can create false merges in digital libraries, literature review systems, citation graphs, and recommendation pipelines. The manuscript proposes IAD-Risk, a risk-aware framework motivated by the ambiguity of single-score matching: it exposes identity, agenda, and agenda-non-identity signals separately and gates automatic merges by false-merge risk.

The manuscript also contributes IAD-Bench as a provenance-aware pair contract: it keeps gold identity labels, proxy agenda evidence, silver hard negatives, and human-review targets separate so that label strength, provenance, split, and hard-negative status remain visible during training, evaluation, and claim interpretation.

In the Open-v2 evidence snapshot, the result rows are scope-bounded mechanism evidence rather than a same-scope comparative ranking: single-space scientific representation baselines show HNFMR 0.790--0.999 on the full pair scope, whereas transformer-backed IAD-Risk variants report same-work F1=0.980 and zero observed HNFMR on the held-out test scope, with ordinary FMR still reported separately as 0.001.

The claims are intentionally conservative: OpenAlex and OpenCitations labels are treated as silver hard-negative evidence, not as human gold, the manuscript does not claim broad method superiority, and it does not claim cluster-level deployment quality without cluster artifacts or workload reduction without coverage and review-capacity evidence.

We also include supplementary material that documents the reproduction levels, fixture rebuild commands, public-source rebuild commands, artifact package requirements, and claim boundaries.

The manuscript is positioned for a data and knowledge engineering venue because it treats scholarly work deduplication as a problem of database-oriented scholarly data integration, knowledge engineering for scholarly records, entity matching, benchmark construction, and reproducible data-processing contracts.

The repository provides source code, small public fixtures, schema contracts, build scripts, and artifact-release instructions; raw third-party data and full experimental outputs are not redistributed in Git and should be obtained from their original sources or from a separate artifact release with manifests and checksums.

For a Git-only review, the repository supports installation checks, fixture rebuild validation, public-release boundary checks, and manuscript builds; full numerical audit of the Open-v2 table requires the L2/L3 public-source rebuild or a released external artifact package.

Sincerely,

Anonymous Authors
