# Routing Lift Report

- Timestamp: `9.5.2`
- Dataset: `connection_routing` (2 cases)
- Retrieve k: 50
- Off = retrieval with NO session labels (pre-9.4.1 no-op path, every candidate served); On = retrieval under the chat's four directed-connection labels (the hard label filter).
- recall must not drop off→on (no gold-set loss, rule 11); served_precision rises and served_count falls as routing narrows the candidate set.

| Metric | Off | On | Δ |
| --- | --- | --- | --- |
| recall | 1.0000 | 1.0000 | +0.0000 |
| served_precision | 0.1667 | 0.3333 | +0.1667 |
| served_count | 6.0000 | 3.0000 | -3.0000 |
