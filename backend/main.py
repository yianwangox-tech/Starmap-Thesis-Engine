from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import asyncio
import sqlite3
import json
import re
import uuid
import time
import secrets
import hashlib
import hmac
from urllib import error, parse, request

app = FastAPI(title="StarMap Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "database.db"
CITATION_GRAPH_JOBS: Dict[str, dict] = {}
PROJECT_TASK_LOCKS: Dict[str, asyncio.Lock] = {}
SESSION_TTL_SECONDS = 60 * 60 * 24 * 14
PBKDF2_ITERATIONS = 120_000
MAX_PROJECT_NAME_LENGTH = 120
MAX_TARGET_TITLE_LENGTH = 300
MAX_TARGET_KEYWORDS_LENGTH = 5000
MAX_TARGET_ABSTRACT_LENGTH = 20000
MAX_TARGET_CURRENT_CONTENT_LENGTH = 80000
MAX_TOP_PAPERS = 500
MAX_PAPER_TITLE_LENGTH = 500
MAX_PAPER_ABSTRACT_LENGTH = 30000
MAX_PAPER_NOTES_LENGTH = 20000
MAX_PAPER_AUTHORS_LENGTH = 1200
MAX_PAPER_KEYWORDS = 25
MAX_PAPER_KEYWORD_LENGTH = 120
MAX_LOOKUP_TITLE_LENGTH = 500
MAX_LOOKUP_AUTHORS_LENGTH = 800
MAX_LOOKUP_YEAR_LENGTH = 20
MAX_LOOKUP_EMAIL_LENGTH = 200

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, project_name TEXT NOT NULL, target_title TEXT, target_abstract TEXT, target_keywords TEXT, target_current_content TEXT, top_papers TEXT, FOREIGN KEY (user_id) REFERENCES users (id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, FOREIGN KEY (user_id) REFERENCES users (id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, project_id INTEGER, action TEXT NOT NULL, detail TEXT, success INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL)''')
    cursor.execute("PRAGMA table_info(projects)")
    project_columns = {row[1] for row in cursor.fetchall()}
    if "target_current_content" not in project_columns:
        cursor.execute("ALTER TABLE projects ADD COLUMN target_current_content TEXT DEFAULT ''")
    conn.commit()
    conn.close()

init_db()

def _db_connect(row_factory: bool = False):
    conn = sqlite3.connect(DB_FILE)
    if row_factory:
        conn.row_factory = sqlite3.Row
    return conn

def _now_ts() -> int:
    return int(time.time())

def _serialize_audit_detail(detail) -> str:
    if detail is None:
        return ""
    if isinstance(detail, str):
        return detail[:4000]
    return json.dumps(detail, ensure_ascii=False)[:4000]

def _write_audit_log(action: str, user_id: Optional[int] = None, project_id: Optional[int] = None, detail=None, success: bool = True):
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO audit_logs (user_id, project_id, action, detail, success, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, project_id, action, _serialize_audit_detail(detail), 1 if success else 0, _now_ts())
    )
    conn.commit()
    conn.close()

def _hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"

def _is_hashed_password(value: str) -> bool:
    return isinstance(value, str) and value.startswith("pbkdf2_sha256$")

def _verify_password(password: str, stored_value: str) -> bool:
    if not stored_value:
        return False
    if not _is_hashed_password(stored_value):
        return hmac.compare_digest(password, stored_value)
    try:
        _, iterations, salt, digest = stored_value.split("$", 3)
        computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)).hex()
        return hmac.compare_digest(computed, digest)
    except Exception:
        return False

def _create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = _now_ts()
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, now, now + SESSION_TTL_SECONDS)
    )
    conn.commit()
    conn.close()
    return token

def _trim_text(value: Optional[str], max_length: int) -> str:
    return str(value or "").strip()[:max_length]

def _validate_auth_payload(user):
    username = _trim_text(user.username, 120)
    password = str(user.password or "")
    if len(username) < 3:
        raise HTTPException(status_code=422, detail="Username must be at least 3 characters.")
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
    if len(password) > 200:
        raise HTTPException(status_code=422, detail="Password is too long.")
    return username, password

def _validate_project_fields(project_name: str, target_title: str, target_abstract: str, target_keywords: str, target_current_content: str):
    cleaned = {
        "project_name": _trim_text(project_name, MAX_PROJECT_NAME_LENGTH),
        "target_title": _trim_text(target_title, MAX_TARGET_TITLE_LENGTH),
        "target_abstract": _trim_text(target_abstract, MAX_TARGET_ABSTRACT_LENGTH),
        "target_keywords": _trim_text(target_keywords, MAX_TARGET_KEYWORDS_LENGTH),
        "target_current_content": _trim_text(target_current_content, MAX_TARGET_CURRENT_CONTENT_LENGTH)
    }
    if not cleaned["project_name"]:
        raise HTTPException(status_code=422, detail="Project name is required.")
    if not cleaned["target_title"]:
        raise HTTPException(status_code=422, detail="Target title is required.")
    return cleaned

def _validate_lookup_payload(payload):
    payload.title = _trim_text(payload.title, MAX_LOOKUP_TITLE_LENGTH)
    payload.doi = _trim_text(payload.doi, 300)
    payload.year = _trim_text(payload.year, MAX_LOOKUP_YEAR_LENGTH)
    payload.authors = _trim_text(payload.authors, MAX_LOOKUP_AUTHORS_LENGTH)
    payload.contact_email = _trim_text(payload.contact_email, MAX_LOOKUP_EMAIL_LENGTH)
    if not payload.title and not payload.doi:
        raise HTTPException(status_code=422, detail="A title or DOI is required for lookup.")

def _validate_paper_list(papers: List["PaperItem"]):
    if len(papers) > MAX_TOP_PAPERS:
        raise HTTPException(status_code=422, detail=f"Too many papers in a single request. Max {MAX_TOP_PAPERS}.")
    for paper in papers:
        paper.filename = _trim_text(paper.filename, 300)
        paper.title = _trim_text(paper.title, MAX_PAPER_TITLE_LENGTH)
        paper.abstract = _trim_text(paper.abstract, MAX_PAPER_ABSTRACT_LENGTH)
        paper.authors = _trim_text(paper.authors, MAX_PAPER_AUTHORS_LENGTH)
        paper.year = _trim_text(paper.year, 40)
        paper.notes = _trim_text(paper.notes, MAX_PAPER_NOTES_LENGTH)
        paper.doi = _trim_text(paper.doi, 300)
        paper.paper_url = _trim_text(paper.paper_url, 1200)
        paper.source_url = _trim_text(paper.source_url, 1200)
        paper.publication_venue = _trim_text(paper.publication_venue, 300)
        paper.arxiv_id = _trim_text(paper.arxiv_id, 200)
        paper.openalex_id = _trim_text(paper.openalex_id, 300)
        paper.openalex_cited_by_api_url = _trim_text(paper.openalex_cited_by_api_url, 1200)
        paper.crossref_url = _trim_text(paper.crossref_url, 1200)
        paper.import_source = _trim_text(paper.import_source, 40) or "local_pdf"
        paper.import_batch_id = _trim_text(paper.import_batch_id, 120)
        paper.keywords = [_trim_text(keyword, MAX_PAPER_KEYWORD_LENGTH) for keyword in (paper.keywords or []) if _trim_text(keyword, MAX_PAPER_KEYWORD_LENGTH)]
        paper.keywords = paper.keywords[:MAX_PAPER_KEYWORDS]
        if not paper.filename or not paper.title:
            raise HTTPException(status_code=422, detail="Every paper must include a filename and title.")

async def _require_session(request: Request):
    token = request.headers.get("X-Session-Token", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sessions.user_id, users.username, sessions.expires_at FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token = ?",
        (token,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Session not found.")
    if int(row["expires_at"]) < _now_ts():
        conn = _db_connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        raise HTTPException(status_code=401, detail="Session expired.")
    return {"token": token, "user_id": int(row["user_id"]), "username": row["username"]}

def _get_owned_project(project_id: int, user_id: int):
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found.")
    return dict(row)

async def _acquire_project_task_lock(project_id: int, task_name: str):
    key = f"{project_id}:{task_name}"
    lock = PROJECT_TASK_LOCKS.setdefault(key, asyncio.Lock())
    if lock.locked():
        raise HTTPException(status_code=409, detail=f"Another {task_name} task is already running for this project.")
    await lock.acquire()
    return lock

# --- 1. 数据模型升级 ---
class UserAuth(BaseModel):
    username: str
    password: str

class AccountUpdate(BaseModel):
    old_password: str
    new_username: str = ""
    new_password: str = ""
    
class PaperItem(BaseModel):
    filename: str
    title: str
    abstract: str
    keywords: List[str]
    authors: str = "Unknown"   
    year: str = "Unknown"      
    similarity: float
    is_new: bool = False
    favorite: bool = False        
    status: str = "Unread"        
    notes: str = ""    
    doi: str = ""
    paper_url: str = ""
    publication_venue: str = ""
    citation_count: Optional[int] = None
    fwci: Optional[float] = None
    arxiv_id: str = ""
    openalex_id: str = ""
    openalex_cited_by_api_url: str = ""
    crossref_url: str = ""
    referenced_openalex_ids: List[str] = Field(default_factory=list)
    source_url: str = ""
    import_source: str = "local_pdf"
    import_batch_id: str = ""
    import_batch_started_at: Optional[int] = None
    analysis_ready: bool = True
    metadata_only: bool = False
    zotero_item_key: str = ""
    # --- 新增：允许接收并保存前端传来的 384 维 Embedding 向量 ---
    network_vec: Optional[List[float]] = None

class MergeRequest(BaseModel):
    new_papers: List[PaperItem]

class ProjectCreate(BaseModel):
    user_id: int
    project_name: str
    target_title: str
    target_abstract: str
    target_keywords: str
    target_current_content: str = ""

class ProjectUpdate(BaseModel): 
    project_name: str
    target_title: str
    target_abstract: str
    target_keywords: str
    target_current_content: str = ""

# 新增：用于覆盖更新论文列表的请求模型 (删除功能依赖此模型)
class UpdatePapersRequest(BaseModel):
    top_papers: List[PaperItem]

class PaperLookupRequest(BaseModel):
    title: str
    doi: str = ""
    year: str = ""
    authors: str = ""
    openalex_api_key: str = ""
    contact_email: str = ""

class CitationLookupRequest(BaseModel):
    openalex_id: str = ""
    doi: str = ""
    title: str = ""
    year: str = ""
    authors: str = ""
    cursor: str = "*"
    openalex_api_key: str = ""
    contact_email: str = ""

class CitationGraphRequest(BaseModel):
    papers: List[PaperItem]
    openalex_api_key: str = ""
    contact_email: str = ""

class CitationGraphJobCreated(BaseModel):
    job_id: str
    status: str

class ZoteroSyncRequest(BaseModel):
    zotero_user_id: str
    zotero_api_key: str = ""
    collection_key: str = ""

def _clean_doi(raw_value: Optional[str]) -> str:
    if not raw_value:
        return ""
    value = raw_value.strip()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^doi:\s*", "", value, flags=re.IGNORECASE)
    return value.strip()

def _extract_openalex_short_id(openalex_id: str) -> str:
    if not openalex_id:
        return ""
    return openalex_id.rstrip("/").split("/")[-1]

def _build_url(base_url: str, params: dict) -> str:
    cleaned = {k: v for k, v in params.items() if v not in (None, "", [])}
    if not cleaned:
        return base_url
    return f"{base_url}?{parse.urlencode(cleaned, doseq=True)}"

def _http_get_json(url: str, contact_email: str = "", extra_headers: Optional[dict] = None):
    headers = {"Accept": "application/json"}
    if contact_email:
        headers["User-Agent"] = f"StarMap System/1.0 (mailto:{contact_email})"
    if extra_headers:
        headers.update(extra_headers)
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(status_code=exc.code, detail=detail or f"External API request failed: {url}")
    except error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"External API unavailable: {exc.reason}")

def _reconstruct_openalex_abstract(abstract_index: Optional[dict]) -> str:
    if not abstract_index:
        return ""
    tokens = []
    for word, positions in abstract_index.items():
        for pos in positions:
            tokens.append((pos, word))
    tokens.sort(key=lambda item: item[0])
    return " ".join(word for _, word in tokens).strip()

def _pick_best_title_match(candidates: List[dict], lookup_title: str, lookup_year: str) -> Optional[dict]:
    if not candidates:
        return None
    normalized_lookup = (lookup_title or "").strip().lower()
    lookup_year_clean = (lookup_year or "").strip()

    def _normalize_title(value) -> str:
        if isinstance(value, list):
            return " ".join(str(item) for item in value if item).strip().lower()
        return str(value or "").strip().lower()

    def score(candidate: dict) -> tuple:
        title = _normalize_title(candidate.get("display_name") or candidate.get("title") or "")
        year = str(candidate.get("publication_year") or candidate.get("year") or "")
        exact = int(title == normalized_lookup and normalized_lookup != "")
        contains = int(normalized_lookup in title or title in normalized_lookup) if normalized_lookup and title else 0
        year_match = int(lookup_year_clean != "" and lookup_year_clean == year)
        cited = candidate.get("cited_by_count") or candidate.get("is-referenced-by-count") or 0
        return (exact, contains, year_match, cited)

    return sorted(candidates, key=score, reverse=True)[0]

def _parse_openalex_work(work: Optional[dict]) -> dict:
    if not work:
        return {}
    primary_location = work.get("primary_location") or {}
    best_oa_location = work.get("best_oa_location") or {}
    open_access = work.get("open_access") or {}
    ids = work.get("ids") or {}
    source = primary_location.get("source") or best_oa_location.get("source") or {}
    raw_doi = work.get("doi") or ids.get("doi") or ""
    abstract = _reconstruct_openalex_abstract(work.get("abstract_inverted_index"))
    keywords = [
        concept.get("display_name", "")
        for concept in (work.get("concepts") or [])
        if concept.get("display_name")
    ][:8]
    paper_url = (
        primary_location.get("landing_page_url")
        or best_oa_location.get("landing_page_url")
        or open_access.get("oa_url")
        or work.get("id")
        or ""
    )

    arxiv_id = ""
    for candidate in (ids.get("arxiv"), ids.get("pmcid"), ids.get("pmid"), work.get("id")):
        if isinstance(candidate, str) and "arxiv" in candidate.lower():
            arxiv_id = candidate
            break

    authors = ", ".join(
        authorship.get("author", {}).get("display_name", "")
        for authorship in (work.get("authorships") or [])
        if authorship.get("author", {}).get("display_name")
    )

    return {
        "openalex_id": work.get("id", ""),
        "doi": _clean_doi(raw_doi),
        "paper_url": paper_url,
        "source_url": primary_location.get("landing_page_url") or best_oa_location.get("landing_page_url") or "",
        "publication_venue": source.get("display_name", ""),
        "citation_count": work.get("cited_by_count"),
        "fwci": work.get("fwci"),
        "arxiv_id": arxiv_id,
        "openalex_cited_by_api_url": work.get("cited_by_api_url", ""),
        "referenced_openalex_ids": work.get("referenced_works") or [],
        "abstract": abstract,
        "keywords": keywords,
        "title": work.get("display_name") or work.get("title") or "",
        "year": str(work.get("publication_year") or ""),
        "authors": authors,
        "source": "OpenAlex"
    }

def _parse_crossref_work(work: Optional[dict]) -> dict:
    if not work:
        return {}
    title = (work.get("title") or [""])[0]
    venue = (work.get("container-title") or [""])[0]
    doi = _clean_doi(work.get("DOI") or "")
    year_parts = (
        ((work.get("published-print") or {}).get("date-parts") or [])
        or ((work.get("published-online") or {}).get("date-parts") or [])
        or ((work.get("issued") or {}).get("date-parts") or [])
    )
    year = str(year_parts[0][0]) if year_parts and year_parts[0] else ""
    authors = ", ".join(
        " ".join(part for part in [author.get("given", ""), author.get("family", "")] if part).strip()
        for author in (work.get("author") or [])
    )
    return {
        "doi": doi,
        "paper_url": work.get("URL", ""),
        "source_url": work.get("URL", ""),
        "publication_venue": venue,
        "citation_count": work.get("is-referenced-by-count"),
        "crossref_url": work.get("URL", ""),
        "abstract": re.sub(r"<[^>]+>", "", work.get("abstract") or "").strip(),
        "keywords": work.get("subject") or [],
        "title": title,
        "year": year,
        "authors": authors,
        "type": work.get("type", ""),
        "source": "Crossref"
    }

def _lookup_openalex(payload: PaperLookupRequest) -> dict:
    api_key = payload.openalex_api_key.strip()
    doi = _clean_doi(payload.doi)

    if doi:
        try:
            url = _build_url(
                f"https://api.openalex.org/works/{parse.quote(f'doi:{doi}', safe='')}",
                {"api_key": api_key}
            )
            work = _http_get_json(url, payload.contact_email)
            return _parse_openalex_work(work)
        except HTTPException:
            pass

    search_url = _build_url(
        "https://api.openalex.org/works",
        {
            "search": payload.title,
            "per_page": 5,
            "api_key": api_key
        }
    )
    results = _http_get_json(search_url, payload.contact_email).get("results", [])
    best_match = _pick_best_title_match(results, payload.title, payload.year)
    return _parse_openalex_work(best_match)

def _lookup_crossref(payload: PaperLookupRequest) -> dict:
    doi = _clean_doi(payload.doi)
    if doi:
        try:
            url = f"https://api.crossref.org/v1/works/{parse.quote(doi, safe='')}"
            response = _http_get_json(url, payload.contact_email)
            return _parse_crossref_work(response.get("message"))
        except HTTPException:
            pass

    url = _build_url(
        "https://api.crossref.org/v1/works",
        {
            "query.title": payload.title,
            "rows": 5,
            "mailto": payload.contact_email
        }
    )
    items = (_http_get_json(url, payload.contact_email).get("message") or {}).get("items", [])
    best_match = _pick_best_title_match(items, payload.title, payload.year)
    return _parse_crossref_work(best_match)

def _merge_paper_sources(openalex_data: dict, crossref_data: dict) -> dict:
    merged = {
        "openalex_id": openalex_data.get("openalex_id", ""),
        "doi": openalex_data.get("doi") or crossref_data.get("doi", ""),
        "paper_url": openalex_data.get("paper_url") or crossref_data.get("paper_url", ""),
        "source_url": openalex_data.get("source_url") or crossref_data.get("source_url", ""),
        "publication_venue": openalex_data.get("publication_venue") or crossref_data.get("publication_venue", ""),
        "citation_count": openalex_data.get("citation_count"),
        "fwci": openalex_data.get("fwci"),
        "arxiv_id": openalex_data.get("arxiv_id", ""),
        "openalex_cited_by_api_url": openalex_data.get("openalex_cited_by_api_url", ""),
        "crossref_url": crossref_data.get("crossref_url", ""),
        "abstract": openalex_data.get("abstract") or crossref_data.get("abstract", ""),
        "keywords": openalex_data.get("keywords") or crossref_data.get("keywords", []),
        "title": openalex_data.get("title") or crossref_data.get("title", ""),
        "year": openalex_data.get("year") or crossref_data.get("year", ""),
        "authors": openalex_data.get("authors") or crossref_data.get("authors", "")
    }
    if merged["citation_count"] is None:
        merged["citation_count"] = crossref_data.get("citation_count")

    validation = {
        "doi_match": bool(openalex_data.get("doi") and crossref_data.get("doi") and openalex_data.get("doi") == crossref_data.get("doi")),
        "year_match": bool(openalex_data.get("year") and crossref_data.get("year") and openalex_data.get("year") == crossref_data.get("year")),
        "venue_match": bool(
            openalex_data.get("publication_venue")
            and crossref_data.get("publication_venue")
            and openalex_data.get("publication_venue").strip().lower() == crossref_data.get("publication_venue").strip().lower()
        )
    }
    return {"merged": merged, "validation": validation, "openalex": openalex_data, "crossref": crossref_data}

def _resolve_openalex_id(payload: CitationLookupRequest) -> str:
    if payload.openalex_id:
        return payload.openalex_id
    openalex_data = _lookup_openalex(PaperLookupRequest(
        title=payload.title,
        doi=payload.doi,
        year=payload.year,
        authors=payload.authors,
        openalex_api_key=payload.openalex_api_key,
        contact_email=payload.contact_email
    ))
    return openalex_data.get("openalex_id", "")

def _fetch_openalex_work_by_id(openalex_id: str, api_key: str = "", contact_email: str = "") -> dict:
    short_id = _extract_openalex_short_id(openalex_id)
    if not short_id:
        return {}
    url = _build_url(f"https://api.openalex.org/works/{short_id}", {"api_key": api_key.strip()})
    return _http_get_json(url, contact_email)

def _enrich_paper_for_citation_graph(paper: PaperItem, api_key: str = "", contact_email: str = "") -> dict:
    enriched = paper.model_dump()

    openalex_id = enriched.get("openalex_id", "")
    if not openalex_id:
        openalex_data = _lookup_openalex(PaperLookupRequest(
            title=enriched.get("title", ""),
            doi=enriched.get("doi", ""),
            year=enriched.get("year", ""),
            authors=enriched.get("authors", ""),
            openalex_api_key=api_key,
            contact_email=contact_email
        ))
        if openalex_data:
            enriched.update({
                "openalex_id": openalex_data.get("openalex_id", enriched.get("openalex_id", "")),
                "doi": openalex_data.get("doi") or enriched.get("doi", ""),
                "paper_url": openalex_data.get("paper_url") or enriched.get("paper_url", ""),
                "publication_venue": openalex_data.get("publication_venue") or enriched.get("publication_venue", ""),
                "citation_count": openalex_data.get("citation_count") if openalex_data.get("citation_count") is not None else enriched.get("citation_count"),
                "fwci": openalex_data.get("fwci") if openalex_data.get("fwci") is not None else enriched.get("fwci"),
                "arxiv_id": openalex_data.get("arxiv_id") or enriched.get("arxiv_id", ""),
                "openalex_cited_by_api_url": openalex_data.get("openalex_cited_by_api_url") or enriched.get("openalex_cited_by_api_url", "")
            })
            openalex_id = enriched.get("openalex_id", "")

    if openalex_id and not enriched.get("referenced_openalex_ids"):
        work = _fetch_openalex_work_by_id(openalex_id, api_key, contact_email)
        parsed_work = _parse_openalex_work(work)
        if parsed_work:
            enriched.update({
                "doi": parsed_work.get("doi") or enriched.get("doi", ""),
                "paper_url": parsed_work.get("paper_url") or enriched.get("paper_url", ""),
                "publication_venue": parsed_work.get("publication_venue") or enriched.get("publication_venue", ""),
                "citation_count": parsed_work.get("citation_count") if parsed_work.get("citation_count") is not None else enriched.get("citation_count"),
                "fwci": parsed_work.get("fwci") if parsed_work.get("fwci") is not None else enriched.get("fwci"),
                "arxiv_id": parsed_work.get("arxiv_id") or enriched.get("arxiv_id", ""),
                "openalex_cited_by_api_url": parsed_work.get("openalex_cited_by_api_url") or enriched.get("openalex_cited_by_api_url", ""),
                "referenced_openalex_ids": parsed_work.get("referenced_openalex_ids") or []
            })

    return enriched

def _build_citation_graph_result(enriched_papers: List[dict]) -> dict:
    unresolved = [
        paper.get("filename") or paper.get("title") or "Unknown paper"
        for paper in enriched_papers
        if not paper.get("openalex_id")
    ]

    index_by_openalex_id = {
        paper.get("openalex_id"): paper
        for paper in enriched_papers
        if paper.get("openalex_id")
    }

    edges = []
    edge_keys = set()
    for source_paper in enriched_papers:
        source_id = source_paper.get("openalex_id")
        if not source_id:
            continue
        for target_id in source_paper.get("referenced_openalex_ids") or []:
            target_paper = index_by_openalex_id.get(target_id)
            if not target_paper:
                continue
            source_filename = source_paper.get("filename")
            target_filename = target_paper.get("filename")
            if not source_filename or not target_filename or source_filename == target_filename:
                continue
            edge_key = (source_filename, target_filename)
            if edge_key in edge_keys:
                continue
            edge_keys.add(edge_key)
            edges.append({
                "source": source_filename,
                "target": target_filename,
                "source_openalex_id": source_id,
                "target_openalex_id": target_id
            })

    resolved_count = sum(1 for paper in enriched_papers if paper.get("openalex_id"))
    cached_reference_count = sum(1 for paper in enriched_papers if paper.get("referenced_openalex_ids"))

    return {
        "papers": enriched_papers,
        "edges": edges,
        "stats": {
            "paper_count": len(enriched_papers),
            "resolved_count": resolved_count,
            "cached_reference_count": cached_reference_count,
            "edge_count": len(edges),
            "unresolved_count": len(unresolved),
            "unresolved_examples": unresolved[:20]
        }
    }

def _create_citation_job(total: int) -> str:
    job_id = uuid.uuid4().hex
    CITATION_GRAPH_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "message": "Queued citation graph build...",
        "total": total,
        "completed": 0,
        "resolved": 0,
        "cached_references": 0,
        "failed": 0,
        "progress": 0,
        "result": None,
        "error": None
    }
    return job_id

def _update_citation_job(job_id: str, **kwargs):
    job = CITATION_GRAPH_JOBS.get(job_id)
    if not job:
        return
    job.update(kwargs)
    total = max(job.get("total") or 0, 1)
    completed = min(job.get("completed") or 0, total)
    job["progress"] = int((completed / total) * 100)

async def _run_citation_graph_job(job_id: str, payload: CitationGraphRequest):
    papers = payload.papers[:500]
    total = len(papers)
    _update_citation_job(job_id, status="running", message="Resolving OpenAlex records...", total=total)

    semaphore = asyncio.Semaphore(8)
    enriched_results: List[Optional[dict]] = [None] * total
    resolved_count = 0
    cached_reference_count = 0
    failed_count = 0

    async def enrich_one(index: int, paper: PaperItem):
        async with semaphore:
            try:
                enriched = await asyncio.to_thread(
                    _enrich_paper_for_citation_graph,
                    paper,
                    payload.openalex_api_key,
                    payload.contact_email
                )
                return index, enriched, None
            except HTTPException as exc:
                return index, paper.model_dump(), exc.detail
            except Exception as exc:
                return index, paper.model_dump(), str(exc)

    try:
        tasks = [asyncio.create_task(enrich_one(index, paper)) for index, paper in enumerate(papers)]
        for completed_count, task in enumerate(asyncio.as_completed(tasks), start=1):
            index, enriched, error_detail = await task
            enriched_results[index] = enriched
            if enriched.get("openalex_id"):
                resolved_count += 1
            if enriched.get("referenced_openalex_ids"):
                cached_reference_count += 1
            if error_detail:
                failed_count += 1

            title = enriched.get("title") or papers[index].title or f"Paper {index + 1}"
            _update_citation_job(
                job_id,
                completed=completed_count,
                resolved=resolved_count,
                cached_references=cached_reference_count,
                failed=failed_count,
                message=f"Resolved {completed_count}/{total}: {title[:80]}"
            )

        final_papers = [paper for paper in enriched_results if paper is not None]
        result = _build_citation_graph_result(final_papers)
        _update_citation_job(
            job_id,
            status="completed",
            completed=total,
            resolved=result["stats"]["resolved_count"],
            cached_references=result["stats"]["cached_reference_count"],
            message=f"Citation graph ready: {result['stats']['edge_count']} links across {result['stats']['paper_count']} papers.",
            result=result
        )
    except Exception as exc:
        _update_citation_job(
            job_id,
            status="failed",
            error=str(exc),
            message="Citation graph build failed."
        )

def _safe_lookup(fn, payload):
    try:
        return fn(payload), None
    except HTTPException as exc:
        return {}, exc.detail

def _fetch_zotero_items(payload: ZoteroSyncRequest) -> List[dict]:
    user_id = payload.zotero_user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Zotero User ID is required.")

    api_key = payload.zotero_api_key.strip()
    collection_key = payload.collection_key.strip()
    base_path = f"https://api.zotero.org/users/{parse.quote(user_id, safe='')}"
    resource = f"/collections/{parse.quote(collection_key, safe='')}/items/top" if collection_key else "/items/top"
    headers = {
        "Zotero-API-Version": "3",
        "Accept": "application/json"
    }
    if api_key:
        headers["Zotero-API-Key"] = api_key

    items = []
    start = 0
    limit = 100
    while True:
        url = f"{base_path}{resource}?v=3&format=json&limit={limit}&start={start}"
        batch = _http_get_json(url, extra_headers=headers)
        if not isinstance(batch, list) or not batch:
            break
        items.extend(batch)
        if len(batch) < limit:
            break
        start += limit

    return items

def _extract_year_from_text(value: str) -> str:
    match = re.search(r"(19|20)\d{2}", value or "")
    return match.group(0) if match else "Unknown"

def _format_zotero_creators(creators: List[dict]) -> str:
    formatted = []
    for creator in creators or []:
        if creator.get("name"):
            formatted.append(creator["name"].strip())
            continue
        first = creator.get("firstName", "").strip()
        last = creator.get("lastName", "").strip()
        full = " ".join(part for part in [first, last] if part).strip()
        if full:
            formatted.append(full)
    return ", ".join(formatted) or "Unknown"

def _map_zotero_item_to_paper(item: dict) -> Optional[dict]:
    data = item.get("data") or {}
    item_type = data.get("itemType", "")
    if item_type in {"attachment", "note", "annotation"}:
        return None

    title = (data.get("title") or "").strip()
    if not title:
        return None

    tags = [tag.get("tag", "").strip() for tag in (data.get("tags") or []) if tag.get("tag")]
    abstract = (data.get("abstractNote") or "").strip()
    keywords = tags[:8]
    analysis_ready = bool(abstract or keywords)
    doi = _clean_doi(data.get("DOI") or "")
    url = (data.get("url") or "").strip()
    item_key = item.get("key") or data.get("key") or ""

    return {
        "filename": f"zotero_{item_key or uuid.uuid4().hex}.pdf",
        "title": title,
        "abstract": abstract or "Unknown",
        "keywords": keywords,
        "authors": _format_zotero_creators(data.get("creators") or []),
        "year": _extract_year_from_text(data.get("date") or ""),
        "similarity": 0,
        "is_new": True,
        "favorite": False,
        "status": "Unread",
        "notes": "",
        "doi": doi,
        "paper_url": url,
        "source_url": url,
        "publication_venue": data.get("publicationTitle") or data.get("bookTitle") or "",
        "citation_count": None,
        "fwci": None,
        "arxiv_id": "",
        "openalex_id": "",
        "openalex_cited_by_api_url": "",
        "crossref_url": "",
        "referenced_openalex_ids": [],
        "import_source": "zotero",
        "analysis_ready": analysis_ready,
        "metadata_only": not analysis_ready,
        "zotero_item_key": item_key,
        "network_vec": None
    }

# --- 2. 路由接口 ---
@app.post("/api/register")
async def register_user(user: UserAuth):
    username, password = _validate_auth_payload(user)
    conn = _db_connect()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, _hash_password(password)))
        conn.commit()
        user_id = cursor.lastrowid
        session_token = _create_session(user_id)
        _write_audit_log("register", user_id=user_id, detail={"username": username}, success=True)
        return {"message": "Registration successful", "user_id": user_id, "username": username, "session_token": session_token}
    except sqlite3.IntegrityError:
        _write_audit_log("register", detail={"username": username}, success=False)
        raise HTTPException(status_code=400, detail="Username already exists")
    finally:
        conn.close()

@app.post("/api/login")
async def login_user(user: UserAuth):
    username, password = _validate_auth_payload(user)
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if not row or not _verify_password(password, row[2]):
        conn.close()
        _write_audit_log("login", detail={"username": username}, success=False)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not _is_hashed_password(row[2]):
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", (_hash_password(password), row[0]))
        conn.commit()
    conn.close()
    session_token = _create_session(row[0])
    _write_audit_log("login", user_id=row[0], detail={"username": row[1]}, success=True)
    return {"message": "Login successful", "user_id": row[0], "username": row[1], "session_token": session_token}

@app.post("/api/logout")
async def logout_user(current_user: dict = Depends(_require_session)):
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (current_user["token"],))
    conn.commit()
    conn.close()
    _write_audit_log("logout", user_id=current_user["user_id"], success=True)
    return {"message": "Logout successful"}

@app.get("/api/session")
async def read_session(current_user: dict = Depends(_require_session)):
    return {
        "user_id": current_user["user_id"],
        "username": current_user["username"],
        "session_token": current_user["token"]
    }

@app.get("/api/users/{user_id}/projects")
async def get_user_projects(user_id: int, current_user: dict = Depends(_require_session)):
    if int(user_id) != int(current_user["user_id"]):
        raise HTTPException(status_code=403, detail="You can only access your own projects.")
    conn = _db_connect(row_factory=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, project_name, target_title, target_abstract, target_keywords, target_current_content FROM projects WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/projects/")
async def create_project(req: ProjectCreate, current_user: dict = Depends(_require_session)):
    cleaned = _validate_project_fields(req.project_name, req.target_title, req.target_abstract, req.target_keywords, req.target_current_content)
    conn = _db_connect()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO projects (user_id, project_name, target_title, target_abstract, target_keywords, target_current_content, top_papers) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (current_user["user_id"], cleaned["project_name"], cleaned["target_title"], cleaned["target_abstract"], cleaned["target_keywords"], cleaned["target_current_content"], "[]"))
        conn.commit()
        project_id = cursor.lastrowid
        _write_audit_log("project_create", user_id=current_user["user_id"], project_id=project_id, detail={"project_name": cleaned["project_name"]}, success=True)
        return {"message": "Project created", "project_id": project_id}
    finally:
        conn.close()

@app.get("/api/projects/{project_id}")
async def get_project(project_id: int, current_user: dict = Depends(_require_session)):
    project_data = _get_owned_project(project_id, current_user["user_id"])
    project_data["top_papers"] = json.loads(project_data["top_papers"]) if project_data["top_papers"] else []
    return project_data

@app.put("/api/projects/{project_id}")
async def update_project(project_id: int, req: ProjectUpdate, current_user: dict = Depends(_require_session)):
    _get_owned_project(project_id, current_user["user_id"])
    cleaned = _validate_project_fields(req.project_name, req.target_title, req.target_abstract, req.target_keywords, req.target_current_content)
    lock = await _acquire_project_task_lock(project_id, "project_update")
    conn = _db_connect()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE projects SET project_name=?, target_title=?, target_abstract=?, target_keywords=?, target_current_content=? WHERE id=? AND user_id=?", 
                       (cleaned["project_name"], cleaned["target_title"], cleaned["target_abstract"], cleaned["target_keywords"], cleaned["target_current_content"], project_id, current_user["user_id"]))
        conn.commit()
        _write_audit_log("project_update", user_id=current_user["user_id"], project_id=project_id, detail={"project_name": cleaned["project_name"]}, success=True)
        return {"message": "Project updated"}
    finally:
        conn.close()
        lock.release()

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: int, current_user: dict = Depends(_require_session)):
    _get_owned_project(project_id, current_user["user_id"])
    lock = await _acquire_project_task_lock(project_id, "project_delete")
    conn = _db_connect()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM projects WHERE id=? AND user_id=?", (project_id, current_user["user_id"]))
        conn.commit()
        _write_audit_log("project_delete", user_id=current_user["user_id"], project_id=project_id, success=True)
        return {"message": "Project deleted"}
    finally:
        conn.close()
        lock.release()

# 修改 main.py 中的 merge_papers 路由
@app.post("/api/projects/{project_id}/merge_papers")
async def merge_top_150_papers(project_id: int, request: MergeRequest, current_user: dict = Depends(_require_session)):
    _get_owned_project(project_id, current_user["user_id"])
    _validate_paper_list(request.new_papers)
    lock = await _acquire_project_task_lock(project_id, "merge_papers")
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT top_papers FROM projects WHERE id = ? AND user_id = ?", (project_id, current_user["user_id"]))
    row = cursor.fetchone()
    try:
        if not row:
            raise HTTPException(status_code=404, detail="Project not found.")
        existing_papers_json = row[0]
        existing_papers = json.loads(existing_papers_json) if existing_papers_json else []
        
        for p in existing_papers:
            p["is_new"] = False
            
        new_papers = []
        for paper in request.new_papers:
            p_dict = paper.model_dump()
            p_dict["is_new"] = True
            new_papers.append(p_dict)
        
        all_papers = existing_papers + new_papers
        all_papers.sort(key=lambda x: x["similarity"], reverse=True)
        top_papers = all_papers[:MAX_TOP_PAPERS]
        
        updated_json = json.dumps(top_papers, ensure_ascii=False)
        cursor.execute("UPDATE projects SET top_papers = ? WHERE id = ? AND user_id = ?", (updated_json, project_id, current_user["user_id"]))
        conn.commit()
        _write_audit_log("project_merge_papers", user_id=current_user["user_id"], project_id=project_id, detail={"new_papers": len(request.new_papers), "stored_papers": len(top_papers)}, success=True)
        return {"message": "Merge successful", "top_papers": top_papers}
    finally:
        conn.close()
        lock.release()

# ==========================================
# 新增：直接覆盖更新项目的 top_papers 列表（用于删除单篇论文）
# ==========================================
@app.put("/api/projects/{project_id}/papers")
async def update_project_papers(project_id: int, request: UpdatePapersRequest, current_user: dict = Depends(_require_session)):
    _get_owned_project(project_id, current_user["user_id"])
    _validate_paper_list(request.top_papers)
    lock = await _acquire_project_task_lock(project_id, "update_papers")
    conn = _db_connect()
    cursor = conn.cursor()
    try:
        updated_json = json.dumps([p.model_dump() for p in request.top_papers], ensure_ascii=False)
        cursor.execute("UPDATE projects SET top_papers = ? WHERE id = ? AND user_id = ?", (updated_json, project_id, current_user["user_id"]))
        conn.commit()
        _write_audit_log("project_update_papers", user_id=current_user["user_id"], project_id=project_id, detail={"paper_count": len(request.top_papers)}, success=True)
        return {"message": "Papers updated successfully"}
    finally:
        conn.close()
        lock.release()

@app.post("/api/papers/lookup")
async def lookup_paper_metadata(payload: PaperLookupRequest, current_user: dict = Depends(_require_session)):
    _validate_lookup_payload(payload)
    openalex_data, openalex_error = _safe_lookup(_lookup_openalex, payload)
    crossref_data, crossref_error = _safe_lookup(_lookup_crossref, payload)

    if not openalex_data and not crossref_data:
        raise HTTPException(
            status_code=502,
            detail=f"Metadata lookup failed. OpenAlex: {openalex_error or 'unknown error'} | Crossref: {crossref_error or 'unknown error'}"
        )

    merged = _merge_paper_sources(openalex_data, crossref_data)
    merged["source_errors"] = {
        "openalex": openalex_error,
        "crossref": crossref_error
    }
    return merged

@app.post("/api/zotero/sync")
async def zotero_sync(payload: ZoteroSyncRequest, current_user: dict = Depends(_require_session)):
    try:
        raw_items = _fetch_zotero_items(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Zotero sync failed: {exc}")

    papers = []
    for item in raw_items:
        mapped = _map_zotero_item_to_paper(item)
        if mapped:
            papers.append(mapped)

    return {
        "papers": papers,
        "count": len(papers)
    }

@app.post("/api/papers/citations")
async def lookup_paper_citations(payload: CitationLookupRequest, current_user: dict = Depends(_require_session)):
    try:
        openalex_id = _resolve_openalex_id(payload)
    except HTTPException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OpenAlex lookup failed, so citations cannot be loaded right now. Detail: {exc.detail}"
        )
    if not openalex_id:
        raise HTTPException(status_code=404, detail="Unable to resolve this paper on OpenAlex.")

    short_id = _extract_openalex_short_id(openalex_id)
    url = _build_url(
        "https://api.openalex.org/works",
        {
            "filter": f"cites:{short_id}",
            "per_page": 100,
            "cursor": payload.cursor or "*",
            "api_key": payload.openalex_api_key.strip()
        }
    )
    response = _http_get_json(url, payload.contact_email)
    results = response.get("results", [])
    citations = []
    for work in results:
        parsed_work = _parse_openalex_work(work)
        citations.append({
            "title": parsed_work.get("title", ""),
            "year": parsed_work.get("year", ""),
            "authors": parsed_work.get("authors", ""),
            "doi": parsed_work.get("doi", ""),
            "paper_url": parsed_work.get("paper_url", ""),
            "publication_venue": parsed_work.get("publication_venue", ""),
            "citation_count": parsed_work.get("citation_count"),
            "fwci": parsed_work.get("fwci"),
            "openalex_id": parsed_work.get("openalex_id", "")
        })

    return {
        "openalex_id": openalex_id,
        "citations": citations,
        "next_cursor": (response.get("meta") or {}).get("next_cursor"),
        "total_count": (response.get("meta") or {}).get("count", len(citations))
    }

@app.post("/api/papers/references")
async def lookup_paper_references(payload: CitationLookupRequest, current_user: dict = Depends(_require_session)):
    try:
        openalex_id = _resolve_openalex_id(payload)
    except HTTPException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OpenAlex lookup failed, so references cannot be loaded right now. Detail: {exc.detail}"
        )
    if not openalex_id:
        raise HTTPException(status_code=404, detail="Unable to resolve this paper on OpenAlex.")

    short_id = _extract_openalex_short_id(openalex_id)
    url = _build_url(
        "https://api.openalex.org/works",
        {
            "filter": f"cited_by:{short_id}",
            "per_page": 100,
            "cursor": payload.cursor or "*",
            "api_key": payload.openalex_api_key.strip()
        }
    )
    response = _http_get_json(url, payload.contact_email)
    results = response.get("results", [])
    references = []
    for work in results:
        parsed_work = _parse_openalex_work(work)
        references.append({
            "title": parsed_work.get("title", ""),
            "year": parsed_work.get("year", ""),
            "authors": parsed_work.get("authors", ""),
            "doi": parsed_work.get("doi", ""),
            "paper_url": parsed_work.get("paper_url", ""),
            "publication_venue": parsed_work.get("publication_venue", ""),
            "citation_count": parsed_work.get("citation_count"),
            "fwci": parsed_work.get("fwci"),
            "openalex_id": parsed_work.get("openalex_id", "")
        })

    return {
        "openalex_id": openalex_id,
        "references": references,
        "next_cursor": (response.get("meta") or {}).get("next_cursor"),
        "total_count": (response.get("meta") or {}).get("count", len(references))
    }

@app.post("/api/papers/citation-graph")
async def build_citation_graph(payload: CitationGraphRequest, current_user: dict = Depends(_require_session)):
    job_id = _create_citation_job(min(len(payload.papers), 500))
    _write_audit_log("citation_graph_create", user_id=current_user["user_id"], detail={"paper_count": len(payload.papers), "job_id": job_id}, success=True)
    asyncio.create_task(_run_citation_graph_job(job_id, payload))
    return {"job_id": job_id, "status": "queued"}

@app.post("/api/papers/citation-graph/jobs", response_model=CitationGraphJobCreated)
async def create_citation_graph_job(payload: CitationGraphRequest, current_user: dict = Depends(_require_session)):
    job_id = _create_citation_job(min(len(payload.papers), 500))
    _write_audit_log("citation_graph_create", user_id=current_user["user_id"], detail={"paper_count": len(payload.papers), "job_id": job_id}, success=True)
    asyncio.create_task(_run_citation_graph_job(job_id, payload))
    return CitationGraphJobCreated(job_id=job_id, status="queued")

@app.get("/api/papers/citation-graph/jobs/{job_id}")
async def get_citation_graph_job(job_id: str, current_user: dict = Depends(_require_session)):
    job = CITATION_GRAPH_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Citation graph job not found.")
    return job

@app.post("/api/update-account")
async def update_account(payload: AccountUpdate, current_user: dict = Depends(_require_session)):
    conn = _db_connect()
    cursor = conn.cursor()
    
    # 1. Verify old password
    cursor.execute("SELECT password FROM users WHERE id = ?", (current_user["user_id"],))
    row = cursor.fetchone()
    if not row or not _verify_password(payload.old_password, row[0]):
        conn.close()
        _write_audit_log("update_account", user_id=current_user["user_id"], success=False, detail="Incorrect old password")
        raise HTTPException(status_code=400, detail="Incorrect current password.")

    update_fields = []
    params = []

    # 2. Handle Username Change
    new_username = payload.new_username.strip()
    if new_username:
        if len(new_username) < 3:
            conn.close()
            raise HTTPException(status_code=422, detail="New username must be at least 3 characters.")
        # Check if the username is already taken by someone else
        cursor.execute("SELECT id FROM users WHERE username = ? AND id != ?", (new_username, current_user["user_id"]))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="This username already exists. Please choose another one.")
        update_fields.append("username = ?")
        params.append(new_username)

    # 3. Handle Password Change
    if payload.new_password:
        if len(payload.new_password) < 8:
            conn.close()
            raise HTTPException(status_code=422, detail="New password must be at least 8 characters.")
        if len(payload.new_password) > 200:
            conn.close()
            raise HTTPException(status_code=422, detail="New password is too long.")
        new_hashed = _hash_password(payload.new_password)
        update_fields.append("password = ?")
        params.append(new_hashed)

    if not update_fields:
        conn.close()
        raise HTTPException(status_code=400, detail="No changes requested.")

    # 4. Apply Updates
    params.append(current_user["user_id"])
    query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
    cursor.execute(query, params)

    # If the password was changed, invalidate all other sessions
    if payload.new_password:
        cursor.execute("DELETE FROM sessions WHERE user_id = ? AND token != ?", (current_user["user_id"], current_user["token"]))
    
    conn.commit()
    conn.close()
    _write_audit_log("update_account", user_id=current_user["user_id"], success=True, detail={"username_changed": bool(new_username), "password_changed": bool(payload.new_password)})
    
    return {"message": "Account updated successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)