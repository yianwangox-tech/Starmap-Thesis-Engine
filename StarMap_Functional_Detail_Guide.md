# StarMap Functional Detail Guide

Review baseline: `2026-05-23`

## Positioning

This document is the implementation-facing English functional guide for StarMap. It is derived from the product-specification PDF `starmap_论文分析管理系统_美化版.pdf` and is intended to replace the older companion reference document.

Use this guide when you need to understand:

- how each major workspace is entered
- what problem that workspace is designed to solve
- how StarMap filters, scores, or organizes candidate papers
- which actions stay local, which actions write back to the project library, and which actions require explicit user approval

For the broader workflow-first explanation of the product, see:

- [StarMap Primary Guide for Research Leads and New Contributors](./StarMap_Primary_Guide_for_Research_Leads_and_New_Contributors.md)

## Table of Contents

1. [Project Library Intake Paths](#1-project-library-intake-paths)
2. [StarMap Visualization](#2-starmap-visualization)
3. [Read A Paper PDF](#3-read-a-paper-pdf)
4. [Evidence Board](#4-evidence-board)
5. [Stardust](#5-stardust)
6. [Project Literature Watch](#6-project-literature-watch)
7. [System-Level Product Logic](#7-system-level-product-logic)

---

## 1. Project Library Intake Paths

### 1.1 Why intake paths matter

StarMap does not rely on a single paper-ingestion workflow. Papers can enter the project library from local files, Zotero, external metadata lookups, or recommendation modules. All of these paths eventually converge on the same project paper pool, but they begin from different evidence sources and serve different research moments.

The main product question here is not only "How does a paper get into the library?" but also "What is the system allowed to trust first?"

### 1.2 Local PDF import

Entry point: `Import PDFs` in the top action area of the project workspace.

This path starts from one or more local PDF files selected by the user. The frontend reads each file locally, extracts title-like text, abstract-like text, and analyzable body content, then attempts to enrich the record with external scholarly metadata such as DOI, venue, and citation information.

After extraction, the system compares the candidate paper with papers already stored in the current project:

- if the paper is new, StarMap creates a new project record
- if the paper is a more complete version of an existing paper, StarMap updates the existing record

After merge, StarMap recomputes project relevance against the current project context and stores the result as part of the formal project library.

The defining characteristic of this intake path is that the PDF itself is the starting source of truth.

### 1.3 Zotero fetch

Entry point: `Sync Zotero`, then `Fetch from Zotero`.

This path starts from the user's Zotero library or a selected Zotero collection. StarMap reads bibliographic data first, then supplements it with abstract, link, and attachment information when available.

During import, the system checks whether the paper already exists in the project library:

- missing papers are created
- existing papers are enriched or updated with fresher Zotero-side metadata

After merge, the imported or updated papers are brought into the same relevance-calculation pipeline as every other paper in the project.

This mode is best understood as library bootstrap or library expansion from an already curated reference manager.

### 1.4 Zotero PDF-content sync

Entry point: `Sync Zotero`, then `Sync PDF Content for Improving Similarity Calculations`.

This mode is not primarily about adding new papers. Its purpose is to enrich papers that already exist in the project library with fuller PDF text recovered from Zotero attachments.

The system first aligns a project paper with the matching Zotero item, then checks whether usable PDF text can be extracted from the Zotero side. If so, that text is written back into the existing StarMap paper record while preserving its project identity and status.

Because full text directly affects similarity and ranking quality, StarMap typically refreshes project relevance after this sync completes.

This path should be read as a quality-improvement workflow for existing records, not as a new-ingestion workflow.

### 1.5 Single-paper external import

Entry points: import-style actions attached to citation views, scholar results, external metadata panels, or other one-paper discovery surfaces.

This path starts from external metadata rather than from a local PDF or Zotero entry. StarMap queries scholarly data sources using fields such as title, author, year, and DOI, then builds a fuller candidate identity before deciding whether to create or update a project record.

Once merged, the paper immediately joins the same relevance-calculation flow as other project papers.

This mode is useful when the user discovers one promising paper while following references, checking citations, or browsing external results.

### 1.6 Literature Watch import

Entry point: `Project Literature Watch`, then select results and use `Add Selected to StarMap`.

This path starts from watch-generated candidate recommendations rather than from the user's own local assets. Even so, watch results do not enter the project library automatically. Users must explicitly confirm which candidates should be admitted.

After confirmation, StarMap runs the normal merge process:

- deduplicate against the main library
- create or update records as needed
- refresh project relevance in the background

This preserves a core StarMap principle: recommendation surfaces can suggest papers, but only confirmed papers graduate into the main project pool.

---

## 2. StarMap Visualization

### 2.1 Workspace purpose

Entry point: the `StarMap Visualization` module inside the project workspace.

This workspace helps users understand the same project library from three different structural perspectives:

- `Orbital (Uni-directional)` asks which papers are closest to the target thesis
- `Network (Bi-directional)` asks which high-relevance papers are closest to one another in content space
- `Citation Graph` asks how papers connect through real citation relations

The user can switch visualization modes and adjust `Visualization Density` to control how many papers remain in the visible range.

### 2.2 Shared foundation for Orbital and Network

Orbital and Network do not begin by drawing shapes. They begin by computing a similarity matrix.

The system treats the target thesis as one comparable object and places it alongside the `n` papers currently inside the visualization scope. The effective input is therefore `n + 1` objects, and the core result is an `(n + 1) x (n + 1)` similarity matrix.

In the current product logic:

- papers are represented using title, abstract, body snippets, and author information
- the target thesis is represented using project title, project abstract, and current thesis content
- text is transformed into embeddings
- pairwise similarity is computed with cosine similarity

The practical meaning is simple: StarMap is comparing semantic direction, not file shape and not keyword overlap alone.

### 2.3 Orbital view

Entry point: `Orbital (Uni-directional)`.

The first filter is project relevance ranking. StarMap sorts project papers by their current thesis relevance score, then applies the density limit so that only the top portion enters the scene.

Once the visible set is chosen, the layout no longer depends on paper-to-paper edges. Instead, StarMap reads the thesis-to-paper similarity vector and places the thesis at the center:

- papers more similar to the thesis sit closer to the center
- weaker papers are placed on outer rings

Orbital therefore visualizes outward relevance from the project center. It is not meant to show a paper relationship network. It is meant to show which papers deserve priority attention relative to the thesis.

If the user temporarily focuses on one paper, the system can re-center the local view around that paper while retaining the original thesis as a reference point.

### 2.4 Network view

Entry point: `Network (Bi-directional)`.

This view uses the same initial scope filter as Orbital:

- sort by project relevance
- keep only the top subset allowed by the density setting

After that, the logic changes. Network uses the full similarity matrix but does not draw every possible pairwise edge. Instead, StarMap keeps only the strongest small set of neighbors for each paper, deduplicates those links, and sends the resulting sparse graph into a force-directed layout.

The meaning of a visible edge is therefore:

- not "these are the only related papers"
- but "these are the strongest relationships worth showing in the current view"

This makes Network useful for spotting content clusters, bridge papers, and local neighborhoods among the most relevant papers in the project.

### 2.5 Citation Graph

Entry point: `Citation Graph`.

This view is built on citation relations rather than semantic similarity. StarMap first checks whether usable citation data already exists in the current project library. If not, it calls OpenAlex to enrich missing citation links.

Only internal project-to-project citation edges are retained. A line is drawn only when:

- paper A is in the current project
- paper B is in the current project
- A cites B or B cites A

In the default focused mode, StarMap applies an additional visibility filter so that the graph emphasizes nodes with stronger structural value. An `All` mode can relax that filter and show more nodes.

Citation Graph should be interpreted as a map of scholarly lineage and citation flow, not as a map of textual similarity.

### 2.6 How the three views differ

The three views share one project library but answer different questions:

| View | Primary filter | Primary relation | Main question |
| --- | --- | --- | --- |
| `Orbital` | Thesis relevance ranking | Thesis-to-paper similarity | Which papers are closest to the project target? |
| `Network` | Thesis relevance ranking | Paper-to-paper semantic proximity | Which high-relevance papers form neighborhoods or bridges? |
| `Citation Graph` | In-project citation availability and display mode | Real citation links | How do these papers connect through scholarly citation structure? |

This separation is deliberate. StarMap avoids collapsing all structure into one overloaded picture.

---

## 3. Read A Paper PDF

### 3.1 Workspace purpose

Entry point: `Read A Paper PDF`.

This module is not a generic PDF viewer. It is StarMap's close-reading workstation for one paper at a time.

Its job is to help the user do a full paper-level reading workflow:

- upload and parse a PDF
- read page by page
- highlight and annotate passages
- ask whole-paper critique questions
- ask passage-level follow-up questions
- preserve reading continuity locally
- export marked reading output to Zotero when desired

Unlike the project library or visualization modules, this workspace is intentionally paper-local rather than repository-wide.

### 3.2 Upload and parse

Entry point: `Choose PDF`.

When the user selects a local PDF, the frontend reads the file inside the browser rather than immediately adding it to the project library. The parsing flow extracts text page by page, builds page-to-text alignment, and prepares reading-ready page content.

The system then assembles paper-level reading material such as:

- candidate title
- candidate abstract
- body snippets
- page context

An LLM-based metadata extraction flow uses those materials to identify structured paper information such as title and abstract.

Important boundary: uploading a PDF here does not automatically add the paper to the project library. It only loads the paper into the current deep-reading session.

### 3.3 Reader view and navigation

After upload, the user reads inside the integrated viewer using page controls, zoom, and scrolling.

The reader module manages:

- current page
- zoom level
- visible region
- stable local state for ongoing reading

The system does not auto-decide which page matters most. Its main responsibility is continuity: preserving where the user was, how far they had zoomed, and what they had already marked.

### 3.4 Whole-paper critique

Entry point: optional paper-level question field plus `Run Paper Critique`.

This feature sends a paper-level analysis request to the backend. The frontend assembles a normalized analysis package containing the parsed paper materials together with the current project context:

- paper title, abstract, body snippets, notes, author, year, and venue information
- project title, project abstract, and target thesis content
- the user's optional question

This is therefore not a context-free paper summary. It is a thesis-aware critical reading workflow.

The backend validates the request, then sends the materials into a paper-critique process that asks the model to behave as a critical reader rather than a polite summarizer. After generation, StarMap attempts to map conclusions back onto real abstract passages, body text, or user notes so the output remains tied to visible evidence.

Typical output includes:

- a deep-reading summary
- a direct answer to the user's question
- threats to validity
- external-validity limits
- design fragilities
- improvement opportunities
- next questions worth asking

### 3.5 Passage analysis

Entry point: draw a box on the PDF page, then use `Analyze Passage`.

This feature is for close inspection of one local passage, figure explanation, methods paragraph, or results sentence. The frontend takes the selected area as a screenshot, extracts surrounding page context, and packages that together with broader paper context for a vision-capable model.

The primary evidence is the actual selected page image. Extracted text acts as support when needed.

This makes the feature well suited to questions like:

- What is this paragraph really claiming?
- Does this figure support the author's conclusion?
- What is the most fragile part of this method description?

Passage analysis is organized on the frontend around the selected region, not through the backend whole-paper critique path.

### 3.6 Highlights and reading annotations

Entry points: region selection, type chooser, color chooser, and note input inside the reading surface.

The annotation manager stores each marked passage as a structured record that can include:

- excerpt text
- page number
- nearby context
- annotation type
- color
- user note
- optional passage-analysis output

Annotation types are normalized into a bounded set such as:

- `claim`
- `evidence`
- `method`
- `threat`
- `limitation`
- `question`
- `to_cite`

This keeps reading traces reusable later instead of reducing them to free-form highlights only.

### 3.7 Local cache and reading continuity

This module relies heavily on local caching because it manages a live reading session rather than a stable project database object.

The cache can persist:

- the uploaded PDF
- page text
- current page
- zoom state
- draft questions
- highlights
- notes
- analysis state

The product principle is clear: preserve the reading scene first, persist durable project artifacts later.

### 3.8 Export to Zotero

Entry point: Zotero export panel, then `Save`.

Export is selective rather than exhaustive. The main objects StarMap exports are:

- the current PDF
- explicitly marked passages
- corresponding notes
- optional whole-paper critique notes

If the user has not marked at least one concrete region, StarMap blocks anchored highlight export because there is not yet enough evidence to produce a traceable annotation artifact.

The export flow typically:

1. confirms the target Zotero library or collection
2. finds or creates the parent Zotero item
3. uploads the marked PDF
4. creates a Zotero note for each marked passage
5. appends a paper-level note when a whole-paper critique exists

The result is not merely "I read this paper" but a portable package of anchored annotations.

### 3.9 Best use case

This module is most valuable after the user has already identified a paper as worth serious attention through the library, visualization, or clustering workflows.

Its function is to convert paper-level reading into reusable, inspectable research output.

---

## 4. Evidence Board

### 4.1 Workspace purpose

Entry point: `Evidence Board`.

Evidence Board asks a different question from ordinary relevance ranking. It does not ask whether a paper is broadly related to the project. It asks what role each paper plays in relation to a specific claim.

The user writes a claim, chapter argument, or research question. StarMap then organizes current project papers into four lanes:

- `support`
- `challenge`
- `setup`
- `pending`

The core value of this module is that it turns a flat library into an argument board.

### 4.2 Analysis scope

Entry point: write the claim, choose the analysis range, then run `Analyze Claim`.

The backend claim-analysis flow does not search the whole world. It only evaluates papers already stored in the current project library.

Two early filters define the candidate scope:

- the user-chosen analysis range, which limits how many papers can be analyzed
- a status filter that usually prioritizes papers such as `Core`, `Pending`, `Underweight`, and `Unread`

The product logic is: first judge whether the current library can support the claim before expanding outside it.

### 4.3 Candidate-pool construction

To build the candidate pool, the backend reads multiple signals for each paper:

- title
- abstract
- user notes
- body snippets
- project relevance score
- paper status
- year
- citation count
- metadata completeness

It does not rely on a single ranking. Instead, it generates multiple ranked lists in parallel, such as:

- claim-match ranking
- support-signal ranking
- challenge-signal ranking
- setup-signal ranking
- overall candidate-score ranking
- project-relevance ranking
- paper-quality ranking

The final candidate pool is assembled by sampling from these different rankings rather than by trusting only one path. This reduces the risk that one dominant interpretation, such as apparent support, crowds out important challenge or method papers.

### 4.4 Scoring and diversification

Candidate scoring combines text signals and quality signals.

Text-side logic looks at whether claim terms, phrases, and role-specific language appear in the paper's title, abstract, notes, or body. Quality-side logic considers whether the paper has enough content and enough metadata to justify serious attention.

Before finalizing the pool, StarMap applies a diversification step so that one cluster or one source category does not monopolize the board. It prefers explicit cluster labels when available and can fall back to journal labels or an uncategorized bucket.

This is not random balancing. It is a deliberate anti-monopoly mechanism for evidence review.

### 4.5 Lane assignment

After the candidate pool is built, the backend classifies each paper into exactly one lane. StarMap prefers an LLM-based classifier but can fall back to local heuristics if the model is unavailable or returns unusable output.

The classifier does not ask whether a paper is simply related to the project. It asks whether the paper mainly functions as:

- direct support for the claim or its core mechanism
- a challenge, boundary condition, limitation, or rebuttal
- methodological or background setup
- a relevant but still inconclusive paper

That is why the four lanes are argument-role categories rather than topic categories.

### 4.6 Meaning of the four lanes

`support` means the paper is judged to strengthen the claim or a core mechanism behind it.

`challenge` means the paper weakens, bounds, questions, or potentially contradicts the claim.

`setup` means the paper is most valuable as design, measurement, identification, dataset, or methodological infrastructure rather than as a direct verdict on the claim itself.

`pending` means the paper is still relevant, but the available evidence is not yet strong enough for the system to force it into one of the other three lanes.

Many `pending` items usually indicate either an immature argument or a thin evidence base.

### 4.7 Evidence cards

Once a paper is assigned, StarMap generates an evidence card. Each card includes scores such as:

- strength
- relevance
- confidence
- quality

These are computed by the backend from classification result, claim fit, paper quality, and classification confidence. StarMap also extracts snippets from abstract text, body text, or notes to explain why the paper landed in its lane.

If a model-proposed snippet cannot be aligned with real text, StarMap falls back to local snippet extraction from the paper's stored content.

### 4.8 Manual control

Evidence Board is not a sealed black box. Users can pin cards, change lanes, hide cards, or revise rationales. Those edits are preserved as user overrides rather than being immediately erased by the next render.

Only an explicit re-analysis with overwrite permission should replace those manual judgments.

---

## 5. Stardust

### 5.1 Workspace purpose

Entry points:

- `Expand to Stardust` from a `challenge` evidence card
- `Expand to Stardust` from a `support` evidence card
- `New From Claim` from the Stardust area

Stardust is a side-pool expansion layer. Its purpose is to search outside the main project library for papers that may further support or challenge a line of argument.

The key design principle is separation:

- the main library holds already admitted project papers
- Stardust holds exploratory candidates outside the main library

This prevents speculative exploration from polluting the core project pool too early.

### 5.2 Three start modes

There are three startup patterns:

- `Challenge Stardust` from a `challenge` evidence card
- `Support Stardust` from a `support` evidence card
- `New From Claim` from a user-written seed claim

The first two have strict entry rules. Challenge expansion must begin from a card already classified as `challenge`, and support expansion must begin from a card already classified as `support`.

This ensures that outward exploration begins from a claim-tested seed rather than from an unvetted paper.

### 5.3 Core search principle

Stardust is not designed as keyword-first search. Its preferred strategy is:

1. walk the real citation neighborhood around the seed
2. use semantic search only when citation expansion remains too sparse

This means StarMap first follows actual scholarly relations such as "papers cited by the seed" and "papers citing the seed." Only when those neighborhoods are still too thin does it generate semantic fallback queries to external scholarly sources.

The result is usually a more coherent literature trail rather than a loose collection of superficially similar papers.

### 5.4 Support and challenge trails

Support Stardust and Challenge Stardust share the same pipeline but not the same emphasis.

Challenge trails give more weight to signals such as:

- limitation
- contradiction
- boundary condition
- weak effect
- method critique

Support trails give more weight to signals such as:

- direct confirmation
- mechanism reinforcement
- robustness support
- context extension
- methodological reinforcement

Stardust therefore does not search once and label later. Directionality already matters during scoring.

### 5.5 First-hop candidate screening

For evidence-seeded Stardust, the first hop comes from OpenAlex neighborhood capture:

- papers the seed cites
- papers that cite the seed

StarMap immediately removes:

- candidates already in the main project library
- candidates with unresolvable or insufficient identity metadata

The remaining pool therefore starts as papers that are outside the project, identifiable, and citation-connected to the seed.

### 5.6 Second-hop expansion

First-hop candidates are not all treated equally. StarMap scores them by:

- closeness to the seed paper
- closeness to the current claim or sub-goal
- support or challenge signal strength
- paper quality
- citation relation pattern

If the first hop yields strong candidates, StarMap chooses only a small subset of those strong items as second-hop seeds. This prevents the trail from expanding blindly while still allowing useful outward reach.

### 5.7 Semantic fallback

If citation-neighborhood expansion still produces too few usable candidates, StarMap builds semantic search expressions from materials such as:

- seed title
- current claim
- sub-goal statement
- overall project target
- explanation text already attached to the evidence seed

Results from this path are explicitly marked as `semantic_fallback` so users can distinguish direct citation-neighborhood discoveries from supplementary semantic recalls.

### 5.8 Final candidate filtering

Regardless of source, final Stardust filtering is performed by a common scoring module. It combines:

- seed proximity
- claim proximity
- support or challenge language signals
- metadata quality
- citation performance
- one-way versus two-way connection to the seed

The system prefers nearby, directionally relevant, and legible candidates. If nothing crosses the main threshold, Stardust can still keep a small fallback set so the user does not face an empty result.

That fallback protects recall, not certainty.

### 5.9 Source filters and type groups

The `Source Filter` in the UI is only a display control over stored origin labels such as:

- `hop_1`
- `hop_2`
- `semantic_fallback`

It does not trigger rescoring.

After admission into the Stardust side pool, candidates can also be grouped into reading-friendly type buckets. Challenge examples include:

- direct contradiction
- boundary condition
- alternative mechanism
- null or weak effect
- context-specific caveat
- methodological challenge

Support examples include:

- direct confirmation
- mechanism reinforcement
- boundary-aligned support
- robustness support
- context extension
- methodological reinforcement

These groups help interpretation, but they are not the hard admission gate.

### 5.10 Importing Stardust papers into the main library

Stardust candidates remain outside the main project by default. The user must explicitly select papers for import.

Once selected, StarMap sends them through the same main-library merge logic used by other intake paths:

- add new records if missing
- update existing records if duplicates are found
- refresh project relevance after merge

Stardust is therefore a staging pool, not a second permanent library.

---

## 6. Project Literature Watch

### 6.1 Workspace purpose

Entry point: `Project Literature Watch`.

This module continuously searches external scholarly sources for papers worth noticing but not yet present in the project library.

Its design goal is bounded monitoring, not limitless search. StarMap first decides where to look, then retrieves candidates, then applies layered filtering before showing the user a shortlist for review.

Watch results remain candidates until the user explicitly imports them.

### 6.2 Three watch modes

StarMap supports three watch modes:

- `Target Watch`
- `Scholar Watch`
- `Journal Watch`

All three aim to produce high-value new-paper candidates for the current project, but they start from different anchors.

### 6.3 Target Watch

Entry point: choose `Target Watch`, set discipline scopes and a time window, then run the watch.

This is not just keyword search on the project title. StarMap first builds a watch strategy from project-side context such as:

- project title
- project abstract
- target thesis content
- titles and abstract fragments from the project's core papers

The strategy module converts that context into a monitoring focus and several search expressions designed to represent the project's live research direction more faithfully than raw thesis text alone.

### 6.4 Scholar Watch

Entry point: choose `Scholar Watch`, then enter scholar names.

The first step is author identity alignment. StarMap tries to match the provided names against external scholarly author records so it does not rely on raw strings alone.

After alignment, the backend retrieves recent publications from those authors and sends them through the common relevance-filtering pipeline. Being written by a watched scholar is therefore a candidate-source signal, not a guarantee of recommendation.

### 6.5 Journal Watch

Entry point: choose `Journal Watch`, then enter journals to follow.

The first step is venue alignment. StarMap matches the provided journal names against external scholarly venue records so that abbreviations or spelling variants do not misdirect retrieval.

After recognition, the backend retrieves recent papers from those journals and sends them into the common filtering pipeline. Being published in a watched journal defines the search boundary, not the final decision.

### 6.6 Time windows and retrieval scope

Watch runs are always bounded by a user-controlled time range, such as recent months or recent years. The backend respects that time window when retrieving candidates.

This is essential because Literature Watch is for current monitoring rather than historical library reconstruction.

### 6.7 Candidate retrieval and early cleanup

Candidate retrieval differs by mode:

- Target Watch uses strategy-generated search expressions
- Scholar Watch uses recent works from identified scholars
- Journal Watch uses recent works from identified journals

After retrieval, StarMap performs early cleanup:

- remove candidates already present in the project library
- merge duplicate candidates found through different query routes
- preserve source-hit information for explanation later

This stage is about deduplication and candidate registration, not final ranking.

### 6.8 Relevance, quality, and freshness

The relevance scorer reads both project-side context and candidate-side metadata.

Project-side material can include:

- project title
- project abstract
- target thesis content
- watch-focus phrases
- watch queries
- titles and abstract fragments from core project papers

Candidate-side material mainly includes:

- title
- abstract
- venue

The system asks whether the candidate is actually discussing the problems that the project cares about, not merely whether it overlaps with a few surface words.

StarMap also scores candidate quality by looking at factors such as:

- metadata completeness
- abstract availability
- source clarity
- citation performance
- alignment with configured discipline scopes

For `Target Watch`, tracked journals can also receive extra weighting tiers so that some venues contribute more lift than others.

Freshness matters too. Publication recency is used as an additional monitoring signal so that similarly strong candidates can be ordered in favor of newer work.

### 6.9 Thresholds and reranking

Before final ranking, StarMap applies a mode-specific but conceptually similar minimum relevance gate. A candidate that is too weak on project fit should not survive simply because it came from a watched scholar or watched journal.

After the first pass, StarMap may run a deeper semantic reranking step on already qualified candidates. If that layer is unavailable, the module falls back to the first-pass text-and-field ranking rather than failing outright.

Final ordering typically combines:

- project relevance
- candidate quality
- freshness

Relevance carries the largest weight, quality comes next, and freshness serves as the final important adjustment.

### 6.10 Explanations and import

Each result can include a readable explanation of why it surfaced, such as:

- which watch query it matched
- which scholar or journal it came from
- why it appears close to the current thesis
- whether extra weighting from a priority journal helped

The explanation layer does not change the ranking. It translates ranking reasons into human-readable cues.

Import still requires explicit user confirmation. Once selected, watch results go through the normal project merge path rather than bypassing main-library rules.

---

## 7. System-Level Product Logic

Several system-wide design principles recur across the modules described above.

### 7.1 The main project library is curated, not automatic

Papers can be suggested by watch flows, Stardust, or external discovery paths, but the main project library remains a governed pool. Automatic discovery does not equal automatic admission.

### 7.2 One project acts as one semantic center

The target thesis context is reused across ranking, visualization, critique, evidence analysis, and watch recommendation. When the project target is well specified, downstream modules become more coherent together.

### 7.3 StarMap separates review from expansion

Evidence Board asks whether the current library already supports an argument. Stardust asks where to expand when it does not. Literature Watch asks what new external work deserves attention over time. These are related functions, but they are intentionally not collapsed into one screen or one score.

### 7.4 Not every useful state belongs in the backend first

Some workflows, especially `Read A Paper PDF`, prioritize local continuity and cached session state before durable project-level persistence. This is a product decision, not an omission.

### 7.5 Explanation is a first-class output

Across Evidence Board, Stardust, and Literature Watch, StarMap tries to show not only results but also why those results appeared. Snippets, why-matched text, source labels, and lane rationales all serve that purpose.

### 7.6 Human judgment remains the final gate

Users can override Evidence Board placements, choose which Stardust papers graduate into the main library, and decide which watch candidates deserve import. StarMap is designed to accelerate research judgment, not replace it.
