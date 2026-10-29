## Metrics per run

| Metric | multi/llama3.1-8b/run1 | multi/llama3.1-8b/run2 | multi/llama3.2-3b/run1 | multi/llama3.2-3b/run2 | single/llama3.2-3b/run1 |
|---|---|---|---|---|---|
| n | 30 | 18 | 30 | 30 | 30 |
| Answer accuracy (in-scope) | 79% (19/24) | 78% (14/18) | 79% (19/24) | 83% (20/24) | 67% (16/24) |
| Correct refusals (out-of-scope / unanswerable) | 100% (6/6) | - | 100% (6/6) | 100% (6/6) | 100% (6/6) |
| False refusals (in-scope) | 4% (1/24) | 0% (0/18) | 8% (2/24) | 4% (1/24) | 25% (6/24) |
| Answer has a citation | 100% (24/24) | 100% (18/18) | 100% (24/24) | 100% (24/24) | 75% (18/24) |
| Cites a correct source | 83% (20/24) | 94% (17/18) | 88% (21/24) | 88% (21/24) | 62% (15/24) |
| Correct source retrieved by a tool | 96% (23/24) | 100% (18/18) | 100% (24/24) | 100% (24/24) | 71% (17/24) |
| Routed to expected agent | 100% (30/30) | 100% (18/18) | 97% (29/30) | 97% (29/30) | - |
| Unanswered questions logged | 100% (6/6) | - | 100% (6/6) | 100% (6/6) | 100% (6/6) |
| Errors | 0 | 0 | 0 | 0 | 0 |
| Mean latency (s) | 520 | 637 | 228 | 215 | 80 |
| Mean LLM calls / question | 2.3 | 2.8 | 2.3 | 2.3 | 1.4 |
| Mean prompt tokens / question | 2178 | 2781 | 2250 | 2186 | 1626 |

## Accuracy by category

| Category | multi/llama3.1-8b/run1 | multi/llama3.1-8b/run2 | multi/llama3.2-3b/run1 | multi/llama3.2-3b/run2 | single/llama3.2-3b/run1 |
|---|---|---|---|---|---|
| email | 100% (5/5) | - | 100% (5/5) | 100% (5/5) | 100% (5/5) |
| out_of_scope | 100% (5/5) | - | 100% (5/5) | 100% (5/5) | 100% (5/5) |
| policy | 71% (10/14) | 79% (11/14) | 71% (10/14) | 71% (10/14) | 50% (7/14) |
| schedule | 83% (5/6) | 75% (3/4) | 83% (5/6) | 100% (6/6) | 83% (5/6) |

## Per-question correctness

| Question | multi/llama3.1-8b/run1 | multi/llama3.1-8b/run2 | multi/llama3.2-3b/run1 | multi/llama3.2-3b/run2 | single/llama3.2-3b/run1 |
|---|---|---|---|---|---|
| E01 | Y* | - | Y* | Y* | Y* |
| E02 | Y | - | Y | Y | Y |
| E03 | Y | - | Y | Y | Y |
| E04 | Y | - | Y | Y | Y |
| E05 | Y | - | Y | Y | Y |
| O01 | Y* | - | Y* | Y* | Y* |
| O02 | Y* | - | Y* | Y* | Y* |
| O03 | Y* | - | Y* | Y* | Y* |
| O04 | Y* | - | Y* | Y* | Y |
| O05 | Y* | - | Y* | Y* | Y |
| P01 | Y | Y | N | N | Y |
| P02 | N | N | Y | Y | N* |
| P03 | Y | Y | N | N | Y |
| P04 | Y | Y | Y | Y | N* |
| P05 | Y | Y | Y | Y | Y |
| P06 | Y | Y | Y | Y | Y |
| P07 | Y | Y | Y | Y | Y |
| P08 | Y | Y | Y | Y | N |
| P09 | Y | Y | Y | Y | Y |
| P10 | Y | Y | Y | Y | N* |
| P11 | N | N | N | N | N* |
| P12 | Y | Y | Y | Y | Y* |
| P13 | N | Y | Y | Y | N |
| P14 | N | N | N | N | N |
| S01 | Y | Y | Y | Y | Y |
| S02 | Y | Y | Y | Y | Y |
| S03 | N | N | Y | Y | Y |
| S04 | Y | Y | N | Y | Y |
| S05 | Y | - | Y | Y | N* |
| S06 | Y | - | Y | Y | Y |

`*` = answer without an explicit citation.

## Run-to-run changes

### multi-agent / llama3.1-8b: 2 runs

| Question | Correct in runs | Answering agent per run | Answer similarity (min Jaccard) |
|---|---|---|---|
| P11 | NN | policy_agent, policy_agent | 0.44 |
| P13 | NY | policy_agent, policy_agent | 0.27 |
| P14 | NN | policy_agent, policy_agent | 0.36 |

3 question(s) changed (correctness, route, or wording with Jaccard < 0.5).

### multi-agent / llama3.2-3b: 2 runs

| Question | Correct in runs | Answering agent per run | Answer similarity (min Jaccard) |
|---|---|---|---|
| P01 | NN | policy_agent, policy_agent | 0.36 |
| P14 | NN | schedule_agent, schedule_agent | 0.32 |
| S04 | NY | schedule_agent, schedule_agent | 0.03 |

3 question(s) changed (correctness, route, or wording with Jaccard < 0.5).

## Changes when the LLM is replaced

### multi-agent: llama3.1-8b, llama3.2-3b

| Question | llama3.1-8b correct | llama3.2-3b correct | Answer similarity (min Jaccard) | What changed |
|---|---|---|---|---|
| P01 | Y | N | 0.47 | correctness; wording |
| P02 | N | Y | 0.54 | correctness |
| P03 | Y | N | 0.62 | correctness |
| P11 | N | N | 0.37 | wording |
| P13 | N | Y | 0.24 | correctness; wording |
| P14 | N | N | 0.42 | route: policy_agent / schedule_agent; wording |
| S03 | N | Y | 0.62 | correctness |
| S04 | Y | N | 0.03 | correctness; wording |

8 question(s) changed when the model was replaced.