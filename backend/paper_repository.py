from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence

MAX_TOP_PAPERS = 500
MAX_PAPER_TITLE_LENGTH = 500
MAX_PAPER_ABSTRACT_LENGTH = 30000
MAX_PAPER_CURRENT_CONTENT_LENGTH = 10000
MAX_PAPER_NOTES_LENGTH = 20000
MAX_PAPER_AUTHORS_LENGTH = 1200

EMBEDDING_VERSION = "v2"
EMBEDDING_SCOPE = "network_graph"

PROJECT_PAPER_COLUMNS = (
    "filename",
    "title",
    "abstract",
    "authors",
    "year",
    "similarity",
    "status",
    "notes",
    "favorite",
    "is_new",
    "doi",
    "paper_url",
    "source_url",
    "publication_venue",
    "citation_count",
    "fwci",
    "arxiv_id",
    "openalex_id",
    "openalex_cited_by_api_url",
    "crossref_url",
    "import_source",
    "import_batch_id",
    "import_batch_started_at",
    "analysis_ready",
    "metadata_only",
    "zotero_item_key",
    "zotero_has_pdf_attachment",
    "zotero_has_fulltext",
    "citation_key",
    "similarity_pending",
    "citation_cluster_id",
    "citation_cluster_theme_name",
    "citation_cluster_theme_summary",
    "citation_cluster_indegree",
    "citation_cluster_core_rank",
    "citation_cluster_is_core",
    "citation_cluster_size",
    "citation_cluster_graph_signature",
    "citation_cluster_version",
)

PATCHABLE_FIELDS = set(PROJECT_PAPER_COLUMNS) | {"current_content", "network_vec", "referenced_openalex_ids"}

PROJECT_PAPER_COLUMN_DEFINITIONS = {
    "filename": "TEXT NOT NULL DEFAULT ''",
    "title": "TEXT NOT NULL DEFAULT ''",
    "abstract": "TEXT NOT NULL DEFAULT 'Unknown'",
    "authors": "TEXT NOT NULL DEFAULT 'Unknown'",
    "year": "TEXT NOT NULL DEFAULT 'Unknown'",
    "similarity": "REAL NOT NULL DEFAULT 0",
    "status": "TEXT NOT NULL DEFAULT 'Unread'",
    "notes": "TEXT NOT NULL DEFAULT ''",
    "favorite": "INTEGER NOT NULL DEFAULT 0",
    "is_new": "INTEGER NOT NULL DEFAULT 0",
    "doi": "TEXT NOT NULL DEFAULT ''",
    "paper_url": "TEXT NOT NULL DEFAULT ''",
    "source_url": "TEXT NOT NULL DEFAULT ''",
    "publication_venue": "TEXT NOT NULL DEFAULT ''",
    "citation_count": "INTEGER",
    "fwci": "REAL",
    "arxiv_id": "TEXT NOT NULL DEFAULT ''",
    "openalex_id": "TEXT NOT NULL DEFAULT ''",
    "openalex_cited_by_api_url": "TEXT NOT NULL DEFAULT ''",
    "crossref_url": "TEXT NOT NULL DEFAULT ''",
    "import_source": "TEXT NOT NULL DEFAULT 'local_pdf'",
    "import_batch_id": "TEXT NOT NULL DEFAULT ''",
    "import_batch_started_at": "INTEGER",
    "analysis_ready": "INTEGER NOT NULL DEFAULT 1",
    "metadata_only": "INTEGER NOT NULL DEFAULT 0",
    "zotero_item_key": "TEXT NOT NULL DEFAULT ''",
    "zotero_has_pdf_attachment": "INTEGER NOT NULL DEFAULT 0",
    "zotero_has_fulltext": "INTEGER NOT NULL DEFAULT 0",
    "citation_key": "TEXT NOT NULL DEFAULT ''",
    "similarity_pending": "INTEGER NOT NULL DEFAULT 0",
    "citation_cluster_id": "TEXT NOT NULL DEFAULT ''",
    "citation_cluster_theme_name": "TEXT NOT NULL DEFAULT ''",
    "citation_cluster_theme_summary": "TEXT NOT NULL DEFAULT ''",
    "citation_cluster_indegree": "INTEGER",
    "citation_cluster_core_rank": "INTEGER",
    "citation_cluster_is_core": "INTEGER NOT NULL DEFAULT 0",
    "citation_cluster_size": "INTEGER",
    "citation_cluster_graph_signature": "TEXT NOT NULL DEFAULT ''",
    "citation_cluster_version": "TEXT NOT NULL DEFAULT ''",
}


