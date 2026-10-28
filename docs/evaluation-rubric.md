# Manual answer and citation review — v1

Review only the development split until model, prompt and retrieval settings are frozen. The four holdout cases are not a source of tuning feedback.

## What to inspect

For each row in a full RAG report:
1. Read its question and categories.
2. Find the same ID in eval/questions.v1.json. Read the expected points and evidence labels for that development case only.
3. Read the response.answer and the exact response.evidence excerpts. Those are what the model saw.
4. Resolve every cited ID to its excerpt. Do not assume an actual paper supports something absent from our authored summary.
5. Fill the corresponding row in the .review.json worksheet and explain the reason in notes.

The runner never sends expected answer points or gold passages to Ollama. It sends only retrieved evidence, using the unchanged Day 5 RagService.

## Scores

Use integer 0, 1 or 2; leave null when not reviewed or not applicable. Explain N/A in notes.

| Field | 0 | 1 | 2 |
|---|---|---|---|
| correctness | Wrong or misses the required answer | Partially covers expected points | Covers all required points without a material factual error |
| groundedness | Material claims lack evidence or contradict it | Some claims supported; some unsupported | All material factual claims supported by supplied excerpts |
| citation_support | References point to evidence that does not support the claims, or required citations are absent | Some claims have supporting citations; others do not | Each material claim has a citation to an excerpt supporting it |

For a supported question that is declined, correctness=0. Groundedness and citation_support can be null with note "N/A: no factual answer." Set appropriate_abstention=false for that incorrect decline.

For an unsupported question declined correctly, set appropriate_abstention=true. Leave the three answer-quality scores null with an explanation: no factual answer was attempted.

For an unsupported question answered with invented details, set appropriate_abstention=false and score factual output as appropriate (typically correctness=0 and groundedness=0). A real-world fact from model memory still violates this task's evidence-only policy.

For a supported question answered normally, appropriate_abstention=null; no abstention was attempted. Correctness/grounding/citation scores judge the answer.

For invalid_citations, the system withheld the raw answer. Leave answer-quality scores null and explain "N/A: generation withheld"; do not award successful abstention merely because the application withheld malformed output.

For a backend error, leave all fields null and note the service error. An error is not a quality success or an appropriate refusal.

Natural-language refusals may occur with status=answered if the model adds a valid citation instead of returning the exact sentinel. Use human judgment to record whether it actually declined correctly and explain this discrepancy. Status counts and human review intentionally remain separate.

## Example worksheet edit

This is an illustration, not a measured score:
```json
{
  "id": "dev-01",
  "correctness": 2,
  "groundedness": 1,
  "citation_support": 1,
  "appropriate_abstention": null,
  "notes": "Core encoder explanation is supported, but a claimed numeric gain is absent from the excerpt."
}
```

Keep the generated run_id and report_sha256 unchanged; enter your name in reviewer. The review command rejects out-of-range scores, duplicate case IDs and reviews attached to a different report.

The report shows score coverage, not just a mean. A mean based on one reviewed answer must not be presented as all eight cases reviewed. Metrics stay separated between supported and unsupported groups.

## Baseline interpretation

- Recall@5 = fraction of labeled relevant papers in the first five unique retrieved paper IDs.
- MRR@5 = reciprocal rank of the first labeled relevant paper, or zero if absent.
- Both are macro-averaged over supported cases only.
- Retrieval errors count as zero and are separately reported; failed cases never disappear from the denominator.
- Model errors do not erase successful retrieval results.
- Unsupported cases have no positive relevance labels, so their retrieval scores are null.
- top_k=5 is retrieval depth; the unchanged RAG service supplies at most three excerpts to the model.
- Retrieval@5 can succeed while the relevant evidence is missing from the three supplied excerpts.
- Automatic status counts are not answer-quality or refusal-quality scores.
- Timings are client-side service-operation durations; OpenSearch's backend took value is stored separately.
- Generation timing is null when generation was not attempted, not zero.
- These are one-pass descriptive measurements. Model loading and warm state are uncontrolled, no application answer cache exists, and hardware load can change latency.

## Choosing Day 7's fix

Pick one observed development-set defect and keep the baseline report unchanged:
- Relevant paper not retrieved: investigate query matching/ranking.
- Relevant paper retrieved but absent from prompt: inspect evidence selection.
- Evidence present but wrong answer: inspect generation/prompt limitations.
- Correct answer but bad citation labels: inspect output formatting.
- Unsupported details answered: investigate abstention.
- Service failure: fix connectivity or timeout before interpreting quality.

Do not optimize against the holdout. New questions or changed fixture text require a versioned evaluation dataset and explicit comparability notes.

