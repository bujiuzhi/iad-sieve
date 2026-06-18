# Cover Letter

Dear Editor,

We submit the manuscript titled "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication" for consideration as a research article.

This work studies a practical failure mode in scholarly entity matching: semantically related papers can share a research agenda without describing the same scholarly work. Such identity-agenda confusion can create false merges in digital libraries, literature review systems, citation graphs, and recommendation pipelines. The manuscript proposes IAD-Risk, a risk-aware framework that separates identity evidence from agenda evidence and gates automatic merges by false-merge risk.

The manuscript contributes a provenance-aware evaluation contract, IAD-Bench, and reports stratified evidence over gold, proxy, and silver labels. In the Open-v2 evidence snapshot, the result rows are scope-bounded mechanism evidence rather than a same-scope comparative ranking: single-space scientific representation baselines show HNFMR 0.790--0.999 on the full pair scope, whereas transformer-backed IAD-Risk variants report same-work F1=0.980 and zero observed HNFMR on the held-out test scope. The claims are intentionally conservative: OpenAlex and OpenCitations labels are treated as silver hard-negative evidence, not as human gold, the manuscript does not claim broad method superiority, and it does not claim cluster-level deployment quality without cluster artifacts. We also include supplementary material that documents the reproduction levels, fixture rebuild commands, public-source rebuild commands, artifact package requirements, and claim boundaries.

The paper addresses scholarly data integration, entity matching, scientific document representation, and reliable literature intelligence systems.

This anonymous preflight cover letter does not treat author declarations as finalized. Before final upload, the author-provided metadata must confirm originality, author approval, competing-interest status, funding, author contribution, permission, and generative AI declarations. The repository provides source code, small public fixtures, schema contracts, build scripts, and artifact-release instructions; raw third-party data and full experimental outputs are not redistributed in Git and should be obtained from their original sources or from a separate artifact release with manifests and checksums. For a Git-only review, the repository supports installation checks, fixture rebuild validation, public-release boundary checks, and manuscript builds; full numerical audit of the Open-v2 table requires the L2/L3 public-source rebuild or a released external artifact package.

Sincerely,

Anonymous Authors
