# StarMap System Algorithms and Project Weights

Last audited: `2026-05-03`

This document is a code-level reference for the current StarMap implementation. It focuses on three things:

1. What the 18 main algorithm-bearing features do.
2. What rules, formulas, thresholds, and heuristics they currently use.
3. Which project settings actually change behavior or weights.

Count rule for the "18 features":

- `Challenge Stardust retrieval` and `Challenge Stardust ranking` are treated as one combined feature.
- Pure CRUD, auth, modal state, and simple import/export plumbing are not counted as algorithmic features.

## 1. Current Project Settings and Defaults

The current project-level settings live in `frontend/index.html` and are stored in localStorage per project. Not every setting changes an algorithm; some only affect preload or presentation.

### 1.1 Settings that change ranking, search, or candidate selection

| Setting key | Default | Current effect | Weight / rule |
| --- | --- | --- | --- |
| `use_citation_count_filter` | `false` | Enables citation-count quality assist inside project similarity scoring | If ON, final similarity becomes `(text_similarity * (1 - blend_weight)) + (citation_score * blend_weight)` |
| `citation_count_weight_tier` | `medium` | Sets the blend strength for the citation-count assist | `low = 0.10`, `medium = 0.12`, `high = 0.15` |
| `literature_watch_range` | `3m` | Sets Literature Watch freshness window and search range | `3m = 92 days`, `1y = 365 days`, `3y = 1095 days` |
| `literature_watch_disciplines` | `[]` | Affects Literature Watch venue bonus, query context, and discipline framing | Up to `3` disciplines |
| `literature_watch_scholars` | `[]` | Affects Scholar Watch source expansion | Up to `20` scholars |
| `literature_watch_journals` | `[]` | Affects Journal Watch source expansion and watched-journal lift | Up to `20` journals |
| `literature_watch_journals[].target_watch_weight` | `standard` | Gives watched journals extra ranking lift in Literature Watch | `off = 0.00`, `standard = 0.12`, `priority = 0.20` |
| `chart_render_limit` | `500` | Caps how many papers the semantic cluster UI feeds into backend clustering / visualization | Allowed values: `150`, `300`, `500` |

### 1.2 Settings that change workflow but not weights

| Setting key | Default | Effect |
| --- | --- | --- |
| `use_background_precompute` | `true` | Preloads citation-cluster-related work when opening a project |
| `use_llm_theme_naming` | `true` | Allows LLM renaming of theme/citation cluster labels; does not change assignments |
| `use_zotero_sync_preload` | `true` | Preloads Zotero sync context; no ranking effect |
| `show_network_target_link_rainbow` | `false` | Visualization-only network styling |

### 1.3 Important implementation note

The project setting naming is now aligned with the implementation:

- the setting is `use_citation_count_filter`
- the blended value in the frontend is `paper.citation_count`
- the compression formula is:

```text
citation_score = min(log(1 + citation_count) / log(1 + 200), 1)
```

Legacy localStorage fallback still reads old keys such as `use_fwci_filter` and `fwci_weight_tier`, but new writes use the citation-count names.

### 1.4 Source references

- `frontend/index.html:3334-3421`
- `frontend/index.html:4149-4157`
- `frontend/index.html:7673-7753`
- `frontend/index.html:9613-9659`

## 2. Shared Scoring Primitives Used Across Multiple Features

Several downstream features reuse the same paper-quality and relevance primitives. It is useful to understand these first.

### 2.1 Project text similarity

Base project similarity is computed from weighted cosine similarity:

```text
text_score =
  cosine(target_title, paper_title) * 1.5
+ cosine(target_abstract, paper_abstract) * 1.0
+ cosine(target_current_content, paper_current_content) * 0.5   (only if both exist)

weight =
  2.5
+ 0.5 if current_content is used

normalized_text_similarity = text_score / weight
```

If citation-count assist is ON:

```text
final_similarity =
  normalized_text_similarity * (1 - citation_blend_weight)
+ compressed_citation_score * citation_blend_weight
```

### 2.2 Paper status weight

Used downstream in Evidence / Challenge scoring:

| Status | Weight |
| --- | --- |
| `Core` | `1.00` |
| `Pending` | `0.72` |
| `Underweight` | `0.62` |
| `Unread` | `0.48` |
| default / unknown | `0.52` |

