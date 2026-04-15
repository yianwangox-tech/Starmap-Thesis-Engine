from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import sqlite3
import json
import os
import re
import math
import unicodedata
import uuid
import time
import secrets
import hashlib
import hmac
from pathlib import Path
from http.client import IncompleteRead
from urllib import error, parse, request
from datetime import date, timedelta
from difflib import SequenceMatcher

app = FastAPI(title="StarMap Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_FILE = PROJECT_ROOT / "database.db"
LEGACY_DB_FILE = Path(__file__).resolve().parent / "database.db"
ENV_FILE = PROJECT_ROOT / ".env"
GEMINI_MODEL = "gemini-2.5-flash"
CITATION_GRAPH_JOBS: Dict[str, dict] = {}
PROJECT_TASK_LOCKS: Dict[str, asyncio.Lock] = {}
ZOTERO_CACHE_TTL_SECONDS = 60 * 5
ZOTERO_FULL_SYNC_INTERVAL_SECONDS = 60 * 60
ZOTERO_ITEM_PAGE_SIZE = 100
ZOTERO_COLLECTION_PAGE_SIZE = 100
SESSION_TTL_SECONDS = 60 * 60 * 24 * 14
PBKDF2_ITERATIONS = 120_000
MAX_PROJECT_NAME_LENGTH = 120
MAX_TARGET_TITLE_LENGTH = 300
MAX_TARGET_ABSTRACT_LENGTH = 20000
MAX_TARGET_CURRENT_CONTENT_LENGTH = 80000
MAX_TOP_PAPERS = 500
MAX_PAPER_TITLE_LENGTH = 500
MAX_PAPER_ABSTRACT_LENGTH = 30000
MAX_PAPER_CURRENT_CONTENT_LENGTH = 10000
MAX_PAPER_NOTES_LENGTH = 20000
MAX_PAPER_AUTHORS_LENGTH = 1200
MAX_LOOKUP_TITLE_LENGTH = 500
MAX_LOOKUP_AUTHORS_LENGTH = 800
MAX_LOOKUP_YEAR_LENGTH = 20
MAX_LOOKUP_EMAIL_LENGTH = 200
CITATION_KEY_STOPWORDS = {
    "a", "an", "the", "on", "in", "of", "for", "to", "and", "or", "by", "with",
    "at", "from", "into", "over", "under", "about", "between", "after", "before"
}
LITERATURE_WATCH_STOPWORDS = set(CITATION_KEY_STOPWORDS) | {
    "this", "that", "these", "those", "their", "there", "which", "while", "where",
    "when", "using", "uses", "used", "study", "studies", "paper", "papers",
    "evidence", "analysis", "approach", "effects", "effect", "impact", "impacts",
    "role", "new", "latest", "recent", "across", "within", "under", "into",
    "based", "from", "toward", "through", "among", "over", "than", "such"
}
LITERATURE_WATCH_DISCIPLINES: Dict[str, dict] = {
    "macroeconomics_monetary": {
        "label": "Macroeconomics & Monetary Economics",
        "top_venues": [
            "american economic review",
            "econometrica",
            "quarterly journal of economics",
            "journal of political economy",
            "review of economics and statistics",
            "journal of monetary economics",
            "journal of economic theory",
            "journal of international economics"
        ],
        "venue_keywords": ["macro", "monetary", "econom", "inflation", "business cycle", "exchange rate", "sovereign", "fiscal"],
    },
    "international_finance_sovereign_debt": {
        "label": "International Finance & Sovereign Debt",
        "top_venues": [
            "journal of finance",
            "review of financial studies",
            "journal of financial economics",
            "american economic review",
            "journal of monetary economics",
            "journal of international economics",
            "journal of banking and finance",
            "review of finance",
            "journal of financial intermediation"
        ],
        "venue_keywords": ["sovereign", "debt", "default", "spread", "bond", "fiscal", "bank", "credit", "international finance", "public debt"],
    },
    "banking_credit_financial_intermediation": {
        "label": "Banking, Credit & Financial Intermediation",
        "top_venues": [
            "journal of finance",
            "review of financial studies",
            "journal of financial economics",
            "journal of financial intermediation",
            "journal of banking and finance",
            "review of finance"
        ],
        "venue_keywords": ["bank", "banking", "credit", "intermediation", "lending", "liquidity", "financial stability", "balance sheet"],
    },
    "asset_pricing_corporate_finance": {
        "label": "Asset Pricing & Corporate Finance",
        "top_venues": [
            "journal of finance",
            "review of financial studies",
            "journal of financial economics",
            "review of finance",
            "management science"
        ],
        "venue_keywords": ["asset pricing", "corporate finance", "equity", "valuation", "maturity", "capital structure", "investment", "returns"],
    },
    "public_finance_political_economy": {
        "label": "Public Finance & Political Economy",
        "top_venues": [
            "american economic review",
            "quarterly journal of economics",
            "journal of political economy",
            "journal of public economics",
            "review of economics and statistics",
            "american political science review",
            "journal of politics",
            "world politics"
        ],
        "venue_keywords": ["public finance", "fiscal", "tax", "government", "political economy", "policy", "state", "regulation"],
    },
    "development_international_political_economy": {
        "label": "Development & International Political Economy",
        "top_venues": [
            "journal of development economics",
            "world development",
            "american economic review",
            "journal of international economics",
            "world politics"
        ],
        "venue_keywords": ["development", "emerging markets", "global", "trade", "aid", "institutions", "political economy", "international"],
    },
    "political_economy_public_policy": {
        "label": "Political Economy & Public Policy",
        "top_venues": [
            "american political science review",
            "journal of politics",
            "world politics",
            "governance",
            "public administration review",
            "journal of public economics"
        ],
        "venue_keywords": ["politic", "policy", "public", "govern", "state", "regulation"],
    },
    "management_strategy_organizations": {
        "label": "Management, Strategy & Organizations",
        "top_venues": [
            "academy of management journal",
            "academy of management review",
            "administrative science quarterly",
            "strategic management journal",
            "organization science",
            "management science"
        ],
        "venue_keywords": ["management", "strategy", "organization", "firm", "leadership", "governance", "business"],
    },
    "marketing_operations_business_analytics": {
        "label": "Marketing, Operations & Business Analytics",
        "top_venues": [
            "journal of marketing",
            "marketing science",
            "management science",
            "manufacturing & service operations management",
            "operations research"
        ],
        "venue_keywords": ["marketing", "operations", "supply chain", "analytics", "pricing", "consumer", "service"],
    },
    "computer_science_ai": {
        "label": "Computer Science & AI",
        "top_venues": [
            "neurips",
            "icml",
            "iclr",
            "aaai",
            "journal of machine learning research",
            "transactions on pattern analysis and machine intelligence"
        ],
        "venue_keywords": ["machine learning", "artificial intelligence", "computer", "computing", "systems", "information"],
    },
    "general_social_science": {
        "label": "General Social Science",
        "top_venues": [
            "american journal of sociology",
            "american sociological review",
            "social forces",
            "annual review of sociology"
        ],
        "venue_keywords": ["social", "sociolog", "politic", "economic", "policy"],
    },
}
DEFAULT_LITERATURE_WATCH_DISCIPLINE = "international_finance_sovereign_debt"

def _scrub_paper_payload(paper: dict) -> dict:
    if not isinstance(paper, dict):
        return paper
    cleaned = dict(paper)
    cleaned.pop("keywords", None)
    abstract = str(cleaned.get("abstract", "") or "").strip()[:MAX_PAPER_ABSTRACT_LENGTH]
    cleaned["abstract"] = abstract or "Unknown"
    cleaned["current_content"] = str(cleaned.get("current_content", "") or "").strip()[:MAX_PAPER_CURRENT_CONTENT_LENGTH]
    cleaned["analysis_ready"] = bool(abstract and abstract.lower() != "unknown")
    cleaned["metadata_only"] = not cleaned["analysis_ready"]
    cleaned["similarity_pending"] = bool(cleaned.get("similarity_pending"))
    cleaned["zotero_has_pdf_attachment"] = bool(cleaned.get("zotero_has_pdf_attachment"))
    cleaned["zotero_has_fulltext"] = bool(cleaned.get("zotero_has_fulltext"))
    return cleaned

def _scrub_top_papers_json(raw_value) -> str:
    if not raw_value:
        return "[]"
    try:
        papers = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    except Exception:
        return "[]"
    if not isinstance(papers, list):
        return "[]"
    return json.dumps([_scrub_paper_payload(paper) for paper in papers if isinstance(paper, dict)], ensure_ascii=False)

def _ensure_projects_schema(cursor):
    expected_columns = [
        "id", "user_id", "project_name", "target_title",
        "target_abstract", "target_current_content", "top_papers"
    ]
    cursor.execute("PRAGMA table_info(projects)")
    current_columns = [row[1] for row in cursor.fetchall()]
    if not current_columns:
        cursor.execute(
            '''CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_name TEXT NOT NULL,
                target_title TEXT,
                target_abstract TEXT,
                target_current_content TEXT,
                top_papers TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )'''
        )
        return
    if current_columns == expected_columns:
        return

    has_target_current_content = "target_current_content" in current_columns
    cursor.execute("ALTER TABLE projects RENAME TO projects_legacy")
    cursor.execute(
        '''CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project_name TEXT NOT NULL,
            target_title TEXT,
            target_abstract TEXT,
            target_current_content TEXT,
            top_papers TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )'''
    )
    if has_target_current_content:
        cursor.execute(
            '''INSERT INTO projects (id, user_id, project_name, target_title, target_abstract, target_current_content, top_papers)
               SELECT id, user_id, project_name, target_title, target_abstract, target_current_content, top_papers
               FROM projects_legacy'''
        )
    else:
        cursor.execute(
            '''INSERT INTO projects (id, user_id, project_name, target_title, target_abstract, target_current_content, top_papers)
               SELECT id, user_id, project_name, target_title, target_abstract, '', top_papers
               FROM projects_legacy'''
        )
    cursor.execute("DROP TABLE projects_legacy")

def init_db():
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, project_name TEXT NOT NULL, target_title TEXT, target_abstract TEXT, target_current_content TEXT, top_papers TEXT, FOREIGN KEY (user_id) REFERENCES users (id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, FOREIGN KEY (user_id) REFERENCES users (id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, project_id INTEGER, action TEXT NOT NULL, detail TEXT, success INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS zotero_cache_state (
        account_key TEXT NOT NULL,
        collection_key TEXT NOT NULL,
        library_version INTEGER NOT NULL DEFAULT 0,
        refreshed_at INTEGER NOT NULL DEFAULT 0,
        full_refreshed_at INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (account_key, collection_key)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS zotero_cache_items (
        account_key TEXT NOT NULL,
        collection_key TEXT NOT NULL,
        item_key TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 0,
        payload TEXT NOT NULL,
        updated_at INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (account_key, collection_key, item_key)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS zotero_collection_cache (
        account_key TEXT NOT NULL,
        collection_key TEXT NOT NULL,
        payload TEXT NOT NULL,
        updated_at INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (account_key, collection_key)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS zotero_collection_cache_state (
        account_key TEXT PRIMARY KEY,
        refreshed_at INTEGER NOT NULL DEFAULT 0
    )''')
    _ensure_projects_schema(cursor)
    cursor.execute("SELECT id, top_papers FROM projects")
    for project_id, top_papers in cursor.fetchall():
        scrubbed = _scrub_top_papers_json(top_papers)
        if scrubbed != (top_papers or "[]"):
            cursor.execute("UPDATE projects SET top_papers = ? WHERE id = ?", (scrubbed, project_id))
    conn.commit()
    conn.close()

init_db()

def _db_connect(row_factory: bool = False):
    conn = sqlite3.connect(str(DB_FILE))
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

def _parse_env_file() -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not ENV_FILE.exists():
        return values
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values

def _write_env_file(settings: Dict[str, str]):
    lines = [
        "## StarMap backend runtime configuration",
        "## Fill in your real keys below.",
        "",
        "# Data/runtime",
        "STARMAP_DATA_DIR=",
        "STARMAP_EXTERNAL_CALL_CONCURRENCY=32",
        "STARMAP_HEAVY_ROUTE_CONCURRENCY=16",
        "",
        "# LLM defaults",
        f"STARMAP_LLM_PROVIDER={settings.get('STARMAP_LLM_PROVIDER', 'groq')}",
        f"STARMAP_LLM_API_KEY={settings.get('STARMAP_LLM_API_KEY', '')}",
        "",
        "# OpenAlex defaults",
        f"STARMAP_OPENALEX_API_KEY={settings.get('STARMAP_OPENALEX_API_KEY', '')}",
        f"STARMAP_CONTACT_EMAIL={settings.get('STARMAP_CONTACT_EMAIL', '')}",
        "",
        "# Zotero defaults",
        f"STARMAP_ZOTERO_USER_ID={settings.get('STARMAP_ZOTERO_USER_ID', '')}",
        f"STARMAP_ZOTERO_API_KEY={settings.get('STARMAP_ZOTERO_API_KEY', '')}",
        f"STARMAP_ZOTERO_COLLECTION_KEY={settings.get('STARMAP_ZOTERO_COLLECTION_KEY', '')}",
        "",
    ]
    ENV_FILE.write_text("\n".join(lines), encoding="utf-8")

def _load_runtime_settings() -> Dict[str, str]:
    values = _parse_env_file()
    return {
        "llm_provider": (values.get("STARMAP_LLM_PROVIDER") or "groq").strip() or "groq",
        "llm_api_key": (values.get("STARMAP_LLM_API_KEY") or "").strip(),
        "openalex_api_key": (values.get("STARMAP_OPENALEX_API_KEY") or "").strip(),
        "contact_email": (values.get("STARMAP_CONTACT_EMAIL") or "").strip(),
        "zotero_user_id": (values.get("STARMAP_ZOTERO_USER_ID") or "").strip(),
        "zotero_api_key": (values.get("STARMAP_ZOTERO_API_KEY") or "").strip(),
        "zotero_collection_key": (values.get("STARMAP_ZOTERO_COLLECTION_KEY") or "").strip(),
    }

def _save_runtime_settings(settings: Dict[str, str]):
    env_settings = {
        "STARMAP_LLM_PROVIDER": settings.get("llm_provider", "groq").strip() or "groq",
        "STARMAP_LLM_API_KEY": settings.get("llm_api_key", "").strip(),
        "STARMAP_OPENALEX_API_KEY": settings.get("openalex_api_key", "").strip(),
        "STARMAP_CONTACT_EMAIL": settings.get("contact_email", "").strip(),
        "STARMAP_ZOTERO_USER_ID": settings.get("zotero_user_id", "").strip(),
        "STARMAP_ZOTERO_API_KEY": settings.get("zotero_api_key", "").strip(),
        "STARMAP_ZOTERO_COLLECTION_KEY": settings.get("zotero_collection_key", "").strip(),
    }
    _write_env_file(env_settings)
    for key, value in env_settings.items():
        os.environ[key] = value

def _env_value(key: str, fallback: str = "") -> str:
    return _parse_env_file().get(key, os.environ.get(key, fallback)).strip()

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

def _project_content_score(row: dict) -> int:
    return sum(
        len(str((row or {}).get(field) or ""))
        for field in ("target_title", "target_abstract", "target_current_content", "top_papers")
    )

def _pick_preferred_password(current_password: str, incoming_password: str) -> str:
    if _is_hashed_password(current_password) and not _is_hashed_password(incoming_password):
        return current_password
    if _is_hashed_password(incoming_password) and not _is_hashed_password(current_password):
        return incoming_password
    return incoming_password if len(str(incoming_password or "")) > len(str(current_password or "")) else current_password

def _merge_legacy_database():
    if not LEGACY_DB_FILE.exists():
        return
    if LEGACY_DB_FILE.resolve() == DB_FILE.resolve():
        return

    legacy = sqlite3.connect(str(LEGACY_DB_FILE))
    legacy.row_factory = sqlite3.Row
    current = _db_connect(row_factory=True)

    legacy_cursor = legacy.cursor()
    current_cursor = current.cursor()

    try:
        legacy_cursor.execute("SELECT id, username, password FROM users ORDER BY id")
        for row in legacy_cursor.fetchall():
            current_cursor.execute("SELECT id, username, password FROM users WHERE username = ?", (row["username"],))
            existing = current_cursor.fetchone()
            if not existing:
                current_cursor.execute(
                    "INSERT INTO users (id, username, password) VALUES (?, ?, ?)",
                    (row["id"], row["username"], row["password"])
                )
                continue

            preferred_password = _pick_preferred_password(existing["password"], row["password"])
            if preferred_password != existing["password"]:
                current_cursor.execute(
                    "UPDATE users SET password = ? WHERE id = ?",
                    (preferred_password, existing["id"])
                )

        legacy_cursor.execute(
            "SELECT id, user_id, project_name, target_title, target_abstract, target_current_content, top_papers "
            "FROM projects ORDER BY id"
        )
        for row in legacy_cursor.fetchall():
            row_dict = dict(row)
            row_dict["top_papers"] = _scrub_top_papers_json(row_dict.get("top_papers"))
            current_cursor.execute(
                "SELECT id, user_id, project_name, target_title, target_abstract, target_current_content, top_papers "
                "FROM projects WHERE id = ?",
                (row["id"],)
            )
            existing = current_cursor.fetchone()
            if not existing:
                current_cursor.execute(
                    "INSERT INTO projects (id, user_id, project_name, target_title, target_abstract, target_current_content, top_papers) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        row["id"], row["user_id"], row["project_name"], row["target_title"], row["target_abstract"],
                        row["target_current_content"], row_dict["top_papers"]
                    )
                )
                continue

            existing_dict = dict(existing)
            if _project_content_score(row_dict) > _project_content_score(existing_dict):
                current_cursor.execute(
                    "UPDATE projects SET user_id = ?, project_name = ?, target_title = ?, target_abstract = ?, "
                    "target_current_content = ?, top_papers = ? WHERE id = ?",
                    (
                        row["user_id"], row["project_name"], row["target_title"], row["target_abstract"],
                        row["target_current_content"], row_dict["top_papers"], row["id"]
                    )
                )

        legacy_cursor.execute(
            "SELECT user_id, project_id, action, detail, success, created_at FROM audit_logs ORDER BY id"
        )
        for row in legacy_cursor.fetchall():
            current_cursor.execute(
                "SELECT 1 FROM audit_logs WHERE user_id IS ? AND project_id IS ? AND action = ? AND detail = ? AND success = ? AND created_at = ? LIMIT 1",
                (row["user_id"], row["project_id"], row["action"], row["detail"], row["success"], row["created_at"])
            )
            if current_cursor.fetchone():
                continue
            current_cursor.execute(
                "INSERT INTO audit_logs (user_id, project_id, action, detail, success, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (row["user_id"], row["project_id"], row["action"], row["detail"], row["success"], row["created_at"])
            )

        now = _now_ts()
        legacy_cursor.execute(
            "SELECT token, user_id, created_at, expires_at FROM sessions WHERE expires_at > ? ORDER BY created_at",
            (now,)
        )
        for row in legacy_cursor.fetchall():
            current_cursor.execute("SELECT 1 FROM sessions WHERE token = ? LIMIT 1", (row["token"],))
            if current_cursor.fetchone():
                continue
            current_cursor.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (row["token"], row["user_id"], row["created_at"], row["expires_at"])
            )

        current.commit()
    finally:
        legacy.close()
        current.close()

_merge_legacy_database()

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

def _collapse_whitespace(value: str) -> str:
    return re.sub(r"[ \t]+", " ", str(value or "")).strip()

def _looks_like_noise_block(block: str) -> bool:
    text = _collapse_whitespace(block)
    if len(text) < 40:
        return True
    lowered = text.lower()
    if any(marker in lowered for marker in [
        "article info", "jel classification", "keywords:", "key words:",
        "corresponding author", "email address", "all rights are reserved",
        "available at", "https://", "http://", "doi.org/", "table ", "figure ",
        "summary statistics", "variable obs mean", "appendix", "acknowledg"
    ]):
        return True
    digit_ratio = sum(ch.isdigit() for ch in text) / max(len(text), 1)
    if digit_ratio > 0.18:
        return True
    if re.search(r"\b[A-Z][a-z]+,\s+[A-Z](?:\.[A-Z])*\.?\s*\(\d{4}\)", text):
        return True
    if len(re.findall(r"[=<>±∑∫λβσπµ]", text)) >= 2:
        return True
    return False

def _slice_academic_body_text(raw_text: str) -> str:
    text = str(raw_text or "")
    if not text.strip():
        return ""

    normalized = re.sub(r"\r\n?", "\n", text)
    lowered = normalized.lower()

    start_index = 0
    for pattern in [
        r"\babstract\b",
        r"\bintroduction\b",
        r"\b1\.\s*introduction\b",
    ]:
        match = re.search(pattern, lowered)
        if match:
            start_index = match.end()
            break

    end_index = len(normalized)
    for pattern in [
        r"\breferences\b",
        r"\bbibliography\b",
        r"\bappendix\b",
        r"\backnowledg(?:e)?ments?\b"
    ]:
        match = re.search(pattern, lowered[start_index:])
        if match:
            end_index = min(end_index, start_index + match.start())
    return normalized[start_index:end_index].strip()

def _compress_body_text(text: str, max_length: int = MAX_PAPER_CURRENT_CONTENT_LENGTH) -> str:
    value = _collapse_whitespace(text)
    if len(value) <= max_length:
        return value
    edge = max(1800, max_length // 3)
    middle = max(1200, max_length - (edge * 2) - 10)
    middle_start = max(0, (len(value) // 2) - (middle // 2))
    middle_end = middle_start + middle
    combined = f"{value[:edge]} [...] {value[middle_start:middle_end]} [...] {value[-edge:]}"
    return combined[:max_length].strip()

def _normalize_paper_current_content(raw_text: str) -> str:
    body = _slice_academic_body_text(raw_text)
    if not body:
        return ""

    raw_blocks = [block.strip() for block in re.split(r"\n{2,}", body) if block.strip()]
    if not raw_blocks:
        raw_blocks = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+(?=[A-Z])", body) if segment.strip()]

    kept_blocks = []
    for block in raw_blocks:
        cleaned = _collapse_whitespace(block)
        if len(cleaned) < 60:
            continue
        if _looks_like_noise_block(cleaned):
            continue
        kept_blocks.append(cleaned)

    if not kept_blocks:
        fallback = _collapse_whitespace(body)
        return _compress_body_text(fallback) if len(fallback) >= 80 else ""

    return _compress_body_text("\n\n".join(kept_blocks))

def _sanitize_citation_key_part(value: str, fallback: str = "Unknown") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", str(value or ""))
    if not cleaned:
        cleaned = fallback
    return f"{cleaned[:1].upper()}{cleaned[1:]}"

def _extract_first_author_last_name(authors: str) -> str:
    normalized = str(authors or "").strip()
    if not normalized:
        return "Unknown"
    first_author = re.split(r"\s+and\s+|\s*&\s*|;", normalized, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if "," in first_author:
        first_author = first_author.split(",", 1)[0].strip()
    else:
        first_author = first_author.split(",")[0].strip()
    parts = [part for part in re.split(r"\s+", first_author) if part]
    if not parts:
        return "Unknown"
    return _sanitize_citation_key_part(parts[-1], "Unknown")

def _extract_citation_year(year: str) -> str:
    match = re.search(r"\b(19|20)\d{2}\b", str(year or ""))
    return match.group(0) if match else "Unknown"

def _extract_title_keyword(title: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", str(title or ""))
    for word in words:
        if word.lower() not in CITATION_KEY_STOPWORDS:
            return _sanitize_citation_key_part(word, "Unknown")
    return "Unknown"

def generate_citation_key(metadata: dict) -> str:
    author_part = _extract_first_author_last_name(metadata.get("authors", ""))
    year_part = _extract_citation_year(metadata.get("year", ""))
    title_part = _extract_title_keyword(metadata.get("title", ""))
    return f"{author_part}{year_part}{title_part}"

def _attach_citation_key(metadata: dict) -> dict:
    enriched = dict(metadata or {})
    enriched["citation_key"] = _trim_text(
        enriched.get("citation_key") or generate_citation_key(enriched),
        120
    )
    return enriched

def _escape_bibtex_value(value: str) -> str:
    escaped = str(value or "")
    replacements = {
        "\\": "\\\\",
        "{": "\\{",
        "}": "\\}",
        "&": "\\&",
        "%": "\\%",
        "_": "\\_",
        "#": "\\#",
        "$": "\\$"
    }
    for source, target in replacements.items():
        escaped = escaped.replace(source, target)
    return escaped.strip()

def _parse_bibtex_authors(authors: str) -> List[str]:
    raw = str(authors or "").strip()
    if not raw:
        return []
    if re.search(r"\s+and\s+|;", raw, flags=re.IGNORECASE):
        parts = re.split(r"\s+and\s+|;", raw, flags=re.IGNORECASE)
    else:
        parts = raw.split(",")
    return [part.strip() for part in parts if part and part.strip()]

def _format_bibtex_authors(authors: str) -> str:
    parsed_authors = _parse_bibtex_authors(authors)
    return " and ".join(parsed_authors) if parsed_authors else "Unknown"

def _build_bibtex_entry(payload) -> str:
    metadata = payload.model_dump()
    citation_key = _trim_text(payload.citation_key, 120) or generate_citation_key(metadata)
    entry_type = "article" if _trim_text(payload.publication_venue, 300) else "misc"
    fields = [
        ("author", _format_bibtex_authors(payload.authors)),
        ("title", payload.title or "Untitled"),
        ("year", _extract_citation_year(payload.year)),
    ]
    venue = _trim_text(payload.publication_venue, 300)
    if venue:
        fields.append(("journal", venue))
    doi = _clean_doi(payload.doi)
    if doi:
        fields.append(("doi", doi))
    url = _trim_text(payload.paper_url or payload.source_url, 1200)
    if url:
        fields.append(("url", url))

    rendered_fields = ",\n".join(
        f"  {name} = {{{_escape_bibtex_value(value)}}}" for name, value in fields if str(value or "").strip()
    )
    return f"@{entry_type}{{{citation_key},\n{rendered_fields}\n}}"

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

def _validate_project_fields(project_name: str, target_title: str, target_abstract: str, target_current_content: str):
    cleaned = {
        "project_name": _trim_text(project_name, MAX_PROJECT_NAME_LENGTH),
        "target_title": _trim_text(target_title, MAX_TARGET_TITLE_LENGTH),
        "target_abstract": _trim_text(target_abstract, MAX_TARGET_ABSTRACT_LENGTH),
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
        paper.current_content = _trim_text(_normalize_paper_current_content(paper.current_content), MAX_PAPER_CURRENT_CONTENT_LENGTH)
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
        paper.zotero_has_pdf_attachment = bool(paper.zotero_has_pdf_attachment)
        paper.zotero_has_fulltext = bool(paper.zotero_has_fulltext)
        paper.citation_key = _trim_text(paper.citation_key, 120) or generate_citation_key(paper.model_dump())
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
    current_content: str = ""
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
    zotero_has_pdf_attachment: bool = False
    zotero_has_fulltext: bool = False
    citation_key: str = ""
    similarity_pending: bool = False
    # --- 新增：允许接收并保存前端传来的 384 维 Embedding 向量 ---
    network_vec: Optional[List[float]] = None

class MergeRequest(BaseModel):
    new_papers: List[PaperItem]

class ProjectCreate(BaseModel):
    user_id: int
    project_name: str
    target_title: str
    target_abstract: str
    target_current_content: str = ""

class ProjectUpdate(BaseModel): 
    project_name: str
    target_title: str
    target_abstract: str
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

class ZoteroUploadRequest(BaseModel):
    papers: List[PaperItem]
    zotero_user_id: str = ""
    zotero_api_key: str = ""
    collection_key: str = ""
    skip_library_dedupe: bool = False

class ZoteroPreviewRequest(BaseModel):
    papers: List[PaperItem]
    zotero_user_id: str = ""
    zotero_api_key: str = ""
    collection_key: str = ""

class ZoteroHydrateRequest(BaseModel):
    papers: List[PaperItem]
    zotero_user_id: str = ""
    zotero_api_key: str = ""

class BibtexExportRequest(BaseModel):
    title: str = ""
    authors: str = ""
    year: str = ""
    doi: str = ""
    paper_url: str = ""
    source_url: str = ""
    publication_venue: str = ""
    citation_key: str = ""

class SettingsPayload(BaseModel):
    llm_provider: str = "groq"
    llm_api_key: str = ""
    openalex_api_key: str = ""
    contact_email: str = ""
    zotero_user_id: str = ""
    zotero_api_key: str = ""
    zotero_collection_key: str = ""

class LlmProxyRequest(BaseModel):
    prompt: str
    temperature: float = 0.2
    json_mode: bool = False

class LiteratureWatchRequest(BaseModel):
    mode: str = "target"
    lookback_window: str = "3m"
    limit: int = 12
    discipline: str = ""
    scholar_names: List[str] = Field(default_factory=list)

def _clean_doi(raw_value: Optional[str]) -> str:
    if not raw_value:
        return ""
    value = raw_value.strip()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^doi:\s*", "", value, flags=re.IGNORECASE)
    return value.strip()

def _apply_runtime_defaults_to_lookup(payload):
    payload.openalex_api_key = _trim_text(payload.openalex_api_key or _env_value("STARMAP_OPENALEX_API_KEY"), 300)
    payload.contact_email = _trim_text(payload.contact_email or _env_value("STARMAP_CONTACT_EMAIL"), MAX_LOOKUP_EMAIL_LENGTH)
    return payload

def _tokenize_literature_watch_text(value: str) -> List[str]:
    return [
        token for token in re.findall(r"[A-Za-z0-9]+", str(value or "").lower())
        if len(token) >= 3 and token not in LITERATURE_WATCH_STOPWORDS
    ]

def _normalize_watch_discipline(raw_value: str) -> str:
    key = str(raw_value or "").strip().lower()
    return key if key in LITERATURE_WATCH_DISCIPLINES else DEFAULT_LITERATURE_WATCH_DISCIPLINE

def _discipline_config(raw_value: str) -> dict:
    return LITERATURE_WATCH_DISCIPLINES[_normalize_watch_discipline(raw_value)]

def _normalize_watch_mode(raw_value: str) -> str:
    mode = str(raw_value or "target").strip().lower()
    return mode if mode in {"target", "scholar"} else "target"

def _extract_json_payload_from_text(text: str) -> str:
    source = str(text or "").strip()
    if not source:
        raise ValueError("Model returned empty text.")
    fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", source, re.IGNORECASE)
    if fenced_match and fenced_match.group(1):
        return fenced_match.group(1).strip()
    start_candidates = [index for index in (source.find("{"), source.find("[")) if index >= 0]
    return source[min(start_candidates):].strip() if start_candidates else source

def _parse_llm_json_payload(text: str):
    raw = _extract_json_payload_from_text(text)
    attempts = [
        raw,
        re.sub(r",\s*([}\]])", r"\1", raw),
        re.sub(r",\s*([}\]])", r"\1", raw.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"'))
    ]
    for candidate in attempts:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise ValueError("The model did not return valid JSON.")

def _paper_identity_key(paper: dict) -> str:
    doi = _clean_doi((paper or {}).get("doi"))
    if doi:
        return f"doi:{doi.lower()}"
    openalex_id = str((paper or {}).get("openalex_id") or "").strip()
    if openalex_id:
        return f"openalex:{openalex_id.lower()}"
    title = _collapse_whitespace(str((paper or {}).get("title") or "")).lower()
    year = _collapse_whitespace(str((paper or {}).get("year") or ""))
    return f"title:{title}|year:{year}"

def _normalize_title_signature(title: str) -> str:
    tokens = [token for token in re.findall(r"[A-Za-z0-9]+", str(title or "").lower()) if token and token not in CITATION_KEY_STOPWORDS]
    return " ".join(tokens)

def _paper_author_year_signature(paper: dict) -> str:
    title_sig = _normalize_title_signature((paper or {}).get("title"))
    first_author = _extract_first_author_last_name((paper or {}).get("authors", "")).lower()
    year = _extract_citation_year((paper or {}).get("year", ""))
    return f"tay:{title_sig}|{first_author}|{year}"

def _paper_identity_signatures(paper: dict) -> List[str]:
    signatures: List[str] = []
    doi = _clean_doi((paper or {}).get("doi"))
    if doi:
        signatures.append(f"doi:{doi.lower()}")
    openalex_id = str((paper or {}).get("openalex_id") or "").strip().lower()
    if openalex_id:
        signatures.append(f"openalex:{openalex_id}")
    title_sig = _normalize_title_signature((paper or {}).get("title"))
    if title_sig:
        signatures.append(f"title:{title_sig}")
        year = _extract_citation_year((paper or {}).get("year", ""))
        if year != "Unknown":
            signatures.append(f"title_year:{title_sig}|{year}")
    author_year = _paper_author_year_signature(paper)
    if author_year:
        signatures.append(author_year)
    seen = []
    for signature in signatures:
        if signature and signature not in seen:
            seen.append(signature)
    return seen

def _normalize_watch_range(raw_value: str) -> Tuple[str, str, str, int]:
    normalized = str(raw_value or "3m").strip().lower()
    today = date.today()
    if normalized == "3y":
        days = 365 * 3
        label = "Past 3 years"
    elif normalized == "1y":
        days = 365
        label = "Past 1 year"
    else:
        normalized = "3m"
        days = 92
        label = "Past 3 months"
    start = (today - timedelta(days=days)).isoformat()
    end = today.isoformat()
    return normalized, label, start, days

def _get_project_watch_context(project_data: dict, discipline: str) -> dict:
    top_papers = json.loads(_scrub_top_papers_json(project_data.get("top_papers"))) if project_data.get("top_papers") else []
    core_papers = [
        paper for paper in top_papers
        if str((paper or {}).get("status") or "").strip() == "Core"
    ]
    core_papers.sort(key=lambda paper: float((paper or {}).get("similarity") or 0), reverse=True)
    return {
        "target_title": _trim_text(project_data.get("target_title"), MAX_TARGET_TITLE_LENGTH),
        "target_abstract": _trim_text(project_data.get("target_abstract"), MAX_TARGET_ABSTRACT_LENGTH),
        "top_papers": top_papers,
        "core_papers": core_papers[:50],
        "discipline": _normalize_watch_discipline(discipline)
    }

def _build_watch_fallback_strategy(context: dict) -> dict:
    weighted_terms: Dict[str, float] = {}
    discipline = _discipline_config(context.get("discipline", ""))

    def add_weighted(text: str, weight: float):
        for token in _tokenize_literature_watch_text(text):
            weighted_terms[token] = weighted_terms.get(token, 0.0) + weight

    add_weighted(context.get("target_title", ""), 5.0)
    add_weighted(context.get("target_abstract", ""), 3.0)
    for keyword in discipline.get("venue_keywords", []):
        add_weighted(keyword, 1.5)
    for paper in context.get("core_papers", []):
        add_weighted(paper.get("title", ""), 2.0)
        add_weighted(_trim_text(paper.get("abstract"), 240), 1.0)

    ranked_terms = [term for term, _ in sorted(weighted_terms.items(), key=lambda item: item[1], reverse=True)]
    top_terms = ranked_terms[:8]
    queries: List[str] = []
    target_title = _collapse_whitespace(context.get("target_title", ""))
    if target_title:
        queries.append(target_title[:120])
    for index in range(0, min(len(top_terms), 6), 2):
        phrase = " ".join(top_terms[index:index + 2]).strip()
        if phrase and phrase.lower() not in {query.lower() for query in queries}:
            queries.append(phrase[:90])
    if not queries:
        queries.append("recent research")
    focus_tokens = top_terms[:4]
    focus_phrase = " / ".join(token.title() for token in focus_tokens) if focus_tokens else (target_title[:80] or "Target Thesis Watch")
    summary = "Built from your target thesis, abstract, and top Core papers without an LLM-generated search plan."
    return {
        "mode": "fallback",
        "focus_phrase": focus_phrase,
        "summary": summary,
        "facets": focus_tokens[:6],
        "queries": queries[:6],
        "discipline": discipline.get("label", "")
    }

def _build_literature_watch_prompt(context: dict) -> str:
    core_lines = []
    for index, paper in enumerate(context.get("core_papers", []), start=1):
        core_lines.append(
            f"{index}. Title: {paper.get('title', '')}\n"
            f"   Abstract snippet: {_trim_text(_collapse_whitespace(paper.get('abstract', '')), 180)}"
        )
    discipline_label = _discipline_config(context.get("discipline", "")).get("label", "Economics & Finance")
    return (
        "You are planning a literature watch for a research project.\n"
        "Use the target thesis, abstract, Core papers, and the declared discipline scope to infer the research direction.\n"
        "Return ONLY JSON matching this schema:\n"
        '{"focus_phrase":"...","summary":"...","facets":["..."],"queries":["..."]}\n'
        "Rules:\n"
        "- focus_phrase: 4-10 words, readable, specific, no slash-separated fragments.\n"
        "- summary: 1-2 sentences, clearly describing the thesis direction.\n"
        "- facets: 4-8 short research facets.\n"
        "- queries: 4-6 concise scholarly search phrases, each 3-8 words, suitable for OpenAlex.\n\n"
        f"Discipline scope:\n{discipline_label}\n\n"
        f"Target thesis title:\n{context.get('target_title', '')}\n\n"
        f"Target thesis abstract:\n{_trim_text(context.get('target_abstract', ''), 1800)}\n\n"
        "Top Core papers:\n"
        f"{chr(10).join(core_lines) if core_lines else 'No Core papers yet. Use the thesis and abstract only.'}"
    )

def _build_literature_watch_strategy(context: dict) -> dict:
    try:
        parsed = _parse_llm_json_payload(_call_llm_from_env(_build_literature_watch_prompt(context), temperature=0.15, json_mode=True))
        focus_phrase = _collapse_whitespace(parsed.get("focus_phrase") or context.get("target_title") or "Target Thesis Watch")[:120]
        summary = _trim_text(_collapse_whitespace(parsed.get("summary") or ""), 600)
        facets = [
            _trim_text(_collapse_whitespace(item), 80)
            for item in (parsed.get("facets") or [])
            if _trim_text(_collapse_whitespace(item), 80)
        ][:8]
        queries = [
            _trim_text(_collapse_whitespace(item), 90)
            for item in (parsed.get("queries") or [])
            if _trim_text(_collapse_whitespace(item), 90)
        ][:6]
        if not queries:
            raise ValueError("No queries returned.")
        return {
            "mode": "llm",
            "focus_phrase": focus_phrase or "Target Thesis Watch",
            "summary": summary or "Generated from your thesis, abstract, and top Core papers.",
            "facets": facets,
            "queries": queries,
            "discipline": _discipline_config(context.get("discipline", "")).get("label", "")
        }
    except Exception:
        return _build_watch_fallback_strategy(context)

def _make_watch_lookup_payload() -> PaperLookupRequest:
    payload = PaperLookupRequest(title="watch", doi="", year="", authors="")
    return _apply_runtime_defaults_to_lookup(payload)

def _search_openalex_recent_works(query: str, lookup_payload: PaperLookupRequest, start_date: str, end_date: str, per_page: int = 18) -> List[dict]:
    params = {
        "search": query,
        "per_page": per_page,
        "filter": f"from_publication_date:{start_date},to_publication_date:{end_date}",
    }
    if lookup_payload.openalex_api_key:
        params["api_key"] = lookup_payload.openalex_api_key
    url = _build_url("https://api.openalex.org/works", params)
    results = (_http_get_json(url, lookup_payload.contact_email) or {}).get("results") or []
    papers = []
    for work in results:
        parsed = _parse_openalex_work(work)
        if not parsed:
            continue
        parsed["publication_date"] = _trim_text(work.get("publication_date"), 20)
        parsed["matched_query"] = query
        papers.append(parsed)
    return papers

def _normalize_person_name(value: str) -> str:
    text = _collapse_whitespace(str(value or ""))
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("’", "'").replace("`", "'")
    text = re.sub(r"[^A-Za-z0-9\s'\-]", " ", text)
    return _collapse_whitespace(text).lower()

def _person_name_tokens(value: str) -> List[str]:
    normalized = _normalize_person_name(value)
    if not normalized:
        return []
    cleaned = normalized.replace("'", " ").replace("-", " ")
    return [
        token for token in cleaned.split()
        if token and token not in {"jr", "sr", "ii", "iii", "iv"}
    ]

def _person_name_initials(tokens: List[str]) -> str:
    return "".join(token[:1] for token in tokens if token)

def _person_first_last(tokens: List[str]) -> Tuple[str, str]:
    if not tokens:
        return "", ""
    if len(tokens) == 1:
        return tokens[0], tokens[0]
    return tokens[0], tokens[-1]

def _person_core_signature(tokens: List[str]) -> str:
    if not tokens:
        return ""
    if len(tokens) == 1:
        return tokens[0]
    return f"{tokens[0]} {tokens[-1]}"

def _candidate_author_names(candidate: dict) -> List[str]:
    names: List[str] = []
    display_name = _trim_text((candidate or {}).get("display_name"), 160)
    if display_name:
        names.append(display_name)
    for alt_name in (candidate or {}).get("display_name_alternatives") or []:
        cleaned = _trim_text(alt_name, 160)
        if cleaned and cleaned not in names:
            names.append(cleaned)
    return names

def _author_name_similarity_score(candidate_name: str, scholar_name: str) -> float:
    requested_tokens = _person_name_tokens(scholar_name)
    candidate_tokens = _person_name_tokens(candidate_name)
    if not requested_tokens or not candidate_tokens:
        return 0.0

    requested_norm = " ".join(requested_tokens)
    candidate_norm = " ".join(candidate_tokens)
    requested_first, requested_last = _person_first_last(requested_tokens)
    candidate_first, candidate_last = _person_first_last(candidate_tokens)
    requested_initials = _person_name_initials(requested_tokens)
    candidate_initials = _person_name_initials(candidate_tokens)
    requested_core = _person_core_signature(requested_tokens)
    candidate_core = _person_core_signature(candidate_tokens)

    score = 0.0
    if requested_norm == candidate_norm:
        score += 220.0
    if requested_core and requested_core == candidate_core:
        score += 110.0
    if requested_last and requested_last == candidate_last:
        score += 90.0
    if requested_first and requested_first == candidate_first:
        score += 75.0
    elif requested_first[:1] and requested_first[:1] == candidate_first[:1]:
        score += 42.0
    if requested_initials and requested_initials == candidate_initials:
        score += 24.0
    if requested_norm and candidate_norm and (requested_norm in candidate_norm or candidate_norm in requested_norm):
        score += 35.0

    requested_token_set = set(requested_tokens)
    candidate_token_set = set(candidate_tokens)
    overlap = len(requested_token_set & candidate_token_set)
    score += (overlap / max(len(requested_token_set), 1)) * 65.0
    score += SequenceMatcher(None, requested_norm, candidate_norm).ratio() * 55.0
    return score

def _build_author_search_queries(scholar_name: str) -> List[str]:
    safe_name = _trim_text(_collapse_whitespace(scholar_name), 120)
    if not safe_name:
        return []
    tokens = _person_name_tokens(safe_name)
    variants: List[str] = []

    def add_variant(value: str):
        cleaned = _trim_text(_collapse_whitespace(value), 120)
        if cleaned and cleaned not in variants:
            variants.append(cleaned)

    add_variant(safe_name)
    normalized = _normalize_person_name(safe_name)
    if normalized and normalized != safe_name.lower():
        add_variant(normalized)
    if len(tokens) >= 2:
        add_variant(f"{tokens[0]} {tokens[-1]}")
        non_initial_middle = [token for token in tokens[1:-1] if len(token) > 1]
        if non_initial_middle:
            add_variant(" ".join([tokens[0], *non_initial_middle, tokens[-1]]))
        middle_initials = " ".join(token[:1] for token in tokens[1:-1] if token)
        if middle_initials:
            add_variant(f"{tokens[0]} {middle_initials} {tokens[-1]}")
    return variants[:4]

def _best_author_match(candidates: List[dict], scholar_name: str) -> Optional[dict]:
    requested_tokens = _person_name_tokens(scholar_name)
    if not requested_tokens:
        return None
    requested_last = requested_tokens[-1]

    ranked_candidates = []
    for candidate in candidates or []:
        candidate_names = _candidate_author_names(candidate)
        if not candidate_names:
            continue
        best_name = ""
        best_score = 0.0
        for candidate_name in candidate_names:
            score = _author_name_similarity_score(candidate_name, scholar_name)
            if score > best_score:
                best_score = score
                best_name = candidate_name
        if not best_name:
            continue
        works_count = int((candidate or {}).get("works_count") or 0)
        cited_by_count = int((candidate or {}).get("cited_by_count") or 0)
        ranked_candidates.append((
            best_score,
            works_count,
            cited_by_count,
            best_name,
            candidate
        ))

    if not ranked_candidates:
        return None

    ranked_candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    best_score, _, _, best_name, best_candidate = ranked_candidates[0]
    best_last = _person_name_tokens(best_name)[-1] if _person_name_tokens(best_name) else ""
    same_last_name = bool(requested_last and best_last and requested_last == best_last)
    if best_score < 120:
        return None
    if not same_last_name and best_score < 175:
        return None
    return {
        **best_candidate,
        "_match_score": round(best_score, 2),
        "_matched_name": best_name
    }

def _resolve_openalex_author(scholar_name: str, lookup_payload: PaperLookupRequest) -> Optional[dict]:
    safe_name = _trim_text(_collapse_whitespace(scholar_name), 120)
    if not safe_name:
        return None
    candidates_by_id: Dict[str, dict] = {}
    for query in _build_author_search_queries(safe_name):
        params = {"search": query, "per_page": 10}
        if lookup_payload.openalex_api_key:
            params["api_key"] = lookup_payload.openalex_api_key
        url = _build_url("https://api.openalex.org/authors", params)
        results = (_http_get_json(url, lookup_payload.contact_email) or {}).get("results") or []
        for result in results:
            candidate_id = str((result or {}).get("id") or "").strip() or f"{result.get('display_name', '')}::{len(candidates_by_id)}"
            if candidate_id not in candidates_by_id:
                candidates_by_id[candidate_id] = result
                continue
            existing = candidates_by_id[candidate_id]
            merged_alt_names = []
            for name in list((existing or {}).get("display_name_alternatives") or []) + list((result or {}).get("display_name_alternatives") or []):
                cleaned = _trim_text(name, 160)
                if cleaned and cleaned not in merged_alt_names:
                    merged_alt_names.append(cleaned)
            if merged_alt_names:
                existing["display_name_alternatives"] = merged_alt_names
    best = _best_author_match(list(candidates_by_id.values()), safe_name)
    if not best:
        return None
    return {
        "id": best.get("id", ""),
        "display_name": best.get("display_name") or safe_name,
        "works_count": best.get("works_count") or 0,
        "match_score": best.get("_match_score") or 0,
        "matched_name": best.get("_matched_name") or (best.get("display_name") or safe_name),
        "requested_name": safe_name
    }

def _fetch_recent_works_for_author(author: dict, lookup_payload: PaperLookupRequest, start_date: str, end_date: str, per_page: int = 18) -> List[dict]:
    author_id = _extract_openalex_short_id(author.get("id", ""))
    if not author_id:
        return []
    params = {
        "per_page": per_page,
        "filter": f"author.id:{author_id},from_publication_date:{start_date},to_publication_date:{end_date}",
        "sort": "publication_date:desc"
    }
    if lookup_payload.openalex_api_key:
        params["api_key"] = lookup_payload.openalex_api_key
    url = _build_url("https://api.openalex.org/works", params)
    results = (_http_get_json(url, lookup_payload.contact_email) or {}).get("results") or []
    papers = []
    for work in results:
        parsed = _parse_openalex_work(work)
        if not parsed:
            continue
        parsed["publication_date"] = _trim_text(work.get("publication_date"), 20)
        parsed["source_scholar"] = author.get("display_name") or ""
        papers.append(parsed)
    return papers

def _build_watch_token_weights(context: dict, strategy: dict) -> Dict[str, float]:
    weights: Dict[str, float] = {}

    def add_tokens(text: str, weight: float):
        for token in _tokenize_literature_watch_text(text):
            weights[token] = weights.get(token, 0.0) + weight

    add_tokens(context.get("target_title", ""), 5.5)
    add_tokens(context.get("target_abstract", ""), 3.5)
    add_tokens(strategy.get("focus_phrase", ""), 4.0)
    for facet in strategy.get("facets", []):
        add_tokens(facet, 3.0)
    for query in strategy.get("queries", []):
        add_tokens(query, 3.5)
    for paper in context.get("core_papers", []):
        add_tokens(paper.get("title", ""), 2.0)
        add_tokens(_trim_text(paper.get("abstract"), 180), 1.0)
    return weights

def _query_match_score(query: str, text: str) -> float:
    normalized_query = _collapse_whitespace(query).lower()
    normalized_text = _collapse_whitespace(text).lower()
    if not normalized_query or not normalized_text:
        return 0.0
    if normalized_query in normalized_text:
        return 1.0
    query_tokens = [token for token in _tokenize_literature_watch_text(normalized_query) if token]
    if not query_tokens:
        return 0.0
    text_tokens = set(_tokenize_literature_watch_text(normalized_text))
    overlap = sum(1 for token in query_tokens if token in text_tokens)
    return overlap / max(len(set(query_tokens)), 1)

def _candidate_relevance_score(candidate: dict, token_weights: Dict[str, float], strategy: dict) -> Tuple[float, List[str]]:
    candidate_text = " ".join([
        str(candidate.get("title") or ""),
        str(candidate.get("abstract") or ""),
        str(candidate.get("publication_venue") or "")
    ])
    candidate_tokens = set(_tokenize_literature_watch_text(candidate_text))
    total_weight = sum(token_weights.values()) or 1.0
    overlap_weight = sum(weight for token, weight in token_weights.items() if token in candidate_tokens)
    lexical_score = min(overlap_weight / total_weight, 1.0)

    query_scores = []
    for query in strategy.get("queries", []):
        score = _query_match_score(query, candidate_text)
        query_scores.append((query, score))
    query_scores.sort(key=lambda item: item[1], reverse=True)
    matched_queries = [query for query, score in query_scores if score >= 0.45][:3]
    best_query_score = query_scores[0][1] if query_scores else 0.0

    relevance = min((lexical_score * 0.78) + (best_query_score * 0.22), 1.0)
    return relevance, matched_queries

def _venue_discipline_bonus(candidate: dict, discipline_key: str) -> float:
    venue_text = _collapse_whitespace(str((candidate or {}).get("publication_venue") or "")).lower()
    if not venue_text:
        return 0.0
    config = _discipline_config(discipline_key)
    if any(top_venue in venue_text for top_venue in config.get("top_venues", [])):
        return 0.22
    if any(keyword in venue_text for keyword in config.get("venue_keywords", [])):
        return 0.10
    return 0.0

def _candidate_quality_score(candidate: dict, discipline_key: str) -> float:
    citation_count = candidate.get("citation_count") or 0
    fwci_value = candidate.get("fwci")
    citation_score = min((math.log1p(max(citation_count, 0)) / math.log1p(500)), 1.0) if citation_count else 0.0
    fwci_score = 0.0
    try:
        numeric_fwci = float(fwci_value)
        if numeric_fwci > 0:
            fwci_score = min((math.log1p(numeric_fwci) / math.log1p(5)), 1.0)
    except Exception:
        fwci_score = 0.0
    completeness_bonus = 0.0
    if candidate.get("publication_venue"):
        completeness_bonus += 0.08
    if candidate.get("doi"):
        completeness_bonus += 0.05
    if candidate.get("abstract"):
        completeness_bonus += 0.07
    venue_bonus = _venue_discipline_bonus(candidate, discipline_key)
    return min((citation_score * 0.58) + (fwci_score * 0.12) + completeness_bonus + venue_bonus, 1.0)

def _candidate_freshness_score(candidate: dict, window_days: int) -> float:
    publication_date = str(candidate.get("publication_date") or "").strip()
    if publication_date:
        try:
            published = date.fromisoformat(publication_date)
            age_days = max((date.today() - published).days, 0)
            return max(0.0, min(1.0, 1 - (age_days / max(window_days, 1))))
        except ValueError:
            pass
    try:
        year = int(str(candidate.get("year") or "").strip())
        if year > 0:
            published = date(year, 1, 1)
            age_days = max((date.today() - published).days, 0)
            return max(0.0, min(1.0, 1 - (age_days / max(window_days, 1))))
    except Exception:
        pass
    return 0.0

def _candidate_completeness_rank(candidate: dict) -> Tuple[int, int, int]:
    return (
        1 if candidate.get("abstract") else 0,
        1 if candidate.get("doi") else 0,
        int(candidate.get("citation_count") or 0)
    )

def _merge_watch_candidate(preferred: dict, incoming: dict) -> dict:
    merged = dict(preferred)
    if _candidate_completeness_rank(incoming) > _candidate_completeness_rank(preferred):
        merged.update(incoming)
    merged_queries = list(dict.fromkeys((preferred.get("matched_queries") or []) + (incoming.get("matched_queries") or [])))
    merged["matched_queries"] = merged_queries
    return merged

def _semantic_watch_rerank(context: dict, strategy: dict, candidates: List[dict]) -> Dict[str, float]:
    if not candidates:
        return {}
    try:
        shortlist = candidates[:24]
        candidate_payload = [
            {
                "id": candidate.get("watch_candidate_id"),
                "title": candidate.get("title", ""),
                "abstract": _trim_text(_collapse_whitespace(candidate.get("abstract", "")), 260),
                "venue": candidate.get("publication_venue", ""),
                "year": candidate.get("year", ""),
                "citation_count": candidate.get("citation_count") or 0,
            }
            for candidate in shortlist
        ]
        core_titles = [paper.get("title", "") for paper in context.get("core_papers", [])[:12]]
        discipline_label = _discipline_config(context.get("discipline", "")).get("label", "Economics & Finance")
        prompt = (
            "You are reranking new-paper candidates for a project literature watch.\n"
            "Judge semantic relevance to the target thesis using the thesis, abstract, declared discipline, and Core-paper titles.\n"
            "Return ONLY JSON with this schema:\n"
            '{"ranked":[{"id":"...","relevance":0.0,"reason":"..."}]}\n'
            "Rules:\n"
            "- relevance must be between 0 and 1.\n"
            "- prioritize tight topical fit to the target thesis.\n"
            "- penalize papers that are only loosely related because of generic macro or finance vocabulary.\n"
            "- return at most 15 candidates.\n\n"
            f"Discipline:\n{discipline_label}\n\n"
            f"Target thesis title:\n{context.get('target_title', '')}\n\n"
            f"Target thesis abstract:\n{_trim_text(context.get('target_abstract', ''), 1500)}\n\n"
            f"Core paper titles:\n{json.dumps(core_titles, ensure_ascii=False)}\n\n"
            f"Search facets:\n{json.dumps(strategy.get('facets') or [], ensure_ascii=False)}\n\n"
            f"Candidate papers:\n{json.dumps(candidate_payload, ensure_ascii=False)}"
        )
        parsed = _parse_llm_json_payload(_call_llm_from_env(prompt, temperature=0.05, json_mode=True))
        ranked = parsed.get("ranked") or []
        scores: Dict[str, float] = {}
        for item in ranked:
            candidate_id = str((item or {}).get("id") or "").strip()
            if not candidate_id:
                continue
            try:
                score = float((item or {}).get("relevance"))
            except Exception:
                continue
            scores[candidate_id] = max(0.0, min(score, 1.0))
        return scores
    except Exception:
        return {}

def _apply_runtime_defaults_to_zotero(payload: ZoteroSyncRequest):
    payload.zotero_user_id = _trim_text(payload.zotero_user_id or _env_value("STARMAP_ZOTERO_USER_ID"), 120)
    payload.zotero_api_key = _trim_text(payload.zotero_api_key or _env_value("STARMAP_ZOTERO_API_KEY"), 300)
    payload.collection_key = _trim_text(payload.collection_key or _env_value("STARMAP_ZOTERO_COLLECTION_KEY"), 120)
    return payload

def _http_post_json(url: str, body: dict, headers: Optional[dict] = None, timeout: int = 90):
    encoded = json.dumps(body).encode("utf-8")
    req = request.Request(url, data=encoded, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        if value:
            req.add_header(key, value)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(status_code=exc.code, detail=detail or f"Upstream request failed with status {exc.code}")
    except error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach upstream provider: {exc.reason}")
    except TimeoutError:
        raise HTTPException(status_code=503, detail="The upstream provider timed out. Please try again in a moment.")

def _call_llm_from_env(prompt: str, temperature: float = 0.2, json_mode: bool = False) -> str:
    provider = (_env_value("STARMAP_LLM_PROVIDER", "groq") or "groq").lower()
    api_key = _env_value("STARMAP_LLM_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="LLM API key is not configured in .env")

    if provider in {"openai", "deepseek", "groq"}:
        if provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            model = "gpt-4o-mini"
        elif provider == "deepseek":
            url = "https://api.deepseek.com/chat/completions"
            model = "deepseek-chat"
        else:
            url = "https://api.groq.com/openai/v1/chat/completions"
            model = "llama-3.1-8b-instant"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = _http_post_json(url, payload, {"Authorization": f"Bearer {api_key}"})
        return (((response.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()

    if provider == "gemini":
        model = GEMINI_MODEL
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={parse.quote(api_key, safe='')}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                **({"response_mime_type": "application/json"} if json_mode else {}),
            }
        }
        response = _http_post_json(url, payload)
        return ((((response.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0].get("text") or "").strip()

    raise HTTPException(status_code=400, detail="Unsupported LLM provider configured in .env")

def _status_result(name: str, state: str, detail: str, configured: bool) -> dict:
    return {
        "name": name,
        "state": state,
        "configured": configured,
        "detail": detail,
    }

def _probe_llm_status() -> dict:
    provider = (_env_value("STARMAP_LLM_PROVIDER", "groq") or "groq").lower()
    api_key = _env_value("STARMAP_LLM_API_KEY")
    if not api_key:
        return _status_result("LLM", "missing", "LLM API key is not configured.", False)

    try:
        prompt = "Reply with OK only."
        if provider in {"openai", "deepseek", "groq"}:
            if provider == "openai":
                url = "https://api.openai.com/v1/chat/completions"
                model = "gpt-4o-mini"
            elif provider == "deepseek":
                url = "https://api.deepseek.com/chat/completions"
                model = "deepseek-chat"
            else:
                url = "https://api.groq.com/openai/v1/chat/completions"
                model = "llama-3.1-8b-instant"
            _http_post_json(
                url,
                {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0},
                {"Authorization": f"Bearer {api_key}"},
                timeout=12
            )
        elif provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={parse.quote(api_key, safe='')}"
            _http_post_json(
                url,
                {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0}},
                timeout=12
            )
        else:
            return _status_result("LLM", "error", f"Unsupported provider: {provider}", True)
        return _status_result("LLM", "ready", f"{provider} reachable ({GEMINI_MODEL if provider == 'gemini' else provider}).", True)
    except HTTPException as exc:
        return _status_result("LLM", "error", f"{provider} check failed: {str(exc.detail)[:180]}", True)

def _probe_scholar_status() -> dict:
    api_key = _env_value("STARMAP_OPENALEX_API_KEY")
    contact_email = _env_value("STARMAP_CONTACT_EMAIL")
    if not api_key and not contact_email:
        return _status_result("Scholar API", "missing", "OpenAlex API key / contact email not configured.", False)
    try:
        url = _build_url(
            "https://api.openalex.org/works",
            {"per_page": 1, "filter": "publication_year:2024", "api_key": api_key}
        )
        _http_get_json(url, contact_email)
        return _status_result("Scholar API", "ready", "OpenAlex reachable.", True)
    except HTTPException as exc:
        return _status_result("Scholar API", "error", f"OpenAlex check failed: {str(exc.detail)[:180]}", bool(api_key or contact_email))

def _probe_zotero_status() -> dict:
    user_id = _env_value("STARMAP_ZOTERO_USER_ID")
    api_key = _env_value("STARMAP_ZOTERO_API_KEY")
    collection_key = _env_value("STARMAP_ZOTERO_COLLECTION_KEY")
    if not user_id or not api_key:
        return _status_result("Zotero", "missing", "Zotero User ID / API key not configured.", False)
    try:
        base_path = f"https://api.zotero.org/users/{parse.quote(user_id, safe='')}"
        path = f"{base_path}/collections/{parse.quote(collection_key, safe='')}/items/top" if collection_key else f"{base_path}/items/top"
        url = _build_url(path, {"limit": 1})
        _http_get_json(url, extra_headers={"Zotero-API-Key": api_key})
        return _status_result("Zotero", "ready", "Zotero reachable.", True)
    except HTTPException as exc:
        return _status_result("Zotero", "error", f"Zotero check failed: {str(exc.detail)[:180]}", True)

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
    last_error = None
    for _ in range(3):
        try:
            with request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except IncompleteRead as exc:
            last_error = exc
            partial = exc.partial.decode("utf-8", errors="ignore") if exc.partial else ""
            if partial:
                try:
                    return json.loads(partial)
                except json.JSONDecodeError:
                    pass
            continue
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise HTTPException(status_code=exc.code, detail=detail or f"External API request failed: {url}")
        except error.URLError as exc:
            last_error = exc
            continue
        except Exception as exc:
            if exc.__class__.__name__ == "IncompleteRead":
                last_error = exc
                partial = getattr(exc, "partial", b"")
                partial_text = partial.decode("utf-8", errors="ignore") if partial else ""
                if partial_text:
                    try:
                        return json.loads(partial_text)
                    except json.JSONDecodeError:
                        pass
                continue
            raise
    if isinstance(last_error, error.URLError):
        raise HTTPException(status_code=502, detail=f"External API unavailable: {last_error.reason}")
    if isinstance(last_error, IncompleteRead):
        raise HTTPException(status_code=502, detail=f"External API returned an incomplete response after retries: {url}")
    raise HTTPException(status_code=502, detail=f"External API unavailable: {url}")

def _http_get_json_with_meta(url: str, contact_email: str = "", extra_headers: Optional[dict] = None) -> Tuple[Any, Dict[str, str]]:
    headers = {"Accept": "application/json"}
    if contact_email:
        headers["User-Agent"] = f"StarMap System/1.0 (mailto:{contact_email})"
    if extra_headers:
        headers.update(extra_headers)
    req = request.Request(url, headers=headers)
    last_error = None
    for _ in range(3):
        try:
            with request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body), {key.lower(): value for key, value in resp.headers.items()}
        except IncompleteRead as exc:
            last_error = exc
            partial = exc.partial.decode("utf-8", errors="ignore") if exc.partial else ""
            if partial:
                try:
                    return json.loads(partial), {}
                except json.JSONDecodeError:
                    pass
            continue
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise HTTPException(status_code=exc.code, detail=detail or f"External API request failed: {url}")
        except error.URLError as exc:
            last_error = exc
            continue
        except Exception as exc:
            if exc.__class__.__name__ == "IncompleteRead":
                last_error = exc
                partial = getattr(exc, "partial", b"")
                partial_text = partial.decode("utf-8", errors="ignore") if partial else ""
                if partial_text:
                    try:
                        return json.loads(partial_text), {}
                    except json.JSONDecodeError:
                        pass
                continue
            raise
    if isinstance(last_error, error.URLError):
        raise HTTPException(status_code=502, detail=f"External API unavailable: {last_error.reason}")
    if isinstance(last_error, IncompleteRead):
        raise HTTPException(status_code=502, detail=f"External API returned an incomplete response after retries: {url}")
    raise HTTPException(status_code=502, detail=f"External API unavailable: {url}")

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

    return _attach_citation_key({
        "openalex_id": work.get("id", ""),
        "doi": _clean_doi(raw_doi),
        "paper_url": paper_url,
        "source_url": primary_location.get("landing_page_url") or best_oa_location.get("landing_page_url") or "",
        "publication_venue": source.get("display_name", ""),
        "publication_date": work.get("publication_date", ""),
        "citation_count": work.get("cited_by_count"),
        "fwci": work.get("fwci"),
        "arxiv_id": arxiv_id,
        "openalex_cited_by_api_url": work.get("cited_by_api_url", ""),
        "referenced_openalex_ids": work.get("referenced_works") or [],
        "abstract": abstract,
        "title": work.get("display_name") or work.get("title") or "",
        "year": str(work.get("publication_year") or ""),
        "authors": authors,
        "source": "OpenAlex"
    })

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
    return _attach_citation_key({
        "doi": doi,
        "paper_url": work.get("URL", ""),
        "source_url": work.get("URL", ""),
        "publication_venue": venue,
        "citation_count": work.get("is-referenced-by-count"),
        "crossref_url": work.get("URL", ""),
        "abstract": re.sub(r"<[^>]+>", "", work.get("abstract") or "").strip(),
        "title": title,
        "year": year,
        "authors": authors,
        "type": work.get("type", ""),
        "source": "Crossref"
    })

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

def _build_project_literature_watch(project_data: dict, request_payload: LiteratureWatchRequest) -> dict:
    discipline_key = _normalize_watch_discipline(request_payload.discipline)
    watch_mode = _normalize_watch_mode(request_payload.mode)
    context = _get_project_watch_context(project_data, discipline_key)
    strategy = _build_literature_watch_strategy(context)
    lookup_payload = _make_watch_lookup_payload()
    lookback_window, range_label, start_date, window_days = _normalize_watch_range(request_payload.lookback_window)
    recommendation_limit = max(3, min(int(request_payload.limit or 12), 30))
    existing_signatures = {
        signature
        for paper in context.get("top_papers", [])
        for signature in _paper_identity_signatures(paper)
    }
    token_weights = _build_watch_token_weights(context, strategy)

    candidates_by_key: Dict[str, dict] = {}
    signature_to_primary: Dict[str, str] = {}
    scholar_sources = []
    unresolved_scholars: List[str] = []
    resolved_scholars: List[dict] = []

    def register_candidate(candidate: dict, *, matched_query: str = "", source_scholar: str = ""):
        identity_signatures = _paper_identity_signatures(candidate)
        if any(signature in existing_signatures for signature in identity_signatures):
            return
        matched_primary = next((signature_to_primary[signature] for signature in identity_signatures if signature in signature_to_primary), None)
        incoming = {
            **candidate,
            "matched_queries": [matched_query] if matched_query else [],
            "source_scholar": source_scholar or candidate.get("source_scholar", "")
        }
        if matched_primary:
            merged = _merge_watch_candidate(candidates_by_key[matched_primary], incoming)
            if source_scholar and not merged.get("source_scholar"):
                merged["source_scholar"] = source_scholar
            candidates_by_key[matched_primary] = merged
            for signature in identity_signatures:
                signature_to_primary[signature] = matched_primary
            return
        primary_key = _paper_identity_key(candidate)
        incoming["watch_candidate_id"] = primary_key
        candidates_by_key[primary_key] = incoming
        for signature in identity_signatures:
            signature_to_primary[signature] = primary_key

    if watch_mode == "scholar":
        requested_scholars = []
        seen_scholars = set()
        for raw_name in request_payload.scholar_names or []:
            cleaned = _trim_text(_collapse_whitespace(raw_name), 120)
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if lowered in seen_scholars:
                continue
            seen_scholars.add(lowered)
            requested_scholars.append(cleaned)
            if len(requested_scholars) >= 20:
                break
        if not requested_scholars:
            raise HTTPException(status_code=422, detail="At least one scholar name is required for Scholar Watch.")

        for scholar_name in requested_scholars:
            author = _resolve_openalex_author(scholar_name, lookup_payload)
            if not author:
                unresolved_scholars.append(scholar_name)
                continue
            scholar_sources.append(author.get("display_name") or scholar_name)
            resolved_scholars.append({
                "requested": scholar_name,
                "resolved": author.get("display_name") or scholar_name,
                "matched_name": author.get("matched_name") or (author.get("display_name") or scholar_name),
                "match_score": author.get("match_score") or 0
            })
            for candidate in _fetch_recent_works_for_author(author, lookup_payload, start_date, date.today().isoformat(), per_page=18):
                register_candidate(candidate, source_scholar=author.get("display_name") or scholar_name)
    else:
        for query in strategy.get("queries", [])[:6]:
            for candidate in _search_openalex_recent_works(query, lookup_payload, start_date, date.today().isoformat(), per_page=18):
                register_candidate(candidate, matched_query=query)

    preliminary_candidates = []
    for candidate in candidates_by_key.values():
        relevance_score, matched_queries = _candidate_relevance_score(candidate, token_weights, strategy)
        quality_score = _candidate_quality_score(candidate, discipline_key)
        freshness_score = _candidate_freshness_score(candidate, window_days)
        lexical_threshold = 0.12 if watch_mode == "scholar" else 0.18
        if relevance_score < lexical_threshold:
            continue
        candidate["lexical_relevance_score"] = round(relevance_score, 3)
        candidate["quality_score"] = round(quality_score, 3)
        candidate["freshness_score"] = round(freshness_score, 3)
        candidate["matched_queries"] = matched_queries or candidate.get("matched_queries", [])[:3]
        preliminary_candidates.append(candidate)

    preliminary_candidates.sort(
        key=lambda item: (
            float(item.get("lexical_relevance_score") or 0),
            float(item.get("quality_score") or 0),
            float(item.get("citation_count") or 0)
        ),
        reverse=True
    )

    semantic_scores = _semantic_watch_rerank(context, strategy, preliminary_candidates)

    recommendations = []
    for candidate in preliminary_candidates:
        lexical_relevance = float(candidate.get("lexical_relevance_score") or 0)
        semantic_relevance = semantic_scores.get(candidate.get("watch_candidate_id"), lexical_relevance)
        final_relevance = min((semantic_relevance * 0.72) + (lexical_relevance * 0.28), 1.0) if semantic_scores else lexical_relevance
        threshold = (0.36 if semantic_scores else 0.22) if watch_mode == "scholar" else (0.42 if semantic_scores else 0.28)
        if final_relevance < threshold:
            continue
        watch_score = min((final_relevance * 0.65) + (float(candidate.get("quality_score") or 0) * 0.30) + (float(candidate.get("freshness_score") or 0) * 0.05), 1.0)
        candidate["semantic_relevance_score"] = round(semantic_relevance, 3)
        candidate["relevance_score"] = round(final_relevance, 3)
        candidate["watch_score"] = round(watch_score, 3)
        candidate["watch_reason"] = (
            f"Matched scholar {candidate.get('source_scholar')} and remained close to the target thesis."
            if watch_mode == "scholar" and candidate.get("source_scholar")
            else (
                f"Strongest query match: {candidate['matched_queries'][0]}"
                if candidate.get("matched_queries")
                else "Matched the target thesis and Core-paper signal."
            )
        )
        recommendations.append(candidate)

    recommendations.sort(
        key=lambda item: (
            float(item.get("watch_score") or 0),
            float(item.get("relevance_score") or 0),
            float(item.get("quality_score") or 0),
            float(item.get("citation_count") or 0)
        ),
        reverse=True
    )

    return {
        "mode": watch_mode,
        "range": lookback_window,
        "range_label": range_label,
        "discipline": {
            "key": discipline_key,
            "label": _discipline_config(discipline_key).get("label", discipline_key)
        },
        "source_summary": {
            "core_papers_used": len(context.get("core_papers", [])),
            "used_target_title": bool(context.get("target_title")),
            "used_target_abstract": bool(context.get("target_abstract"))
        },
        "query_strategy": strategy,
        "scholar_sources": scholar_sources[:20],
        "resolved_scholars": resolved_scholars[:20],
        "unresolved_scholars": unresolved_scholars[:20],
        "candidate_count": len(recommendations),
        "recommendations": recommendations[:recommendation_limit]
    }

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
    except Exception as exc:
        return {}, f"{fn.__name__} crashed: {exc}"

def _zotero_account_cache_key(payload: ZoteroSyncRequest) -> str:
    return _normalize_zotero_match_key(payload.zotero_user_id)

def _read_zotero_cache_state(account_key: str, collection_key: str) -> Optional[dict]:
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT account_key, collection_key, library_version, refreshed_at, full_refreshed_at FROM zotero_cache_state WHERE account_key = ? AND collection_key = ?",
        (account_key, collection_key)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def _write_zotero_cache_state(account_key: str, collection_key: str, library_version: int, refreshed_at: int, full_refreshed_at: Optional[int] = None):
    conn = _db_connect()
    cursor = conn.cursor()
    current = _read_zotero_cache_state(account_key, collection_key) or {}
    cursor.execute(
        '''INSERT INTO zotero_cache_state (account_key, collection_key, library_version, refreshed_at, full_refreshed_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(account_key, collection_key) DO UPDATE SET
               library_version = excluded.library_version,
               refreshed_at = excluded.refreshed_at,
               full_refreshed_at = excluded.full_refreshed_at''',
        (
            account_key,
            collection_key,
            int(library_version or 0),
            int(refreshed_at or 0),
            int(full_refreshed_at if full_refreshed_at is not None else current.get("full_refreshed_at") or refreshed_at or 0)
        )
    )
    conn.commit()
    conn.close()

def _load_cached_zotero_items(account_key: str, collection_key: str) -> List[dict]:
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT payload FROM zotero_cache_items WHERE account_key = ? AND collection_key = ? ORDER BY updated_at DESC, item_key ASC",
        (account_key, collection_key)
    )
    rows = cursor.fetchall()
    conn.close()
    items: List[dict] = []
    for (payload,) in rows:
        try:
            item = json.loads(payload)
        except Exception:
            continue
        if isinstance(item, dict):
            items.append(item)
    return items

def _replace_zotero_cache_items(account_key: str, collection_key: str, items: List[dict], library_version: int):
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM zotero_cache_items WHERE account_key = ? AND collection_key = ?",
        (account_key, collection_key)
    )
    now = _now_ts()
    for item in items:
        item_key = (item.get("key") or (item.get("data") or {}).get("key") or "").strip()
        if not item_key:
            continue
        version = int((item.get("version") or (item.get("data") or {}).get("version") or library_version or 0))
        cursor.execute(
            "INSERT OR REPLACE INTO zotero_cache_items (account_key, collection_key, item_key, version, payload, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (account_key, collection_key, item_key, version, json.dumps(item, ensure_ascii=False), now)
        )
    conn.commit()
    conn.close()

def _merge_zotero_cache_items(account_key: str, collection_key: str, items: List[dict], library_version: int):
    if not items:
        return
    conn = _db_connect()
    cursor = conn.cursor()
    now = _now_ts()
    for item in items:
        item_key = (item.get("key") or (item.get("data") or {}).get("key") or "").strip()
        if not item_key:
            continue
        deleted = bool(item.get("deleted") or (item.get("data") or {}).get("deleted"))
        if deleted:
            cursor.execute(
                "DELETE FROM zotero_cache_items WHERE account_key = ? AND collection_key = ? AND item_key = ?",
                (account_key, collection_key, item_key)
            )
            continue
        version = int((item.get("version") or (item.get("data") or {}).get("version") or library_version or 0))
        cursor.execute(
            "INSERT OR REPLACE INTO zotero_cache_items (account_key, collection_key, item_key, version, payload, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (account_key, collection_key, item_key, version, json.dumps(item, ensure_ascii=False), now)
        )
    conn.commit()
    conn.close()

def _read_zotero_collection_cache_state(account_key: str) -> Optional[dict]:
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT account_key, refreshed_at FROM zotero_collection_cache_state WHERE account_key = ?",
        (account_key,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def _load_cached_zotero_collections(account_key: str) -> List[dict]:
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT payload FROM zotero_collection_cache WHERE account_key = ? ORDER BY updated_at DESC, collection_key ASC",
        (account_key,)
    )
    rows = cursor.fetchall()
    conn.close()
    collections: List[dict] = []
    for (payload,) in rows:
        try:
            item = json.loads(payload)
        except Exception:
            continue
        if isinstance(item, dict):
            collections.append(item)
    return collections

def _replace_zotero_collections_cache(account_key: str, collections: List[dict]):
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM zotero_collection_cache WHERE account_key = ?", (account_key,))
    now = _now_ts()
    for item in collections:
        key = (item.get("key") or "").strip()
        if not key:
            continue
        cursor.execute(
            "INSERT OR REPLACE INTO zotero_collection_cache (account_key, collection_key, payload, updated_at) VALUES (?, ?, ?, ?)",
            (account_key, key, json.dumps(item, ensure_ascii=False), now)
        )
    cursor.execute(
        '''INSERT INTO zotero_collection_cache_state (account_key, refreshed_at)
           VALUES (?, ?)
           ON CONFLICT(account_key) DO UPDATE SET refreshed_at = excluded.refreshed_at''',
        (account_key, now)
    )
    conn.commit()
    conn.close()

def _extract_zotero_library_version(headers: Dict[str, str]) -> int:
    raw_value = headers.get("last-modified-version") or headers.get("last_modified_version") or headers.get("total-results-version") or "0"
    try:
        return int(raw_value)
    except Exception:
        return 0

def _fetch_zotero_items_from_api(payload: ZoteroSyncRequest, collection_key: str, since_version: int = 0) -> Tuple[List[dict], int]:
    user_id = payload.zotero_user_id.strip()
    api_key = payload.zotero_api_key.strip()
    base_path = f"https://api.zotero.org/users/{parse.quote(user_id, safe='')}"
    resource = f"/collections/{parse.quote(collection_key, safe='')}/items/top" if collection_key else "/items/top"
    headers = _build_zotero_headers(api_key)
    items: List[dict] = []
    start = 0
    latest_version = int(since_version or 0)

    while True:
        params = {"v": 3, "format": "json", "limit": ZOTERO_ITEM_PAGE_SIZE, "start": start}
        if since_version:
            params["since"] = since_version
        url = _build_url(f"{base_path}{resource}", params)
        batch, meta = _http_get_json_with_meta(url, extra_headers=headers)
        if not isinstance(batch, list) or not batch:
            latest_version = max(latest_version, _extract_zotero_library_version(meta))
            break
        latest_version = max(latest_version, _extract_zotero_library_version(meta))
        items.extend(batch)
        if len(batch) < ZOTERO_ITEM_PAGE_SIZE:
            break
        start += ZOTERO_ITEM_PAGE_SIZE
    return items, latest_version

def _fetch_zotero_items(payload: ZoteroSyncRequest, collection_key: Optional[str] = None) -> List[dict]:
    user_id = payload.zotero_user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Zotero User ID is required.")
    resolved_collection_key = payload.collection_key.strip() if collection_key is None else str(collection_key).strip()
    account_key = _zotero_account_cache_key(payload)
    state = _read_zotero_cache_state(account_key, resolved_collection_key)
    cached_items = _load_cached_zotero_items(account_key, resolved_collection_key) if state else []
    now = _now_ts()

    if state and cached_items and (now - int(state.get("refreshed_at") or 0) < ZOTERO_CACHE_TTL_SECONDS):
        return cached_items

    should_do_full_refresh = (
        not state
        or not cached_items
        or (now - int(state.get("full_refreshed_at") or 0) >= ZOTERO_FULL_SYNC_INTERVAL_SECONDS)
    )

    try:
        if should_do_full_refresh:
            fresh_items, latest_version = _fetch_zotero_items_from_api(payload, resolved_collection_key, since_version=0)
            _replace_zotero_cache_items(account_key, resolved_collection_key, fresh_items, latest_version)
            _write_zotero_cache_state(account_key, resolved_collection_key, latest_version, now, full_refreshed_at=now)
            return fresh_items

        delta_items, latest_version = _fetch_zotero_items_from_api(
            payload,
            resolved_collection_key,
            since_version=int(state.get("library_version") or 0)
        )
        _merge_zotero_cache_items(account_key, resolved_collection_key, delta_items, latest_version)
        _write_zotero_cache_state(
            account_key,
            resolved_collection_key,
            max(latest_version, int(state.get("library_version") or 0)),
            now,
            full_refreshed_at=int(state.get("full_refreshed_at") or 0)
        )
        return _load_cached_zotero_items(account_key, resolved_collection_key)
    except HTTPException:
        if cached_items:
            return cached_items
        raise

def _fetch_zotero_collections(payload: ZoteroSyncRequest) -> List[dict]:
    user_id = payload.zotero_user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Zotero User ID is required.")
    account_key = _zotero_account_cache_key(payload)
    state = _read_zotero_collection_cache_state(account_key)
    cached_collections = _load_cached_zotero_collections(account_key) if state else []
    now = _now_ts()
    if state and cached_collections and (now - int(state.get("refreshed_at") or 0) < ZOTERO_CACHE_TTL_SECONDS):
        return cached_collections

    api_key = payload.zotero_api_key.strip()
    base_path = f"https://api.zotero.org/users/{parse.quote(user_id, safe='')}/collections"
    headers = {
        "Zotero-API-Version": "3",
        "Accept": "application/json"
    }
    if api_key:
        headers["Zotero-API-Key"] = api_key

    try:
        collections = []
        start = 0
        limit = ZOTERO_COLLECTION_PAGE_SIZE
        while True:
            url = f"{base_path}?v=3&format=json&limit={limit}&start={start}"
            batch = _http_get_json(url, extra_headers=headers)
            if not isinstance(batch, list) or not batch:
                break
            collections.extend(batch)
            if len(batch) < limit:
                break
            start += limit
        _replace_zotero_collections_cache(account_key, collections)
        return collections
    except HTTPException:
        if cached_collections:
            return cached_collections
        raise

def _build_collection_options(collections: List[dict]) -> List[dict]:
    rows = []
    by_key = {}
    for collection in collections:
        key = collection.get("key") or ""
        data = collection.get("data") or {}
        by_key[key] = {
            "key": key,
            "name": data.get("name", key or "Unnamed Collection"),
            "parent": data.get("parentCollection") or "",
        }

    def build_label(key: str) -> str:
        node = by_key.get(key)
        if not node:
            return ""
        if not node["parent"]:
            return node["name"]
        parent_label = build_label(node["parent"])
        return f"{parent_label} / {node['name']}" if parent_label else node["name"]

    for key, node in by_key.items():
        rows.append({
            "key": key,
            "name": node["name"],
            "label": build_label(key)
        })
    rows.sort(key=lambda item: item["label"].lower())
    return rows

def _build_zotero_headers(api_key: str = "") -> dict:
    headers = {
        "Zotero-API-Version": "3",
        "Accept": "application/json"
    }
    if api_key:
        headers["Zotero-API-Key"] = api_key
    return headers

def _extract_zotero_fulltext_content(payload) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("content", "text", "fulltext"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""

def _get_zotero_child_items(user_id: str, parent_key: str, api_key: str = "") -> List[dict]:
    if not user_id or not parent_key:
        return []
    encoded_user = parse.quote(user_id, safe="")
    encoded_parent = parse.quote(parent_key, safe="")
    url = f"https://api.zotero.org/users/{encoded_user}/items/{encoded_parent}/children?v=3&format=json"
    return _http_get_json(url, extra_headers=_build_zotero_headers(api_key))

def _get_zotero_attachment_fulltext(user_id: str, attachment_key: str, api_key: str = "") -> str:
    if not user_id or not attachment_key:
        return ""
    encoded_user = parse.quote(user_id, safe="")
    encoded_attachment = parse.quote(attachment_key, safe="")
    url = f"https://api.zotero.org/users/{encoded_user}/items/{encoded_attachment}/fulltext?v=3&format=json"
    payload = _http_get_json(url, extra_headers=_build_zotero_headers(api_key))
    return _extract_zotero_fulltext_content(payload)

def _hydrate_paper_from_zotero(paper: dict, payload: ZoteroSyncRequest) -> dict:
    hydrated = dict(paper or {})
    item_key = hydrated.get("zotero_item_key") or ""
    if not item_key:
        return hydrated

    try:
        child_items = _get_zotero_child_items(payload.zotero_user_id, item_key, payload.zotero_api_key)
    except HTTPException:
        return hydrated

    pdf_attachments = []
    for child in child_items or []:
        data = child.get("data") or {}
        if data.get("itemType") != "attachment":
            continue
        content_type = str(data.get("contentType") or "").lower()
        filename = str(data.get("filename") or "").lower()
        if "pdf" in content_type or filename.endswith(".pdf"):
            pdf_attachments.append(child)

    hydrated["zotero_has_pdf_attachment"] = bool(pdf_attachments)
    hydrated["zotero_has_fulltext"] = bool(str(hydrated.get("current_content") or "").strip())

    if hydrated["zotero_has_fulltext"]:
        return hydrated

    for attachment in pdf_attachments:
        attachment_key = attachment.get("key") or (attachment.get("data") or {}).get("key") or ""
        if not attachment_key:
            continue
        try:
            fulltext = _get_zotero_attachment_fulltext(payload.zotero_user_id, attachment_key, payload.zotero_api_key)
        except HTTPException:
            continue
        normalized = _normalize_paper_current_content(fulltext)
        if normalized:
            hydrated["current_content"] = normalized
            hydrated["zotero_has_fulltext"] = True
            break

    return hydrated

def _upload_zotero_items(payload: ZoteroUploadRequest) -> dict:
    sync_payload = _apply_runtime_defaults_to_zotero(ZoteroSyncRequest(
        zotero_user_id=payload.zotero_user_id,
        zotero_api_key=payload.zotero_api_key,
        collection_key=payload.collection_key
    ))
    account_key = _zotero_account_cache_key(sync_payload)
    existing_doi = set()
    existing_title = set()
    if not payload.skip_library_dedupe:
        existing_items = _fetch_zotero_items(sync_payload, collection_key="")
        existing_doi = {
            _normalize_zotero_match_key(_clean_doi((item.get("data") or {}).get("DOI") or ""))
            for item in existing_items
            if _clean_doi((item.get("data") or {}).get("DOI") or "")
        }
        existing_title = {
            _normalize_zotero_match_key((item.get("data") or {}).get("title") or "")
            for item in existing_items
            if (item.get("data") or {}).get("title")
        }

    upload_candidates = []
    skipped = 0
    for paper in payload.papers:
        doi_key = _normalize_zotero_match_key(_clean_doi(paper.doi))
        title_key = _normalize_zotero_match_key(paper.title)
        if (doi_key and doi_key in existing_doi) or (title_key and title_key in existing_title):
            skipped += 1
            continue
        upload_candidates.append(_paper_to_zotero_item(paper, sync_payload.collection_key))
        if doi_key:
            existing_doi.add(doi_key)
        if title_key:
            existing_title.add(title_key)

    if not upload_candidates:
        return {"created": 0, "skipped": skipped}

    base_path = f"https://api.zotero.org/users/{parse.quote(sync_payload.zotero_user_id, safe='')}/items"
    headers = {
        "Zotero-API-Version": "3",
        "Accept": "application/json",
        "Zotero-API-Key": sync_payload.zotero_api_key
    }

    created = 0
    for start in range(0, len(upload_candidates), 50):
        batch = upload_candidates[start:start + 50]
        response = _http_post_json(base_path, batch, headers=headers, timeout=30)
        success = response.get("successful") or {}
        created += len(success)

    if created > 0:
        now = _now_ts()
        synthetic_items = []
        for item in upload_candidates:
            item_key = uuid.uuid4().hex
            synthetic_items.append({
                "key": item_key,
                "version": now,
                "data": {
                    **item,
                    "key": item_key,
                    "version": now,
                    "itemType": item.get("itemType") or "journalArticle",
                    "title": item.get("title") or "Untitled",
                    "creators": item.get("creators") or [],
                    "date": item.get("date") or "",
                    "publicationTitle": item.get("publicationTitle") or "",
                    "url": item.get("url") or "",
                    "DOI": item.get("DOI") or "",
                    "abstractNote": item.get("abstractNote") or ""
                }
            })
        if synthetic_items:
            _merge_zotero_cache_items(account_key, "", synthetic_items, now)
            if sync_payload.collection_key:
                _merge_zotero_cache_items(account_key, sync_payload.collection_key, synthetic_items, now)
            _write_zotero_cache_state(
                account_key,
                "",
                max(now, int((_read_zotero_cache_state(account_key, "") or {}).get("library_version") or 0)),
                now,
                full_refreshed_at=int((_read_zotero_cache_state(account_key, "") or {}).get("full_refreshed_at") or now)
            )
            if sync_payload.collection_key:
                _write_zotero_cache_state(
                    account_key,
                    sync_payload.collection_key,
                    max(now, int((_read_zotero_cache_state(account_key, sync_payload.collection_key) or {}).get("library_version") or 0)),
                    now,
                    full_refreshed_at=int((_read_zotero_cache_state(account_key, sync_payload.collection_key) or {}).get("full_refreshed_at") or now)
                )

    return {"created": created, "skipped": skipped}

def _build_zotero_sync_preview(payload: ZoteroPreviewRequest) -> dict:
    sync_payload = _apply_runtime_defaults_to_zotero(ZoteroSyncRequest(
        zotero_user_id=payload.zotero_user_id,
        zotero_api_key=payload.zotero_api_key,
        collection_key=payload.collection_key
    ))
    raw_library_items = _fetch_zotero_items(sync_payload, collection_key="")
    raw_selected_items = _fetch_zotero_items(sync_payload)
    zotero_library_papers = []
    for item in raw_library_items:
        mapped = _map_zotero_item_to_paper(item)
        if mapped:
            zotero_library_papers.append(mapped)

    zotero_selected_papers = []
    for item in raw_selected_items:
        mapped = _map_zotero_item_to_paper(item)
        if mapped:
            zotero_selected_papers.append(mapped)

    project_papers = [paper.model_dump() for paper in payload.papers]
    zotero_library_token_set = set()
    for paper in zotero_library_papers:
        zotero_library_token_set.update(_paper_match_tokens(paper))

    project_token_set = set()
    for paper in project_papers:
        project_token_set.update(_paper_match_tokens(paper))

    upload_candidates = []
    for paper in project_papers:
        if _paper_match_tokens(paper).intersection(zotero_library_token_set):
            continue
        candidate_id = paper.get("filename") or paper.get("doi") or paper.get("title") or uuid.uuid4().hex
        upload_candidates.append(_serialize_sync_candidate(paper, candidate_id))

    fetch_candidates = []
    for paper in zotero_selected_papers:
        if _paper_match_tokens(paper).intersection(project_token_set):
            continue
        candidate_id = paper.get("zotero_item_key") or paper.get("doi") or paper.get("title") or uuid.uuid4().hex
        fetch_candidates.append(_serialize_sync_candidate(paper, candidate_id))

    return {
        "upload_candidates": upload_candidates,
        "fetch_candidates": fetch_candidates,
        "upload_count": len(upload_candidates),
        "fetch_count": len(fetch_candidates),
    }

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

def _split_authors_for_zotero(authors: str) -> List[dict]:
    parts = [part.strip() for part in re.split(r"\s+and\s+|;", str(authors or ""), flags=re.IGNORECASE)]
    normalized = []
    if len(parts) == 1 and "," in parts[0]:
        comma_parts = [part.strip() for part in parts[0].split(",") if part.strip()]
        if len(comma_parts) > 1:
            parts = comma_parts
    for author in parts:
        if not author:
            continue
        if "," in author:
            last, first = [segment.strip() for segment in author.split(",", 1)]
        else:
            tokens = author.split()
            if len(tokens) == 1:
                normalized.append({"creatorType": "author", "name": author})
                continue
            first = " ".join(tokens[:-1]).strip()
            last = tokens[-1].strip()
        creator = {"creatorType": "author"}
        if first or last:
            creator["firstName"] = first
            creator["lastName"] = last
        else:
            creator["name"] = author
        normalized.append(creator)
    return normalized or [{"creatorType": "author", "name": "Unknown"}]

def _normalize_zotero_match_key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())

def _paper_match_tokens(paper_like: dict) -> set:
    tokens = set()
    doi = _normalize_zotero_match_key(_clean_doi(paper_like.get("doi") or ""))
    title = _normalize_zotero_match_key(paper_like.get("title") or "")
    zotero_key = _normalize_zotero_match_key(paper_like.get("zotero_item_key") or "")
    if doi:
        tokens.add(f"doi:{doi}")
    if title:
        tokens.add(f"title:{title}")
    if zotero_key:
        tokens.add(f"zotero:{zotero_key}")
    return tokens

def _serialize_sync_candidate(paper_like: dict, candidate_id: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "title": paper_like.get("title", ""),
        "authors": paper_like.get("authors", ""),
        "year": paper_like.get("year", ""),
        "publication_venue": paper_like.get("publication_venue", ""),
        "doi": paper_like.get("doi", ""),
        "zotero_item_key": paper_like.get("zotero_item_key", ""),
        "paper": paper_like,
    }

def _paper_to_zotero_item(paper: PaperItem, collection_key: str = "") -> dict:
    item_type = "journalArticle" if (paper.publication_venue or paper.doi) else "document"
    payload = {
        "itemType": item_type,
        "title": _trim_text(paper.title, MAX_PAPER_TITLE_LENGTH) or "Untitled",
        "creators": _split_authors_for_zotero(paper.authors),
        "abstractNote": _trim_text(paper.abstract, MAX_PAPER_ABSTRACT_LENGTH),
        "date": _extract_citation_year(paper.year),
        "DOI": _clean_doi(paper.doi),
        "url": _trim_text(paper.paper_url or paper.source_url, 1200),
        "publicationTitle": _trim_text(paper.publication_venue, 300),
        "collections": [collection_key] if collection_key else [],
    }
    if paper.notes:
        payload["extra"] = _trim_text(paper.notes, 2000)
    return payload

def _map_zotero_item_to_paper(item: dict) -> Optional[dict]:
    data = item.get("data") or {}
    item_type = data.get("itemType", "")
    if item_type in {"attachment", "note", "annotation"}:
        return None

    title = (data.get("title") or "").strip()
    if not title:
        return None

    abstract = (data.get("abstractNote") or "").strip()
    analysis_ready = bool(abstract)
    doi = _clean_doi(data.get("DOI") or "")
    url = (data.get("url") or "").strip()
    item_key = item.get("key") or data.get("key") or ""

    return {
        "filename": f"zotero_{item_key or uuid.uuid4().hex}.pdf",
        "title": title,
        "abstract": abstract or "Unknown",
        "current_content": "",
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
        "zotero_has_pdf_attachment": False,
        "zotero_has_fulltext": False,
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
    cursor.execute("SELECT id, project_name, target_title, target_abstract, target_current_content FROM projects WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/projects/")
async def create_project(req: ProjectCreate, current_user: dict = Depends(_require_session)):
    cleaned = _validate_project_fields(req.project_name, req.target_title, req.target_abstract, req.target_current_content)
    conn = _db_connect()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO projects (user_id, project_name, target_title, target_abstract, target_current_content, top_papers) VALUES (?, ?, ?, ?, ?, ?)",
            (current_user["user_id"], cleaned["project_name"], cleaned["target_title"], cleaned["target_abstract"], cleaned["target_current_content"], "[]"))
        conn.commit()
        project_id = cursor.lastrowid
        _write_audit_log("project_create", user_id=current_user["user_id"], project_id=project_id, detail={"project_name": cleaned["project_name"]}, success=True)
        return {"message": "Project created", "project_id": project_id}
    finally:
        conn.close()

@app.get("/api/projects/{project_id}")
async def get_project(project_id: int, current_user: dict = Depends(_require_session)):
    project_data = _get_owned_project(project_id, current_user["user_id"])
    project_data["top_papers"] = json.loads(_scrub_top_papers_json(project_data["top_papers"])) if project_data["top_papers"] else []
    project_data.pop("target_keywords", None)
    return project_data

@app.put("/api/projects/{project_id}")
async def update_project(project_id: int, req: ProjectUpdate, current_user: dict = Depends(_require_session)):
    _get_owned_project(project_id, current_user["user_id"])
    cleaned = _validate_project_fields(req.project_name, req.target_title, req.target_abstract, req.target_current_content)
    lock = await _acquire_project_task_lock(project_id, "project_update")
    conn = _db_connect()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE projects SET project_name=?, target_title=?, target_abstract=?, target_current_content=? WHERE id=? AND user_id=?", 
                       (cleaned["project_name"], cleaned["target_title"], cleaned["target_abstract"], cleaned["target_current_content"], project_id, current_user["user_id"]))
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
        existing_papers = json.loads(_scrub_top_papers_json(existing_papers_json)) if existing_papers_json else []
        
        for p in existing_papers:
            p["is_new"] = False
            
        new_papers = []
        protected_filenames = set()
        for paper in request.new_papers:
            p_dict = paper.model_dump()
            p_dict["is_new"] = True
            if p_dict.get("filename"):
                protected_filenames.add(p_dict["filename"])
            new_papers.append(p_dict)
        
        all_papers = existing_papers + new_papers
        protected_papers = [paper for paper in all_papers if paper.get("filename") in protected_filenames]
        remaining_papers = [paper for paper in all_papers if paper.get("filename") not in protected_filenames]
        remaining_papers.sort(key=lambda x: x["similarity"], reverse=True)
        top_papers = (protected_papers + remaining_papers)[:MAX_TOP_PAPERS]
        top_papers.sort(key=lambda x: x["similarity"], reverse=True)
        
        updated_json = _scrub_top_papers_json(top_papers)
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
        updated_json = _scrub_top_papers_json([p.model_dump() for p in request.top_papers])
        cursor.execute("UPDATE projects SET top_papers = ? WHERE id = ? AND user_id = ?", (updated_json, project_id, current_user["user_id"]))
        conn.commit()
        _write_audit_log("project_update_papers", user_id=current_user["user_id"], project_id=project_id, detail={"paper_count": len(request.top_papers)}, success=True)
        return {"message": "Papers updated successfully"}
    finally:
        conn.close()
        lock.release()

@app.post("/api/papers/lookup")
async def lookup_paper_metadata(payload: PaperLookupRequest, current_user: dict = Depends(_require_session)):
    try:
        payload = _apply_runtime_defaults_to_lookup(payload)
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
        return _attach_citation_key(merged)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Metadata lookup crashed: {exc}")

@app.post("/api/projects/{project_id}/literature_watch")
async def project_literature_watch(project_id: int, payload: LiteratureWatchRequest, current_user: dict = Depends(_require_session)):
    project_data = _get_owned_project(project_id, current_user["user_id"])
    try:
        result = _build_project_literature_watch(project_data, payload)
        _write_audit_log(
            "project_literature_watch",
            user_id=current_user["user_id"],
            project_id=project_id,
            detail={
                "range": result.get("range"),
                "discipline": (result.get("discipline") or {}).get("key", ""),
                "core_papers_used": (result.get("source_summary") or {}).get("core_papers_used", 0),
                "recommendations": len(result.get("recommendations") or [])
            },
            success=True
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Project literature watch failed: {exc}")

@app.post("/api/export/bibtex", response_class=PlainTextResponse)
async def export_bibtex(payload: BibtexExportRequest, current_user: dict = Depends(_require_session)):
    return PlainTextResponse(_build_bibtex_entry(payload), media_type="application/x-bibtex; charset=utf-8")

@app.get("/api/settings")
async def get_runtime_settings(current_user: dict = Depends(_require_session)):
    return _load_runtime_settings()

@app.post("/api/settings")
async def save_runtime_settings(payload: SettingsPayload, current_user: dict = Depends(_require_session)):
    _save_runtime_settings(payload.model_dump())
    _write_audit_log("settings_update", user_id=current_user["user_id"], success=True)
    return _load_runtime_settings()

@app.get("/api/integrations/status")
async def integration_status(current_user: dict = Depends(_require_session)):
    return {
        "llm": _probe_llm_status(),
        "zotero": _probe_zotero_status(),
        "scholar": _probe_scholar_status(),
        "checked_at": _now_ts(),
    }

@app.post("/api/llm/text")
async def llm_text(payload: LlmProxyRequest, current_user: dict = Depends(_require_session)):
    prompt = _trim_text(payload.prompt, 120000)
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    return {"text": _call_llm_from_env(prompt, temperature=payload.temperature, json_mode=payload.json_mode)}

@app.get("/api/zotero/collections")
async def zotero_collections(current_user: dict = Depends(_require_session)):
    payload = _apply_runtime_defaults_to_zotero(ZoteroSyncRequest(zotero_user_id=""))
    try:
        collections = _fetch_zotero_collections(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not load Zotero collections: {exc}")
    return {
        "collections": [{"key": "", "name": "My Library", "label": "My Library"}] + _build_collection_options(collections)
    }

@app.post("/api/zotero/preview")
async def zotero_preview(payload: ZoteroPreviewRequest, current_user: dict = Depends(_require_session)):
    _validate_paper_list(payload.papers)
    try:
        preview = _build_zotero_sync_preview(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not compare Zotero and StarMap papers: {exc}")
    return preview

@app.post("/api/zotero/items/hydrate")
async def zotero_hydrate_items(payload: ZoteroHydrateRequest, current_user: dict = Depends(_require_session)):
    _validate_paper_list(payload.papers)
    sync_payload = _apply_runtime_defaults_to_zotero(ZoteroSyncRequest(
        zotero_user_id=payload.zotero_user_id,
        zotero_api_key=payload.zotero_api_key,
        collection_key=""
    ))
    try:
        hydrated = [
            _hydrate_paper_from_zotero(paper.model_dump(), sync_payload)
            for paper in payload.papers
        ]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not hydrate Zotero PDF text: {exc}")
    return {"papers": hydrated, "count": len(hydrated)}

@app.post("/api/zotero/sync")
async def zotero_sync(payload: ZoteroSyncRequest, current_user: dict = Depends(_require_session)):
    payload = _apply_runtime_defaults_to_zotero(payload)
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

@app.post("/api/zotero/upload")
async def zotero_upload(payload: ZoteroUploadRequest, current_user: dict = Depends(_require_session)):
    _validate_paper_list(payload.papers)
    try:
        result = _upload_zotero_items(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Zotero upload failed: {exc}")
    _write_audit_log("zotero_upload", user_id=current_user["user_id"], detail=result, success=True)
    return result

@app.post("/api/papers/citations")
async def lookup_paper_citations(payload: CitationLookupRequest, current_user: dict = Depends(_require_session)):
    payload = _apply_runtime_defaults_to_lookup(payload)
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
    payload = _apply_runtime_defaults_to_lookup(payload)
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
    payload = _apply_runtime_defaults_to_lookup(payload)
    job_id = _create_citation_job(min(len(payload.papers), 500))
    _write_audit_log("citation_graph_create", user_id=current_user["user_id"], detail={"paper_count": len(payload.papers), "job_id": job_id}, success=True)
    asyncio.create_task(_run_citation_graph_job(job_id, payload))
    return {"job_id": job_id, "status": "queued"}

@app.post("/api/papers/citation-graph/jobs", response_model=CitationGraphJobCreated)
async def create_citation_graph_job(payload: CitationGraphRequest, current_user: dict = Depends(_require_session)):
    payload = _apply_runtime_defaults_to_lookup(payload)
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
