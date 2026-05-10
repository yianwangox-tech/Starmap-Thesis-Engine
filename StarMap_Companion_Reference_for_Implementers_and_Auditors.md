# StarMap Companion Reference for Implementers and Auditors

Review baseline: `2026-05-10`

## Positioning

This document is the implementation-facing companion to the primary guide:

- [StarMap Primary Guide for Research Leads and New Contributors](./StarMap_Primary_Guide_for_Research_Leads_and_New_Contributors.md)

The primary guide is workflow-first and system-first. This companion is workspace-first and implementation-first. It exists for readers who need the details intentionally omitted from the primary guide:

- low-value but operationally important implementation details
- function-level algorithm explanations
- local weight ledgers and threshold notes
- cache, endpoint, and audit-oriented reference material

Unlike a purely architecture-oriented appendix, this companion is intentionally organized around the same six workspace surfaces that users see in the product. Repetition across chapters is deliberate. The goal is that a maintainer can open one workspace chapter in isolation and still find the important defaults, heuristics, and persistence notes for that area without hunting through the rest of the document.

| Document | Primary audience | Main question |
| --- | --- | --- |
| Primary Guide | Leads, product owners, new contributors | What is StarMap doing, and why is the workflow organized this way? |
| Companion Reference | Implementers, maintainers, auditors | Which caches, routes, functions, weights, thresholds, and limits make that behavior happen? |

## How to Use This Companion

This document is easiest to use in one of two ways:

- read one workspace chapter when you are implementing or auditing one product surface
- jump to Section 7 when you need the consolidated cross-system ledger

Sections 1 through 6 are intentionally self-sufficient and may repeat shared details. Section 7 is the authoritative consolidated reference for shared defaults, global caps, and cross-workspace implementation notes.

## Table of Contents