### 2.3 Paper recency score

| Paper age | Score |
| --- | --- |
| `<= 2 years` | `1.00` |
| `<= 5 years` | `0.82` |
| `<= 10 years` | `0.62` |
| `<= 20 years` | `0.46` |
| `> 20 years` | `0.32` |
| unknown year | `0.35` |

### 2.4 Paper quality score

```text
citation_score = min(log1p(citation_count) / log1p(500), 1.0)

completeness_score =
  fraction of available fields among:
  title, authors, year, abstract, publication_venue

quality_score =
  citation_score * 0.45
+ completeness_score * 0.35
+ core_bonus 0.12
+ fulltext_bonus 0.08
```

### 2.5 Claim candidate metrics

Many claim-facing features reuse the same claim-side metrics:

```text
claim_relevance =
  title_score * 0.29
+ abstract_score * 0.31
+ notes_score * 0.20
+ body_score * 0.20
+ exact_phrase_bonus 0.08

challenge_hint =
  max(challenge_marker) * 0.55
+ max(phrase_overlap) * 0.30
+ max(notes/body token overlap) * 0.15

setup_hint =
  max(setup_marker) * 0.58
+ max(phrase_overlap) * 0.22
+ max(notes/body token overlap) * 0.20

support_hint =
  max(support_marker) * 0.34
+ claim_relevance * 0.46
+ max(abstract/body phrase overlap) * 0.20
```

### 2.6 Source references

- `frontend/index.html:23955-23972`
- `backend/main.py:1283-1395`

## 3. The 18 Algorithmic Features

### 3.1 PDF Metadata Extraction

### Goal

When a user imports local PDFs, StarMap tries to extract a usable `title` and `abstract` before the paper is scored or shown elsewhere.

### Entry points

- Dashboard / workspace `Import PDFs`

### Current method

1. Use PDF.js to read text from the PDF.
2. Send extracted text to the LLM with a strict JSON schema.
3. Ask the LLM to return only `title` and `abstract`.
4. If extraction fails, queue the file for retry.

### Rules and thresholds

- The pipeline is schema-constrained rather than open-form summarization.
- Extraction is deliberately narrow: this step does not generate notes, stance, or critique.
- Failure handling is queue-based, so this is resilient but still LLM-dependent.

### Dependencies

- LLM: yes
- OpenAlex: no
- Zotero: no

### Project settings that matter

- None directly

### Source references

- `frontend/index.html:24441-24692`

### 3.2 Project Similarity Scoring and Top Related Papers Ranking

### Goal

Rank project papers against the current thesis target so the main paper list, similarity refresh, and several downstream workflows have a stable relevance signal.

### Entry points

- `Top Related Papers`
- project similarity refresh
- several downstream ranking utilities

### Current method

1. Build text vectors for the project target.
2. Build text vectors for each paper.
3. Compute weighted cosine similarity across title / abstract / current content.
4. Optionally blend in compressed citation count if the project setting enables it.

### Main formula

```text
text_similarity =
  [title_cos * 1.5 + abstract_cos * 1.0 + current_content_cos * 0.5] / [2.5 or 3.0]

if citation-count assist OFF:
  final_similarity = text_similarity

if citation-count assist ON:
  final_similarity =
    text_similarity * (1 - blend_weight)
  + compressed_citation_score * blend_weight
```

### Current weights

- title: `1.5`
- abstract: `1.0`
- current content: `0.5`
- citation blend: `0.10`, `0.12`, or `0.15`

### Dependencies

- LLM: no
- OpenAlex: optional, only when backfilling citation counts
- Zotero: no

### Project settings that matter

- `use_citation_count_filter`
- `citation_count_weight_tier`

### Source references

- `frontend/index.html:23955-24120`
- `frontend/index.html:9613-9659`

### 3.3 Focused StarMap Neighbor Ranking

### Goal

When the user focuses the map around one paper, StarMap re-ranks the local neighborhood by paper-to-paper similarity rather than only project-to-paper similarity.

### Entry points

- `StarMap Visualization` focused view

### Current method

