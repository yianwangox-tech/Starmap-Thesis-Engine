# StarMap System

StarMap System is a thesis-centered literature analysis workspace for academic research. It combines PDF import, similarity ranking, citation exploration, theme clustering, literature-watch workflows, Zotero sync, repository analytics, and BibTeX export in one interface.

The product is designed for users who do not just want to store papers, but want to actively shape a research repository around a live argument: define the target thesis, build a focused seed library, identify core papers, inspect citation structure, monitor new literature, and keep writing-ready references close at hand.

## What StarMap Is For

StarMap works best when one project represents one research direction. A project stores the thesis title, target abstract, and current draft content, then uses that context to rank papers, explain match quality, support clustering, and guide watch recommendations.

Typical use cases include:

- thesis scoping and early-stage literature mapping
- literature review building and maintenance
- citation-structure inspection for a focused repository
- Zotero-assisted paper curation
- BibTeX preparation for Overleaf or other LaTeX workflows
- monitoring newly published work around a target topic, scholar set, or journal set

## Core Workflow

1. Create a project and define the target thesis context.
2. Import a focused seed library from local PDFs or Zotero.
3. Curate `Top Related Papers` and assign statuses such as `Core`, `Pending`, `Underweight`, or `Unread`.
4. Inspect the repository through `Workspace Atlas` in orbital, network, and citation views.
5. Run `Auto Cluster Themes` as either `Semantic Cluster` or `Citation Cluster`.
6. Audit library quality through `Repository Analytics`.
7. Use `Project Literature Watch` to keep the frontier current.
8. Export BibTeX and move selected papers into writing workflows.

## Feature Overview

### 1. Project-Based Research Workspace

- user registration, login, session persistence, and multi-project management
- per-project thesis framing with:
  - `Target Title`
  - `Target Abstract`
  - `Target Current Content`
- project settings for background precompute, LLM theme naming, Zotero preload, and citation-count quality assist

### 2. PDF Import, Metadata Extraction, and Rollback

- drag-and-drop local PDF import
- PDF parsing in the browser with PDF.js
- metadata and text extraction for titles, abstracts, authors, year, and body content
- retry handling for temporary LLM-assisted extraction failures
- `Rollback Latest Import` support to undo the most recent import batch

### 3. Similarity Ranking and Match Explanations

- `Top Related Papers` acts as the main review queue
- ranking uses the project target context together with paper metadata and extracted content
- optional citation-count quality assist blends compressed citation signal from OpenAlex into similarity ranking
- match explanation cards show weighted signal contributions such as title, abstract, current content, and citation support

### 4. Paper Detail and Review Actions

Each paper can open in a centered modal or a side drawer depending on the visualization flow. The paper view includes:

- title, authors, year, venue, citation count, abstract, and notes
- match explanations and weighted contribution breakdowns
- reading status and project-level note-taking
- direct actions such as:
  - `Generate BibTeX`
  - `Cited By`
  - `References`
  - `Read the Paper`
  - `See Paper Info`
  - `Mark Node`

### 5. Workspace Atlas

`Workspace Atlas` is the main visualization layer of the system. It provides three coordinated views of the same repository:

- `Orbital (Uni-directional)` for broad orientation around the target
- `Network (Bi-directional)` for neighborhood structure and paper-to-paper relationship inspection
- `Citation Graph` for explicit citation flow

Additional visualization behavior in the current version includes:

- density controls for `Top 150`, `Top 300`, and `Top 500`
- performance warnings for higher-density rendering
- zoom controls with press-and-hold support
- high-density gesture restrictions to reduce lag
- marked-node highlighting for saved exploration anchors

### 6. Theme Clusters

`Auto Cluster Themes` now lets the user choose which clustering mode to run instead of computing all modes at once.

- `Semantic Cluster` groups papers by topic similarity
- `Citation Cluster` groups papers by citation topology inside the project citation graph

Current citation-cluster behavior includes:

- local citation topology maps for each selected cluster
- in-cluster core-paper ranking based on citation indegree
- hop-based local exploration modes
- LLM naming and overview generation
- `LLM Re-overview` for rerunning failed citation-cluster naming or overview attempts

### 7. Project Literature Watch

`Project Literature Watch` helps users track new literature without leaving the StarMap workflow. The current version supports three modes:

- `Target Watch` for thesis-direction scanning
- `Scholar Watch` for watched authors
- `Journal Watch` for watched journals

The watch workflow also supports:

- configurable time windows
- discipline scoping
- journal-to-target weighting logic

The current version adds a dedicated `Adjust Journal Weightings` flow for `Target Watch`, so journals saved in `Journal Watch` do not all contribute the same lift. Users can place watched journals into tiers such as `No lift`, `Standard lift`, and `Priority lift`.

### 8. Zotero Integration

StarMap integrates with Zotero for both repository building and repository maintenance.

