# Cover Letter

Dear Editor,

We submit the manuscript titled "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication" for consideration as a research article.

This work studies a practical failure mode in scholarly entity matching: semantically related papers can share a research agenda without describing the same scholarly work. Such identity-agenda confusion can create false merges in digital libraries, literature review systems, citation graphs, and recommendation pipelines. The manuscript proposes IAD-Risk, a risk-aware framework that separates identity evidence from agenda evidence and gates automatic merges by false-merge risk.

The manuscript contributes a provenance-aware evaluation contract, IAD-Bench, and reports stratified evidence over gold, proxy, and silver labels. In the Open-v2 evidence snapshot, single-space scientific representation baselines show HNFMR 0.790--0.999 on the full pair scope, whereas transformer-backed IAD-Risk variants report same-work F1=0.980 and HNFMR=0.000 on the held-out test scope. The claims are intentionally conservative: OpenAlex and OpenCitations labels are treated as silver hard-negative evidence, not as human gold, and the manuscript does not claim broad method superiority. We also include supplementary material that documents the reproduction levels, fixture rebuild commands, public-source rebuild commands, artifact package requirements, and claim boundaries.

The paper addresses scholarly data integration, entity matching, scientific document representation, and reliable literature intelligence systems.

The manuscript is original, has not been published previously, and is not under consideration elsewhere. All listed authors have approved the submitted version. The authors declare no competing interests. The repository provides source code, small public fixtures, schema contracts, build scripts, and artifact-release instructions; raw third-party data and full experimental outputs are not redistributed in Git and should be obtained from their original sources or from a separate artifact release with manifests and checksums.

Sincerely,

Anonymous Authors