1. Take the focal paper's `network_vec`.
2. Compare it against other papers' `network_vec`.
3. Rank neighbors by cosine similarity to the focal paper.

### Rules and thresholds

- This is a local reordering step.
- It depends on precomputed paper vectors already stored in the workspace.
- No citation-count blend is added here.

### Dependencies

- LLM: no
- OpenAlex: no
- Zotero: no

### Project settings that matter

- None directly

### Source references

- `frontend/index.html:4843-4897`

### 3.4 Citation Graph Construction

### Goal

Turn project papers into a directed citation graph that can support network visualization, citation clusters, and one-hop expansion features.

### Entry points

- `Citation Graph`
- `Citation Cluster`
- challenge-side citation expansion

### Current method

1. Enrich papers with OpenAlex identifiers and references.
2. Match project papers against each other's citation signatures.
3. Build a directed graph from in-project citation links.
4. Remove duplicates and store graph edges.

### Rules and thresholds

- Uses OpenAlex metadata as the canonical citation source.
- Max top-paper context is capped by backend global limits.
- Graph build runs as an async job.

### Dependencies

- LLM: no
- OpenAlex: yes
- Zotero: no

### Project settings that matter

- `use_background_precompute` changes whether some graph-related work starts early

### Source references

- `backend/main.py:59`
- `backend/main.py:6230-6353`
- `frontend/index.html:25903-26025`

### 3.5 Citation Cluster Discovery

### Goal

Find meaningful citation communities inside the project graph so the user can inspect literature structure from a graph-topology angle.

### Entry points

- `Auto Cluster Themes` -> `Citation Cluster`

### Current method

This is a hybrid graph procedure, not a single off-the-shelf algorithm:

1. Build the citation topology graph.
2. Find weakly connected components.
3. For the primary component, choose strong seed nodes.
4. Partition the component outward from the seeds.
5. Split oversized clusters.
6. Rebalance small or awkward clusters.
7. Use a Louvain-style community pass for some leftover node groups.
8. Return a mixture of recommended clusters and fallback clusters.

### Current constants

| Constant | Value |
| --- | --- |
| algorithm version | `v2` |
| target size | `20` |
| min balanced size | `12` |
| max balanced size | `28` |
| min recommended size | `16` |
| max recommended display size | `35` |
| modal recommended cluster count | `5` |

### Recommendation score used when ordering clusters

```text
cluster_recommendation_score =
  size * 8
+ avg_similarity * 100
+ total_indegree * 0.35
+ total_degree * 0.12
```

### Dependencies

- LLM: no
- OpenAlex: indirectly yes, because graph construction depends on OpenAlex
- Zotero: no

### Project settings that matter

- `use_background_precompute`

### Source references

- `frontend/index.html:4946-4958`
- `frontend/index.html:5444-6028`

### 3.6 Citation Cluster Core-Paper Ranking

### Goal

Within each citation cluster, identify the papers most representative of that cluster.

### Entry points

- `Citation Cluster` detail views
- cluster naming context

### Current method

Papers inside a cluster are sorted by:

1. higher indegree first
2. then higher degree
3. then higher project similarity

The top N become representative papers.

### Current constants

- core paper limit: `5`

### Dependencies

- LLM: no
- OpenAlex: indirectly yes
- Zotero: no

### Project settings that matter

- None directly

### Source references

- `frontend/index.html:6006-6028`

### 3.7 Citation Cluster LLM Naming and Overview Generation

### Goal

Take graph-formed clusters and turn them into more readable themes for users.

### Entry points

- `Citation Cluster` modal / summary cards

### Current method

1. Select representative papers from each cluster.
2. Feed core titles / abstracts into the LLM.
3. Ask for a clearer cluster label and overview.
4. Fall back if the LLM is unavailable or fails.

### Rules and thresholds

- This changes labels and explanations only.
- It does not change cluster membership.

### Dependencies

- LLM: yes
- OpenAlex: no
- Zotero: no

### Project settings that matter

- `use_llm_theme_naming`

### Source references

- `frontend/index.html:6240-6335`

### 3.8 Semantic Cluster

### Goal

Group papers by topical similarity rather than citation topology.

### Entry points

- `Auto Cluster Themes` -> `Semantic Cluster`

### Current method