Supported workflows include:

- checking Zotero connectivity
- loading collection lists
- previewing unmatched Zotero items
- syncing StarMap papers to Zotero
- fetching Zotero items into the current project
- syncing Zotero PDF text into existing StarMap papers

Runtime defaults can be read from `.env`, so users do not need to re-enter Zotero credentials in every session.

### 9. OpenAlex-Powered Citation Enrichment

StarMap uses OpenAlex to enrich repository metadata and citation structure. This supports:

- paper lookup and metadata completion
- citation count enrichment
- `Cited By` and `References` expansion
- full citation graph construction
- citation-community detection used by `Citation Cluster`

### 10. Repository Analytics

`Repository Analytics` is the repository-readiness dashboard. It helps users decide whether the library is clean enough for ranking, clustering, and drafting.

Current analytics include:

- `Repository Health`
- `Metadata Completeness`
- venue, author, and year-level repository summaries

The new metadata completeness view separates missing-data problems such as:

- author missing
- venue missing
- year missing
- multiple metadata fields missing

### 11. BibTeX and Writing Support

StarMap can generate project-ready BibTeX entries and supports citation-key cleaning for LaTeX workflows. It also includes literature-review assistance built from curated core papers and user notes, making it easier to turn repository structure into early writing scaffolds.

## Architecture

### Frontend

- single-page web app
- main UI defined in `frontend/index.html`
- ECharts-based visualizations
- PDF.js-based local PDF reading and parsing
- lightweight client-side state for project interaction, visualization, clustering, and watch workflows

### Backend

- FastAPI application in `backend/main.py`
- SQLite-backed storage for users, projects, sessions, papers, and settings
- OpenAlex and Zotero integration endpoints
- LLM proxy and cluster-overview support
- citation-graph job endpoints for heavier repository graph work

## Local Development

The repository currently ships as a lightweight source tree without a packaged dependency manifest, so local setup is simple but manual.

### Backend

Install the Python dependencies you need for `backend/main.py`, then run:

```bash
python backend/main.py
```

The backend starts on:

- `http://127.0.0.1:8001`

### Frontend

Serve the `frontend` directory with any static file server. For example:

```bash
python -m http.server 8000 --directory frontend
```

Then open:

- `http://127.0.0.1:8000`

The frontend automatically probes common local API origins and will try the backend on port `8001`.

### Auto-start on macOS

If you want both services to come back automatically after a reboot, this repo now includes helper scripts for `launchd`:

```bash
chmod +x scripts/start_backend.sh scripts/start_frontend.sh scripts/install_launch_agents.sh
./scripts/install_launch_agents.sh
```

This installs two user LaunchAgents:

- `com.ianwang.starmap.backend`
- `com.ianwang.starmap.frontend`

They start automatically when you log in and restart themselves if they exit unexpectedly. Logs are written to:

- `logs/backend.stdout.log`
- `logs/backend.stderr.log`
- `logs/frontend.stdout.log`
- `logs/frontend.stderr.log`

These scripts are macOS-only and do not affect Windows users.

### Auto-start on Windows

Windows users can install equivalent per-user startup tasks with Task Scheduler:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_windows_startup.ps1
```

This registers two Scheduled Tasks for the current Windows user:

- `StarMap Backend`
- `StarMap Frontend`

They start automatically the next time that user logs in to Windows, and the installer also starts them immediately once. Windows startup uses dedicated PowerShell scripts and does not interfere with the macOS `launchd` setup.

Windows startup scripts prefer these Python locations in order:

1. `backend\.venv\Scripts\python.exe`
2. `py -3`
3. `python`

Logs are written to the same repo-local files:

- `logs/backend.stdout.log`
- `logs/backend.stderr.log`
- `logs/frontend.stdout.log`
- `logs/frontend.stderr.log`

## Configuration

Runtime configuration is read from the project-level `.env` file. Common variables include:

- `STARMAP_LLM_PROVIDER`
- `STARMAP_LLM_API_KEY`
- `STARMAP_OPENALEX_API_KEY`
- `STARMAP_CONTACT_EMAIL`
- `STARMAP_ZOTERO_USER_ID`
- `STARMAP_ZOTERO_API_KEY`
- `STARMAP_ZOTERO_COLLECTION_KEY`

The backend reads these values so API keys do not need to be exposed directly in the browser.

## Recommended Usage Pattern

StarMap is most effective when the repository stays selective. A good default pattern is:

1. define the target clearly
2. import a focused seed set
3. curate `Top Related Papers`
4. identify `Core` papers
5. inspect the library in `Workspace Atlas`
6. run `Semantic Cluster` or `Citation Cluster` when structure matters
7. audit metadata quality in `Repository Analytics`
8. keep the frontier current with `Project Literature Watch`

This leads to a cleaner and more thesis-relevant repository than bulk-importing first and trying to clean it later.
