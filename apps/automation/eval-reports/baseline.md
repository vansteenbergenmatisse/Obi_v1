# Baseline Evaluation Report

- Timestamp: `baseline`
- Cutoff k: 5
- Ranker: trivial baseline (manifest order, space-scoped, current-status only). No relevance modelling; this is the floor to beat.

## Dataset: `retrieval_smoke` (6 cases)

| Metric | Mean |
| --- | --- |
| hit_rate@5 | 1.0000 |
| mrr | 0.7500 |
| ndcg@5 | 0.8155 |
| precision@5 | 0.2000 |
| recall@5 | 1.0000 |

| Case | Kind | recall@k | mrr | ranked (top 5) |
| --- | --- | --- | --- | --- |
| rs-01 | retrieval | 1.000 | 1.000 | 1001, 1002 |
| rs-02 | retrieval | 1.000 | 0.500 | 1001, 1002 |
| rs-03 | retrieval | 1.000 | 0.500 | 1001, 1002 |
| rs-04 | retrieval | 1.000 | 1.000 | 2001, 2002 |
| rs-05 | retrieval | 1.000 | 0.500 | 2001, 2002 |
| rs-06 | retrieval | 1.000 | 1.000 | 1001, 1002 |

## Dataset: `ambiguity` (3 cases)

| Metric | Mean |
| --- | --- |
| hit_rate@5 | 1.0000 |
| mrr | 0.6667 |
| ndcg@5 | 0.7540 |
| precision@5 | 0.2667 |
| recall@5 | 1.0000 |

| Case | Kind | recall@k | mrr | ranked (top 5) |
| --- | --- | --- | --- | --- |
| amb-01 | ambiguity | 1.000 | 0.500 | 2001, 2002 |
| amb-02 | ambiguity | 1.000 | 0.500 | 1001, 1002 |
| amb-03 | ambiguity | 1.000 | 1.000 | 2001, 2002 |

## Dataset: `permission` (3 cases)

| Metric | Mean |
| --- | --- |
| hit_rate@5 | 0.6667 |
| mrr | 0.2500 |
| ndcg@5 | 0.3539 |
| precision@5 | 0.1333 |
| recall@5 | 0.6667 |

| Case | Kind | recall@k | mrr | ranked (top 5) |
| --- | --- | --- | --- | --- |
| perm-01 | permission | 1.000 | 0.250 | 1001, 1002, 2001, 2002 |
| perm-02 | permission | 1.000 | 0.500 | 1001, 1002, 2001, 2002 |
| perm-03 | permission | 0.000 | 0.000 | 1001, 1002, 2001, 2002 |

## Dataset: `out_of_corpus` (1 cases)

| Metric | Mean |
| --- | --- |
| hit_rate@5 | 0.0000 |
| mrr | 0.0000 |
| ndcg@5 | 0.0000 |
| precision@5 | 0.0000 |
| recall@5 | 0.0000 |

| Case | Kind | recall@k | mrr | ranked (top 5) |
| --- | --- | --- | --- | --- |
| ooc-01 | answer | 0.000 | 0.000 | 1001, 1002, 2001, 2002 |