This is a backend semantic clustering pipeline with lightweight hashed text vectors:

1. Select assignment papers and seed papers.
2. Build weighted term bags from title / abstract / current content.
3. Add bigrams for title and abstract.
4. Hash weighted terms into a `384`-dimensional signed vector with IDF-like scaling.
5. Try cluster counts `3`, `4`, and `5`.
6. Initialize centroids with a k-means++ style strategy.
7. Iterate assignment / centroid updates for up to `8` rounds.
8. Rebalance undersized clusters.
9. Score the run and keep the best result.
10. Assign papers to the nearest centroid and produce representative papers.

### Current weights and constants

| Item | Value |
| --- | --- |
| algorithm version | `backend-v1` |
| vector dim | `384` |
| default seed limit | `60` |
| cluster count options | `3, 4, 5` |
| min cluster size | `4` |
| current-content text cap | `1000 chars` |
| max display papers per cluster | `10` |
| quality retry threshold | `0.055` |

Weighted terms:

- title: `3.0`
- abstract: `1.8`
- current content: `0.9`
- bigrams: `base_weight * 1.15`

Undersized-cluster penalty:

```text
penalty += (min_cluster_size - actual_size) * 0.28
```

Target-side vector building uses the same weights:

- target title: `3.0`
- target abstract: `1.8`
- target current content: `0.9`

### Dependencies

- LLM: no
- OpenAlex: no
- Zotero: no

### Project settings that matter

- `chart_render_limit` changes frontend assignment limit passed into clustering
- `use_llm_theme_naming` may change only the human-facing label layer afterward

### Source references

- `backend/main.py:251-259`
- `backend/main.py:4222-4398`
- `backend/main.py:4488-4635`
- `frontend/index.html:22065-22120`

### 3.9 Evidence Board Candidate Recall

### Goal

Given a claim, pull a manageable candidate pool of project papers that might support, challenge, or contextualize it.

### Entry points

- `Evidence Board`

### Current method

1. Build claim tokens and phrases.
2. Score each paper against the claim across title / abstract / notes / current content.
3. Compute derived signals such as `claim_relevance`, `challenge_hint`, `setup_hint`, `support_hint`.
4. Add paper status, quality, fulltext availability, recency, and project similarity.
5. Seed candidates from multiple ranked lists.
6. Diversify by cluster key so one local area of the literature does not monopolize the board.

### Candidate score formula

```text
candidate_score =
  claim_relevance * 0.32
+ project_similarity * 0.14
+ status_weight * 0.11
+ notes_relevance * 0.12
+ quality_score * 0.13
+ fulltext_bonus * 0.08
+ recency_score * 0.05
+ support_score * 0.05
```

### Multi-list seeding rules

Seed lists are drawn with dynamic caps such as:

- claim-ranked: `max(10, ceil(max_candidates * 0.45))`
- support-ranked: `max(8, ceil(max_candidates * 0.35))`
- challenge-ranked: `max(6, ceil(max_candidates * 0.22))`
- setup-ranked: `max(6, ceil(max_candidates * 0.22))`
- score-ranked: `max(8, ceil(max_candidates * 0.35))`
- similarity-ranked: `max(5, ceil(max_candidates * 0.22))`
- quality-ranked: `max(4, ceil(max_candidates * 0.18))`
- core-ranked: `max(4, ceil(max_candidates * 0.18))`
- cluster leaders: `max(4, ceil(max_candidates * 0.25))`

Diversification rule:

```text
max_per_cluster = max(2, min(5, ceil(max_candidates / 4)))
```

### Global limits

- `MAX_CLAIM_CANDIDATES = 96`
- request default: `36`

### Dependencies

- LLM: no, for recall itself
- OpenAlex: no
- Zotero: no

### Project settings that matter

- Indirectly affected by the project's similarity scores

### Source references

- `backend/main.py:103`
- `backend/main.py:1336-1455`

### 3.10 Evidence Board Stance Classification

### Goal

Place each recalled candidate into `support`, `challenge`, `setup`, or `pending`.

### Entry points

- `Evidence Board` result columns

### Current method

This is a hybrid heuristic + LLM classification stage:

