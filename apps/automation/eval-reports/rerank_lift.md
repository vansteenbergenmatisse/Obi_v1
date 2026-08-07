# Rerank Lift Report

- Timestamp: `phase3.5.5`
- Dataset: `retrieval_smoke` (6 cases)
- Reranker: `rerank-v3.5`
- Before = fused + permission-filtered ranking (no cross-encoder); After = with the cross-encoder rerank.

| Metric | Before | After | Δ |
| --- | --- | --- | --- |
| precision@5 | 0.2000 | 0.2000 | +0.0000 |
| ndcg@10 | 1.0000 | 0.8770 | -0.1230 |