def _now_ts() -> int:
    return int(time.time())


def _trim_text(value: Any, max_length: int) -> str:
    return str(value or "").strip()[:max_length]


def _normalize_current_content(value: Any) -> str:
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _coerce_optional_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except Exception:
        return default


def _clean_doi(value: Any) -> str:
    return str(value or "").replace("https://doi.org/", "").replace("http://doi.org/", "").replace("https://dx.doi.org/", "").replace("http://dx.doi.org/", "").strip().lower().removeprefix("doi:").strip()


def _normalize_title(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _scrub_references(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    cleaned: List[str] = []
    seen = set()
    for raw in values:
        value = _trim_text(raw, 300)
        if not value or value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned[:500]


def _scrub_network_vec(value: Any) -> Optional[List[float]]:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    cleaned: List[float] = []
    for item in value:
        try:
            cleaned.append(float(item))
        except Exception:
            cleaned.append(0.0)
    return cleaned or None


def _build_citation_key(paper: Dict[str, Any]) -> str:
    title = _normalize_title(paper.get("title"))
    if not title:
        return ""
    year = _trim_text(paper.get("year"), 40)
    first_word = re.sub(r"[^a-z0-9]+", "", title.split(" ", 1)[0])[:24]
    return f"{first_word}{year}".strip()


def scrub_paper_dict(paper: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(paper or {})
    abstract = _trim_text(cleaned.get("abstract"), MAX_PAPER_ABSTRACT_LENGTH)
    current_content = _trim_text(_normalize_current_content(cleaned.get("current_content")), MAX_PAPER_CURRENT_CONTENT_LENGTH)
    analysis_ready = bool(abstract and abstract.lower() != "unknown")

    result = {
        "id": _coerce_optional_int(cleaned.get("id")),
        "filename": _trim_text(cleaned.get("filename"), 300),
        "title": _trim_text(cleaned.get("title"), MAX_PAPER_TITLE_LENGTH),
        "abstract": abstract or "Unknown",
        "current_content": current_content,
        "authors": _trim_text(cleaned.get("authors"), MAX_PAPER_AUTHORS_LENGTH) or "Unknown",
        "year": _trim_text(cleaned.get("year"), 40) or "Unknown",
        "similarity": _coerce_optional_float(cleaned.get("similarity"), 0.0) or 0.0,
        "status": _trim_text(cleaned.get("status"), 80) or "Unread",
        "notes": _trim_text(cleaned.get("notes"), MAX_PAPER_NOTES_LENGTH),
        "favorite": _coerce_bool(cleaned.get("favorite")),
        "is_new": _coerce_bool(cleaned.get("is_new")),
        "doi": _trim_text(cleaned.get("doi"), 300),
        "paper_url": _trim_text(cleaned.get("paper_url"), 1200),
        "source_url": _trim_text(cleaned.get("source_url"), 1200),
        "publication_venue": _trim_text(cleaned.get("publication_venue"), 300),
        "citation_count": _coerce_optional_int(cleaned.get("citation_count")),
        "fwci": _coerce_optional_float(cleaned.get("fwci")),
        "arxiv_id": _trim_text(cleaned.get("arxiv_id"), 200),
        "openalex_id": _trim_text(cleaned.get("openalex_id"), 300),
        "openalex_cited_by_api_url": _trim_text(cleaned.get("openalex_cited_by_api_url"), 1200),
        "crossref_url": _trim_text(cleaned.get("crossref_url"), 1200),
        "referenced_openalex_ids": _scrub_references(cleaned.get("referenced_openalex_ids")),
        "source_url": _trim_text(cleaned.get("source_url"), 1200),
        "import_source": _trim_text(cleaned.get("import_source"), 40) or "local_pdf",
        "import_batch_id": _trim_text(cleaned.get("import_batch_id"), 120),
        "import_batch_started_at": _coerce_optional_int(cleaned.get("import_batch_started_at")),
        "analysis_ready": _coerce_bool(cleaned.get("analysis_ready"), analysis_ready),
        "metadata_only": _coerce_bool(cleaned.get("metadata_only"), not analysis_ready),
        "zotero_item_key": _trim_text(cleaned.get("zotero_item_key"), 120),
        "zotero_has_pdf_attachment": _coerce_bool(cleaned.get("zotero_has_pdf_attachment")),
        "zotero_has_fulltext": _coerce_bool(cleaned.get("zotero_has_fulltext")),
        "citation_key": _trim_text(cleaned.get("citation_key"), 120),
        "similarity_pending": _coerce_bool(cleaned.get("similarity_pending")),
        "network_vec": _scrub_network_vec(cleaned.get("network_vec")),
        "citation_cluster_id": _trim_text(cleaned.get("citation_cluster_id"), 120),
        "citation_cluster_theme_name": _trim_text(cleaned.get("citation_cluster_theme_name"), 300),
        "citation_cluster_theme_summary": _trim_text(cleaned.get("citation_cluster_theme_summary"), 4000),
        "citation_cluster_indegree": _coerce_optional_int(cleaned.get("citation_cluster_indegree")),
        "citation_cluster_core_rank": _coerce_optional_int(cleaned.get("citation_cluster_core_rank")),
        "citation_cluster_is_core": _coerce_bool(cleaned.get("citation_cluster_is_core")),
        "citation_cluster_size": _coerce_optional_int(cleaned.get("citation_cluster_size")),
        "citation_cluster_graph_signature": _trim_text(cleaned.get("citation_cluster_graph_signature"), 240),
        "citation_cluster_version": _trim_text(cleaned.get("citation_cluster_version"), 120),
    }
    if not result["citation_key"]:
        result["citation_key"] = _build_citation_key(result)
    return result


def scrub_top_papers_json(raw_value: Any) -> str:
    if not raw_value:
        return "[]"
    try:
        papers = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    except Exception:
        return "[]"
    if not isinstance(papers, list):
        return "[]"
    return json.dumps([scrub_paper_dict(paper) for paper in papers if isinstance(paper, dict)], ensure_ascii=False)


def scrub_paper_patch(changes: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for key, value in dict(changes or {}).items():
        if key not in PATCHABLE_FIELDS:
            continue
        if key == "filename":
            sanitized[key] = _trim_text(value, 300)
        elif key == "title":
            sanitized[key] = _trim_text(value, MAX_PAPER_TITLE_LENGTH)
        elif key == "abstract":
            sanitized[key] = _trim_text(value, MAX_PAPER_ABSTRACT_LENGTH) or "Unknown"
        elif key == "current_content":
            sanitized[key] = _trim_text(_normalize_current_content(value), MAX_PAPER_CURRENT_CONTENT_LENGTH)
        elif key == "authors":
            sanitized[key] = _trim_text(value, MAX_PAPER_AUTHORS_LENGTH) or "Unknown"
        elif key == "year":
            sanitized[key] = _trim_text(value, 40) or "Unknown"
        elif key == "similarity":
            sanitized[key] = _coerce_optional_float(value, 0.0) or 0.0
        elif key == "status":
            sanitized[key] = _trim_text(value, 80) or "Unread"
        elif key == "notes":
            sanitized[key] = _trim_text(value, MAX_PAPER_NOTES_LENGTH)
        elif key in {"favorite", "is_new", "analysis_ready", "metadata_only", "zotero_has_pdf_attachment", "zotero_has_fulltext", "similarity_pending", "citation_cluster_is_core"}:
            sanitized[key] = _coerce_bool(value)
        elif key in {"citation_count", "import_batch_started_at", "citation_cluster_indegree", "citation_cluster_core_rank", "citation_cluster_size"}:
            sanitized[key] = _coerce_optional_int(value)
        elif key in {"fwci"}:
            sanitized[key] = _coerce_optional_float(value)
        elif key in {"doi"}:
            sanitized[key] = _trim_text(value, 300)
        elif key in {"paper_url", "source_url", "openalex_cited_by_api_url", "crossref_url"}:
            sanitized[key] = _trim_text(value, 1200)
        elif key in {"publication_venue", "citation_cluster_theme_name"}:
            sanitized[key] = _trim_text(value, 300)
        elif key in {"arxiv_id"}:
            sanitized[key] = _trim_text(value, 200)
        elif key in {"openalex_id"}:
            sanitized[key] = _trim_text(value, 300)
        elif key in {"import_source"}:
            sanitized[key] = _trim_text(value, 40) or "local_pdf"
        elif key in {"import_batch_id", "zotero_item_key", "citation_key", "citation_cluster_id", "citation_cluster_version"}:
            sanitized[key] = _trim_text(value, 120)
        elif key in {"citation_cluster_theme_summary"}:
            sanitized[key] = _trim_text(value, 4000)
        elif key in {"citation_cluster_graph_signature"}:
            sanitized[key] = _trim_text(value, 240)
        elif key == "network_vec":
            sanitized[key] = _scrub_network_vec(value)
        elif key == "referenced_openalex_ids":
            sanitized[key] = _scrub_references(value)
    if "citation_key" in sanitized and not sanitized["citation_key"]:
        title_value = changes.get("title")
        year_value = changes.get("year")
        sanitized["citation_key"] = _build_citation_key({"title": title_value, "year": year_value})
    return sanitized


def _fetchall_dicts(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
    columns = [column[0] for column in cursor.description or []]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _fetchone_dict(cursor: sqlite3.Cursor) -> Optional[Dict[str, Any]]:
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [column[0] for column in cursor.description or []]
    return dict(zip(columns, row))


class PaperRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ensure_schema(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS project_papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                filename TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                abstract TEXT NOT NULL DEFAULT 'Unknown',
                authors TEXT NOT NULL DEFAULT 'Unknown',
                year TEXT NOT NULL DEFAULT 'Unknown',
                similarity REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Unread',
                notes TEXT NOT NULL DEFAULT '',
                favorite INTEGER NOT NULL DEFAULT 0,
                is_new INTEGER NOT NULL DEFAULT 0,
                doi TEXT NOT NULL DEFAULT '',
                paper_url TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                publication_venue TEXT NOT NULL DEFAULT '',
                citation_count INTEGER,
                fwci REAL,
                arxiv_id TEXT NOT NULL DEFAULT '',
                openalex_id TEXT NOT NULL DEFAULT '',
                openalex_cited_by_api_url TEXT NOT NULL DEFAULT '',
                crossref_url TEXT NOT NULL DEFAULT '',
                import_source TEXT NOT NULL DEFAULT 'local_pdf',
                import_batch_id TEXT NOT NULL DEFAULT '',
                import_batch_started_at INTEGER,
                analysis_ready INTEGER NOT NULL DEFAULT 1,
                metadata_only INTEGER NOT NULL DEFAULT 0,
                zotero_item_key TEXT NOT NULL DEFAULT '',
                zotero_has_pdf_attachment INTEGER NOT NULL DEFAULT 0,
                zotero_has_fulltext INTEGER NOT NULL DEFAULT 0,
                citation_key TEXT NOT NULL DEFAULT '',
                similarity_pending INTEGER NOT NULL DEFAULT 0,
                citation_cluster_id TEXT NOT NULL DEFAULT '',
                citation_cluster_theme_name TEXT NOT NULL DEFAULT '',
                citation_cluster_theme_summary TEXT NOT NULL DEFAULT '',
                citation_cluster_indegree INTEGER,
                citation_cluster_core_rank INTEGER,
                citation_cluster_is_core INTEGER NOT NULL DEFAULT 0,
                citation_cluster_size INTEGER,
                citation_cluster_graph_signature TEXT NOT NULL DEFAULT '',
                citation_cluster_version TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )"""
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS project_paper_contents (
                project_paper_id INTEGER PRIMARY KEY,
                current_content TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (project_paper_id) REFERENCES project_papers (id)
            )"""
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS project_paper_embeddings (
                project_paper_id INTEGER PRIMARY KEY,
                network_vec_json TEXT NOT NULL DEFAULT '',
                embedding_version TEXT NOT NULL DEFAULT '',
                embedding_scope TEXT NOT NULL DEFAULT '',
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (project_paper_id) REFERENCES project_papers (id)
            )"""
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS project_paper_references (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_paper_id INTEGER NOT NULL,
                referenced_openalex_id TEXT NOT NULL,
                FOREIGN KEY (project_paper_id) REFERENCES project_papers (id)
            )"""
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS project_paper_migration_state (
                project_id INTEGER PRIMARY KEY,
                legacy_blob_sha1 TEXT NOT NULL DEFAULT '',
                migrated_at INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )"""
        )
        self._ensure_table_columns(cursor, "project_papers", PROJECT_PAPER_COLUMN_DEFINITIONS)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_papers_project_id ON project_papers (project_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_papers_similarity ON project_papers (project_id, similarity DESC, id ASC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_papers_openalex ON project_papers (project_id, openalex_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_papers_zotero ON project_papers (project_id, zotero_item_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_papers_doi ON project_papers (project_id, doi)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_project_paper_references_unique ON project_paper_references (project_paper_id, referenced_openalex_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_paper_references_paper_id ON project_paper_references (project_paper_id)")

    def migrate_all_projects_from_legacy_blob(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, top_papers FROM projects ORDER BY id")
        for project_id, top_papers in cursor.fetchall():
            self.migrate_project_from_legacy_blob(int(project_id), top_papers)

    def migrate_project_from_legacy_blob(self, project_id: int, raw_blob: Any) -> bool:
        scrubbed = scrub_top_papers_json(raw_blob)
        source_hash = hashlib.sha1(scrubbed.encode("utf-8")).hexdigest()
        cursor = self.conn.cursor()
        cursor.execute("SELECT legacy_blob_sha1 FROM project_paper_migration_state WHERE project_id = ?", (project_id,))
        row = cursor.fetchone()
        if row and row[0] == source_hash:
            return False
        papers = json.loads(scrubbed)
        self.replace_project_papers(project_id, papers)
        cursor.execute(
            "INSERT INTO project_paper_migration_state (project_id, legacy_blob_sha1, migrated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(project_id) DO UPDATE SET legacy_blob_sha1 = excluded.legacy_blob_sha1, migrated_at = excluded.migrated_at",
            (project_id, source_hash, _now_ts())
        )
        return True

    def list_project_papers(self, project_id: int) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, project_id, created_at, updated_at, " + ", ".join(PROJECT_PAPER_COLUMNS) +
            " FROM project_papers WHERE project_id = ? ORDER BY similarity DESC, id ASC",
            (project_id,)
        )
        papers = _fetchall_dicts(cursor)
        return self._hydrate_papers(papers)

    def get_project_paper(self, project_id: int, paper_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, project_id, created_at, updated_at, " + ", ".join(PROJECT_PAPER_COLUMNS) +
            " FROM project_papers WHERE project_id = ? AND id = ?",
            (project_id, paper_id)
        )
        row = _fetchone_dict(cursor)
        if not row:
            return None
        hydrated = self._hydrate_papers([row])
        return hydrated[0] if hydrated else None

    def replace_project_papers(self, project_id: int, papers: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sanitized = [scrub_paper_dict(paper) for paper in list(papers or [])[:MAX_TOP_PAPERS]]
        existing = self.list_project_papers(project_id)
        existing_map = {int(paper["id"]): paper for paper in existing if paper.get("id") is not None}
        seen_ids = set()
        resolved_papers: List[Dict[str, Any]] = []
        for paper in sanitized:
            matched = None
            requested_id = _coerce_optional_int(paper.get("id"))
            if requested_id and requested_id in existing_map:
                matched = existing_map[requested_id]
            if matched is None:
                matched = self._find_matching_paper(existing, paper, exclude_ids=seen_ids)
            if matched:
                paper["id"] = matched["id"]
                seen_ids.add(int(matched["id"]))
            resolved_papers.append(paper)

        incoming_ids = {
            int(paper["id"])
            for paper in resolved_papers
            if _coerce_optional_int(paper.get("id")) is not None
        }
        to_delete = [paper["id"] for paper in existing if int(paper["id"]) not in incoming_ids]
        if to_delete:
            self._delete_project_papers_by_ids(project_id, to_delete)
        self._upsert_project_papers(project_id, resolved_papers)
        return self.list_project_papers(project_id)

    def merge_project_papers(self, project_id: int, new_papers: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("UPDATE project_papers SET is_new = 0, updated_at = ? WHERE project_id = ?", (_now_ts(), project_id))
        touched = self._upsert_project_papers(
            project_id,
            [{**scrub_paper_dict(paper), "is_new": True} for paper in list(new_papers or [])[:MAX_TOP_PAPERS]]
        )
        self._trim_project_papers(project_id, {int(paper["id"]) for paper in touched})
        return self.list_project_papers(project_id)

    def upsert_project_papers(self, project_id: int, papers: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self._upsert_project_papers(project_id, [scrub_paper_dict(paper) for paper in list(papers or [])[:MAX_TOP_PAPERS]])
        return self.list_project_papers(project_id)

    def patch_project_paper(self, project_id: int, paper_id: int, changes: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = scrub_paper_patch(changes)
        if not sanitized:
            paper = self.get_project_paper(project_id, paper_id)
            if not paper:
                raise KeyError("paper_not_found")
            return paper
        self._apply_patch(project_id, paper_id, sanitized)
        paper = self.get_project_paper(project_id, paper_id)
        if not paper:
            raise KeyError("paper_not_found")
        return paper

    def batch_patch_project_papers(self, project_id: int, patches: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        updated: List[Dict[str, Any]] = []
        for patch in patches or []:
            paper_id = _coerce_optional_int((patch or {}).get("id"))
            if not paper_id:
                continue
            updated.append(self.patch_project_paper(project_id, paper_id, (patch or {}).get("changes") or {}))
        return updated

    def delete_project_paper(self, project_id: int, paper_id: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM project_papers WHERE project_id = ? AND id = ?", (project_id, paper_id))
        if not cursor.fetchone():
            return False
        self._delete_project_papers_by_ids(project_id, [paper_id])
        return True

    def clear_project_papers(self, project_id: int) -> None:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM project_papers WHERE project_id = ?", (project_id,))
        ids = [int(row[0]) for row in cursor.fetchall()]
        if ids:
            self._delete_project_papers_by_ids(project_id, ids)

    def delete_project_data(self, project_id: int) -> None:
        self.clear_project_papers(project_id)
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM project_paper_migration_state WHERE project_id = ?", (project_id,))

    def _ensure_table_columns(self, cursor: sqlite3.Cursor, table_name: str, definitions: Dict[str, str]) -> None:
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}
        for column_name, definition in definitions.items():
            if column_name not in existing_columns:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def _hydrate_papers(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not papers:
            return []
        paper_ids = [int(paper["id"]) for paper in papers]
        id_placeholders = ",".join("?" for _ in paper_ids)
        cursor = self.conn.cursor()

        content_by_id: Dict[int, str] = {}
        cursor.execute(
            f"SELECT project_paper_id, current_content FROM project_paper_contents WHERE project_paper_id IN ({id_placeholders})",
            paper_ids
        )
        for project_paper_id, current_content in cursor.fetchall():
            content_by_id[int(project_paper_id)] = str(current_content or "")

        embedding_by_id: Dict[int, Dict[str, Any]] = {}
        cursor.execute(
            f"SELECT project_paper_id, network_vec_json, embedding_version, embedding_scope FROM project_paper_embeddings WHERE project_paper_id IN ({id_placeholders})",
            paper_ids
        )
        for project_paper_id, network_vec_json, embedding_version, embedding_scope in cursor.fetchall():
            try:
                embedding_by_id[int(project_paper_id)] = {
                    "vector": json.loads(network_vec_json) if network_vec_json else None,
                    "embedding_version": str(embedding_version or ""),
                    "embedding_scope": str(embedding_scope or ""),
                }
            except Exception:
                embedding_by_id[int(project_paper_id)] = {
                    "vector": None,
                    "embedding_version": str(embedding_version or ""),
                    "embedding_scope": str(embedding_scope or ""),
                }

        references_by_id: Dict[int, List[str]] = {paper_id: [] for paper_id in paper_ids}
        cursor.execute(
            f"SELECT project_paper_id, referenced_openalex_id FROM project_paper_references WHERE project_paper_id IN ({id_placeholders}) ORDER BY id ASC",
            paper_ids
        )
        for project_paper_id, referenced_openalex_id in cursor.fetchall():
            references_by_id.setdefault(int(project_paper_id), []).append(str(referenced_openalex_id or ""))

        for paper in papers:
            paper_id = int(paper["id"])
            paper["favorite"] = bool(paper.get("favorite"))
            paper["is_new"] = bool(paper.get("is_new"))
            paper["analysis_ready"] = bool(paper.get("analysis_ready"))
            paper["metadata_only"] = bool(paper.get("metadata_only"))
            paper["zotero_has_pdf_attachment"] = bool(paper.get("zotero_has_pdf_attachment"))
            paper["zotero_has_fulltext"] = bool(paper.get("zotero_has_fulltext"))
            paper["similarity_pending"] = bool(paper.get("similarity_pending"))
            paper["citation_cluster_is_core"] = bool(paper.get("citation_cluster_is_core"))
            paper["current_content"] = content_by_id.get(paper_id, "")
            embedding_record = embedding_by_id.get(paper_id) or {}
            paper["network_vec"] = embedding_record.get("vector")
            paper["network_vec_embedding_scope"] = embedding_record.get("embedding_scope", "")
            paper["network_vec_embedding_version"] = embedding_record.get("embedding_version", "")
            paper["referenced_openalex_ids"] = references_by_id.get(paper_id, [])
        return papers

    def _find_matching_paper(self, existing_papers: Iterable[Dict[str, Any]], candidate: Dict[str, Any], exclude_ids: Optional[set] = None) -> Optional[Dict[str, Any]]:
        exclude_ids = exclude_ids or set()
        candidate_zotero = _trim_text(candidate.get("zotero_item_key"), 120)
        candidate_openalex = _trim_text(candidate.get("openalex_id"), 300)
        candidate_doi = _clean_doi(candidate.get("doi"))
        candidate_title = _normalize_title(candidate.get("title"))

        for paper in existing_papers:
            paper_id = int(paper["id"])
            if paper_id in exclude_ids:
                continue
            if candidate_zotero and candidate_zotero == _trim_text(paper.get("zotero_item_key"), 120):
                return paper
        for paper in existing_papers:
            paper_id = int(paper["id"])
            if paper_id in exclude_ids:
                continue
            if candidate_openalex and candidate_openalex == _trim_text(paper.get("openalex_id"), 300):
                return paper
        for paper in existing_papers:
            paper_id = int(paper["id"])
            if paper_id in exclude_ids:
                continue
            if candidate_doi and candidate_doi == _clean_doi(paper.get("doi")):
                return paper
        for paper in existing_papers:
            paper_id = int(paper["id"])
            if paper_id in exclude_ids:
                continue
            if candidate_title and candidate_title == _normalize_title(paper.get("title")):
                return paper
        return None

    def _upsert_project_papers(self, project_id: int, papers: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        existing = self.list_project_papers(project_id)
        existing_map = {int(paper["id"]): paper for paper in existing}
        touched_ids: List[int] = []
        for paper in papers:
            requested_id = _coerce_optional_int(paper.get("id"))
            matched = existing_map.get(requested_id) if requested_id else None
            if matched is None:
                matched = self._find_matching_paper(existing_map.values(), paper)
            if matched:
                paper_id = int(matched["id"])
                self._update_project_paper_row(project_id, paper_id, paper)
            else:
                paper_id = self._insert_project_paper_row(project_id, paper)
            paper["id"] = paper_id
            existing_map[paper_id] = {**paper, "id": paper_id}
            touched_ids.append(paper_id)
        return [paper for paper in self.list_project_papers(project_id) if int(paper["id"]) in set(touched_ids)]

    def _insert_project_paper_row(self, project_id: int, paper: Dict[str, Any]) -> int:
        cursor = self.conn.cursor()
        now = _now_ts()
        values = [project_id] + [paper.get(column) for column in PROJECT_PAPER_COLUMNS] + [now, now]
        cursor.execute(
            "INSERT INTO project_papers (project_id, " + ", ".join(PROJECT_PAPER_COLUMNS) + ", created_at, updated_at) VALUES (" +
            ",".join("?" for _ in range(len(values))) + ")",
            values
        )
        paper_id = int(cursor.lastrowid)
        self._write_content_embedding_and_references(paper_id, paper)
        return paper_id

    def _update_project_paper_row(self, project_id: int, paper_id: int, paper: Dict[str, Any]) -> None:
        cursor = self.conn.cursor()
        assignments = ", ".join(f"{column} = ?" for column in PROJECT_PAPER_COLUMNS)
        values = [paper.get(column) for column in PROJECT_PAPER_COLUMNS] + [_now_ts(), project_id, paper_id]
        cursor.execute(
            f"UPDATE project_papers SET {assignments}, updated_at = ? WHERE project_id = ? AND id = ?",
            values
        )
        self._write_content_embedding_and_references(paper_id, paper)

    def _write_content_embedding_and_references(self, paper_id: int, paper: Dict[str, Any]) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO project_paper_contents (project_paper_id, current_content) VALUES (?, ?) "
            "ON CONFLICT(project_paper_id) DO UPDATE SET current_content = excluded.current_content",
            (paper_id, paper.get("current_content") or "")
        )
        network_vec = paper.get("network_vec")
        if network_vec:
            cursor.execute(
                "INSERT INTO project_paper_embeddings (project_paper_id, network_vec_json, embedding_version, embedding_scope, updated_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(project_paper_id) DO UPDATE SET network_vec_json = excluded.network_vec_json, embedding_version = excluded.embedding_version, embedding_scope = excluded.embedding_scope, updated_at = excluded.updated_at",
                (paper_id, json.dumps(network_vec), EMBEDDING_VERSION, EMBEDDING_SCOPE, _now_ts())
            )
        else:
            cursor.execute("DELETE FROM project_paper_embeddings WHERE project_paper_id = ?", (paper_id,))
        cursor.execute("DELETE FROM project_paper_references WHERE project_paper_id = ?", (paper_id,))
        references = _scrub_references(paper.get("referenced_openalex_ids"))
        if references:
            cursor.executemany(
                "INSERT INTO project_paper_references (project_paper_id, referenced_openalex_id) VALUES (?, ?)",
                [(paper_id, reference_id) for reference_id in references]
            )

    def _apply_patch(self, project_id: int, paper_id: int, changes: Dict[str, Any]) -> None:
        cursor = self.conn.cursor()
        main_updates = {key: value for key, value in changes.items() if key in PROJECT_PAPER_COLUMNS}
        if "abstract" in main_updates and "analysis_ready" not in main_updates:
            main_updates["analysis_ready"] = bool(main_updates["abstract"] and str(main_updates["abstract"]).lower() != "unknown")
        if "analysis_ready" in main_updates and "metadata_only" not in main_updates:
            main_updates["metadata_only"] = not bool(main_updates["analysis_ready"])
        if {"title", "year"} & set(main_updates.keys()) and not _trim_text(main_updates.get("citation_key"), 120):
            cursor.execute("SELECT title, year, citation_key FROM project_papers WHERE project_id = ? AND id = ?", (project_id, paper_id))
            current = _fetchone_dict(cursor)
            if not current:
                raise KeyError("paper_not_found")
            if "citation_key" not in main_updates:
                main_updates["citation_key"] = _build_citation_key({
                    "title": main_updates.get("title", current.get("title")),
                    "year": main_updates.get("year", current.get("year")),
                }) or current.get("citation_key") or ""
        if main_updates:
            assignments = ", ".join(f"{column} = ?" for column in main_updates.keys())
            values = list(main_updates.values()) + [_now_ts(), project_id, paper_id]
            cursor.execute(
                f"UPDATE project_papers SET {assignments}, updated_at = ? WHERE project_id = ? AND id = ?",
                values
            )
            if cursor.rowcount <= 0:
                raise KeyError("paper_not_found")
        elif not self.get_project_paper(project_id, paper_id):
            raise KeyError("paper_not_found")

        if "current_content" in changes:
            cursor.execute(
                "INSERT INTO project_paper_contents (project_paper_id, current_content) VALUES (?, ?) "
                "ON CONFLICT(project_paper_id) DO UPDATE SET current_content = excluded.current_content",
                (paper_id, changes.get("current_content") or "")
            )
        if "network_vec" in changes:
            network_vec = changes.get("network_vec")
            if network_vec:
                cursor.execute(
                    "INSERT INTO project_paper_embeddings (project_paper_id, network_vec_json, embedding_version, embedding_scope, updated_at) VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(project_paper_id) DO UPDATE SET network_vec_json = excluded.network_vec_json, embedding_version = excluded.embedding_version, embedding_scope = excluded.embedding_scope, updated_at = excluded.updated_at",
                    (paper_id, json.dumps(network_vec), EMBEDDING_VERSION, EMBEDDING_SCOPE, _now_ts())
                )
            else:
                cursor.execute("DELETE FROM project_paper_embeddings WHERE project_paper_id = ?", (paper_id,))
        if "referenced_openalex_ids" in changes:
            cursor.execute("DELETE FROM project_paper_references WHERE project_paper_id = ?", (paper_id,))
            references = _scrub_references(changes.get("referenced_openalex_ids"))
            if references:
                cursor.executemany(
                    "INSERT INTO project_paper_references (project_paper_id, referenced_openalex_id) VALUES (?, ?)",
                    [(paper_id, reference_id) for reference_id in references]
                )

    def _trim_project_papers(self, project_id: int, protected_ids: set[int]) -> None:
        papers = self.list_project_papers(project_id)
        if len(papers) <= MAX_TOP_PAPERS:
            return
        protected = [paper for paper in papers if int(paper["id"]) in protected_ids]
        remainder = [paper for paper in papers if int(paper["id"]) not in protected_ids]
        kept = (protected + remainder)[:MAX_TOP_PAPERS]
        kept_ids = {int(paper["id"]) for paper in kept}
        to_delete = [int(paper["id"]) for paper in papers if int(paper["id"]) not in kept_ids]
        if to_delete:
            self._delete_project_papers_by_ids(project_id, to_delete)

    def _delete_project_papers_by_ids(self, project_id: int, paper_ids: Sequence[int]) -> None:
        if not paper_ids:
            return
        cursor = self.conn.cursor()
        placeholders = ",".join("?" for _ in paper_ids)
        params = [project_id] + list(paper_ids)
        cursor.execute(
            f"DELETE FROM project_paper_references WHERE project_paper_id IN (SELECT id FROM project_papers WHERE project_id = ? AND id IN ({placeholders}))",
            params
        )
        cursor.execute(
            f"DELETE FROM project_paper_embeddings WHERE project_paper_id IN (SELECT id FROM project_papers WHERE project_id = ? AND id IN ({placeholders}))",
            params
        )
        cursor.execute(
            f"DELETE FROM project_paper_contents WHERE project_paper_id IN (SELECT id FROM project_papers WHERE project_id = ? AND id IN ({placeholders}))",
            params
        )
        cursor.execute(
            f"DELETE FROM project_papers WHERE project_id = ? AND id IN ({placeholders})",
            params
        )