1. Start from the candidate metrics already built during recall.
2. Compute heuristic support / challenge / setup signals.
3. Optionally ask the LLM for structured stance judgments.
4. Apply thresholds to assign a stance.

### Current heuristic combination

```text
support_signal = support_hint * 0.52 + claim_relevance * 0.48
challenge_signal = challenge_hint * 0.64 + claim_relevance * 0.36
setup_signal = setup_hint * 0.70 + claim_relevance * 0.30
```

### Current thresholds

- classify as `challenge` if:
  - `challenge_signal >= 0.32`
  - and it beats support by at least `0.05`
  - and it is not weaker than setup
- classify as `setup` if:
  - `setup_signal >= 0.34`
  - and `setup >= support + 0.03`
- classify as `support` if:
  - `support_signal >= 0.36`
- otherwise:
  - `pending`

### Dependencies

- LLM: optional
- OpenAlex: no
- Zotero: no

### Project settings that matter

- None directly

### Source references

- `backend/main.py:1943-2014`

### 3.11 Evidence Snippet Grounding and Local Extraction

### Goal

Attach grounded evidence snippets to evidence cards so users can see why a paper was matched.

### Entry points

- `Evidence Board`
- `Read A Paper`

### Current method

There are two related snippet extractors:

1. claim-oriented evidence snippet extraction
2. read-paper query snippet extraction

Both split source text into sentence-like segments, score them, dedupe them, and keep the best few.

### Claim-oriented snippet score

```text
snippet_score =
  overlap * 0.34
+ phrase_overlap * 0.28
+ stance_alignment_bonus * 0.18
+ length_quality * 0.08
+ source_weight * 0.12
```

Source weights:

- abstract: `1.00`
- notes: `0.94`
- current content: `0.90`

### Read-paper snippet score

```text
snippet_score =
  overlap * 0.40
+ phrase_overlap * 0.30
+ length_quality * 0.16
+ source_weight * 0.14
```

Source weights:

- abstract: `1.00`
- current content: `0.95`
- notes: `0.92`

### Dependencies

- LLM: optional upstream, but local extraction itself is not LLM-only
- OpenAlex: no
- Zotero: no

### Project settings that matter

- None directly

### Source references

- `backend/main.py:1514-1668`

### 3.12 Read A Paper Deep Analysis

### Goal

Provide a critical reading view for one paper or a small cluster of papers, emphasizing weaknesses and actionable questions rather than polite summary.

### Entry points

- `Read A Paper PDF`

### Current method

1. Limit and normalize the selected papers.
2. Build a strict JSON prompt for the LLM.
3. Ask for:
   - `deep_read_summary`
   - `user_question_answer`
   - `paper_takeaways`
   - `threats_to_validity`
   - `external_validity_limits`
   - `design_vulnerabilities`
   - `improvement_opportunities`
   - `questions_to_press`
4. Post-process the result.
5. Ground snippet candidates back to local paper text where possible.

### Current limits

| Item | Value |
| --- | --- |
| max papers per request | `12` |
| max questions to press | `6` |
| summary max length | `2200` |
| finding detail max length | `1400` |

### Dependencies

- LLM: yes
- OpenAlex: no
- Zotero: no

### Project settings that matter

- None directly

### Source references

- `backend/main.py:90-96`
- `backend/main.py:1163-1170`
- `backend/main.py:1857-1939`

### 3.13 Challenge Expand

### Goal

Given a challenge-side seed paper in the Evidence Board, find one-hop neighboring papers that may extend the challenge trail.

### Entry points

- `Evidence Board` -> challenge paper -> `Expand Trail`

### Current method

1. Resolve the seed paper on OpenAlex.
2. Pull one-hop `references` and `cited_by` works.
3. Score each candidate heuristically against:
   - claim relevance
   - challenge language
   - seed similarity
   - paper quality
   - relation type
4. Ask the LLM to judge the strongest candidates.
5. Blend heuristic and LLM scores.
6. Return challenge-adjacent recommendations.

### Seed-similarity subscore

```text
seed_similarity =
  token_overlap * 0.56
+ phrase_overlap * 0.32
+ challenge_marker * 0.12
```

### Heuristic challenge score