1. [Interface Layer and Foundational Functions](#1-interface-layer-and-foundational-functions)
2. [Workspace Atlas](#2-workspace-atlas)
3. [Read A Paper](#3-read-a-paper)
4. [Evidence Board](#4-evidence-board)
5. [Challenge Stardust](#5-challenge-stardust)
6. [Project Literature Watch](#6-project-literature-watch)
7. [Cross-System Reference and Audit Ledger](#7-cross-system-reference-and-audit-ledger)

---

## 1. Interface Layer and Foundational Functions

### 1.1 Purpose and Boundary

This section covers the shared project shell that appears before a user commits to any deep analytical workspace. In implementation terms, it is where project identity, runtime readiness, shared paper-pool maintenance, and cross-workspace preferences are surfaced.

The scope here includes:

- auth and session continuity
- project creation, loading, update, and deletion
- integration status and settings
- local PDF import and rollback
- Zotero sync entry points
- the paper-status overview and project-wide `All Papers` handoff

This section does not cover the internal ranking, clustering, evidence, or watch algorithms themselves except where those algorithms depend on shared project state established here.

### 1.2 Main User Actions

The interface layer currently supports the following operational actions:

| Surface | Main action |
| --- | --- |
| `Dashboard` handoff | Move between the global project list and one live project |
| `Settings` | Read and update runtime credentials and integration defaults |
| Integration pills | Confirm LLM, Zotero, and Scholar / OpenAlex reachability |
| `Paper Status Overview` | Inspect the current reading-state distribution |
| `Import PDFs` | Add a local PDF batch into the project |
| `Rollback Latest Import` | Remove only the latest local import batch |
| `Auto Cluster Themes` | Enter clustering without first navigating through a graph |
| `Sync Zotero` | Pull or hydrate Zotero material into the project |
| `All Papers` | Open the project-wide paper hub for search, filtering, and cleanup |

Operationally, this layer is where the shared library is prepared and where the project thesis context is kept current before downstream workspaces consume it.

### 1.3 Frontend State and Persistence

Three pieces of shared frontend behavior matter most here.

First, the frontend does not assume one fixed backend origin. It probes API candidates in this order:

1. `http(s)://<hostname>:8001`
2. the current browser origin
3. `http(s)://<hostname>:8000`

The first origin that returns a usable `openapi.json` becomes `API_BASE`.

Second, session transport is browser-persisted:

- `localStorage["starmap_user"]` stores the current user snapshot
- authenticated requests attach `X-Session-Token`
- a backend `401` clears `starmap_user` and forces the UI back to auth mode

Third, project-scoped shared preferences are persisted outside the database in browser storage:

| Storage target | Key | What it carries |
| --- | --- | --- |
| `localStorage` | `starmap_project_settings_<projectId>` | Project-level preferences, watch settings, marked nodes, manual paths, and saved citation-cluster customizations |
| `localStorage` | `starmap:workspace-section-collapse` | Global collapse state for workspace panels |
| `localStorage` | `starmap:workspace-active-module` | Most recently active workspace module |

This means some foundational behavior is durable per browser even when it is not yet part of the canonical SQLite project record.

### 1.4 Backend Data and Endpoints

The interface layer depends on a small group of shared routes:

| Area | Routes |
| --- | --- |
| Auth | `POST /api/register`, `POST /api/login`, `POST /api/logout`, `GET /api/session` |
| Project list | `GET /api/users/{user_id}/projects` |
| Project CRUD | `POST /api/projects/`, `GET /api/projects/{project_id}`, `PUT /api/projects/{project_id}`, `DELETE /api/projects/{project_id}` |
| Paper-pool mutation | `POST /api/projects/{project_id}/merge_papers`, `PUT /api/projects/{project_id}/papers` |
| Settings and readiness | `GET /api/settings`, `POST /api/settings`, `GET /api/integrations/status` |
| Zotero entry points | `GET /api/zotero/collections`, `POST /api/zotero/preview`, `POST /api/zotero/items/hydrate`, `POST /api/zotero/sync`, `POST /api/zotero/upload` |

Shared backend data surfaces that matter immediately:

- `projects.top_papers` stores the live project paper pool as embedded JSON
- `.env` stores repository-level runtime credentials and defaults
- `audit_logs` records high-value actions such as settings updates and major project mutations

Project-scoped write actions are protected by in-memory async locks keyed as:

```text
<project_id>:<task_name>
```

This lock layer currently protects, among other tasks:

- `project_update`
- `project_delete`
- `merge_papers`
- `update_papers`

### 1.5 Core Algorithms and Heuristics

Although this layer is more operational than analytical, several heuristics here have large downstream consequences.

#### Session and auth defaults

Backend session validation is performed by `_require_session`. The current backend defaults are:

| Item | Current behavior |
| --- | --- |
| Session TTL | `14` days |
| Password hashing | `pbkdf2_sha256` |
| PBKDF2 iterations | `120000` |

#### Runtime settings persistence

Settings are not stored inside the project object. They are written through `/api/settings` into `.env`, then mirrored into `os.environ`. Current persisted keys are:

- `STARMAP_LLM_PROVIDER`
- `STARMAP_LLM_API_KEY`
- `STARMAP_OPENALEX_API_KEY`
- `STARMAP_CONTACT_EMAIL`
- `STARMAP_ZOTERO_USER_ID`
- `STARMAP_ZOTERO_API_KEY`
- `STARMAP_ZOTERO_COLLECTION_KEY`

Operational consequence:

- settings are repository-level runtime state, not project-level state
- a settings change affects every project in the same deployment
- the write is audit-logged as `settings_update`

#### Paper normalization and import bookkeeping

Shared paper normalization defaults:

| Field | Current behavior |
| --- | --- |
| `abstract` | Trimmed, truncated, and normalized to `"Unknown"` if empty |
| `current_content` | Truncated to `10000` chars on normalization paths |
| `analysis_ready` | True if abstract or `current_content` is meaningfully present |
| `metadata_only` | Inverse of `analysis_ready` |
| `similarity_pending` | Boolean marker for background rescoring |
| `zotero_has_fulltext` | True if full text exists or normalized `current_content` is meaningful |

Local PDF imports are batch-aware:

- each imported paper receives `import_batch_id`
- each batch records `import_batch_started_at`
- rollback removes only the latest `local_pdf` batch
- rollback is client-driven by filtering out that latest batch and writing the result back through the paper update route

The merge path also protects newly imported filenames from being trimmed away before the top-`500` cap is applied.

### 1.6 Default Weights, Thresholds, and Limits

The most important foundational defaults for this layer are:

| Item | Current value |
| --- | --- |
| Session TTL | `14` days |
| PBKDF2 iterations | `120000` |
| Max project papers | `500` |
| Max local PDF file size | `50 MB` |
| Max local PDF body scan pages | `24` |
| Max local PDF raw text before cleaning | `140000` chars |
| Local PDF import save batch size | `8` |
| Max paper `current_content` | `10000` chars |
| Max target title | `300` chars |
| Max target abstract | `20000` chars |
| Max target current content | `80000` chars |
| Zotero cache TTL | `5` minutes |
| Zotero full sync interval | `1` hour |

### 1.7 Dependencies and Handoffs

This layer feeds every deeper workspace in three ways:

- it defines the project thesis context through `target_title`, `target_abstract`, and `target_current_content`
- it controls the shared paper pool and reading statuses consumed everywhere else
- it stores many of the project-level preferences that later alter clustering, watch behavior, and navigation state

If the paper pool is weak, if runtime integrations are unavailable, or if the target thesis context is underspecified, all downstream workspaces degrade together rather than independently.

### 1.8 Failure Modes and Operational Notes

- `401` responses clear the saved browser session and return the UI to auth mode.
- Project task locks are process-local. A backend restart clears them.
- A concurrent write on the same project returns `409` with an "Another <task_name> task is already running" error.
- Rollback is intentionally narrow: it removes only the most recent `local_pdf` batch, not arbitrary historical batches.
- Settings are shared across all projects in the same runtime because they live in `.env`, not in the project record.

For consolidated cross-system defaults, see Section 7.

---

## 2. Workspace Atlas

### 2.1 Purpose and Boundary

`Workspace Atlas` is the structure-analysis surface of StarMap. It is responsible for turning the project paper pool into navigable maps, theme groups, and citation communities.

From an implementation perspective, this chapter covers:

- project similarity scoring
- orbital, network, and citation views
- semantic clustering
- citation clustering
- marked nodes, manual paths, and cluster lineage persistence

It does not cover deep paper critique, claim analysis, or watch recommendation logic except where those systems depend on Atlas outputs such as similarity, cluster labels, or graph neighborhoods.

### 2.2 Main User Actions

The Atlas workspace supports several structurally important operations:

| Action | What it does |
| --- | --- |
| Open `Orbital` view | Inspect broad thesis-proximity distribution |
| Open `Network` view | Inspect local neighborhoods and bridge papers |
| Open `Citation Graph` | Inspect directed citation structure |
| Run `Semantic Cluster` | Build topic-style groupings from text |
| Run `Citation Cluster` | Build topology-driven citation communities |
| Mark nodes | Persist local sets of important papers |
| Save manual paths | Persist exploration trails across the graph |
| Save custom citation clusters | Preserve manually meaningful citation partitions |
| Adjust density | Trade display completeness against clarity and performance |

Atlas therefore mixes visualization, ranking, cache reuse, and user-authored navigation state in one workspace.

### 2.3 Frontend State and Persistence

Atlas keeps more browser-persisted state than most StarMap workspaces.

| Storage target | Key | Purpose |
| --- | --- | --- |
| `localStorage` | `starmap_cluster_cache_v1_<projectId>_<mode>` | Cached semantic or citation cluster result |
| `localStorage` | `starmap_cluster_lineage_v1_<projectId>_<mode>` | Tracks cluster lineage across reruns |
| `localStorage` | `starmap_citation_cluster_naming_retry_v1_<projectId>` | Memoizes citation-cluster naming retries |
| `localStorage` | `starmap_project_settings_<projectId>` | Stores marked nodes, manual paths, and custom citation structures |

Audit-relevant frontend persistence rules:

- cluster cache writes are size-limited to `900000` JSON characters
- saved custom citation clusters are capped at `10`
- saved breadcrumb trails are capped at `12`
- citation-cluster persistence is accepted only when both `citation_cluster_graph_signature` and `citation_cluster_version` match the current algorithm version

This means Atlas is deliberately tolerant of local persistence, but only while cache signatures still match the current clustering logic.

### 2.4 Backend Data and Endpoints

Atlas depends on both synchronous data loading and async job endpoints:

| Area | Routes |
| --- | --- |
| Semantic clustering | `POST /api/papers/semantic-cluster/jobs`, `GET /api/papers/semantic-cluster/jobs/{job_id}` |
| Citation hydration | `POST /api/papers/citations` |
| Citation graph | `POST /api/papers/citation-graph`, `POST /api/papers/citation-graph/jobs`, `GET /api/papers/citation-graph/jobs/{job_id}` |
| Project paper pool | `GET /api/projects/{project_id}` |

Important backend facts:

- semantic clustering is backend-owned
- citation clustering is frontend-owned after citation topology is available
- project papers still originate from `projects.top_papers`, which Atlas consumes as the shared repository substrate

### 2.5 Core Algorithms and Heuristics

#### Project similarity scoring in the frontend

Main helpers:

- `getSimilarityExtractor`
- `buildProjectSimilarityVectors`
- `buildPaperSimilarityVectors`
- `computePaperSimilarity`
- `buildSimilarityBreakdownFromVectors`

Current transformer model:

```text
Xenova/all-MiniLM-L6-v2
```

Current weighted text score:

```text
text_score =
  cosine(project.title, paper.title) * 1.5
  + cosine(project.abstract, paper.abstract) * 1.0
  + cosine(project.current_content, paper.current_content) * 0.5   # only if both sides exist

normalized_text_score = text_score / 2.5   # or / 3.0 when current_content is active
```

Optional citation-count blend:

```text
compressed_citation_score =
  min(log(1 + citation_count) / log(1 + 200), 1.0)

final_similarity =
  normalized_text_score * (1 - citation_blend_weight)
  + compressed_citation_score * citation_blend_weight
```

Current citation blend tiers:

| Tier | Weight |
| --- | --- |
| `low` | `0.10` |
| `medium` | `0.12` |
| `high` | `0.15` |

Implementation note: several frontend names still use legacy `fwci` wording, but the actual auxiliary blended signal is `citation_count`.

#### Backend semantic clustering

Main helpers:

- `_build_semantic_cluster_term_weights`
- `_hash_weighted_terms_to_vector`
- `_initialize_kmeans_plus_plus`
- `_rebalance_undersized_clusters`
- `_evaluate_cluster_assignments`
- `_build_semantic_cluster_result`

Weighted term construction:

```text
title weight = 3.0
abstract weight = 1.8
current_content weight = 0.9
bigram multiplier = 1.15
```

Vectorization is backend-local feature hashing with signed buckets plus IDF weighting:

```text
bucket = hash(term) % 384
sign = +/- 1 from a second hash
vector[bucket] += term_weight * idf * sign
```

Cluster search procedure:

1. Build weighted terms for analyzable papers.
2. Hash them into normalized vectors.
3. Try cluster counts `3`, `4`, and `5` when enough seed papers exist.
4. Run up to `2` passes total because `SEMANTIC_CLUSTER_BASE_ATTEMPTS = 1` and the loop evaluates `range(base_attempts + 1)`.
5. Use a deterministic k-means++ variant for initialization.
6. Run up to `8` centroid-recalculation iterations.
7. Rebalance undersized clusters.
8. Choose the best assignment by the internal evaluation score.

Undersized-cluster relocation and evaluation:

```text
relocation_score = target_score * 1.15 - donor_score

evaluation_score =
  average(own_cluster_cosine - next_best_cluster_cosine)
  - undersized_penalty

undersized_penalty += (min_cluster_size - actual_size) * 0.28
```

Cluster labels in the backend semantic path are not LLM-generated. Distinctive terms are scored from local overrepresentation:

```text
term_score = cluster_ratio * idf * lift * phrase_boost
phrase_boost = 1.18 if the term is a phrase else 1.0
```

#### Frontend citation clustering

Main helpers:

- `buildCitationTopologyGraph`
- `detectCitationCommunitiesLouvain`
- `selectCitationClusterSeeds`
- `partitionCitationComponentBySeeds`
- `buildCitationTopologyClusters`
- `ensureCitationTopologyClusters`

Important topology rule:

- the raw citation graph is directed
- community detection converts it into undirected adjacency for grouping
- directed indegree is still preserved for ranking and recommendation

Current Louvain-style gain:

```text
gain =
  internal_weight_to_candidate_community
  - (node_degree * candidate_community_weight / total_weight_twice)
```

Seed selection and growth:

```text
seed_score =
  indegree * 4
  + degree * 1.5
  + similarity * 20

candidate_seed_score = base_seed_score + shortest_path_distance_to_existing_seeds * 16

oversized_split_score =
  connectivity_to_current_bucket * 12
  + indegree * 0.35
  + degree * 0.12

connected_growth_score =
  connectivity_to_current_cluster * 14
  + seed_score
```

Cluster recommendation ranking:

```text
recommendation_score =
  size * 8
  + average_similarity * 100
  + total_indegree * 0.35
  + total_degree * 0.12
```

### 2.6 Default Weights, Thresholds, and Limits

#### Similarity and blending

| Parameter | Current value |
| --- | --- |
| Title cosine weight | `1.5` |
| Abstract cosine weight | `1.0` |
| Current-content cosine weight | `0.5` |
| Citation blend `low` | `0.10` |
| Citation blend `medium` | `0.12` |
| Citation blend `high` | `0.15` |
| Citation compression cap | `200` |

#### Semantic cluster constants

| Constant | Current value |
| --- | --- |
| Algorithm version | `backend-v1` |
| Default seed limit | `60` |
| Vector dimension | `384` |
| Max representative papers per cluster | `10` |
| Min cluster size | `4` |
| Candidate cluster counts | `3`, `4`, `5` |
| Base attempts | `1` |
| Retry threshold | `0.055` |
| Current-content cap for clustering | `1000` chars |

#### Citation cluster constants

| Constant | Current value |
| --- | --- |
| Algorithm version | `v2` |
| Core-paper limit per cluster | `5` |
| Max modal clusters | `5` |
| Target cluster size | `20` |
| Min balanced size | `12` |
| Max balanced size | `28` |
| Min recommended size | `16` |
| Max recommended display size | `35` |
| Max persisted cluster cache payload | `900000` chars |
| Saved custom citation clusters per project | `10` |
| Saved breadcrumb trails per project | `12` |

### 2.7 Dependencies and Handoffs

Atlas depends on:

- the project thesis fields from the interface layer
- the shared project paper pool
- paper statuses, notes, and imported full-text state

Atlas then hands useful structure forward to other workspaces:

- high-similarity or bridge papers become likely `Read A Paper` targets
- cluster leaders influence claim candidate seeding in the Evidence Board
- citation neighborhoods and marked nodes can seed challenge-side exploration

### 2.8 Failure Modes and Operational Notes

- Atlas caches can look valid while being semantically stale if version and signature review is skipped after a logic change.
- Semantic-cluster job progress and citation-graph job progress are process-local and disappear on restart.
- Citation clustering intentionally simplifies directed structure into undirected communities for grouping, so "community" and "causal direction" should not be conflated.
- Semantic cluster labels are backend heuristic labels rather than LLM-written labels, which improves determinism but can reduce prose readability.

For consolidated cross-system defaults, see Section 7.

---

## 3. Read A Paper

### 3.1 Purpose and Boundary

`Read A Paper` is StarMap's close-reading workspace. It is designed for one specific paper PDF at a time in the current frontend, with separate support for:

- paper-level critique
- passage-level critique on a selected region
- highlight, mark, and note capture
- Zotero export of the marked PDF and critique notes

There is an important implementation split inside this workspace:

- the paper-level critique path uses a backend endpoint and structured normalization
- the passage-level critique path is driven directly from the frontend using a vision-capable LLM over the captured screenshot region

The current UI supports only one uploaded PDF at a time even though the backend analysis schema still supports `paper` and `cluster` selection types up to a larger batch cap.

### 3.2 Main User Actions

The current reader flow supports the following actions:

| Action | Current behavior |
| --- | --- |
| Upload one PDF | Parse a local PDF and extract metadata plus body text |
| Re-upload another PDF | Replace the current uploaded paper |
| Navigate the viewer | Move page-by-page and zoom |
| Arm area selection | Select one region in the displayed PDF |
| Create passage marks | Save excerpt, page, context, type, color, and note |
| Run `Analyze Passage` | Ask for screenshot-grounded passage critique |
| Run `Run Paper Critique` | Ask for full paper-level critical reading |
| Open Zotero export prompt | Choose library / collection destination |
| Export to Zotero | Upload the marked PDF plus note items |

The workspace therefore combines PDF parsing, OCR-like text extraction, client-side state persistence, and both paper-level and passage-level LLM workflows.

### 3.3 Frontend State and Persistence

Read A Paper stores more local state than most other StarMap workspaces because the underlying artifact is a live PDF session rather than a normalized server-side entity.

#### IndexedDB cache

The uploaded PDF cache is stored in:

| Storage target | Name |
| --- | --- |
| IndexedDB database | `starmap-read-paper-cache` |
| Object store | `recent_pdfs` |

The serialized cached record includes:

- bibliographic metadata such as title, abstract, year, venue, DOI, and citation count
- extracted `current_content`
- `pageTexts` for the parsed PDF
- raw `pdfBytes`
- the last captured reader state snapshot

#### Reader-state snapshot

The cached reader-state snapshot currently includes:

| Field | Current rule |
| --- | --- |
| `viewerPage` | Clamped to `1..pageCount` |
| `viewerScale` | Clamped to `0.75..2.2` |
| `userQuestion` | Max `2000` chars |
| `passageMarks` | Stored as an array of full mark objects |
| `activePassageMarkId` | Max `120` chars |
| `detailMode` | `paper` or `passage` |
| `selectionQuestion` | Max `2000` chars |
| `selectedExcerptText` | Max `4000` chars |
| `selectedExcerptContext` | Max `5000` chars |
| `selectedExcerptUserNote` | Max `4000` chars |
| `selectedExcerptUserNoteStatus` | Max `300` chars |
| `zoteroCollectionKey` | Max `120` chars |

Mark typing and coloring are also normalized locally:

| Mark types | Colors |
| --- | --- |
| `default`, `claim`, `evidence`, `method`, `threat`, `limitation`, `question`, `to_cite` | `yellow`, `green`, `blue`, `purple`, `rose`, `orange` |

Persistence rules worth calling out:

- only one uploaded PDF is kept in the current UI
- dropping multiple PDFs keeps the first and ignores the rest
- the cached PDF is restored only when the same project is reopened and no live upload is already present

### 3.4 Backend Data and Endpoints

Read A Paper relies on a small but distinct route surface:

| Area | Routes |
| --- | --- |
| Paper-level critique | `POST /api/projects/{project_id}/read-paper/analyze` |
| Zotero export | `POST /api/zotero/read-paper/export` |
| Zotero collection lookup | `GET /api/zotero/collections` |

The paper-level analysis response currently returns:

- `selection_type`
- `selection_label`
- `analyzed_paper_count`
- `papers` with one takeaway per paper when available
- `analysis` with:
  - `deep_read_summary`
  - `user_question_answer`
  - `threats_to_validity`
  - `external_validity_limits`
  - `design_vulnerabilities`
  - `improvement_opportunities`
  - `questions_to_press`

Unlike Evidence Board or Stardust, the core reader state is not persisted as first-class relational rows. Most durable reader state remains browser-side until the user exports the work to Zotero.

### 3.5 Core Algorithms and Heuristics

#### PDF ingestion and metadata extraction

When the user uploads a PDF, the frontend:

1. parses the PDF client-side with `pdfjs`
2. extracts page text for all pages
3. uses the first two pages for quick metadata extraction context
4. scans up to `24` pages and up to `140000` raw characters for body text
5. normalizes that extracted body text into `current_content`
6. calls the configured LLM to extract title and abstract-like metadata

This is why the current upload flow requires an LLM API key before ingestion.

#### Paper-level critique path

The backend validates the payload via `_validate_read_paper_payload`:

- `selection_type` is normalized to `paper` or `cluster`
- `selection_label` is trimmed to `220` chars
- `user_question` is trimmed to `2000` chars
- the selection must contain at least one paper
- the current cap is `12` papers

The backend then normalizes each paper into a trimmed analysis payload that includes:

- title
- abstract
- `current_content`
- notes
- authors
- year
- venue
- citation count
- shared project similarity
- status

The prompt used by `_build_read_paper_prompt` is intentionally critique-oriented rather than summary-oriented. It instructs the model to:

- read critically rather than summarize politely
- stay inside the supplied paper text
- distinguish paper-wide concerns from concerns that apply to only some papers
- return only a strict JSON schema

#### Paper-level finding normalization and snippet grounding

After the LLM returns JSON, the backend does not trust raw snippet candidates blindly. It normalizes each section and attempts to ground snippet candidates back onto real text from `abstract`, `current_content`, or `notes`.

Fallback snippet extraction currently scores text segments as:

```text
score =
  token_overlap * 0.40
  + phrase_overlap * 0.30
  + length_quality * 0.16
  + source_weight * 0.14
```

Current source weights:

| Source | Weight |
| --- | --- |
| `abstract` | `1.00` |
| `current_content` | `0.95` |
| `notes` | `0.92` |

When the system tries to ground a user-facing snippet candidate back to real text, it currently scores candidates as:

```text
score =
  sequence_overlap * 0.62
  + token_overlap * 0.16
  + phrase_overlap * 0.14
  + length_quality * 0.08
```

The grounding path accepts approximate text only when the `SequenceMatcher` overlap is at least `0.42` or one string contains the other.

#### Passage-level critique path

Passage analysis is currently frontend-driven. The browser:

1. captures the highlighted region as a PNG data URL
2. builds local page context around the selected excerpt
3. builds whole-paper context from abstract, `current_content`, page snapshots, and any existing paper-level summary
4. calls `callProviderVisionLLM(...)` with the screenshot as primary evidence

The passage prompt explicitly tells the model:

- treat the screenshot as primary evidence
- use OCR-like extracted text only as fallback
- explain formulas or figure-like content conservatively
- answer the user's question directly when possible

#### Zotero export behavior

The Zotero export route:

- finds or creates a Zotero parent item for the paper
- tries to delete prior StarMap export children under that parent
- uploads the current annotated PDF as a Zotero attachment
- creates one note item per marked passage
- optionally creates one paper-level critique note

Export notes preserve passage mapping through quote text, page number, and normalized highlight coordinates rather than native Zotero annotation objects.

### 3.6 Default Weights, Thresholds, and Limits

| Item | Current value |
| --- | --- |
| Read A Paper max papers | `12` |
| Max selection label | `220` chars |
| Max paper-level question | `2000` chars |
| Max deep-read summary | `2200` chars |
| Max finding label | `220` chars |
| Max finding detail | `1400` chars |
| Max findings per section | `6` |
| Max questions to press | `6` |
| Max evidence snippets per item | `3` |
| Max snippet text | `360` chars |
| Excerpt normalization cap | `3200` chars |
| Viewer zoom range | `0.75` to `2.2` |
| Max selected excerpt text | `4000` chars |
| Max selected excerpt context | `5000` chars |
| Max selected excerpt note | `4000` chars |
| Max Zotero collection key in cache | `120` chars |

### 3.7 Dependencies and Handoffs

Read A Paper depends on:

- project context from the interface layer
- imported or uploaded paper text
- configured LLM credentials
- optional Zotero credentials for export

It then hands information outward in two ways:

- the user may convert close reading into notes, critiques, and export artifacts in Zotero
- the insights can later inform claim writing and challenge-side exploration even though there is no strict relational dependency from the reader into those workspaces

### 3.8 Failure Modes and Operational Notes

- The current UI supports only one uploaded PDF at a time. Re-uploading another PDF replaces the current one.
- Multi-file drag-and-drop keeps the first PDF and ignores the rest.
- PDF upload currently requires an LLM API key because metadata extraction happens during ingestion.
- Passage analysis fails fast if no screenshot snapshot exists for the marked region.
- Zotero export requires at least one marked area if the exported PDF is expected to preserve a highlight anchor.
- If old StarMap export children under the parent Zotero item cannot be cleaned up fully, the export still proceeds but returns a cleanup warning.

For consolidated cross-system defaults, see Section 7.

---

## 4. Evidence Board

### 4.1 Purpose and Boundary

`Evidence Board` is StarMap's claim-testing workspace. It takes a user-authored claim, generates a claim-specific candidate pool from the project library, classifies evidence into stance buckets, and returns grounded evidence cards with rationale and snippets.

The scope of this chapter includes:

- claim creation and deletion
- claim analysis
- candidate seeding and diversification
- heuristic stance assignment
- evidence snippets and claim-snippet caching
- challenge expansion initiated from a claim board

This chapter does not cover larger challenge-side repository building beyond the initial expansion handoff; that deeper lifecycle lives in Section 5.

### 4.2 Main User Actions

The current board flow supports:

| Action | What it does |
| --- | --- |
| Create a claim | Persist a thesis claim, chapter claim, or research question |
| Run claim analysis | Build and score a candidate evidence pool |
| Review the board | Inspect `support`, `challenge`, `setup`, and `pending` columns |
| Review evidence cards | Inspect stance, strength, relevance, confidence, quality, rationale, caveat, and snippets |
| Re-run analysis | Refresh the board against the current repository state |
| Expand challenge-side evidence | Launch challenge expansion from the active claim |
| Delete a claim | Remove the persisted claim and its associated evidence items |

### 4.3 Frontend State and Persistence

Compared with Atlas and Read A Paper, the Evidence Board keeps less durable state in browser storage. Its important persistence surfaces are mostly backend-owned:

| Storage surface | Role |
| --- | --- |
| `project_claims` | Stores persisted claims, their type, status, and analysis version |
| `claim_evidence_items` | Stores classified evidence rows, stance, rationale, caveat, snippets, and override state |
| `claim_snippet_cache` | Stores grounded snippet payloads keyed by a snippet-specific cache hash |

The current snippet cache key is built as:

```text
claim-snippet:<payload_hash>
```

This means claim reasoning is primarily server-backed rather than browser-backed. The frontend is mostly a view and interaction surface over normalized claim data.

### 4.4 Backend Data and Endpoints

Evidence Board uses a compact claim-focused API surface:

| Area | Routes |
| --- | --- |
| Claim CRUD | `POST /api/projects/{project_id}/claims`, `GET /api/projects/{project_id}/claims`, `DELETE /api/projects/{project_id}/claims/{claim_id}` |
| Claim analysis | `POST /api/projects/{project_id}/claims/{claim_id}/analyze` |
| Board retrieval | `GET /api/projects/{project_id}/claims/{claim_id}/board` |
| Challenge expansion handoff | `POST /api/projects/{project_id}/claims/{claim_id}/challenge-expand` |

Relevant durable tables:

- `project_claims`
- `claim_evidence_items`
- `claim_snippet_cache`
- `audit_logs`

Claim analysis is protected under a project lock name shaped like:

```text
claim_analysis_<claim_id>
```

### 4.5 Core Algorithms and Heuristics

#### Signal primitives

Main backend helpers:

- `_claim_tokens`
- `_claim_phrases`
- `_token_overlap_score`
- `_phrase_overlap_score`
- `_marker_score`
- `_length_quality_score`
- `_build_claim_candidate_metrics`
- `_build_claim_candidate_pool`
- `_heuristic_claim_classification`

Current signal behaviors:

| Helper | Current behavior |
| --- | --- |
| Token overlap | Overlap of claim tokens against a text, normalized to `[0,1]` |
| Phrase overlap | Overlap of claim bi/tri-grams against a text, normalized to `[0,1]` |
| Marker score | Number of stance markers found, capped at `3`, then normalized to `[0,1]` |
| Length quality | Rewards roughly `70` to `280` chars and softly penalizes very short or long text |

#### Status, recency, and quality priors

Current status weights:

| Paper status | Weight |
| --- | --- |
| `Core` | `1.00` |
| `Pending` | `0.72` |
| `Underweight` | `0.62` |
| `Unread` | `0.48` |
| Other / unknown | `0.52` |

Current recency buckets:

| Paper age | Score |
| --- | --- |
| `<= 2` years | `1.00` |
| `<= 5` years | `0.82` |
| `<= 10` years | `0.62` |
| `<= 20` years | `0.46` |
| `> 20` years | `0.32` |
| Unknown year | `0.35` |

Current paper-quality score:

```text
citation_score = min(log1p(citation_count) / log1p(500), 1.0)
completeness_score = mean(
  title_present,
  meaningful_authors_present,
  year_present,
  meaningful_abstract_present,
  venue_present
)
core_bonus = 0.12 if status == Core else 0.0
fulltext_bonus = 0.08 if current_content exists else 0.0

quality_score =
  min(citation_score * 0.45 + completeness_score * 0.35 + core_bonus + fulltext_bonus, 1.0)
```

#### Claim relevance and stance hints

Current relevance construction:

```text
title_score    = token_overlap * 0.65 + phrase_overlap * 0.35
abstract_score = token_overlap * 0.58 + phrase_overlap * 0.42
notes_score    = token_overlap * 0.50 + phrase_overlap * 0.50
body_score     = token_overlap * 0.55 + phrase_overlap * 0.45

exact_phrase_bonus = 0.08 if the full claim text appears in title, abstract, notes, or body

claim_relevance =
  min(
    title_score * 0.29
    + abstract_score * 0.31
    + notes_score * 0.20
    + body_score * 0.20
    + exact_phrase_bonus,
    1.0
  )
```

Current stance-hint construction:

```text
challenge_hint =
  min(
    max(challenge_markers) * 0.55
    + max(abstract_or_body_or_notes_phrase_overlap) * 0.30
    + max(notes_or_body_token_overlap) * 0.15,
    1.0
  )

setup_hint =
  min(
    max(setup_markers) * 0.58
    + max(title_or_abstract_or_notes_phrase_overlap) * 0.22
    + max(notes_or_body_token_overlap) * 0.20,
    1.0
  )

support_hint =
  min(
    max(support_markers) * 0.34
    + claim_relevance * 0.46
    + max(abstract_or_body_phrase_overlap) * 0.20,
    1.0
  )
```

#### Candidate scoring and pool seeding

Current candidate score:

```text
candidate_score =
  min(
    claim_relevance * 0.32
    + project_similarity * 0.14
    + status_weight * 0.11
    + notes_relevance * 0.12
    + quality_score * 0.13
    + fulltext_bonus * 0.08
    + recency_score * 0.05
    + support_hint * 0.05,
    1.0
  )
```

Candidate-pool seeding strategy:

| Ranked list | Seed quota |
| --- | --- |
| Claim relevance | `max(10, ceil(max_candidates * 0.45))` |
| Support hint | `max(8, ceil(max_candidates * 0.35))` |
| Challenge hint | `max(6, ceil(max_candidates * 0.22))` |
| Setup hint | `max(6, ceil(max_candidates * 0.22))` |
| Candidate score | `max(8, ceil(max_candidates * 0.35))` |
| Project similarity | `max(5, ceil(max_candidates * 0.22))` |
| Quality | `max(4, ceil(max_candidates * 0.18))` |
| Core-only score list | `max(4, ceil(max_candidates * 0.18))` |
| Cluster leaders | `max(4, ceil(max_candidates * 0.25))` |

Cluster diversification cap:

```text
max_per_cluster = max(2, min(5, ceil(max_candidates / 4)))
```

#### Heuristic stance classification

Current signal merge:

```text
support_signal   = support_hint * 0.52 + claim_relevance * 0.48
challenge_signal = challenge_hint * 0.64 + claim_relevance * 0.36
setup_signal     = setup_hint * 0.70 + claim_relevance * 0.30
```

Current thresholds:

| Stance | Rule |
| --- | --- |
| `challenge` | `challenge_signal >= 0.32` and at least `0.05` above support and at least as high as setup |
| `setup` | `setup_signal >= 0.34` and at least `0.03` above support |
| `support` | `support_signal >= 0.36` |
| `pending` | Fallback |

#### Post-classification scoring and snippets

Current strength score:

```text
strength_score =
  min(
    directness * 0.45
    + relevance_score * 0.20
    + quality_score * 0.20
    + confidence * 0.15,
    1.0
  )
```

Current evidence-snippet scoring:

```text
score =
  token_overlap * 0.34
  + phrase_overlap * 0.28
  + stance_alignment_bonus * 0.18
  + length_quality * 0.08
  + source_weight * 0.12
```

Current snippet source weights:

| Source | Weight |
| --- | --- |
| `abstract` | `1.00` |
| `notes` | `0.94` |
| `current_content` | `0.90` |

### 4.6 Default Weights, Thresholds, and Limits

| Item | Current value |
| --- | --- |
| Max claim text | `4000` chars |
| Max claim candidates | `96` |
| Claim analysis batch size | `8` |
| Default included statuses | `Core`, `Pending`, `Underweight`, `Unread` |
| Max evidence snippets per item | `3` |
| Max snippet text | `360` chars |
| Claim relevance exact phrase bonus | `0.08` |
| Challenge threshold | `0.32` |
| Setup threshold | `0.34` |
| Support threshold | `0.36` |
| Cluster diversification minimum | `2` |
| Cluster diversification maximum | `5` |

### 4.7 Dependencies and Handoffs

Evidence Board depends on:

- project similarity scores computed from shared thesis context
- paper statuses and notes prepared elsewhere
- full-text availability from import and sync layers
- cluster labels and cluster leaders as one candidate-seeding signal

Evidence Board then hands forward:

- challenge-side seeds into Challenge Stardust
- persistent claim records that can be revisited and reanalyzed as the repository changes

### 4.8 Failure Modes and Operational Notes

- Concurrent analysis of the same claim is protected by a project-scoped lock and can return `409`.
- Snippet grounding is best-effort. If LLM-returned snippet candidates cannot be grounded, the system falls back to heuristic extraction.
- Dense clusters can be underrepresented intentionally because the diversification cap prevents one cluster from dominating the board.
- Board quality depends strongly on `current_content`, notes quality, and paper status hygiene; a metadata-only library produces thinner evidence.

For consolidated cross-system defaults, see Section 7.

---

## 5. Challenge Stardust

### 5.1 Purpose and Boundary

`Challenge Stardust` is StarMap's challenge-side discovery workspace. It turns a challenge-oriented seed into a curated counter-evidence candidate set, keeps that set separate from the main repository until the user is ready, and supports graph building around that side network.

This chapter covers two closely related stages:

- one-hop challenge expansion launched from Evidence Board
- full Stardust candidate generation, storage, and graph lifecycle

The purpose of the separation is strategic: challenge-side exploration should not pollute the main paper pool automatically.

### 5.2 Main User Actions

The current Stardust flow supports:

| Action | What it does |
| --- | --- |
| Launch challenge expansion from a claim | Build an initial challenge candidate set from the active board |
| Create a Stardust seed | Persist a challenge-side exploration bundle |
| Inspect candidate papers | Review challenge score, seed similarity, and import state |
| Build or refresh a Stardust graph | Turn the candidate pool into a separate challenge-side graph |
| Inspect the side network | Explore references, cited-by relationships, and semantic supplements |
| Select papers for import | Decide which challenge-side papers graduate into the main repository |
| Delete or archive Stardust | Retire a side exploration without disturbing the main project |

### 5.3 Frontend State and Persistence

Stardust persistence is primarily backend-owned rather than browser-owned.

Relevant durable entities:

| Storage surface | Role |
| --- | --- |
| `challenge_stardusts` | Stores Stardust bundle metadata and lifecycle state |
| `challenge_stardust_papers` | Stores per-paper scores, seed similarity, discovery source, and import selection state |

Important enum-like implementation values:

| Field | Current values |
| --- | --- |
| Stardust status | `draft`, `ready`, `building`, `failed`, `archived` |
| Graph mode | `directed`, `mutual`, `full` |

Operationally, this means Stardust behaves like a semi-independent project layer rather than like a purely ephemeral query result.

### 5.4 Backend Data and Endpoints

The Stardust API surface is:

| Area | Routes |
| --- | --- |
| Upstream challenge expansion | `POST /api/projects/{project_id}/claims/{claim_id}/challenge-expand` |
| Stardust CRUD | `POST /api/projects/{project_id}/stardusts`, `GET /api/projects/{project_id}/stardusts`, `GET /api/projects/{project_id}/stardusts/{stardust_id}`, `DELETE /api/projects/{project_id}/stardusts/{stardust_id}` |
| Stardust papers | `GET /api/projects/{project_id}/stardusts/{stardust_id}/papers` |
| Stardust graph | `GET /api/projects/{project_id}/stardusts/{stardust_id}/graph`, `POST /api/projects/{project_id}/stardusts/{stardust_id}/graph/build` |

Durable backend surfaces that matter:

- `challenge_stardusts`
- `challenge_stardust_papers`
- `audit_logs`

### 5.5 Core Algorithms and Heuristics

#### Challenge expansion from Evidence Board

Main helpers:

- `_challenge_expansion_seed_similarity`
- `_heuristic_challenge_expansion_match`
- `_expand_challenge_seed`

Current seed-to-candidate similarity:

```text
seed_similarity =
  min(
    token_overlap * 0.56
    + phrase_overlap * 0.32
    + challenge_marker * 0.12,
    1.0
  )
```

Current one-hop challenge strength:

```text
relation_bonus = 0.05 if relationship_type == cited_by else 0.03

challenge_strength =
  min(
    challenge_hint * 0.33
    + claim_relevance * 0.29
    + seed_similarity * 0.28
    + quality_score * 0.10
    + relation_bonus,
    1.0
  )
```

Current include rule:

```text
include if
  challenge_strength >= 0.26
  and (
    challenge_hint >= 0.16
    or seed_similarity >= 0.20
    or claim_relevance >= 0.24
  )
```

Optional LLM merge:

```text
final_score = llm_strength * 0.56 + heuristic_strength * 0.44
```

If the LLM does not explicitly include the paper and `final_score < 0.34`, the candidate is dropped.

#### Stardust candidate generation

Main helpers:

- `_build_stardust_semantic_queries`
- `_register_stardust_candidate`
- `_score_stardust_candidate`
- `_generate_challenge_stardust`

Current semantic-query generation builds up to `5` queries from combinations of:

- the seed title
- sub-target thesis terms
- seed title plus thesis terms
- thesis plus claim plus evidence rationale
- seed title plus project target plus thesis terms

Current semantic overlap:

```text
semantic_overlap =
  min(seed_similarity * 0.58 + claim_relevance * 0.42, 1.0)
```

Current Stardust candidate score:

```text
citation_bonus =
  min(log1p(citation_count) / log1p(250), 1.0) * 0.02

semantic_bonus = 0.045 if discovery_source includes semantic_supplement else 0.0

semantic_linked_bonus =
  0.05   if semantic_overlap >= 0.24 and both cited_by and reference
  0.038  if semantic_overlap >= 0.24 and cited_by only
  0.03   if semantic_overlap >= 0.24 and reference only
  0.0    otherwise

challenge_score =
  min(
    semantic_overlap * 0.50
    + challenge_hint * 0.20
    + claim_relevance * 0.12
    + quality_score * 0.10
    + semantic_bonus
    + semantic_linked_bonus
    + citation_bonus,
    1.0
  )
```

Current include rule:

```text
include if
  challenge_score >= 0.27
  and (
    semantic_overlap >= 0.24
    or claim_relevance >= 0.28
    or seed_similarity >= 0.22
    or (semantic_supplement and semantic_overlap >= 0.30)
  )
```

Fallback behavior when nothing passes:

```text
keep candidates with challenge_score >= 0.22
```

### 5.6 Default Weights, Thresholds, and Limits

| Item | Current value |
| --- | --- |
| Challenge expansion include floor | `0.26` |
| Challenge expansion LLM blend weight | `0.56` |
| Challenge expansion heuristic blend weight | `0.44` |
| Challenge expansion drop floor when not included | `0.34` |
| Max references fetched in expansion | `12` |
| Max cited-by fetched in expansion | `12` |
| Max ranked candidates before LLM pass | `18` |
| Max expansion results returned | `12` |
| Stardust semantic overlap weight | `0.50` |
| Stardust challenge-hint weight | `0.20` |
| Stardust claim-relevance weight | `0.12` |
| Stardust quality weight | `0.10` |
| Stardust semantic supplement bonus | `0.045` |
| Stardust dual-link bonus | `0.05` |
| Stardust cited-by-only bonus | `0.038` |
| Stardust reference-only bonus | `0.03` |
| Stardust citation bonus multiplier | `0.02` |
| Stardust include floor | `0.27` |
| Stardust fallback floor | `0.22` |
| Max Stardusts per project | `5` |
| Max saved papers per Stardust | `50` |
| Hop-1 references | `16` |
| Hop-1 cited-by | `16` |
| Semantic query count | `5` |
| Semantic results per query | `12` |
| Candidate-pool constant | `120` |

### 5.7 Dependencies and Handoffs

Stardust depends heavily on shared metrics developed elsewhere:

- claim relevance from Evidence Board helpers
- project similarity and thesis context from the shared project object
- quality and full-text priors from the paper normalization layer
- citation relationships hydrated for Atlas and citation tools

Its main handoff is controlled import into the main repository. Stardust papers do not become part of `projects.top_papers` until the user explicitly decides to bring them in.

### 5.8 Failure Modes and Operational Notes

- The workspace is intentionally conservative about automatic import. Discovery and repository admission are separate steps.
- Fallback inclusion can return weaker candidates when no papers satisfy the main include rule; that is recall-preserving behavior, not a signal that the candidates are strong.
- Stardust state is durable, but any surrounding temporary job state is still vulnerable to process-local restart behavior in the broader backend.
- Because challenge discovery reuses several Evidence Board signals, poor claim phrasing or thin full text propagates into weak challenge-side retrieval.

For consolidated cross-system defaults, see Section 7.

---

## 6. Project Literature Watch

### 6.1 Purpose and Boundary

`Project Literature Watch` is StarMap's current-awareness workspace. It recommends newly relevant papers by combining thesis context, project-specific strategy terms, venue preferences, and freshness-aware ranking.

Its scope includes:

- target watch
- scholar watch
- journal watch
- watched journal lifts
- lexical relevance
- optional semantic reranking
- recall-padding for low-yield watch runs

This section does not cover the repository mapping or challenge-side graph lifecycle, even though recommended papers may later flow into those workspaces after import.

### 6.2 Main User Actions

The current watch surface supports:

| Action | What it does |
| --- | --- |
| Configure a target watch | Follow the project's main thesis direction |
| Configure a scholar watch | Follow a scholar- or author-shaped direction |
| Configure a journal watch | Follow venue-shaped discovery with optional lift tiers |
| Set focus phrases, facets, and queries | Shape lexical relevance priors |
| Configure top venues and watched journals | Alter quality and priority bonuses |
| Set time windows | Alter freshness behavior |
| Review recommendations | Inspect ranked watch results before import decisions |

### 6.3 Frontend State and Persistence

Project Literature Watch uses shared project preferences rather than a dedicated backend table. The most relevant browser storage surface is:

| Storage target | Key | What it typically carries |
| --- | --- | --- |
| `localStorage` | `starmap_project_settings_<projectId>` | Watch strategy details, venue preferences, watched-journal preferences, and workspace-local watch UI state |

Operationally, this means watch configuration is durable per browser / project pairing even when the watch result list itself is recomputed on demand from the backend.

### 6.4 Backend Data and Endpoints

Project Literature Watch currently exposes a compact backend surface:

| Area | Route |
| --- | --- |
| Watch generation | `POST /api/projects/{project_id}/literature_watch` |

Key upstream dependencies:

- project thesis context from the project record
- current project library, especially core papers
- runtime availability of OpenAlex / scholar-facing integrations
- `.env` settings such as `STARMAP_OPENALEX_API_KEY` and `STARMAP_CONTACT_EMAIL`

### 6.5 Core Algorithms and Heuristics

#### Token weighting

Current watch token weights:

| Source | Weight |
| --- | --- |
| `target_title` | `5.5` |
| `target_abstract` | `3.5` |
| strategy `focus_phrase` | `4.0` |
| each strategy facet | `3.0` |
| each strategy query | `3.5` |
| each core paper title | `2.0` |
| each core paper abstract excerpt | `1.0` |

#### Lexical relevance

Current lexical relevance:

```text
lexical_score = overlap_weight / total_weight
best_query_score = best exact-or-token query match against title + abstract + venue
relevance = min(lexical_score * 0.78 + best_query_score * 0.22, 1.0)
```

Matched queries are retained only when:

```text
query_match_score >= 0.45
```

#### Venue and journal bonuses

Watched-journal lift tiers:

| Tier | Bonus | UI label |
| --- | --- | --- |
| `off` | `0.00` | `No lift` |
| `standard` | `0.12` | `Standard lift` |
| `priority` | `0.20` | `Priority lift` |

Current venue bonuses:

| Condition | Bonus |
| --- | --- |
| Venue matches configured top venue | `0.22` |
| Venue matches configured discipline keyword | `0.10` |

#### Candidate quality and freshness

Current quality score:

```text
citation_score = min(log1p(citation_count) / log1p(500), 1.0)
fwci_score = min(log1p(fwci) / log1p(5), 1.0)   # when fwci exists and is > 0

completeness_bonus =
  0.08 if venue exists
  + 0.05 if doi exists
  + 0.07 if abstract exists

quality_score =
  min(
    citation_score * 0.58
    + fwci_score * 0.12
    + completeness_bonus
    + venue_bonus
    + watched_journal_bonus,
    1.0
  )
```

Freshness behavior:

- if `publication_date` exists, freshness is linear over the requested watch window
- if only `year` exists, January 1 of that year is used as fallback
- otherwise freshness is `0.0`

#### Semantic rerank and final thresholds

Pre-rerank lexical thresholds:

| Watch mode | Minimum lexical relevance |
| --- | --- |
| `scholar` | `0.12` |
| `journal` | `0.14` |
| `target` | `0.18` |

Optional semantic rerank:

```text
final_relevance = semantic_relevance * 0.72 + lexical_relevance * 0.28
```

If semantic rerank is unavailable, `final_relevance = lexical_relevance`.

Current recommendation thresholds:

| Watch mode | Threshold with semantic rerank | Threshold without rerank |
| --- | --- | --- |
| `scholar` | `0.36` | `0.22` |
| `journal` | `0.34` | `0.24` |
| `target` | `0.42` | `0.28` |

Current watch score:

```text
watch_score =
  min(
    final_relevance * 0.65
    + quality_score * 0.30
    + freshness_score * 0.05,
    1.0
  )
```

Recall-padding behavior:

- target and journal watch attempt to return at least `12` recommendations
- if too few candidates meet the main threshold, StarMap pads recall with supplemental candidates
- supplemental floors are `0.24` for target watch and `0.22` for journal watch

### 6.6 Default Weights, Thresholds, and Limits

| Item | Current value |
| --- | --- |
| Lexical overlap weight | `0.78` |
| Best-query weight | `0.22` |
| Semantic rerank weight | `0.72` |
| Lexical rerank weight | `0.28` |
| Watch-score relevance weight | `0.65` |
| Watch-score quality weight | `0.30` |
| Watch-score freshness weight | `0.05` |
| Watched journal `standard` lift | `0.12` |
| Watched journal `priority` lift | `0.20` |
| Top-venue bonus | `0.22` |
| Keyword-venue bonus | `0.10` |
| Query retention floor | `0.45` |
| Scholar lexical floor | `0.12` |
| Journal lexical floor | `0.14` |
| Target lexical floor | `0.18` |
| Scholar recommendation floor with rerank | `0.36` |
| Journal recommendation floor with rerank | `0.34` |
| Target recommendation floor with rerank | `0.42` |
| Target supplemental floor | `0.24` |
| Journal supplemental floor | `0.22` |
| Minimum padded return count for target and journal watch | `12` |

### 6.7 Dependencies and Handoffs

Project Literature Watch depends on:

- thesis context from the project record
- core papers already curated in the repository
- browser-persisted watch strategy preferences
- runtime access to external literature APIs

It hands forward:

- candidate papers that may later enter the main repository
- updated awareness of the live literature frontier around the thesis topic

### 6.8 Failure Modes and Operational Notes

- If semantic rerank is unavailable, watch quality falls back to lexical relevance only.
- Venue lifts and watched-journal bonuses are intentionally biasing terms; they improve strategic recall but can distort pure topical ranking.
- Freshness becomes coarse when only year-level metadata is available because the system falls back to January 1 of that year.
- Recall padding is meant to avoid empty results, so low-threshold padded candidates should not be interpreted as equally strong recommendations.

For consolidated cross-system defaults, see Section 7.

---

## 7. Cross-System Reference and Audit Ledger

### 7.1 What this section is for

Sections 1 through 6 are workspace-oriented and intentionally repetitive. This final section is the consolidated cross-system ledger. If a default, weight, or cap appears both here and elsewhere, this section should be treated as the authoritative audit summary.

### 7.2 Implementation Surfaces

| Surface | Current implementation | Notes |
| --- | --- | --- |
| Frontend | `frontend/index.html` | Single-file SPA holding UI state, similarity scoring, citation clustering, PDF reader state, and most interaction logic |
| Backend | `backend/main.py` | Single FastAPI entry point for auth, persistence, Zotero, OpenAlex, claims, Stardust, jobs, and LLM-backed analysis |
| Durable storage | `database.db` | SQLite file; `projects.top_papers` stores the project paper pool as embedded JSON |
| Runtime config | `.env` | Repository-level integration defaults written through `/api/settings` |

### 7.3 Authentication and Session Model

Cross-system session behavior:

- the frontend stores the user snapshot in `localStorage["starmap_user"]`
- authenticated requests attach `X-Session-Token`
- backend validation is performed by `_require_session`
- a `401` response clears the client-side session snapshot and returns the UI to auth mode

Current auth-sensitive defaults:

| Item | Current value |
| --- | --- |
| Session TTL | `14` days |
| Password hashing | `pbkdf2_sha256` |
| PBKDF2 iterations | `120000` |

### 7.4 Runtime Settings and `.env`

Runtime settings are repository-level rather than project-level. Current persisted keys:

- `STARMAP_LLM_PROVIDER`
- `STARMAP_LLM_API_KEY`
- `STARMAP_OPENALEX_API_KEY`
- `STARMAP_CONTACT_EMAIL`
- `STARMAP_ZOTERO_USER_ID`
- `STARMAP_ZOTERO_API_KEY`
- `STARMAP_ZOTERO_COLLECTION_KEY`

Operational consequences:

- all projects in the same runtime share these settings
- saving settings updates both `.env` and `os.environ`
- settings writes are audit-logged as `settings_update`

### 7.5 Shared Persistence Map

#### Browser persistence

| Storage target | Key / store | Main use |
| --- | --- | --- |
| `localStorage` | `starmap_user` | Session snapshot |
| `localStorage` | `starmap_project_settings_<projectId>` | Shared project preferences, watch settings, marked nodes, manual paths, citation-cluster customizations |
| `localStorage` | `starmap_cluster_cache_v1_<projectId>_<mode>` | Semantic / citation cluster cache |
| `localStorage` | `starmap_citation_cluster_naming_retry_v1_<projectId>` | Citation-cluster naming retry memo |
| `localStorage` | `starmap_cluster_lineage_v1_<projectId>_<mode>` | Cluster lineage cache |
| `localStorage` | `starmap:workspace-section-collapse` | UI collapse state |
| `localStorage` | `starmap:workspace-active-module` | Last active workspace |
| IndexedDB | DB `starmap-read-paper-cache`, store `recent_pdfs` | Cached uploaded Read A Paper PDF plus reader state |

#### SQLite and normalized artifacts

| Table / field | Why it matters |
| --- | --- |
| `projects.top_papers` | Canonical embedded JSON paper pool for the live project |
| `project_claims` | Claim entities with type, status, and analysis version |
| `claim_evidence_items` | Evidence rows with stance, strength, relevance, confidence, quality, rationale, caveat, and snippet payloads |
| `claim_snippet_cache` | Cache of grounded evidence snippets |
| `challenge_stardusts` | Separate challenge-side exploration bundles |
| `challenge_stardust_papers` | Per-Stardust paper scores, discovery source, and import state |
| `audit_logs` | Cross-system mutation and job audit trail |

#### Process-local state

The following behaviors are not durable across backend restart:

- project task locks
- citation-graph job progress
- semantic-cluster job progress

### 7.6 Canonical Data Shape and Enum Notes

#### Paper normalization

| Field | Current behavior |
| --- | --- |
| `abstract` | Trimmed, truncated, normalized to `"Unknown"` when empty |
| `current_content` | Truncated to `10000` chars in normalization paths |
| `analysis_ready` | True when meaningful abstract or `current_content` exists |
| `metadata_only` | Inverse of `analysis_ready` |
| `similarity_pending` | Boolean flag for background rescoring |
| `zotero_has_fulltext` | True when full text exists or normalized `current_content` is meaningful |

#### Important enum-like values

| Area | Current values |
| --- | --- |
| Claim type | `thesis_claim`, `chapter_claim`, `research_question` |
| Claim status | `active`, `archived` |
| Claim stance | `support`, `challenge`, `setup`, `pending` |
| Read A Paper selection type | `paper`, `cluster` |
| Stardust status | `draft`, `ready`, `building`, `failed`, `archived` |
| Stardust graph mode | `directed`, `mutual`, `full` |

### 7.7 Endpoint Index

#### Auth, projects, and settings

| Area | Routes |
| --- | --- |
| Auth | `POST /api/register`, `POST /api/login`, `POST /api/logout`, `GET /api/session` |
| Project list | `GET /api/users/{user_id}/projects` |
| Project CRUD | `POST /api/projects/`, `GET /api/projects/{project_id}`, `PUT /api/projects/{project_id}`, `DELETE /api/projects/{project_id}` |
| Paper pool | `POST /api/projects/{project_id}/merge_papers`, `PUT /api/projects/{project_id}/papers` |
| Settings | `GET /api/settings`, `POST /api/settings` |
| Integration readiness | `GET /api/integrations/status` |

#### Atlas and clustering

| Area | Routes |
| --- | --- |
| Citation hydration | `POST /api/papers/citations` |
| Citation graph | `POST /api/papers/citation-graph`, `POST /api/papers/citation-graph/jobs`, `GET /api/papers/citation-graph/jobs/{job_id}` |
| Semantic cluster | `POST /api/papers/semantic-cluster/jobs`, `GET /api/papers/semantic-cluster/jobs/{job_id}` |

#### Read A Paper

| Area | Routes |
| --- | --- |
| Paper critique | `POST /api/projects/{project_id}/read-paper/analyze` |
| Zotero export | `POST /api/zotero/read-paper/export` |

#### Evidence Board

| Area | Routes |
| --- | --- |
| Claim CRUD | `POST /api/projects/{project_id}/claims`, `GET /api/projects/{project_id}/claims`, `DELETE /api/projects/{project_id}/claims/{claim_id}` |
| Claim analysis | `POST /api/projects/{project_id}/claims/{claim_id}/analyze` |
| Board retrieval | `GET /api/projects/{project_id}/claims/{claim_id}/board` |
| Challenge expansion | `POST /api/projects/{project_id}/claims/{claim_id}/challenge-expand` |

#### Challenge Stardust

| Area | Routes |
| --- | --- |
| Stardust CRUD | `POST /api/projects/{project_id}/stardusts`, `GET /api/projects/{project_id}/stardusts`, `GET /api/projects/{project_id}/stardusts/{stardust_id}`, `DELETE /api/projects/{project_id}/stardusts/{stardust_id}` |
| Stardust papers | `GET /api/projects/{project_id}/stardusts/{stardust_id}/papers` |
| Stardust graph | `GET /api/projects/{project_id}/stardusts/{stardust_id}/graph`, `POST /api/projects/{project_id}/stardusts/{stardust_id}/graph/build` |

#### Project Literature Watch

| Area | Route |
| --- | --- |
| Watch generation | `POST /api/projects/{project_id}/literature_watch` |

#### Zotero and integration support

| Area | Routes |
| --- | --- |
| Zotero collections | `GET /api/zotero/collections` |
| Zotero preview | `POST /api/zotero/preview` |
| Zotero hydration | `POST /api/zotero/items/hydrate` |
| Zotero sync | `POST /api/zotero/sync` |
| Zotero upload | `POST /api/zotero/upload` |

### 7.8 Consolidated Local Weight Ledger

#### Similarity and ranking

| Subsystem | Parameter | Current value |
| --- | --- | --- |
| Frontend similarity | Title cosine weight | `1.5` |
| Frontend similarity | Abstract cosine weight | `1.0` |
| Frontend similarity | Current-content cosine weight | `0.5` |
| Citation-count blend | `low` | `0.10` |
| Citation-count blend | `medium` | `0.12` |
| Citation-count blend | `high` | `0.15` |
| Citation compression cap | `CITATION_SCORE_LOG_CAP` | `200` |

#### Evidence Board

| Subsystem | Parameter | Current value |
| --- | --- | --- |
| Claim relevance | Title contribution | `0.29` |
| Claim relevance | Abstract contribution | `0.31` |
| Claim relevance | Notes contribution | `0.20` |
| Claim relevance | Body contribution | `0.20` |
| Claim relevance | Exact phrase bonus | `0.08` |
| Candidate score | Claim relevance | `0.32` |
| Candidate score | Project similarity | `0.14` |
| Candidate score | Status weight | `0.11` |
| Candidate score | Notes relevance | `0.12` |
| Candidate score | Quality score | `0.13` |
| Candidate score | Fulltext bonus | `0.08` |
| Candidate score | Recency score | `0.05` |
| Candidate score | Support hint | `0.05` |
| Strength score | Directness | `0.45` |
| Strength score | Relevance | `0.20` |
| Strength score | Quality | `0.20` |
| Strength score | Confidence | `0.15` |

#### Challenge expansion and Stardust

| Subsystem | Parameter | Current value |
| --- | --- | --- |
| Challenge expansion | Challenge hint | `0.33` |
| Challenge expansion | Claim relevance | `0.29` |
| Challenge expansion | Seed similarity | `0.28` |
| Challenge expansion | Quality | `0.10` |
| Challenge expansion | `cited_by` relation bonus | `0.05` |
| Challenge expansion | `reference` relation bonus | `0.03` |
| Challenge expansion | Heuristic include floor | `0.26` |
| Challenge expansion | LLM blend weight | `0.56` |
| Challenge expansion | Heuristic blend weight | `0.44` |
| Challenge expansion | Drop floor when not included | `0.34` |
| Stardust | Semantic overlap | `0.50` |
| Stardust | Challenge hint | `0.20` |
| Stardust | Claim relevance | `0.12` |
| Stardust | Quality | `0.10` |
| Stardust | Semantic supplement bonus | `0.045` |
| Stardust | Dual-direction citation bonus | `0.05` |
| Stardust | Cites-seed bonus | `0.038` |
| Stardust | Referenced-by-seed bonus | `0.03` |
| Stardust | Citation bonus cap multiplier | `0.02` |
| Stardust | Include floor | `0.27` |
| Stardust | Fallback inclusion floor | `0.22` |

#### Literature Watch

| Subsystem | Parameter | Current value |
| --- | --- | --- |
| Watch relevance | Lexical score weight | `0.78` |
| Watch relevance | Best-query score weight | `0.22` |
| Watch rerank | Semantic relevance | `0.72` |
| Watch rerank | Lexical relevance | `0.28` |
| Watch score | Final relevance | `0.65` |
| Watch score | Quality | `0.30` |
| Watch score | Freshness | `0.05` |
| Watched journal | `standard` lift | `0.12` |
| Watched journal | `priority` lift | `0.20` |
| Venue bonus | Top venue | `0.22` |
| Venue bonus | Keyword venue | `0.10` |

#### Semantic and citation clustering

| Subsystem | Parameter | Current value |
| --- | --- | --- |
| Semantic Cluster | Title term weight | `3.0` |
| Semantic Cluster | Abstract term weight | `1.8` |
| Semantic Cluster | Current-content term weight | `0.9` |
| Semantic Cluster | Bigram multiplier | `1.15` |
| Semantic Cluster | Vector dimension | `384` |
| Semantic Cluster | Retry threshold | `0.055` |
| Semantic Cluster | Undersized penalty per missing paper | `0.28` |
| Citation Cluster | Seed score similarity multiplier | `20` |
| Citation Cluster | Seed score indegree multiplier | `4` |
| Citation Cluster | Seed score degree multiplier | `1.5` |
| Citation Cluster | Seed separation distance bonus | `16` |
| Citation Cluster | Bucket growth connectivity multiplier | `12` |
| Citation Cluster | Connected-growth connectivity multiplier | `14` |
| Citation Cluster | Recommendation size multiplier | `8` |
| Citation Cluster | Recommendation average-similarity multiplier | `100` |

### 7.9 Defaults, Limits, and Audit-Sensitive Caps

| Area | Current default / cap |
| --- | --- |
| Max project papers | `500` |
| Max local PDF file size | `50 MB` |
| Max local PDF body scan pages | `24` |
| Max local PDF raw text before cleaning | `140000` chars |
| Local PDF import save batch size | `8` |
| Max paper current content | `10000` chars |
| Max target title | `300` chars |
| Max target abstract | `20000` chars |
| Max target current content | `80000` chars |
| Max claim text | `4000` chars |
| Max claim candidates | `96` |
| Claim analysis batch size | `8` |
| Max evidence snippets per item | `3` |
| Max snippet text length | `360` chars |
| Read A Paper max papers | `12` |
| Read A Paper max findings per section | `6` |
| Read A Paper max questions to press | `6` |
| Max Stardusts per project | `5` |
| Max papers per Stardust | `50` |
| Max persisted cluster cache payload | `900000` chars |
| Saved breadcrumb trails per project | `12` |
| Saved custom citation clusters per project | `10` |
| Zotero cache TTL | `5` minutes |
| Zotero full sync interval | `1` hour |

### 7.10 Maintenance Notes

- If a scoring constant changes, update this companion reference in the same change set.
- If citation-cluster logic changes materially, review or bump `CITATION_CLUSTER_ALGORITHM_VERSION`, otherwise stale per-paper assignments may appear valid when they should be recomputed.
- If semantic-cluster hashing, tokenization, or scoring changes materially, review `SEMANTIC_CLUSTER_ALGORITHM_VERSION` and related cache-signature behavior.
- If browser-stored schema changes, review localStorage version keys, IndexedDB payload shape, and restoration behavior in the frontend.
- Remember that several operational guarantees remain process-local rather than durable: project task locks, citation-graph job progress, and semantic-cluster job progress all disappear on restart.
