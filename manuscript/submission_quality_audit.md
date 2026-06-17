# Submission Quality Audit

## Problem Decomposition

The manuscript must satisfy four quality-gate conditions before submission: the contribution must be clear, the evidence must support the claims, the evaluation must separate label strengths, and the PDF package must be buildable from source.

## Key Conclusion

The package is suitable for Q2/B-class submission preparation under a conservative claim scope. Final submission still depends on the selected journal template, author metadata, and any journal-specific declarations.

## Claim-Evidence Matrix

| Manuscript claim | Evidence location | Decision |
| --- | --- | --- |
| Scholarly entity matching can confuse agenda similarity with work identity. | `manuscript/main.tex`, Introduction and Problem Formulation | Supported as the core problem statement |
| IAD-Risk separates identity, agenda, agenda-non-identity, and false-merge risk signals. | `manuscript/main.tex`, Method | Supported as the method contribution |
| IAD-Risk uses provenance-aware multi-task supervision. | `manuscript/main.tex`, Training Objective | Supported as the training design |
| IAD-Bench separates gold, proxy, silver, LLM-silver, and human-audit evidence. | `manuscript/main.tex`, IAD-Bench; `docs/iad-bench-contract.md` | Supported by the benchmark contract |
| Open-v2 evidence supports targeted hard-negative false-merge suppression. | `manuscript/main.tex`, Experiments table and discussion | Supported within the Open-v2 boundary |
| The method is broadly superior across scholarly domains. | Not supported by current evidence | Excluded from the manuscript |
| Human gold annotation is complete. | Not supported by current evidence | Excluded from the manuscript |

## Reviewer Risk Assessment

| Dimension | Assessment | Required handling |
| --- | --- | --- |
| Contribution | Clear if framed as identity-agenda risk modeling, not a generic deduplication pipeline | Keep the problem formulation explicit in Abstract and Introduction |
| Writing clarity | Acceptable for a first journal submission package | Preserve stable terms: identity, agenda, hard negative, false-merge risk |
| Experimental strength | Strongest evidence is Open-v2; Open-v3 should remain extended evidence | Avoid broad ranking language |
| Evaluation completeness | Label provenance is explicit; human audit remains incomplete | Report gold, proxy, and silver strata separately |
| Method soundness | Risk-aware merge gating is technically coherent and reproducible | Keep thresholds and cannot-link constraints visible |

## Independent Reviewer Checks

| Reviewer lens | Main concern | Judgment | Boundary condition |
| --- | --- | --- | --- |
| Contribution reviewer | Whether the work is more than another entity matching pipeline | Pass | The contribution must remain identity-agenda risk modeling and benchmark provenance, not generic matching |
| Method reviewer | Whether the risk heads and merge gate are technically motivated | Pass | The paper must keep identity, agenda, agenda-non-identity, and false-merge risk as separate signals |
| Experiment reviewer | Whether the empirical evidence is strong enough for Q2/B-class review | Conditional pass | Open-v2 supports the main claim; Open-v3 and source-heldout evidence should be described as extended validation |
| Reproducibility reviewer | Whether readers can rebuild the package and inspect data boundaries | Pass | Raw third-party data are not redistributed; reproduction depends on public sources, scripts, manifests, and checksums |
| Claim-safety reviewer | Whether the paper overclaims human labels or broad superiority | Pass | Human audit and broad method-ranking claims must remain excluded |

## Submission Gate

Pass for conservative Q2/B-class preparation.

The manuscript should be submitted only with the following constraints:

1. Use the selected journal template if the journal requires one.
2. Keep OpenAlex and OpenCitations labels described as silver evidence.
3. Keep human audit described as future validation.
4. Do not claim broad method superiority or completed human gold annotation.