```text
heuristic_score =
  challenge_hint * 0.33
+ claim_relevance * 0.29
+ seed_similarity * 0.28
+ quality_score * 0.10
+ relation_bonus
```

Relation bonus:

- `cited_by`: `0.05`
- `reference`: `0.03`

Inclusion gate:

- keep if `score >= 0.26` and one of:
  - `challenge_hint >= 0.16`
  - `seed_similarity >= 0.20`
  - `claim_relevance >= 0.24`

### LLM blend

```text
final_score =
  llm_strength * 0.56
+ heuristic_score * 0.44
```

Candidate is dropped only if:

- LLM/include says no
- and `final_score < 0.34`

### Current limits

| Item | Value |
| --- | --- |
| references default | `12` |
| cited-by default | `12` |
| candidate shortlist | `18` |
| returned results default | `12` |
| request validation bounds | `4..20` |

### Dependencies

- LLM: optional but normally used
- OpenAlex: yes
- Zotero: no

### Project settings that matter

- None directly

### Source references

- `backend/main.py:98-102`
- `backend/main.py:2200-2438`
- `backend/main.py:4012-4014`

### 3.14 Challenge Stardust Retrieval and Ranking

### Goal

Build a challenge-side mini-library from either a challenge paper or a claim-only seed, combining semantic retrieval and citation-neighborhood evidence.

### Entry points

- `Challenge Stardusts`
- `New From Claim`
- `New From Challenge Paper`

### Current method

This is the most complex retrieval/ranking pipeline in the system:

1. Normalize creation mode:
   - `challenge_paper`
   - `claim_only`
2. Build a seed representation.
3. Build up to `5` semantic queries from:
   - seed title
   - sub-target thesis
   - claim text
   - evidence explanations
   - project target context
4. Search OpenAlex for each semantic query.
5. Pull hop-1 citation neighbors if a real seed paper exists.
6. Merge and dedupe candidates across discovery sources.
7. Annotate candidates with relationship type and discovery source.
8. Score each candidate.
9. Apply inclusion gates.
10. If too few pass, use a weaker fallback threshold.

### Current retrieval limits

| Item | Value |
| --- | --- |
| max returned stardust papers | `50` |
| hop-1 references | `16` |
| hop-1 cited-by | `16` |
| semantic query count | `5` |
| semantic results per query | `12` |
| candidate pool cap | `120` |
| max stardust records per project | `5` |

### Query construction pattern

The five semantic queries are currently assembled from combinations of:

- seed title
- first `8` sub-target thesis tokens
- seed-title tokens + thesis tokens
- thesis tokens + claim tokens + evidence tokens
- seed-title tokens + project-target tokens + thesis tokens

### Scoring formula

First compute:

```text
semantic_overlap =
  seed_similarity * 0.58
+ claim_relevance * 0.42
```

Then compute:

```text
challenge_score =
  semantic_overlap * 0.50
+ challenge_hint * 0.20
+ claim_relevance * 0.12
+ quality_score * 0.10
+ semantic_bonus
+ semantic_linked_bonus
+ citation_bonus
```

Bonuses:

- `semantic_bonus = 0.045` if discovered by `semantic_supplement`
- `semantic_linked_bonus = 0.03` if linked as `reference`
- `semantic_linked_bonus = 0.038` if linked as `cited_by`
- `semantic_linked_bonus = 0.05` if linked in both directions
- `citation_bonus = min(log1p(citations) / log1p(250), 1.0) * 0.02`

Main inclusion gate:

- `challenge_score >= 0.27`
- and at least one of:
  - `semantic_overlap >= 0.24`
  - `claim_relevance >= 0.28`
  - `seed_similarity >= 0.22`
  - semantic supplement plus `semantic_overlap >= 0.30`

Fallback behavior:

- if too few pass, candidates with `challenge_score >= 0.22` can still be used downstream

### Dependencies

- LLM: no for retrieval/ranking itself
- OpenAlex: yes
- Zotero: no

### Project settings that matter

- Indirectly influenced by project similarity and paper quality fields already present in the project

### Source references

- `backend/main.py:74-85`
- `backend/main.py:2483-2765`
- `backend/main.py:2893-2902`

### 3.15 Challenge Stardust Type Inference

### Goal

Auto-group Stardust papers into interpretable challenge types so the user can reason about what kind of counterpressure exists.

### Entry points

- `Challenge Stardusts` grouped type views

### Current method

This is a rule-based keyword classifier with small contextual bonuses.

Current type buckets:

- `direct_contradiction`
- `boundary_condition`
- `alternative_mechanism`
- `null_weak_effect`
- `context_specific_caveat`
- `methodological_challenge`

### Current rules

- Most keyword hits are worth `2` points each.
- Additional small bonuses are added from:
  - non-empty `caveat`
  - low `quality_score`
  - low `claim_relevance`
  - `seed_similarity` much larger than `claim_relevance`
  - claim-specific terms like `signal` or `default risk`

Fallback logic:

- if no type gets a meaningful score:
  - prefer `context_specific_caveat` when a caveat exists
  - otherwise sometimes prefer `alternative_mechanism`
  - or `boundary_condition` for deeper-hop items

### Dependencies

- LLM: no
- OpenAlex: no
- Zotero: no

### Project settings that matter

- None directly

### Source references

- `frontend/index.html:13894-14030`

### 3.16 Project Literature Watch Recommendation Engine

### Goal

Recommend newly published outside papers that are likely relevant to the current project, scholar list, or journal list.

### Entry points

- `Project Literature Watch`
- `Scholar Watch`
- `Journal Watch`

### Current method

1. Build watch context from project thesis and top core papers.
2. Normalize the watch range.
3. Fetch candidates from OpenAlex according to mode:
   - target
   - scholar
   - journal
4. Build weighted token vocabulary from thesis and watch strategy.
5. Compute lexical relevance and query match.
6. Compute quality and freshness.
7. Optionally run an LLM semantic rerank on shortlisted papers.
8. Apply mode-specific thresholds.
9. Compute final `watch_score`.

### Context construction rules

- only the top `50` core papers are used for context

Fallback token weights:

- target title: `5.0`
- target abstract: `3.0`
- discipline venue keywords: `1.5`
- core paper title: `2.0`
- core paper abstract: `1.0`

Main token weights:

- target title: `5.5`
- target abstract: `3.5`
- focus phrase: `4.0`
- each facet: `3.0`
- each query: `3.5`
- core paper title: `2.0`
- core paper abstract: `1.0`

### Relevance formula

```text
lexical_score = overlap_weight / total_weight

relevance =
  lexical_score * 0.78
+ best_query_score * 0.22
```

If semantic rerank exists:

```text
final_relevance =
  semantic_relevance * 0.72
+ lexical_relevance * 0.28
```

### Quality formula

```text
quality_score =
  citation_score * 0.58
+ fwci_score * 0.12
+ venue_bonus
+ watched_journal_bonus
+ completeness_bonus
```

Completeness bonus pieces:

- venue: `+0.08`
- doi: `+0.05`
- abstract: `+0.07`

Venue bonus:

- top discipline venue match: `+0.22`
- discipline venue keyword match: `+0.10`

Watched journal bonus:

- `off = 0.00`
- `standard = 0.12`
- `priority = 0.20`

### Freshness formula

- score decays linearly inside the selected window
- range windows:
  - `3m = 92 days`
  - `1y = 365 days`
  - `3y = 1095 days`

### Thresholds by mode

Lexical threshold:

- scholar: `0.12`
- journal: `0.14`
- target: `0.18`

Recommendation threshold with semantic rerank:

- scholar: `0.36`
- journal: `0.34`
- target: `0.42`

Recommendation threshold without semantic rerank:

- scholar: `0.22`
- journal: `0.24`
- target: `0.28`

### Final watch score

```text
watch_score =
  final_relevance * 0.65
+ quality_score * 0.30
+ freshness_score * 0.05
```

### Dependencies

- LLM: optional semantic rerank
- OpenAlex: yes
- Zotero: no

### Project settings that matter

- `literature_watch_range`
- `literature_watch_disciplines`
- `literature_watch_scholars`
- `literature_watch_journals`
- each watched journal's `target_watch_weight`

### Source references

- `backend/main.py:4135-4167`
- `backend/main.py:5060-5268`
- `backend/main.py:5880-6035`
- `frontend/index.html:15764-16006`

### 3.17 Workspace / All Papers Search

### Goal

Help users quickly find papers inside the current repository, first with cheap local rules and then, if needed, with LLM semantic search.

### Entry points

- `All Papers`
- workspace paper search

### Current method

1. Normalize text to lowercase alphanumeric tokens.
2. Run local fuzzy inclusion:
   - full normalized query is a substring
   - or every query token appears somewhere
3. Score the locally matched papers.
4. Sort by query score, then by project similarity.
5. If results are poor and LLM search is available, run semantic item search fallback.

### Local scoring formula

Exact-match bonus:

- title contains full query: `+120`
- abstract contains full query: `+85`
- venue contains full query: `+45`
- authors contains full query: `+36`
- combined fields contain full query: `+24`

Per-token bonuses:

- title: `+16`
- abstract: `+10`
- venue: `+7`
- authors: `+6`
- year exact token: `+5`

Query-length bonus:

- `+ min(tokens * 2, 12)`

Tie-break:

- higher project `similarity`

### Heuristic for when similarity should be prioritized

Search behavior pays extra attention to similarity when:

- a workspace filter is active
- or query word count is greater than `4`

### Dependencies

- LLM: optional fallback
- OpenAlex: no
- Zotero: no

### Project settings that matter

- None directly, but existing similarity scores matter as tie-breakers

### Source references

- `frontend/index.html:16157-16265`
- `frontend/index.html:17371-17640`

### 3.18 Repository Analytics

### Goal

Provide a lightweight health view of the repository so the user can see whether the project library is complete enough for analysis.

### Entry points

- `All Papers` -> `Repository Analytics`

### Current method

This is rule-based bucketing rather than model-based scoring.

Health buckets:

- `complete`
- `abstractOnly`
- `incomplete`

Metadata buckets:

- `complete`
- `missingAuthor`
- `missingVenue`
- `missingYear`
- `multipleMissing`

### Rules

- Based on whether key metadata fields exist and whether full text is present.
- Used for repository readiness and QA rather than ranking.

### Dependencies

- LLM: no
- OpenAlex: no
- Zotero: no

### Project settings that matter

- None

### Source references

- `frontend/index.html:22346-22460`

## 4. Quick Dependency Map

### Strong OpenAlex dependence

- Citation Graph
- Citation Cluster input layer
- Challenge Expand
- Challenge Stardust retrieval/ranking
- Literature Watch

### Strong LLM dependence

- PDF metadata extraction
- Citation Cluster naming
- Read A Paper
- Evidence Board stance classification when LLM path is used
- Literature Watch semantic rerank

### Mostly local heuristics / rules

- project similarity scoring
- semantic clustering
- evidence recall
- evidence snippet extraction
- challenge type inference
- workspace search
- repository analytics

## 5. Highest-Leverage Current Weights

If you later write technical docs or tune behavior, these are the most consequential current weights in practice:

1. Project similarity:
   - `title 1.5`
   - `abstract 1.0`
   - `current content 0.5`
   - citation blend `0.10 / 0.12 / 0.15`
2. Evidence Board candidate score:
   - `claim_relevance 0.32`
   - `quality_score 0.13`
   - `project_similarity 0.14`
3. Challenge Expand:
   - `challenge_hint 0.33`
   - `claim_relevance 0.29`
   - `seed_similarity 0.28`
4. Challenge Stardust:
   - `semantic_overlap 0.50`
   - `challenge_hint 0.20`
   - `claim_relevance 0.12`
   - `quality_score 0.10`
5. Literature Watch:
   - `final_relevance 0.65`
   - `quality_score 0.30`
   - `freshness_score 0.05`
6. Semantic Cluster term construction:
   - `title 3.0`
   - `abstract 1.8`
   - `current content 0.9`

## 6. Recommended Next Documentation Split

If you want to turn this into a full technical doc set, the cleanest next split is:

1. `ranking-and-similarity.md`
2. `clustering-and-graph.md`
3. `evidence-board-and-claim-analysis.md`
4. `challenge-pipeline.md`
5. `literature-watch.md`
6. `search-and-repository-analytics.md`

That split matches the actual code architecture fairly well and avoids repeating the same shared scoring primitives in every document.
