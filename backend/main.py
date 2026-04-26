from __future__ import annotations

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
import random
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
SEMANTIC_CLUSTER_JOBS: Dict[str, dict] = {}
PROJECT_TASK_LOCKS: Dict[str, asyncio.Lock] = {}
CLAIM_CACHE_MAINTENANCE = {"last_checked_at": 0}
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
MAX_CLAIM_TEXT_LENGTH = 4000
MAX_CLAIM_SECTION_LABEL_LENGTH = 160
MAX_CLAIM_TYPE_LENGTH = 40
MAX_CLAIM_STATUS_LENGTH = 40
MAX_CLAIM_ANALYSIS_VERSION_LENGTH = 40
MAX_STARDUST_NAME_LENGTH = 180
MAX_STARDUST_STATUS_LENGTH = 40
MAX_SUB_TARGET_THESIS_LENGTH = 8000
MAX_STARDUST_PAPERS = 50
MAX_STARDUST_HOP1_REFERENCES = 16
MAX_STARDUST_HOP1_CITED_BY = 16
MAX_STARDUST_HOP2_SEEDS = 8
MAX_STARDUST_HOP2_REFERENCES_PER_SEED = 6
MAX_STARDUST_HOP2_CITED_BY_PER_SEED = 6
MAX_STARDUST_SEMANTIC_QUERY_COUNT = 5
MAX_STARDUST_SEMANTIC_RESULTS_PER_QUERY = 12
MAX_STARDUST_CANDIDATE_POOL = 120
MAX_EVIDENCE_WHY_MATCHED_LENGTH = 1200
MAX_EVIDENCE_CAVEAT_LENGTH = 800
MAX_EVIDENCE_SNIPPET_TEXT_LENGTH = 360
MAX_EVIDENCE_SNIPPETS_PER_ITEM = 3
MAX_CHALLENGE_EXPANSION_REFERENCES = 12
MAX_CHALLENGE_EXPANSION_CITED_BY = 12
MAX_CHALLENGE_EXPANSION_CANDIDATES = 18
MAX_CHALLENGE_EXPANSION_RESULTS = 12
MAX_CHALLENGE_EXPANSION_SEED_CONTENT_LENGTH = 1800
MAX_CLAIM_CANDIDATES = 96
CLAIM_ANALYSIS_BATCH_SIZE = 8
CLAIM_TYPE_VALUES = {"thesis_claim", "chapter_claim", "research_question"}
CLAIM_STATUS_VALUES = {"active", "archived"}
CLAIM_STANCE_VALUES = {"support", "challenge", "setup", "pending"}
STARDUST_STATUS_VALUES = {"draft", "ready", "building", "failed", "archived"}
STARDUST_GRAPH_MODE_VALUES = {"directed", "mutual", "full"}
MAX_STARDUSTS_PER_PROJECT = 5
CACHE_SOFT_LIMIT_BYTES = 128 * 1024 * 1024
CACHE_TARGET_LIMIT_BYTES = 96 * 1024 * 1024
CACHE_HARD_LIMIT_BYTES = 192 * 1024 * 1024
CACHE_ROW_LIMIT = 80_000
CACHE_TARGET_ROW_LIMIT = 60_000
CACHE_CLEANUP_BATCH_SIZE = 500
CACHE_CLEANUP_MIN_INTERVAL_SECONDS = 45
CACHE_PRIORITY_ORDER = [
    ("claim_snippet_cache", "snippet_json"),
    ("claim_candidate_cache", "candidate_json"),
    ("claim_llm_batch_cache", "response_json"),
]
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
    "a_general_economics_teaching": {
        "label": "A. General Economics and Teaching",
        "top_venues": ["journal of economic literature", "journal of economic perspectives", "american economic review", "econometrica"],
        "venue_keywords": ["economics", "economic education", "teaching", "survey", "literature", "overview"],
    },
    "b_history_methodology_heterodox": {
        "label": "B. History of Economic Thought, Methodology, and Heterodox Approaches",
        "top_venues": ["history of political economy", "journal of the history of economic thought", "cambridge journal of economics"],
        "venue_keywords": ["history of economic thought", "methodology", "heterodox", "epistemology", "school of thought"],
    },
    "c_mathematical_quantitative_methods": {
        "label": "C. Mathematical and Quantitative Methods",
        "top_venues": ["econometrica", "quantitative economics", "journal of econometrics", "theoretical economics", "review of economics and statistics"],
        "venue_keywords": ["econometric", "estimation", "identification", "quantitative", "mathematical", "causal inference", "time series", "panel data"],
    },
    "d_microeconomics": {
        "label": "D. Microeconomics",
        "top_venues": ["american economic review", "econometrica", "quarterly journal of economics", "journal of political economy", "the rand journal of economics"],
        "venue_keywords": ["microeconomics", "consumer", "firm", "game theory", "incentive", "contract", "pricing", "information"],
    },
    "e_macroeconomics_monetary": {
        "label": "E. Macroeconomics and Monetary Economics",
        "top_venues": ["american economic review", "econometrica", "quarterly journal of economics", "journal of political economy", "journal of monetary economics", "review of economics and statistics"],
        "venue_keywords": ["macro", "macroeconomics", "monetary", "inflation", "business cycle", "fiscal", "sovereign", "debt", "credit rating", "default"],
    },
    "f_international_economics": {
        "label": "F. International Economics",
        "top_venues": ["journal of international economics", "journal of international money and finance", "american economic review", "journal of monetary economics", "review of international economics"],
        "venue_keywords": ["international", "trade", "exchange rate", "sovereign debt", "default", "capital flows", "external debt", "balance of payments"],
    },
    "g_financial_economics": {
        "label": "G. Financial Economics",
        "top_venues": ["journal of finance", "review of financial studies", "journal of financial economics", "review of finance", "journal of banking and finance", "journal of financial intermediation"],
        "venue_keywords": ["finance", "financial", "banking", "credit", "bond", "spread", "asset pricing", "corporate finance", "intermediation", "risk"],
    },
    "h_public_economics": {
        "label": "H. Public Economics",
        "top_venues": ["journal of public economics", "national tax journal", "american economic review", "quarterly journal of economics", "journal of political economy"],
        "venue_keywords": ["public economics", "tax", "taxation", "government", "public debt", "fiscal policy", "public finance", "state capacity"],
    },
    "i_health_education_welfare": {
        "label": "I. Health, Education, and Welfare",
        "top_venues": ["journal of health economics", "economics of education review", "journal of human resources", "american economic journal: economic policy"],
        "venue_keywords": ["health", "education", "welfare", "human capital", "schooling", "insurance", "public health"],
    },
    "j_labor_demographic_economics": {
        "label": "J. Labor and Demographic Economics",
        "top_venues": ["journal of labor economics", "industrial and labor relations review", "demography", "journal of human resources"],
        "venue_keywords": ["labor", "employment", "wages", "demography", "migration", "household", "family", "gender"],
    },
    "k_law_economics": {
        "label": "K. Law and Economics",
        "top_venues": ["journal of law and economics", "international review of law and economics", "journal of legal studies"],
        "venue_keywords": ["law", "legal", "regulation", "crime", "litigation", "property rights", "contract enforcement"],
    },
    "l_industrial_organization": {
        "label": "L. Industrial Organization",
        "top_venues": ["the rand journal of economics", "journal of industrial economics", "international journal of industrial organization", "management science"],
        "venue_keywords": ["industrial organization", "competition", "market structure", "antitrust", "platform", "oligopoly", "innovation"],
    },
    "m_business_administration_business_economics": {
        "label": "M. Business Administration and Business Economics • Marketing • Accounting • Personnel Economics",
        "top_venues": ["management science", "marketing science", "accounting review", "strategic management journal", "organization science"],
        "venue_keywords": ["business", "management", "marketing", "accounting", "personnel", "organization", "strategy", "firm performance"],
    },
    "n_economic_history": {
        "label": "N. Economic History",
        "top_venues": ["journal of economic history", "explorations in economic history", "economic history review"],
        "venue_keywords": ["economic history", "historical", "long run", "industrialization", "institutions", "historical development"],
    },
    "o_development_innovation_growth": {
        "label": "O. Economic Development, Innovation, Technological Change, and Growth",
        "top_venues": ["journal of development economics", "world development", "research policy", "economic journal", "american economic journal: applied economics"],
        "venue_keywords": ["development", "innovation", "technology", "growth", "structural transformation", "productivity", "emerging economy"],
    },
    "p_political_economy_comparative_systems": {
        "label": "P. Political Economy and Comparative Economic Systems",
        "top_venues": ["public choice", "journal of comparative economics", "journal of politics", "world politics", "journal of public economics"],
        "venue_keywords": ["political economy", "comparative systems", "institutions", "state", "governance", "regime", "policy choice"],
    },
    "q_agricultural_environmental_resource": {
        "label": "Q. Agricultural and Natural Resource Economics • Environmental and Ecological Economics",
        "top_venues": ["american journal of agricultural economics", "journal of environmental economics and management", "resource and energy economics", "ecological economics"],
        "venue_keywords": ["agricultural", "natural resource", "environmental", "ecological", "climate", "energy", "land use"],
    },
    "r_urban_regional_real_estate_transportation": {
        "label": "R. Urban, Rural, Regional, Real Estate, and Transportation Economics",
        "top_venues": ["journal of urban economics", "regional science and urban economics", "real estate economics", "transportation research part b"],
        "venue_keywords": ["urban", "regional", "real estate", "housing", "transportation", "city", "spatial", "land"],
    },
    "y_miscellaneous": {
        "label": "Y. Miscellaneous Categories",
        "top_venues": ["american economic review", "economic journal", "review of economics and statistics"],
        "venue_keywords": ["economics", "economic", "policy", "applied economics", "miscellaneous"],
    },
    "z_other_special_topics": {
        "label": "Z. Other Special Topics",
        "top_venues": ["american economic review", "economic journal", "review of economics and statistics"],
        "venue_keywords": ["special topic", "economics", "policy", "interdisciplinary"],
    },
}
LITERATURE_WATCH_DISCIPLINE_ALIASES: Dict[str, str] = {
    "macroeconomics_monetary": "e_macroeconomics_monetary",
    "international_finance_sovereign_debt": "f_international_economics",
    "banking_credit_financial_intermediation": "g_financial_economics",
    "asset_pricing_corporate_finance": "g_financial_economics",
    "public_finance_political_economy": "h_public_economics",
    "development_international_political_economy": "o_development_innovation_growth",
    "political_economy_public_policy": "p_political_economy_comparative_systems",
    "management_strategy_organizations": "m_business_administration_business_economics",
    "marketing_operations_business_analytics": "m_business_administration_business_economics",
    "computer_science_ai": "c_mathematical_quantitative_methods",
    "general_social_science": "y_miscellaneous",
}
DEFAULT_LITERATURE_WATCH_DISCIPLINE = "e_macroeconomics_monetary"
SEMANTIC_CLUSTER_ALGORITHM_VERSION = "backend-v1"
SEMANTIC_CLUSTER_SEED_LIMIT = 60
SEMANTIC_CLUSTER_TEXT_VECTOR_DIM = 384
SEMANTIC_CLUSTER_MAX_DISPLAY_PAPERS = 10
SEMANTIC_CLUSTER_MIN_SIZE = 4
SEMANTIC_CLUSTER_COUNT_OPTIONS = (3, 4, 5)
SEMANTIC_CLUSTER_BASE_ATTEMPTS = 1
SEMANTIC_CLUSTER_QUALITY_RETRY_THRESHOLD = 0.055
SEMANTIC_CLUSTER_CURRENT_CONTENT_LIMIT = 1000
SEMANTIC_CLUSTER_STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "with", "from", "that", "this", "these", "those",
    "into", "over", "under", "between", "among", "through", "using", "used", "their", "there",
    "which", "while", "where", "when", "about", "after", "before", "study", "studies", "paper",
    "papers", "evidence", "analysis", "analyses", "approach", "approaches", "effect", "effects",
    "impact", "impacts", "role", "new", "recent", "latest", "across", "within", "such", "based",
    "because", "than", "also", "been", "being", "into", "onto", "your", "ours", "theirs"
}
CLAIM_CHALLENGE_MARKERS = {
    "however", "but", "limited", "limit", "limits", "conditional", "only", "except",
    "fails", "fail", "not", "contrary", "mixed", "heterogeneous", "weak", "weaker",
    "insignificant", "inconsistent", "depends", "depending"
}
CLAIM_SUPPORT_MARKERS = {
    "increase", "increases", "decrease", "decreases", "raise", "raises", "reduce",
    "reduces", "improve", "improves", "worsen", "worsens", "associated", "predicts",
    "drives", "causes", "effect", "evidence", "supports", "find", "finds", "shows"
}
CLAIM_SETUP_MARKERS = {
    "method", "methods", "identification", "specification", "estimation", "dataset",
    "measure", "measurement", "instrument", "regression", "model", "framework",
    "strategy", "empirical", "approach", "sampling", "design"
}

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

def _ensure_claims_schema(cursor):
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS project_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            claim_text TEXT NOT NULL,
            claim_type TEXT NOT NULL DEFAULT 'thesis_claim',
            section_label TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            analysis_version TEXT NOT NULL DEFAULT 'v1',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects (id)
        )'''
    )
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS claim_evidence_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            paper_key TEXT NOT NULL,
            paper_title TEXT NOT NULL DEFAULT '',
            paper_year TEXT NOT NULL DEFAULT '',
            paper_authors TEXT NOT NULL DEFAULT '',
            citation_key TEXT NOT NULL DEFAULT '',
            stance TEXT NOT NULL DEFAULT 'pending',
            strength_score REAL NOT NULL DEFAULT 0,
            relevance_score REAL NOT NULL DEFAULT 0,
            confidence_score REAL NOT NULL DEFAULT 0,
            quality_score REAL NOT NULL DEFAULT 0,
            why_matched TEXT NOT NULL DEFAULT '',
            caveat TEXT NOT NULL DEFAULT '',
            evidence_snippets_json TEXT NOT NULL DEFAULT '[]',
            source_pass TEXT NOT NULL DEFAULT 'auto',
            user_override INTEGER NOT NULL DEFAULT 0,
            pinned INTEGER NOT NULL DEFAULT 0,
            hidden INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (claim_id) REFERENCES project_claims (id),
            FOREIGN KEY (project_id) REFERENCES projects (id),
            UNIQUE (claim_id, paper_key)
        )'''
    )
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS claim_analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            candidate_count INTEGER NOT NULL DEFAULT 0,
            analyzed_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'queued',
            summary_json TEXT NOT NULL DEFAULT '{}',
            error_text TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (claim_id) REFERENCES project_claims (id),
            FOREIGN KEY (project_id) REFERENCES projects (id)
        )'''
    )
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS claim_candidate_cache (
            cache_key TEXT PRIMARY KEY,
            project_id INTEGER NOT NULL,
            claim_id INTEGER NOT NULL,
            analysis_version TEXT NOT NULL DEFAULT 'v1',
            payload_hash TEXT NOT NULL,
            candidate_json TEXT NOT NULL DEFAULT '[]',
            created_at INTEGER NOT NULL,
            last_hit_at INTEGER NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects (id),
            FOREIGN KEY (claim_id) REFERENCES project_claims (id)
        )'''
    )
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS claim_llm_batch_cache (
            cache_key TEXT PRIMARY KEY,
            project_id INTEGER NOT NULL,
            claim_id INTEGER NOT NULL,
            analysis_version TEXT NOT NULL DEFAULT 'v1',
            model_name TEXT NOT NULL DEFAULT '',
            payload_hash TEXT NOT NULL,
            response_json TEXT NOT NULL DEFAULT '[]',
            created_at INTEGER NOT NULL,
            last_hit_at INTEGER NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects (id),
            FOREIGN KEY (claim_id) REFERENCES project_claims (id)
        )'''
    )
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS claim_snippet_cache (
            cache_key TEXT PRIMARY KEY,
            project_id INTEGER NOT NULL,
            claim_id INTEGER NOT NULL,
            analysis_version TEXT NOT NULL DEFAULT 'v1',
            paper_key TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            snippet_json TEXT NOT NULL DEFAULT 'null',
            created_at INTEGER NOT NULL,
            last_hit_at INTEGER NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects (id),
            FOREIGN KEY (claim_id) REFERENCES project_claims (id)
        )'''
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_claims_project_id ON project_claims (project_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim_id ON claim_evidence_items (claim_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_evidence_project_id ON claim_evidence_items (project_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_analysis_runs_claim_id ON claim_analysis_runs (claim_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_candidate_cache_claim_id ON claim_candidate_cache (claim_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_llm_batch_cache_claim_id ON claim_llm_batch_cache (claim_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_snippet_cache_claim_id ON claim_snippet_cache (claim_id)")

def _ensure_stardust_schema(cursor):
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS challenge_stardusts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            claim_id INTEGER NOT NULL,
            seed_evidence_id INTEGER NOT NULL,
            seed_paper_key TEXT NOT NULL,
            name TEXT NOT NULL,
            sub_target_thesis TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft',
            paper_count INTEGER NOT NULL DEFAULT 0,
            graph_cache_signature TEXT NOT NULL DEFAULT '',
            source_summary_json TEXT NOT NULL DEFAULT '{}',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects (id),
            FOREIGN KEY (claim_id) REFERENCES project_claims (id),
            FOREIGN KEY (seed_evidence_id) REFERENCES claim_evidence_items (id)
        )'''
    )
    cursor.execute("PRAGMA table_info(challenge_stardusts)")
    stardust_columns = {row[1] for row in cursor.fetchall()}
    if "source_summary_json" not in stardust_columns:
        cursor.execute("ALTER TABLE challenge_stardusts ADD COLUMN source_summary_json TEXT NOT NULL DEFAULT '{}'")
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS challenge_stardust_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stardust_id INTEGER NOT NULL,
            paper_key TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            abstract TEXT NOT NULL DEFAULT '',
            current_content TEXT NOT NULL DEFAULT '',
            authors TEXT NOT NULL DEFAULT '',
            year TEXT NOT NULL DEFAULT '',
            doi TEXT NOT NULL DEFAULT '',
            openalex_id TEXT NOT NULL DEFAULT '',
            paper_url TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            publication_venue TEXT NOT NULL DEFAULT '',
            citation_count INTEGER,
            referenced_openalex_ids_json TEXT NOT NULL DEFAULT '[]',
            relationship_type TEXT NOT NULL DEFAULT '',
            discovery_source TEXT NOT NULL DEFAULT '',
            hop_distance INTEGER NOT NULL DEFAULT 0,
            challenge_score REAL NOT NULL DEFAULT 0,
            seed_similarity REAL NOT NULL DEFAULT 0,
            claim_relevance REAL NOT NULL DEFAULT 0,
            quality_score REAL NOT NULL DEFAULT 0,
            why_matched TEXT NOT NULL DEFAULT '',
            caveat TEXT NOT NULL DEFAULT '',
            selected_for_import INTEGER NOT NULL DEFAULT 0,
            hidden INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (stardust_id) REFERENCES challenge_stardusts (id),
            UNIQUE (stardust_id, paper_key)
        )'''
    )
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS challenge_stardust_graph_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stardust_id INTEGER NOT NULL,
            graph_mode TEXT NOT NULL,
            graph_signature TEXT NOT NULL DEFAULT '',
            nodes_json TEXT NOT NULL DEFAULT '[]',
            edges_json TEXT NOT NULL DEFAULT '[]',
            meta_json TEXT NOT NULL DEFAULT '{}',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (stardust_id) REFERENCES challenge_stardusts (id),
            UNIQUE (stardust_id, graph_mode)
        )'''
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stardust_project_id ON challenge_stardusts (project_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stardust_claim_id ON challenge_stardusts (claim_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stardust_updated_at ON challenge_stardusts (updated_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stardust_papers_stardust_id ON challenge_stardust_papers (stardust_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stardust_papers_score ON challenge_stardust_papers (stardust_id, challenge_score DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stardust_papers_openalex ON challenge_stardust_papers (openalex_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stardust_graph_cache_stardust_id ON challenge_stardust_graph_cache (stardust_id)")

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
    _ensure_claims_schema(cursor)
    _ensure_stardust_schema(cursor)
    cursor.execute("UPDATE claim_evidence_items SET stance = 'setup' WHERE LOWER(COALESCE(stance, '')) IN ('method', 'methods', 'methodology')")
    cursor.execute("UPDATE claim_evidence_items SET stance = 'pending' WHERE LOWER(COALESCE(stance, '')) IN ('background', 'context', 'foundation')")
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

def _normalize_claim_type(raw_value: str) -> str:
    value = _trim_text(str(raw_value or "").lower(), MAX_CLAIM_TYPE_LENGTH)
    return value if value in CLAIM_TYPE_VALUES else "thesis_claim"

def _normalize_claim_status(raw_value: str) -> str:
    value = _trim_text(str(raw_value or "").lower(), MAX_CLAIM_STATUS_LENGTH)
    return value if value in CLAIM_STATUS_VALUES else "active"

def _normalize_claim_stance(raw_value: str) -> str:
    value = _trim_text(str(raw_value or "").lower(), 40)
    aliases = {
        "supports": "support",
        "supported": "support",
        "contradict": "challenge",
        "contradicts": "challenge",
        "contradiction": "challenge",
        "oppose": "challenge",
        "opposes": "challenge",
        "limit": "challenge",
        "limits": "challenge",
        "method": "setup",
        "methods": "setup",
        "methodology": "setup",
        "setups": "setup",
        "design": "setup",
        "approach": "setup",
        "context": "pending",
        "foundation": "pending",
        "background": "pending",
        "uncertain": "pending",
        "unclear": "pending",
    }
    normalized = aliases.get(value, value)
    return normalized if normalized in CLAIM_STANCE_VALUES else "pending"

def _validate_claim_create_payload(payload: ClaimCreateRequest) -> ClaimCreateRequest:
    payload.claim_text = _trim_text(payload.claim_text, MAX_CLAIM_TEXT_LENGTH)
    payload.claim_type = _normalize_claim_type(payload.claim_type)
    payload.section_label = _trim_text(payload.section_label, MAX_CLAIM_SECTION_LABEL_LENGTH)
    if not payload.claim_text:
        raise HTTPException(status_code=422, detail="Claim text is required.")
    return payload

def _validate_claim_analyze_payload(payload: ClaimAnalyzeRequest) -> ClaimAnalyzeRequest:
    payload.max_candidates = max(8, min(int(payload.max_candidates or 36), MAX_CLAIM_CANDIDATES))
    cleaned_statuses = []
    for raw_status in payload.include_statuses or []:
        value = _trim_text(raw_status, 40)
        if value and value not in cleaned_statuses:
            cleaned_statuses.append(value)
    payload.include_statuses = cleaned_statuses or ["Core", "Pending", "Underweight", "Unread"]
    payload.prefer_fulltext = bool(payload.prefer_fulltext)
    payload.reanalyze_overrides = bool(payload.reanalyze_overrides)
    return payload

def _load_project_top_papers(project_data: dict) -> List[dict]:
    raw_value = project_data.get("top_papers")
    if not raw_value:
        return []
    if isinstance(raw_value, list):
        papers = raw_value
    else:
        papers = json.loads(_scrub_top_papers_json(raw_value))
    return [_scrub_paper_payload(paper) for paper in papers if isinstance(paper, dict)]

def _make_claim_paper_key(paper: dict) -> str:
    openalex_id = _trim_text((paper or {}).get("openalex_id"), 300)
    if openalex_id:
        return f"openalex:{openalex_id.lower()}"
    zotero_key = _trim_text((paper or {}).get("zotero_item_key"), 120)
    if zotero_key:
        return f"zotero:{zotero_key.lower()}"
    doi = _clean_doi((paper or {}).get("doi"))
    if doi:
        return f"doi:{doi.lower()}"
    title = _collapse_whitespace(str((paper or {}).get("title") or "")).lower()
    year = _extract_citation_year((paper or {}).get("year", ""))
    authors = _collapse_whitespace(str((paper or {}).get("authors") or "")).lower()
    digest = hashlib.sha1(f"{title}|{year}|{authors}".encode("utf-8")).hexdigest()[:20]
    return f"paper:{digest}"

def _claim_tokens(value: str) -> List[str]:
    return [
        token for token in re.findall(r"[A-Za-z0-9]+", str(value or "").lower())
        if len(token) >= 3 and token not in LITERATURE_WATCH_STOPWORDS
    ]

def _claim_phrases(value: str, min_size: int = 2, max_size: int = 3) -> List[str]:
    tokens = _claim_tokens(value)
    phrases = []
    for size in range(min_size, max_size + 1):
        for index in range(0, max(len(tokens) - size + 1, 0)):
            phrase = " ".join(tokens[index:index + size]).strip()
            if phrase:
                phrases.append(phrase)
    deduped = []
    for phrase in phrases:
        if phrase not in deduped:
            deduped.append(phrase)
    return deduped

def _token_overlap_score(text: str, tokens: List[str]) -> float:
    if not tokens:
        return 0.0
    text_tokens = set(_claim_tokens(text))
    if not text_tokens:
        return 0.0
    overlap = sum(1 for token in tokens if token in text_tokens)
    return min(overlap / max(len(set(tokens)), 1), 1.0)

def _phrase_overlap_score(text: str, phrases: List[str]) -> float:
    lowered = str(text or "").lower()
    if not lowered.strip() or not phrases:
        return 0.0
    hits = sum(1 for phrase in phrases if phrase in lowered)
    return min(hits / max(len(phrases), 1), 1.0)

def _marker_score(text: str, markers: set) -> float:
    lowered = str(text or "").lower()
    if not lowered.strip():
        return 0.0
    hits = sum(1 for marker in markers if marker in lowered)
    return min(hits / 3.0, 1.0)

def _length_quality_score(text: str, ideal_min: int = 70, ideal_max: int = 280) -> float:
    length = len(_compact_whitespace(text))
    if length <= 0:
        return 0.0
    if ideal_min <= length <= ideal_max:
        return 1.0
    if length < ideal_min:
        return max(length / max(ideal_min, 1), 0.25)
    overflow = min((length - ideal_max) / max(ideal_max, 1), 1.0)
    return max(1.0 - overflow, 0.35)

def _text_signal_bundle(text: str, claim_tokens: List[str], claim_phrases: List[str]) -> dict:
    return {
        "token_overlap": _token_overlap_score(text, claim_tokens),
        "phrase_overlap": _phrase_overlap_score(text, claim_phrases),
        "support_marker": _marker_score(text, CLAIM_SUPPORT_MARKERS),
        "challenge_marker": _marker_score(text, CLAIM_CHALLENGE_MARKERS),
        "setup_marker": _marker_score(text, CLAIM_SETUP_MARKERS),
    }

def _stance_alignment_bonus(signal_bundle: dict, preferred_stance: str) -> float:
    stance = _normalize_claim_stance(preferred_stance)
    if stance == "challenge":
        return float(signal_bundle.get("challenge_marker") or 0)
    if stance == "setup":
        return float(signal_bundle.get("setup_marker") or 0)
    return float(signal_bundle.get("support_marker") or 0)

def _project_similarity_score(paper: dict) -> float:
    try:
        return max(0.0, min(float((paper or {}).get("similarity") or 0.0), 1.0))
    except (TypeError, ValueError):
        return 0.0

def _safe_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default

def _paper_status_weight(status: str) -> float:
    normalized = str(status or "").strip().lower()
    if normalized == "core":
        return 1.0
    if normalized == "pending":
        return 0.72
    if normalized == "underweight":
        return 0.62
    if normalized == "unread":
        return 0.48
    return 0.52

def _paper_recency_score(paper: dict) -> float:
    year = _extract_citation_year((paper or {}).get("year", ""))
    if year == "Unknown":
        return 0.35
    try:
        delta = max(date.today().year - int(year), 0)
    except ValueError:
        return 0.35
    if delta <= 2:
        return 1.0
    if delta <= 5:
        return 0.82
    if delta <= 10:
        return 0.62
    if delta <= 20:
        return 0.46
    return 0.32

def _paper_quality_score(paper: dict) -> float:
    citation_count = _safe_int((paper or {}).get("citation_count"), 0)
    citation_score = min((math.log1p(max(citation_count, 0)) / math.log1p(500)), 1.0) if citation_count else 0.0
    completeness_parts = [
        bool(_trim_text((paper or {}).get("title"), MAX_PAPER_TITLE_LENGTH)),
        bool(_trim_text((paper or {}).get("authors"), MAX_PAPER_AUTHORS_LENGTH) and str((paper or {}).get("authors") or "").strip().lower() != "unknown"),
        _extract_citation_year((paper or {}).get("year", "")) != "Unknown",
        bool(_trim_text((paper or {}).get("abstract"), MAX_PAPER_ABSTRACT_LENGTH) and str((paper or {}).get("abstract") or "").strip().lower() != "unknown"),
        bool(_trim_text((paper or {}).get("publication_venue"), 300)),
    ]
    completeness_score = sum(1 for item in completeness_parts if item) / len(completeness_parts)
    core_bonus = 0.12 if str((paper or {}).get("status") or "").strip().lower() == "core" else 0.0
    fulltext_bonus = 0.08 if _trim_text((paper or {}).get("current_content"), MAX_PAPER_CURRENT_CONTENT_LENGTH) else 0.0
    return min((citation_score * 0.45) + (completeness_score * 0.35) + core_bonus + fulltext_bonus, 1.0)

def _claim_cluster_key(paper: dict) -> str:
    for key in ("citation_cluster_id", "citation_cluster_theme_name", "publication_venue"):
        value = _collapse_whitespace(str((paper or {}).get(key) or "")).lower()
        if value:
            return value
    return "uncategorized"

def _build_claim_candidate_metrics(paper: dict, claim_text: str, claim_tokens: List[str], claim_phrases: List[str], prefer_fulltext: bool) -> dict:
    title = str((paper or {}).get("title") or "")
    abstract = str((paper or {}).get("abstract") or "")
    notes = str((paper or {}).get("notes") or "")
    body = str((paper or {}).get("current_content") or "")
    title_signal = _text_signal_bundle(title, claim_tokens, claim_phrases)
    abstract_signal = _text_signal_bundle(abstract, claim_tokens, claim_phrases)
    notes_signal = _text_signal_bundle(notes, claim_tokens, claim_phrases)
    body_signal = _text_signal_bundle(body, claim_tokens, claim_phrases) if body else _text_signal_bundle("", claim_tokens, claim_phrases)
    title_score = (title_signal["token_overlap"] * 0.65) + (title_signal["phrase_overlap"] * 0.35)
    abstract_score = (abstract_signal["token_overlap"] * 0.58) + (abstract_signal["phrase_overlap"] * 0.42)
    notes_score = (notes_signal["token_overlap"] * 0.5) + (notes_signal["phrase_overlap"] * 0.5)
    body_score = ((body_signal["token_overlap"] * 0.55) + (body_signal["phrase_overlap"] * 0.45)) if body else 0.0
    exact_phrase_bonus = 0.08 if claim_text and claim_text.lower() in f"{title}\n{abstract}\n{notes}\n{body}".lower() else 0.0
    claim_relevance = min(
        (title_score * 0.29) +
        (abstract_score * 0.31) +
        (notes_score * 0.20) +
        (body_score * 0.20) +
        exact_phrase_bonus,
        1.0
    )
    challenge_score = min(
        (max(title_signal["challenge_marker"], abstract_signal["challenge_marker"], notes_signal["challenge_marker"], body_signal["challenge_marker"]) * 0.55) +
        (max(abstract_signal["phrase_overlap"], body_signal["phrase_overlap"], notes_signal["phrase_overlap"]) * 0.30) +
        (max(notes_signal["token_overlap"], body_signal["token_overlap"]) * 0.15),
        1.0
    )
    setup_score = min(
        (max(title_signal["setup_marker"], abstract_signal["setup_marker"], notes_signal["setup_marker"], body_signal["setup_marker"]) * 0.58) +
        (max(title_signal["phrase_overlap"], abstract_signal["phrase_overlap"], notes_signal["phrase_overlap"]) * 0.22) +
        (max(notes_signal["token_overlap"], body_signal["token_overlap"]) * 0.20),
        1.0
    )
    support_score = min(
        (max(title_signal["support_marker"], abstract_signal["support_marker"], body_signal["support_marker"]) * 0.34) +
        (claim_relevance * 0.46) +
        (max(abstract_signal["phrase_overlap"], body_signal["phrase_overlap"]) * 0.20),
        1.0
    )
    fulltext_bonus = 1.0 if (prefer_fulltext and body) or bool((paper or {}).get("zotero_has_fulltext")) else 0.0
    project_similarity = _project_similarity_score(paper)
    quality_score = _paper_quality_score(paper)
    recency_score = _paper_recency_score(paper)
    notes_relevance = notes_score
    candidate_score = min(
        (claim_relevance * 0.32) +
        (project_similarity * 0.14) +
        (_paper_status_weight((paper or {}).get("status")) * 0.11) +
        (notes_relevance * 0.12) +
        (quality_score * 0.13) +
        (fulltext_bonus * 0.08) +
        (recency_score * 0.05) +
        (support_score * 0.05),
        1.0
    )
    return {
        "paper_key": _make_claim_paper_key(paper),
        "claim_relevance": round(claim_relevance, 4),
        "project_similarity": round(project_similarity, 4),
        "status_weight": round(_paper_status_weight((paper or {}).get("status")), 4),
        "notes_relevance": round(notes_relevance, 4),
        "quality_score": round(quality_score, 4),
        "fulltext_bonus": round(fulltext_bonus, 4),
        "recency_score": round(recency_score, 4),
        "support_hint": round(support_score, 4),
        "challenge_hint": round(challenge_score, 4),
        "setup_hint": round(setup_score, 4),
        "candidate_score": round(candidate_score, 4),
        "cluster_key": _claim_cluster_key(paper),
    }

def _diversify_claim_candidates(candidates: List[dict], max_candidates: int) -> List[dict]:
    selected: List[dict] = []
    cluster_counts: Dict[str, int] = {}
    max_per_cluster = max(2, min(5, math.ceil(max_candidates / 4)))
    leftovers: List[dict] = []
    for candidate in candidates:
        cluster_key = candidate.get("cluster_key", "uncategorized")
        count = cluster_counts.get(cluster_key, 0)
        if count < max_per_cluster:
            selected.append(candidate)
            cluster_counts[cluster_key] = count + 1
        else:
            leftovers.append(candidate)
        if len(selected) >= max_candidates:
            return selected[:max_candidates]
    for candidate in leftovers:
        selected.append(candidate)
        if len(selected) >= max_candidates:
            break
    return selected[:max_candidates]

def _build_claim_candidate_pool(project_data: dict, claim_row: dict, include_statuses: List[str], max_candidates: int, prefer_fulltext: bool) -> List[dict]:
    cache_input = _build_claim_candidate_cache_input(project_data, claim_row, include_statuses, max_candidates, prefer_fulltext)
    payload_hash = _hash_cache_payload(cache_input)
    cache_key = f"claim-candidates:{payload_hash}"
    cached_payload = _read_claim_cache_payload("claim_candidate_cache", cache_key, "candidate_json")
    if cached_payload:
        try:
            cached_candidates = json.loads(cached_payload)
        except Exception:
            cached_candidates = None
        if isinstance(cached_candidates, list):
            return [item for item in cached_candidates if isinstance(item, dict)]

    claim_text = claim_row.get("claim_text", "")
    papers = _load_project_top_papers(project_data)
    allowed_statuses = {str(status or "").strip().lower() for status in include_statuses if str(status or "").strip()}
    claim_tokens = _claim_tokens(claim_text)
    claim_phrases = _claim_phrases(claim_text)
    enriched = []
    for paper in papers:
        if allowed_statuses and str((paper or {}).get("status") or "").strip().lower() not in allowed_statuses:
            continue
        metrics = _build_claim_candidate_metrics(paper, claim_text, claim_tokens, claim_phrases, prefer_fulltext)
        enriched.append({**paper, **metrics})
    if not enriched:
        return []

    claim_ranked = sorted(enriched, key=lambda item: (float(item.get("claim_relevance") or 0), float(item.get("candidate_score") or 0)), reverse=True)
    score_ranked = sorted(enriched, key=lambda item: (float(item.get("candidate_score") or 0), float(item.get("quality_score") or 0)), reverse=True)
    similarity_ranked = sorted(enriched, key=lambda item: (float(item.get("project_similarity") or 0), float(item.get("candidate_score") or 0)), reverse=True)
    support_ranked = sorted(enriched, key=lambda item: (float(item.get("support_hint") or 0), float(item.get("claim_relevance") or 0), float(item.get("candidate_score") or 0)), reverse=True)
    challenge_ranked = sorted(enriched, key=lambda item: (float(item.get("challenge_hint") or 0), float(item.get("claim_relevance") or 0)), reverse=True)
    setup_ranked = sorted(enriched, key=lambda item: (float(item.get("setup_hint") or 0), float(item.get("claim_relevance") or 0), float(item.get("quality_score") or 0)), reverse=True)
    quality_ranked = sorted(enriched, key=lambda item: (float(item.get("quality_score") or 0), float(item.get("citation_count") or 0)), reverse=True)
    core_ranked = sorted(
        [item for item in enriched if str(item.get("status") or "").strip().lower() == "core"],
        key=lambda item: (float(item.get("candidate_score") or 0), float(item.get("claim_relevance") or 0)),
        reverse=True
    )
    cluster_leaders = {}
    for item in score_ranked:
        cluster_key = item.get("cluster_key", "uncategorized")
        if cluster_key not in cluster_leaders:
            cluster_leaders[cluster_key] = item

    selected_by_key: Dict[str, dict] = {}
    def seed(candidates: List[dict], limit: int):
        for item in candidates[:limit]:
            selected_by_key.setdefault(item.get("paper_key"), item)

    seed(claim_ranked, max(10, math.ceil(max_candidates * 0.45)))
    seed(support_ranked, max(8, math.ceil(max_candidates * 0.35)))
    seed(challenge_ranked, max(6, math.ceil(max_candidates * 0.22)))
    seed(setup_ranked, max(6, math.ceil(max_candidates * 0.22)))
    seed(score_ranked, max(8, math.ceil(max_candidates * 0.35)))
    seed(similarity_ranked, max(5, math.ceil(max_candidates * 0.22)))
    seed(quality_ranked, max(4, math.ceil(max_candidates * 0.18)))
    seed(core_ranked, max(4, math.ceil(max_candidates * 0.18)))
    seed(list(cluster_leaders.values()), max(4, math.ceil(max_candidates * 0.25)))

    merged = list(selected_by_key.values())
    merged.sort(
        key=lambda item: (
            float(item.get("candidate_score") or 0),
            float(item.get("claim_relevance") or 0),
            float(item.get("support_hint") or 0),
            float(item.get("quality_score") or 0),
            float(item.get("project_similarity") or 0)
        ),
        reverse=True
    )
    selected_candidates = _diversify_claim_candidates(merged, max_candidates)
    _write_claim_candidate_cache(
        cache_key,
        int(project_data.get("id") or 0),
        int((claim_row or {}).get("id") or 0),
        _claim_analysis_version(claim_row),
        payload_hash,
        _stable_json_dumps(selected_candidates)
    )
    return selected_candidates

def _compact_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()

def _ground_claim_snippet(project_id: int, claim_row: dict, raw_snippet: str, paper: dict, claim_tokens: List[str], claim_phrases: List[str], preferred_stance: str = "support") -> Optional[dict]:
    snippet = _trim_text(_compact_whitespace(raw_snippet), MAX_EVIDENCE_SNIPPET_TEXT_LENGTH)
    if not snippet:
        return None
    cache_input = _build_claim_snippet_cache_input(project_id, claim_row, paper, snippet, preferred_stance)
    payload_hash = _hash_cache_payload(cache_input)
    cache_key = f"claim-snippet:{payload_hash}"
    cached_payload = _read_claim_cache_payload("claim_snippet_cache", cache_key, "snippet_json")
    if cached_payload is not None:
        try:
            cached_snippet = json.loads(cached_payload)
        except Exception:
            cached_snippet = None
        if cached_snippet is None or isinstance(cached_snippet, dict):
            return cached_snippet

    best = None
    for source_field in ("abstract", "current_content", "notes"):
        raw_text = str((paper or {}).get(source_field) or "")
        if not raw_text.strip():
            continue
        segments = re.split(r"(?<=[.!?])\s+|\n+", raw_text)
        for segment in segments:
            compact = _compact_whitespace(segment)
            if len(compact) < 20:
                continue
            overlap = SequenceMatcher(None, snippet.lower(), compact.lower()).ratio()
            if overlap < 0.42 and snippet.lower() not in compact.lower() and compact.lower() not in snippet.lower():
                continue
            signal_bundle = _text_signal_bundle(compact, claim_tokens, claim_phrases)
            score = (
                overlap * 0.55 +
                signal_bundle["token_overlap"] * 0.18 +
                signal_bundle["phrase_overlap"] * 0.17 +
                _stance_alignment_bonus(signal_bundle, preferred_stance) * 0.10
            )
            start = raw_text.find(segment)
            candidate = {
                "score": score,
                "text": compact[:MAX_EVIDENCE_SNIPPET_TEXT_LENGTH],
                "source_field": source_field,
                "char_start": max(start, 0),
                "char_end": max(start, 0) + len(segment),
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate
    if not best:
        _write_claim_snippet_cache(
            cache_key,
            int(project_id or 0),
            int((claim_row or {}).get("id") or 0),
            _claim_analysis_version(claim_row),
            _trim_text(paper.get("paper_key"), 160),
            payload_hash,
            "null"
        )
        return None
    best.pop("score", None)
    _write_claim_snippet_cache(
        cache_key,
        int(project_id or 0),
        int((claim_row or {}).get("id") or 0),
        _claim_analysis_version(claim_row),
        _trim_text(paper.get("paper_key"), 160),
        payload_hash,
        _stable_json_dumps(best)
    )
    return best

def _extract_claim_evidence_snippets(paper: dict, claim_tokens: List[str], claim_phrases: List[str], limit: int = 2, preferred_stance: str = "support") -> List[dict]:
    snippets = []
    seen_texts = set()
    for source_field in ("abstract", "current_content", "notes"):
        raw_text = str((paper or {}).get(source_field) or "")
        if not raw_text.strip():
            continue
        segments = re.split(r"(?<=[.!?])\s+|\n+", raw_text)
        scored = []
        for segment in segments:
            compact = _compact_whitespace(segment)
            if len(compact) < 30:
                continue
            signal_bundle = _text_signal_bundle(compact, claim_tokens, claim_phrases)
            overlap = signal_bundle["token_overlap"]
            phrase_overlap = signal_bundle["phrase_overlap"]
            if overlap <= 0 and phrase_overlap <= 0:
                continue
            start = raw_text.find(segment)
            source_weight = 1.0 if source_field == "abstract" else (0.94 if source_field == "notes" else 0.9)
            score = (
                overlap * 0.34 +
                phrase_overlap * 0.28 +
                _stance_alignment_bonus(signal_bundle, preferred_stance) * 0.18 +
                _length_quality_score(compact) * 0.08 +
                source_weight * 0.12
            )
            scored.append((score, compact, source_field, max(start, 0), max(start, 0) + len(segment)))
        scored.sort(key=lambda item: (item[0], len(item[1]) <= 240, len(item[1])), reverse=True)
        for _, text, field, start, end in scored:
            dedupe_key = text.lower()
            if dedupe_key in seen_texts:
                continue
            seen_texts.add(dedupe_key)
            snippets.append({
                "text": text[:MAX_EVIDENCE_SNIPPET_TEXT_LENGTH],
                "source_field": field,
                "char_start": start,
                "char_end": end,
            })
            if len(snippets) >= limit:
                return snippets[:limit]
    return snippets[:limit]

def _build_claim_classification_prompt(project_data: dict, claim_row: dict, candidates: List[dict]) -> str:
    payload = _build_claim_classification_payload(candidates)
    return (
        "You are classifying project papers against a specific research claim.\n\n"
        "Assign exactly one stance for each paper:\n"
        "- support = directly supports the claim or a core mechanism\n"
        "- challenge = weakens, narrows, conditions, or contradicts the claim\n"
        "- setup = mainly contributes identification, data, measurement, empirical strategy, or research design\n"
        "- pending = plausibly relevant, but evidence is too weak or unclear\n\n"
        "Rules:\n"
        "- Prefer the supplied abstract, notes, and current_content.\n"
        "- challenge includes partial contradiction, boundary conditions, null effects, and domain-specific limitations.\n"
        "- setup should win when the paper is mainly useful for identification, data, measurement, or design rather than substantive support.\n"
        "- Do not invent evidence not present in the supplied text.\n"
        "- why_matched must be one sentence.\n"
        "- caveat should be short and empty when not needed.\n"
        "- snippet_candidates should be short verbatim fragments copied from the supplied text when possible.\n"
        "- Return JSON only in the form {\"results\":[...]}\n\n"
        f"Project target title: {_trim_text(project_data.get('target_title'), 300)}\n"
        f"Project target abstract: {_trim_text(_compact_whitespace(project_data.get('target_abstract')), 1800)}\n"
        f"Project current content: {_trim_text(_compact_whitespace(project_data.get('target_current_content')), 1800)}\n"
        f"Claim text: {_trim_text(claim_row.get('claim_text'), MAX_CLAIM_TEXT_LENGTH)}\n"
        f"Claim type: {_trim_text(claim_row.get('claim_type'), MAX_CLAIM_TYPE_LENGTH)}\n"
        f"Section label: {_trim_text(claim_row.get('section_label'), MAX_CLAIM_SECTION_LABEL_LENGTH)}\n\n"
        "Return one object per input paper with keys:\n"
        "paper_key, stance, directness, confidence, why_matched, caveat, snippet_candidates\n\n"
        f"Papers:\n{json.dumps(payload, ensure_ascii=False)}"
    )

def _heuristic_claim_classification(paper: dict, claim_tokens: List[str], claim_phrases: Optional[List[str]] = None) -> dict:
    claim_phrases = claim_phrases or []
    claim_relevance = float(paper.get("claim_relevance") or 0)
    support_hint = float(paper.get("support_hint") or 0)
    challenge_hint = float(paper.get("challenge_hint") or 0)
    setup_hint = float(paper.get("setup_hint") or 0)
    support_signal = (support_hint * 0.52) + (claim_relevance * 0.48)
    challenge_signal = (challenge_hint * 0.64) + (claim_relevance * 0.36)
    setup_signal = (setup_hint * 0.7) + (claim_relevance * 0.3)
    if challenge_signal >= 0.32 and challenge_signal >= support_signal + 0.05 and challenge_signal >= setup_signal:
        stance = "challenge"
    elif setup_signal >= 0.34 and setup_signal >= support_signal + 0.03:
        stance = "setup"
    elif support_signal >= 0.36:
        stance = "support"
    else:
        stance = "pending"
    snippets = _extract_claim_evidence_snippets(paper, claim_tokens, claim_phrases, limit=2, preferred_stance=stance)
    why_matched = (
        "The paper appears to provide direct evidence that aligns with the claim or one of its core mechanisms."
        if stance == "support"
        else (
            "The paper appears to qualify, limit, or condition the claim rather than cleanly support it."
            if stance == "challenge"
            else (
                "The paper looks most useful for setup, measurement, identification, or research design support."
                if stance == "setup"
                else "The paper may matter for the claim, but the current evidence is not decisive."
            )
        )
    )
    return {
        "paper_key": paper.get("paper_key"),
        "stance": stance,
        "directness": round(max(
            support_signal if stance == "support" else (
                challenge_signal if stance == "challenge" else (
                    setup_signal if stance == "setup" else claim_relevance
                )
            ),
            0.12 if stance == "setup" else 0.08
        ), 3),
        "confidence": round(min(max(
            support_signal if stance == "support" else (
                challenge_signal if stance == "challenge" else (
                    setup_signal if stance == "setup" else claim_relevance
                )
            ),
            0.22
        ), 0.86), 3),
        "why_matched": why_matched,
        "caveat": "",
        "snippet_candidates": [item.get("text", "") for item in snippets],
    }

def _normalize_claim_snippets(project_id: int, claim_row: dict, raw_snippets, paper: dict, claim_tokens: List[str], claim_phrases: Optional[List[str]] = None, preferred_stance: str = "support") -> List[dict]:
    claim_phrases = claim_phrases or []
    normalized = []
    for raw_snippet in raw_snippets or []:
        grounded = _ground_claim_snippet(project_id, claim_row, raw_snippet, paper, claim_tokens, claim_phrases, preferred_stance=preferred_stance)
        if grounded:
            normalized.append(grounded)
            if len(normalized) >= MAX_EVIDENCE_SNIPPETS_PER_ITEM:
                break
            continue
        text = _trim_text(_compact_whitespace(raw_snippet), MAX_EVIDENCE_SNIPPET_TEXT_LENGTH)
        if text:
            normalized.append({
                "text": text,
                "source_field": "model_excerpt",
                "char_start": 0,
                "char_end": len(text),
            })
        if len(normalized) >= MAX_EVIDENCE_SNIPPETS_PER_ITEM:
            break
    if normalized:
        return normalized
    return _extract_claim_evidence_snippets(
        paper,
        claim_tokens,
        claim_phrases,
        limit=MAX_EVIDENCE_SNIPPETS_PER_ITEM,
        preferred_stance=preferred_stance
    )

def _analyze_claim_candidates(project_data: dict, claim_row: dict, candidates: List[dict]) -> Tuple[List[dict], bool]:
    if not candidates:
        return [], False
    project_id = int(project_data.get("id") or 0)
    claim_id = int((claim_row or {}).get("id") or 0)
    analysis_version = _claim_analysis_version(claim_row)
    claim_tokens = _claim_tokens(claim_row.get("claim_text", ""))
    claim_phrases = _claim_phrases(claim_row.get("claim_text", ""))
    llm_used = False
    final_items = []
    for index in range(0, len(candidates), CLAIM_ANALYSIS_BATCH_SIZE):
        batch = candidates[index:index + CLAIM_ANALYSIS_BATCH_SIZE]
        batch_results = []
        try:
            batch_payload = _build_claim_classification_payload(batch)
            cache_input = _build_claim_llm_batch_cache_input(project_data, claim_row, batch_payload)
            payload_hash = _hash_cache_payload(cache_input)
            cache_key = f"claim-llm-batch:{payload_hash}"
            cached_payload = _read_claim_cache_payload("claim_llm_batch_cache", cache_key, "response_json")
            if cached_payload:
                parsed = json.loads(cached_payload)
            else:
                prompt = _build_claim_classification_prompt(project_data, claim_row, batch)
                parsed = _parse_llm_json_payload(_call_llm_from_env(prompt, temperature=0.05, json_mode=True))
                _write_claim_llm_batch_cache(
                    cache_key,
                    project_id,
                    claim_id,
                    analysis_version,
                    _llm_cache_model_name(),
                    payload_hash,
                    _stable_json_dumps(parsed)
                )
            batch_results = parsed.get("results") if isinstance(parsed, dict) else parsed
            if not isinstance(batch_results, list):
                raise ValueError("Model returned an unexpected claim-analysis payload.")
            llm_used = True
        except Exception:
            batch_results = [_heuristic_claim_classification(paper, claim_tokens, claim_phrases) for paper in batch]

        result_map = {}
        for item in batch_results:
            if not isinstance(item, dict):
                continue
            paper_key = _trim_text(item.get("paper_key"), 120)
            if paper_key:
                result_map[paper_key] = item

        for paper in batch:
            fallback = _heuristic_claim_classification(paper, claim_tokens, claim_phrases)
            raw = result_map.get(paper.get("paper_key"), fallback)
            stance = _normalize_claim_stance(raw.get("stance"))
            try:
                directness = max(0.0, min(float(raw.get("directness") or fallback.get("directness") or 0), 1.0))
            except (TypeError, ValueError):
                directness = float(fallback.get("directness") or 0)
            try:
                confidence = max(0.0, min(float(raw.get("confidence") or fallback.get("confidence") or 0), 1.0))
            except (TypeError, ValueError):
                confidence = float(fallback.get("confidence") or 0)
            relevance_score = float(paper.get("claim_relevance") or 0)
            quality_score = float(paper.get("quality_score") or 0)
            strength_score = min(
                (directness * 0.45) +
                (relevance_score * 0.20) +
                (quality_score * 0.20) +
                (confidence * 0.15),
                1.0
            )
            final_items.append({
                "paper_key": paper.get("paper_key"),
                "paper_title": _trim_text(paper.get("title"), MAX_PAPER_TITLE_LENGTH),
                "paper_year": _trim_text(paper.get("year"), 40),
                "paper_authors": _trim_text(paper.get("authors"), MAX_PAPER_AUTHORS_LENGTH),
                "citation_key": _trim_text(paper.get("citation_key"), 120),
                "stance": stance,
                "strength_score": round(strength_score, 4),
                "relevance_score": round(relevance_score, 4),
                "confidence_score": round(confidence, 4),
                "quality_score": round(quality_score, 4),
                "why_matched": _trim_text(raw.get("why_matched") or fallback.get("why_matched"), MAX_EVIDENCE_WHY_MATCHED_LENGTH),
                "caveat": _trim_text(raw.get("caveat") or "", MAX_EVIDENCE_CAVEAT_LENGTH),
                "evidence_snippets": _normalize_claim_snippets(project_id, claim_row, raw.get("snippet_candidates"), paper, claim_tokens, claim_phrases, preferred_stance=stance),
            })
    return final_items, llm_used

def _resolve_project_paper_for_evidence(project_data: dict, evidence_row: dict) -> Optional[dict]:
    papers = _load_project_top_papers(project_data)
    if not papers:
        return None
    target_key = _trim_text((evidence_row or {}).get("paper_key"), 300)
    if target_key:
        for paper in papers:
            if _make_claim_paper_key(paper) == target_key:
                return paper

    target_signatures = set(_paper_identity_signatures(evidence_row or {}))
    target_title = _normalize_title_signature((evidence_row or {}).get("paper_title"))
    for paper in papers:
        paper_signatures = set(_paper_identity_signatures(paper))
        if target_signatures and paper_signatures.intersection(target_signatures):
            return paper
        if target_title and _normalize_title_signature(paper.get("title")) == target_title:
            return paper
    return None

def _fetch_openalex_works_by_ids(openalex_ids: List[str], api_key: str = "", contact_email: str = "", limit: int = MAX_CHALLENGE_EXPANSION_REFERENCES) -> List[dict]:
    works: List[dict] = []
    seen: set[str] = set()
    for openalex_id in openalex_ids or []:
        normalized = _trim_text(openalex_id, 300)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        try:
            work = _fetch_openalex_work_by_id(normalized, api_key, contact_email)
        except HTTPException:
            continue
        parsed_work = _parse_openalex_work(work)
        if parsed_work.get("openalex_id") and parsed_work.get("title"):
            works.append(parsed_work)
        if len(works) >= limit:
            break
    return works

def _fetch_openalex_cited_by_works(openalex_id: str, api_key: str = "", contact_email: str = "", limit: int = MAX_CHALLENGE_EXPANSION_CITED_BY) -> List[dict]:
    short_id = _extract_openalex_short_id(openalex_id)
    if not short_id:
        return []
    url = _build_url(
        "https://api.openalex.org/works",
        {
            "filter": f"cites:{short_id}",
            "per_page": max(1, min(int(limit or MAX_CHALLENGE_EXPANSION_CITED_BY), 25)),
            "cursor": "*",
            "api_key": api_key.strip()
        }
    )
    response = _http_get_json(url, contact_email)
    works: List[dict] = []
    for work in response.get("results", []) or []:
        parsed_work = _parse_openalex_work(work)
        if parsed_work.get("openalex_id") and parsed_work.get("title"):
            works.append(parsed_work)
        if len(works) >= limit:
            break
    return works

def _challenge_seed_text(seed_paper: dict) -> str:
    return "\n\n".join([
        _trim_text(seed_paper.get("title"), MAX_PAPER_TITLE_LENGTH),
        _trim_text(_compact_whitespace(seed_paper.get("abstract")), MAX_PAPER_ABSTRACT_LENGTH),
        _trim_text(_compact_whitespace(seed_paper.get("current_content")), MAX_CHALLENGE_EXPANSION_SEED_CONTENT_LENGTH),
    ]).strip()

def _challenge_expansion_seed_similarity(candidate: dict, seed_tokens: List[str], seed_phrases: List[str]) -> float:
    signal = _text_signal_bundle(
        "\n".join([
            str(candidate.get("title") or ""),
            str(candidate.get("abstract") or "")
        ]),
        seed_tokens,
        seed_phrases
    )
    return min(
        (signal["token_overlap"] * 0.56) +
        (signal["phrase_overlap"] * 0.32) +
        (signal["challenge_marker"] * 0.12),
        1.0
    )

def _heuristic_challenge_expansion_match(candidate: dict, claim_row: dict, seed_tokens: List[str], seed_phrases: List[str]) -> dict:
    claim_text = str((claim_row or {}).get("claim_text") or "")
    claim_tokens = _claim_tokens(claim_text)
    claim_phrases = _claim_phrases(claim_text)
    metrics = _build_claim_candidate_metrics(
        {
            **candidate,
            "status": candidate.get("status") or "Unread",
            "similarity": candidate.get("similarity") or 0,
        },
        claim_text,
        claim_tokens,
        claim_phrases,
        False
    )
    seed_similarity = _challenge_expansion_seed_similarity(candidate, seed_tokens, seed_phrases)
    relation_type = str(candidate.get("relationship_type") or "one_hop").strip().lower()
    relation_bonus = 0.05 if relation_type == "cited_by" else 0.03
    score = min(
        (float(metrics.get("challenge_hint") or 0) * 0.33) +
        (float(metrics.get("claim_relevance") or 0) * 0.29) +
        (seed_similarity * 0.28) +
        (float(metrics.get("quality_score") or 0) * 0.10) +
        relation_bonus,
        1.0
    )
    include = bool(
        score >= 0.26 and (
            float(metrics.get("challenge_hint") or 0) >= 0.16
            or seed_similarity >= 0.20
            or float(metrics.get("claim_relevance") or 0) >= 0.24
        )
    )
    why_matched = (
        "This one-hop paper appears to discuss limitations, boundary conditions, or contradictory findings close to the seed challenge paper."
        if include
        else "This one-hop paper looks related to the seed, but its challenge signal is still too weak or too indirect."
    )
    return {
        "include": include,
        "challenge_strength": round(score, 4),
        "claim_relevance": round(float(metrics.get("claim_relevance") or 0), 4),
        "seed_similarity": round(seed_similarity, 4),
        "why_matched": why_matched,
        "caveat": ""
    }

def _build_challenge_expansion_prompt(project_data: dict, claim_row: dict, seed_item: dict, seed_paper: dict, candidates: List[dict]) -> str:
    payload = []
    for candidate in candidates:
        payload.append({
            "candidate_key": candidate.get("candidate_key"),
            "relationship_type": candidate.get("relationship_type"),
            "title": _trim_text(candidate.get("title"), 320),
            "year": _trim_text(candidate.get("year"), 40),
            "authors": _trim_text(candidate.get("authors"), 220),
            "publication_venue": _trim_text(candidate.get("publication_venue"), 220),
            "citation_count": _safe_int(candidate.get("citation_count")),
            "abstract": _trim_text(_compact_whitespace(candidate.get("abstract")), 1800),
        })
    return (
        "You are expanding challenge literature for a research claim.\n\n"
        "The seed paper is already classified as a challenge paper for this claim.\n"
        "Your task is to inspect one-hop neighbors of the seed paper and decide which neighbors are worth recommending as additional challenge literature.\n\n"
        "Recommend a candidate only when it likely does at least one of the following:\n"
        "- contradicts the claim\n"
        "- narrows the claim with boundary conditions\n"
        "- reports null effects that weaken a broad version of the claim\n"
        "- challenges a mechanism used by the claim or by the seed paper\n\n"
        "Do not recommend generic background, mostly supportive papers, or methods-only setup papers unless they clearly function as challenge literature.\n"
        "Return JSON only in the form {\"results\":[{\"candidate_key\":\"...\",\"include\":true,\"challenge_strength\":0.0,\"why_matched\":\"...\",\"caveat\":\"...\"}]}\n\n"
        f"Project target title: {_trim_text(project_data.get('target_title'), 300)}\n"
        f"Project target abstract: {_trim_text(_compact_whitespace(project_data.get('target_abstract')), 1400)}\n"
        f"Claim text: {_trim_text(claim_row.get('claim_text'), MAX_CLAIM_TEXT_LENGTH)}\n"
        f"Seed evidence why matched: {_trim_text(seed_item.get('why_matched'), 600)}\n"
        f"Seed evidence caveat: {_trim_text(seed_item.get('caveat'), 500)}\n"
        f"Seed paper title: {_trim_text(seed_paper.get('title'), 320)}\n"
        f"Seed paper abstract: {_trim_text(_compact_whitespace(seed_paper.get('abstract')), 1600)}\n"
        f"Seed paper current content excerpt: {_trim_text(_compact_whitespace(seed_paper.get('current_content')), MAX_CHALLENGE_EXPANSION_SEED_CONTENT_LENGTH)}\n\n"
        f"Candidates:\n{json.dumps(payload, ensure_ascii=False)}"
    )

def _expand_challenge_seed(project_data: dict, claim_row: dict, evidence_row: dict, payload: ChallengeExpansionRequest) -> dict:
    if _normalize_claim_stance((evidence_row or {}).get("stance")) != "challenge":
        raise HTTPException(status_code=409, detail="Challenge expansion only works from a paper in the challenge column.")

    seed_paper = _resolve_project_paper_for_evidence(project_data, evidence_row)
    if not seed_paper:
        raise HTTPException(status_code=404, detail="Could not match this evidence item back to a project paper.")

    try:
        enriched_seed = _enrich_paper_for_citation_graph(
            PaperItem(**seed_paper),
            payload.openalex_api_key,
            payload.contact_email
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not resolve the seed paper on OpenAlex: {exc}")

    seed_openalex_id = _trim_text(enriched_seed.get("openalex_id"), 300)
    if not seed_openalex_id:
        raise HTTPException(status_code=404, detail="The seed challenge paper could not be resolved on OpenAlex.")

    references = _fetch_openalex_works_by_ids(
        enriched_seed.get("referenced_openalex_ids") or [],
        payload.openalex_api_key,
        payload.contact_email,
        payload.max_references
    )
    cited_by = _fetch_openalex_cited_by_works(
        seed_openalex_id,
        payload.openalex_api_key,
        payload.contact_email,
        payload.max_cited_by
    )

    project_signature_set = set()
    for paper in _load_project_top_papers(project_data):
        project_signature_set.update(_paper_identity_signatures(paper))

    candidates: List[dict] = []
    seen_candidate_keys: set[str] = set()
    skipped_existing = 0
    for relationship_type, works in (("reference", references), ("cited_by", cited_by)):
        for work in works:
            candidate_key = _paper_identity_key(work)
            if not candidate_key or candidate_key in seen_candidate_keys:
                continue
            seen_candidate_keys.add(candidate_key)
            if any(signature in project_signature_set for signature in _paper_identity_signatures(work)):
                skipped_existing += 1
                continue
            candidates.append({
                **work,
                "candidate_key": candidate_key,
                "relationship_type": relationship_type,
                "status": "Unread",
                "similarity": 0,
                "import_source": "citation_import"
            })

    if not candidates:
        return {
            "seed_paper": enriched_seed,
            "recommendations": [],
            "source_summary": {
                "reference_count": len(references),
                "cited_by_count": len(cited_by),
                "candidate_count": 0,
                "skipped_existing_count": skipped_existing,
                "returned_count": 0,
            }
        }

    seed_text = _challenge_seed_text(enriched_seed)
    seed_tokens = _claim_tokens(seed_text)
    seed_phrases = _claim_phrases(seed_text)
    heuristics_by_key: Dict[str, dict] = {}
    for candidate in candidates:
        heuristics_by_key[candidate["candidate_key"]] = _heuristic_challenge_expansion_match(candidate, claim_row, seed_tokens, seed_phrases)

    ranked_candidates = sorted(
        candidates,
        key=lambda candidate: (
            float((heuristics_by_key.get(candidate["candidate_key"]) or {}).get("challenge_strength") or 0),
            _safe_int(candidate.get("citation_count")),
            _trim_text(candidate.get("year"), 40)
        ),
        reverse=True
    )[:MAX_CHALLENGE_EXPANSION_CANDIDATES]

    llm_results_by_key: Dict[str, dict] = {}
    try:
        prompt = _build_challenge_expansion_prompt(project_data, claim_row, evidence_row, enriched_seed, ranked_candidates)
        parsed = _parse_llm_json_payload(_call_llm_from_env(prompt, temperature=0.05, json_mode=True))
        raw_results = parsed.get("results") if isinstance(parsed, dict) else []
        if isinstance(raw_results, list):
            for item in raw_results:
                if not isinstance(item, dict):
                    continue
                candidate_key = _trim_text(item.get("candidate_key"), 240)
                if candidate_key:
                    llm_results_by_key[candidate_key] = item
    except Exception:
        llm_results_by_key = {}

    recommendations = []
    for candidate in ranked_candidates:
        candidate_key = candidate["candidate_key"]
        heuristic = heuristics_by_key.get(candidate_key, {})
        llm_item = llm_results_by_key.get(candidate_key) or {}
        try:
            llm_strength = max(0.0, min(float(llm_item.get("challenge_strength") or 0), 1.0))
        except (TypeError, ValueError):
            llm_strength = 0.0
        include = bool(llm_item.get("include")) if "include" in llm_item else bool(heuristic.get("include"))
        final_score = (
            (llm_strength * 0.56) + (float(heuristic.get("challenge_strength") or 0) * 0.44)
            if llm_item else float(heuristic.get("challenge_strength") or 0)
        )
        if not include and final_score < 0.34:
            continue
        recommendations.append({
            **candidate,
            "relationship_label": "Referenced by seed" if candidate.get("relationship_type") == "reference" else "Cites seed",
            "challenge_score": round(min(final_score, 1.0), 4),
            "claim_relevance": heuristic.get("claim_relevance"),
            "seed_similarity": heuristic.get("seed_similarity"),
            "why_matched": _trim_text(llm_item.get("why_matched") or heuristic.get("why_matched"), MAX_EVIDENCE_WHY_MATCHED_LENGTH),
            "caveat": _trim_text(llm_item.get("caveat") or heuristic.get("caveat") or "", MAX_EVIDENCE_CAVEAT_LENGTH),
        })

    recommendations.sort(
        key=lambda item: (
            float(item.get("challenge_score") or 0),
            float(item.get("seed_similarity") or 0),
            _safe_int(item.get("citation_count"))
        ),
        reverse=True
    )
    recommendations = recommendations[:payload.max_results]

    return {
        "seed_paper": enriched_seed,
        "recommendations": recommendations,
        "source_summary": {
            "reference_count": len(references),
            "cited_by_count": len(cited_by),
            "candidate_count": len(candidates),
            "skipped_existing_count": skipped_existing,
            "returned_count": len(recommendations),
        }
    }

def _search_openalex_works(query: str, api_key: str = "", contact_email: str = "", per_page: int = MAX_STARDUST_SEMANTIC_RESULTS_PER_QUERY) -> List[dict]:
    cleaned_query = _trim_text(_compact_whitespace(query), 240)
    if not cleaned_query:
        return []
    params = {
        "search": cleaned_query,
        "per_page": max(1, min(int(per_page or MAX_STARDUST_SEMANTIC_RESULTS_PER_QUERY), 25)),
    }
    if api_key:
        params["api_key"] = api_key.strip()
    url = _build_url("https://api.openalex.org/works", params)
    response = _http_get_json(url, contact_email) or {}
    papers: List[dict] = []
    for work in response.get("results", []) or []:
        parsed = _parse_openalex_work(work)
        if not parsed or not parsed.get("title"):
            continue
        parsed["matched_query"] = cleaned_query
        papers.append(parsed)
    return papers

def _build_stardust_semantic_queries(project_data: dict, claim_row: dict, evidence_row: dict, seed_paper: dict, sub_target_thesis: str) -> List[str]:
    seed_title = _trim_text(_compact_whitespace(seed_paper.get("title")), 220)
    thesis_tokens = _claim_tokens(sub_target_thesis)
    claim_tokens = _claim_tokens((claim_row or {}).get("claim_text"))
    evidence_tokens = _claim_tokens(
        f"{_trim_text((evidence_row or {}).get('why_matched'), 600)} {_trim_text((evidence_row or {}).get('caveat'), 400)}"
    )
    target_tokens = _claim_tokens(
        f"{_trim_text((project_data or {}).get('target_title'), 220)} {_trim_text((project_data or {}).get('target_abstract'), 1400)}"
    )
    seed_title_tokens = _claim_tokens(seed_title)
    raw_queries = [
        seed_title,
        " ".join(thesis_tokens[:8]),
        " ".join(dict.fromkeys(seed_title_tokens[:4] + thesis_tokens[:5]).keys()),
        " ".join(dict.fromkeys(thesis_tokens[:4] + claim_tokens[:4] + evidence_tokens[:3]).keys()),
        " ".join(dict.fromkeys(seed_title_tokens[:3] + target_tokens[:3] + thesis_tokens[:3]).keys()),
    ]
    queries: List[str] = []
    for raw_query in raw_queries:
        cleaned = _trim_text(_compact_whitespace(raw_query), 240)
        if cleaned and cleaned not in queries:
            queries.append(cleaned)
        if len(queries) >= MAX_STARDUST_SEMANTIC_QUERY_COUNT:
            break
    return queries

def _register_stardust_candidate(
    candidates_by_key: Dict[str, dict],
    signature_to_primary: Dict[str, str],
    project_signature_set: set[str],
    work: dict,
    *,
    discovery_source: str,
    relationship_type: str,
    hop_distance: int,
    skipped: dict,
) -> bool:
    candidate_key = _paper_identity_key(work)
    if not candidate_key or not _trim_text(work.get("title"), MAX_PAPER_TITLE_LENGTH):
        skipped["invalid_count"] = int(skipped.get("invalid_count") or 0) + 1
        return False
    identity_signatures = list(dict.fromkeys(_paper_identity_signatures(work) + [candidate_key]))
    if any(signature in project_signature_set for signature in identity_signatures):
        skipped["existing_count"] = int(skipped.get("existing_count") or 0) + 1
        return False
    matched_primary = candidates_by_key.get(candidate_key)
    if not matched_primary:
        existing_primary_key = next((signature_to_primary.get(signature) for signature in identity_signatures if signature_to_primary.get(signature)), None)
        matched_primary = candidates_by_key.get(existing_primary_key or "")
    if matched_primary:
        candidate = matched_primary
        skipped["duplicate_count"] = int(skipped.get("duplicate_count") or 0) + 1
    else:
        candidate = {
            "paper_key": candidate_key,
            "title": _trim_text(work.get("title"), MAX_PAPER_TITLE_LENGTH),
            "abstract": _trim_text(work.get("abstract"), MAX_PAPER_ABSTRACT_LENGTH),
            "current_content": _trim_text(work.get("current_content"), MAX_PAPER_CURRENT_CONTENT_LENGTH),
            "authors": _trim_text(work.get("authors"), MAX_PAPER_AUTHORS_LENGTH),
            "year": _trim_text(work.get("year"), 40),
            "doi": _clean_doi(work.get("doi")),
            "openalex_id": _trim_text(work.get("openalex_id"), 300),
            "paper_url": _trim_text(work.get("paper_url"), 1000),
            "source_url": _trim_text(work.get("source_url"), 1000),
            "publication_venue": _trim_text(work.get("publication_venue"), 300),
            "citation_count": _safe_int(work.get("citation_count"), 0),
            "referenced_openalex_ids": list(work.get("referenced_openalex_ids") or []),
            "_identity_signatures": identity_signatures,
            "_discovery_sources": [],
            "_relationship_types": [],
            "_matched_queries": [],
            "hop_distance": max(1, _safe_int(hop_distance, 1)),
        }
        candidates_by_key[candidate_key] = candidate
        for signature in identity_signatures:
            signature_to_primary[signature] = candidate_key
    for field_name, max_length in (
        ("title", MAX_PAPER_TITLE_LENGTH),
        ("abstract", MAX_PAPER_ABSTRACT_LENGTH),
        ("current_content", MAX_PAPER_CURRENT_CONTENT_LENGTH),
        ("authors", MAX_PAPER_AUTHORS_LENGTH),
        ("year", 40),
        ("doi", 300),
        ("openalex_id", 300),
        ("paper_url", 1000),
        ("source_url", 1000),
        ("publication_venue", 300),
    ):
        incoming = _trim_text(work.get(field_name), max_length)
        if incoming and (not candidate.get(field_name) or len(incoming) > len(str(candidate.get(field_name) or ""))):
            candidate[field_name] = incoming
    candidate["citation_count"] = max(_safe_int(candidate.get("citation_count"), 0), _safe_int(work.get("citation_count"), 0))
    referenced_ids = list(dict.fromkeys((candidate.get("referenced_openalex_ids") or []) + list(work.get("referenced_openalex_ids") or [])))
    candidate["referenced_openalex_ids"] = referenced_ids[:120]
    if discovery_source and discovery_source not in candidate["_discovery_sources"]:
        candidate["_discovery_sources"].append(discovery_source)
    if relationship_type and relationship_type not in candidate["_relationship_types"]:
        candidate["_relationship_types"].append(relationship_type)
    matched_query = _trim_text(work.get("matched_query"), 240)
    if matched_query and matched_query not in candidate["_matched_queries"]:
        candidate["_matched_queries"].append(matched_query)
    candidate["hop_distance"] = min(max(1, _safe_int(candidate.get("hop_distance"), 1)), max(1, _safe_int(hop_distance, 1)))
    return True

def _score_stardust_candidate(candidate: dict, focus_claim_text: str, focus_tokens: List[str], focus_phrases: List[str], seed_tokens: List[str], seed_phrases: List[str]) -> dict:
    metrics = _build_claim_candidate_metrics(
        {
            **candidate,
            "status": candidate.get("status") or "Unread",
            "similarity": candidate.get("similarity") or 0,
        },
        focus_claim_text,
        focus_tokens,
        focus_phrases,
        False
    )
    challenge_hint = float(metrics.get("challenge_hint") or 0)
    claim_relevance = float(metrics.get("claim_relevance") or 0)
    quality_score = float(metrics.get("quality_score") or 0)
    seed_similarity = _challenge_expansion_seed_similarity(candidate, seed_tokens, seed_phrases)
    discovery_sources = list(candidate.get("_discovery_sources") or [])
    relationship_types = list(candidate.get("_relationship_types") or [])
    hop_distance = max(1, _safe_int(candidate.get("hop_distance"), 1))
    citation_bonus = min((math.log1p(max(_safe_int(candidate.get("citation_count"), 0), 0)) / math.log1p(250)), 1.0) * 0.03
    hop_bonus = 0.08 if hop_distance == 1 else (0.05 if hop_distance == 2 else 0.02)
    semantic_bonus = 0.06 if "semantic_supplement" in discovery_sources else 0.0
    relationship_bonus = 0.03 if "cited_by" in relationship_types else (0.02 if "reference" in relationship_types else 0.0)
    score = min(
        (challenge_hint * 0.32) +
        (claim_relevance * 0.29) +
        (seed_similarity * 0.20) +
        (quality_score * 0.10) +
        hop_bonus +
        semantic_bonus +
        relationship_bonus +
        citation_bonus,
        1.0
    )
    include = bool(
        score >= 0.28 and (
            challenge_hint >= 0.14
            or claim_relevance >= 0.25
            or seed_similarity >= 0.18
            or ("semantic_supplement" in discovery_sources and claim_relevance >= 0.34)
        )
    )
    reasons: List[str] = []
    if hop_distance == 1:
        reasons.append("it is directly connected to the seed paper in the citation graph")
    elif hop_distance == 2:
        reasons.append("it stays within two citation hops of the seed paper")
    elif "semantic_supplement" in discovery_sources:
        reasons.append("semantic search surfaced it outside the strict two-hop neighborhood")
    if claim_relevance >= 0.28:
        reasons.append("it matches the sub-target thesis closely")
    if seed_similarity >= 0.18:
        reasons.append("it overlaps strongly with the seed paper's topic")
    if challenge_hint >= 0.16:
        reasons.append("its language suggests limits, null effects, or boundary conditions")
    if "semantic_supplement" in discovery_sources and hop_distance <= 2:
        reasons.append("semantic search independently reinforced the citation-based match")
    if not reasons:
        reasons.append("it remained one of the strongest challenge-adjacent candidates in this seed trail")
    why_matched = f"This paper was kept because {'; '.join(reasons[:3])}."
    caveat = ""
    if challenge_hint < 0.12:
        caveat = "The challenge signal is inferred mostly from topical similarity rather than explicit contradictory language."
    elif hop_distance >= 3 and claim_relevance < 0.30:
        caveat = "This paper sits outside the direct citation neighborhood, so its fit depends more on semantic overlap."
    return {
        **candidate,
        "relationship_type": "+".join(sorted(relationship_types)) or "semantic_match",
        "discovery_source": "+".join(sorted(discovery_sources)) or "semantic_supplement",
        "challenge_score": round(score, 4),
        "seed_similarity": round(seed_similarity, 4),
        "claim_relevance": round(claim_relevance, 4),
        "quality_score": round(quality_score, 4),
        "why_matched": _trim_text(why_matched, MAX_EVIDENCE_WHY_MATCHED_LENGTH),
        "caveat": _trim_text(caveat, MAX_EVIDENCE_CAVEAT_LENGTH),
        "include": include,
    }

def _generate_challenge_stardust(project_data: dict, claim_row: dict, evidence_row: dict, payload: ChallengeStardustCreateRequest) -> dict:
    if _normalize_claim_stance((evidence_row or {}).get("stance")) != "challenge":
        raise HTTPException(status_code=409, detail="Challenge Stardust can only be created from a paper in the challenge column.")

    seed_paper = _resolve_project_paper_for_evidence(project_data, evidence_row)
    if not seed_paper:
        raise HTTPException(status_code=404, detail="Could not match this evidence item back to a project paper.")

    try:
        enriched_seed = _enrich_paper_for_citation_graph(
            PaperItem(**seed_paper),
            payload.openalex_api_key,
            payload.contact_email
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not resolve the seed paper on OpenAlex: {exc}")

    seed_openalex_id = _trim_text(enriched_seed.get("openalex_id"), 300)
    if not seed_openalex_id:
        raise HTTPException(status_code=404, detail="The seed challenge paper could not be resolved on OpenAlex.")

    project_signature_set = set()
    for paper in _load_project_top_papers(project_data):
        project_signature_set.update(_paper_identity_signatures(paper))

    candidates_by_key: Dict[str, dict] = {}
    signature_to_primary: Dict[str, str] = {}
    skipped = {"existing_count": 0, "duplicate_count": 0, "invalid_count": 0}
    partial_failures: List[dict] = []

    hop1_references = _fetch_openalex_works_by_ids(
        enriched_seed.get("referenced_openalex_ids") or [],
        payload.openalex_api_key,
        payload.contact_email,
        MAX_STARDUST_HOP1_REFERENCES
    )
    hop1_cited_by = _fetch_openalex_cited_by_works(
        seed_openalex_id,
        payload.openalex_api_key,
        payload.contact_email,
        MAX_STARDUST_HOP1_CITED_BY
    )
    for relationship_type, works in (("reference", hop1_references), ("cited_by", hop1_cited_by)):
        for work in works:
            _register_stardust_candidate(
                candidates_by_key,
                signature_to_primary,
                project_signature_set,
                work,
                discovery_source="hop_1",
                relationship_type=relationship_type,
                hop_distance=1,
                skipped=skipped,
            )

    focus_claim_text = "\n".join(
        part for part in [
            _trim_text(payload.sub_target_thesis, MAX_SUB_TARGET_THESIS_LENGTH),
            _trim_text((claim_row or {}).get("claim_text"), MAX_CLAIM_TEXT_LENGTH),
        ]
        if part
    )
    focus_tokens = _claim_tokens(focus_claim_text)
    focus_phrases = _claim_phrases(focus_claim_text)
    seed_text = _challenge_seed_text(enriched_seed)
    seed_tokens = _claim_tokens(seed_text)
    seed_phrases = _claim_phrases(seed_text)

    hop1_ranked: List[dict] = []
    for candidate in candidates_by_key.values():
        if max(1, _safe_int(candidate.get("hop_distance"), 1)) != 1:
            continue
        hop1_ranked.append(_score_stardust_candidate(candidate, focus_claim_text, focus_tokens, focus_phrases, seed_tokens, seed_phrases))
    hop1_ranked.sort(
        key=lambda item: (
            float(item.get("challenge_score") or 0),
            float(item.get("claim_relevance") or 0),
            float(item.get("seed_similarity") or 0),
            _safe_int(item.get("citation_count"), 0)
        ),
        reverse=True
    )

    hop2_seed_candidates = hop1_ranked[:MAX_STARDUST_HOP2_SEEDS]
    hop2_reference_count = 0
    hop2_cited_by_count = 0
    for seed_candidate in hop2_seed_candidates:
        seed_candidate_openalex_id = _trim_text(seed_candidate.get("openalex_id"), 300)
        if not seed_candidate_openalex_id:
            continue
        try:
            hop2_references = _fetch_openalex_works_by_ids(
                seed_candidate.get("referenced_openalex_ids") or [],
                payload.openalex_api_key,
                payload.contact_email,
                MAX_STARDUST_HOP2_REFERENCES_PER_SEED
            )
            hop2_cited_by = _fetch_openalex_cited_by_works(
                seed_candidate_openalex_id,
                payload.openalex_api_key,
                payload.contact_email,
                MAX_STARDUST_HOP2_CITED_BY_PER_SEED
            )
        except HTTPException as exc:
            partial_failures.append({
                "stage": "hop_2",
                "seed_title": _trim_text(seed_candidate.get("title"), 160),
                "detail": _trim_text(str(exc.detail), 200),
            })
            continue
        hop2_reference_count += len(hop2_references)
        hop2_cited_by_count += len(hop2_cited_by)
        for relationship_type, works in (("reference", hop2_references), ("cited_by", hop2_cited_by)):
            for work in works:
                _register_stardust_candidate(
                    candidates_by_key,
                    signature_to_primary,
                    project_signature_set,
                    work,
                    discovery_source="hop_2",
                    relationship_type=relationship_type,
                    hop_distance=2,
                    skipped=skipped,
                )

    semantic_queries = _build_stardust_semantic_queries(project_data, claim_row, evidence_row, enriched_seed, payload.sub_target_thesis)
    semantic_result_count = 0
    for query in semantic_queries:
        try:
            semantic_results = _search_openalex_works(
                query,
                payload.openalex_api_key,
                payload.contact_email,
                MAX_STARDUST_SEMANTIC_RESULTS_PER_QUERY
            )
        except HTTPException as exc:
            partial_failures.append({
                "stage": "semantic_supplement",
                "query": _trim_text(query, 140),
                "detail": _trim_text(str(exc.detail), 200),
            })
            continue
        semantic_result_count += len(semantic_results)
        for work in semantic_results:
            _register_stardust_candidate(
                candidates_by_key,
                signature_to_primary,
                project_signature_set,
                work,
                discovery_source="semantic_supplement",
                relationship_type="semantic_match",
                hop_distance=3,
                skipped=skipped,
            )

    scored_candidates = [
        _score_stardust_candidate(candidate, focus_claim_text, focus_tokens, focus_phrases, seed_tokens, seed_phrases)
        for candidate in candidates_by_key.values()
    ]
    scored_candidates.sort(
        key=lambda item: (
            float(item.get("challenge_score") or 0),
            float(item.get("claim_relevance") or 0),
            float(item.get("seed_similarity") or 0),
            float(item.get("quality_score") or 0),
            _safe_int(item.get("citation_count"), 0)
        ),
        reverse=True
    )
    included_candidates = [item for item in scored_candidates if item.get("include")]
    if not included_candidates:
        included_candidates = [item for item in scored_candidates if float(item.get("challenge_score") or 0) >= 0.22]
    if len(included_candidates) < payload.max_papers:
        seen_candidate_ids = {id(item) for item in included_candidates}
        for item in scored_candidates:
            if id(item) in seen_candidate_ids:
                continue
            included_candidates.append(item)
            seen_candidate_ids.add(id(item))
            if len(included_candidates) >= payload.max_papers:
                break
    included_candidates = included_candidates[:payload.max_papers]
    for item in included_candidates:
        item.pop("include", None)
        item.pop("_identity_signatures", None)
        item.pop("_discovery_sources", None)
        item.pop("_relationship_types", None)
        item.pop("_matched_queries", None)

    source_summary = {
        "hop1_reference_count": len(hop1_references),
        "hop1_cited_by_count": len(hop1_cited_by),
        "hop2_seed_count": len(hop2_seed_candidates),
        "hop2_reference_count": hop2_reference_count,
        "hop2_cited_by_count": hop2_cited_by_count,
        "semantic_query_count": len(semantic_queries),
        "semantic_result_count": semantic_result_count,
        "deduped_candidate_count": len(candidates_by_key),
        "skipped_existing_count": int(skipped.get("existing_count") or 0),
        "skipped_duplicate_count": int(skipped.get("duplicate_count") or 0),
        "skipped_invalid_count": int(skipped.get("invalid_count") or 0),
        "stored_count": len(included_candidates),
        "partial_failures": partial_failures[:12],
    }
    return {
        "seed_paper": enriched_seed,
        "papers": included_candidates,
        "source_summary": source_summary,
    }

def _default_claim_summary() -> dict:
    return {stance: 0 for stance in sorted(CLAIM_STANCE_VALUES)}

def _serialize_claim_evidence_row(row: dict) -> dict:
    item = dict(row)
    try:
        item["evidence_snippets"] = json.loads(item.get("evidence_snippets_json") or "[]")
    except Exception:
        item["evidence_snippets"] = []
    item.pop("evidence_snippets_json", None)
    item["user_override"] = bool(item.get("user_override"))
    item["pinned"] = bool(item.get("pinned"))
    item["hidden"] = bool(item.get("hidden"))
    return item

def _create_claim_analysis_run(claim_id: int, project_id: int) -> int:
    now = _now_ts()
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO claim_analysis_runs (claim_id, project_id, candidate_count, analyzed_count, status, summary_json, error_text, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (claim_id, project_id, 0, 0, "running", "{}", "", now, now)
    )
    conn.commit()
    run_id = int(cursor.lastrowid)
    conn.close()
    return run_id

def _update_claim_analysis_run(run_id: int, **kwargs):
    if not kwargs:
        return
    allowed = {"candidate_count", "analyzed_count", "status", "summary_json", "error_text", "updated_at"}
    fields = []
    params = []
    for key, value in kwargs.items():
        if key not in allowed:
            continue
        fields.append(f"{key} = ?")
        params.append(value)
    if not fields:
        return
    params.append(run_id)
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE claim_analysis_runs SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()

def _stable_json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _hash_cache_payload(value) -> str:
    return hashlib.sha1(_stable_json_dumps(value).encode("utf-8")).hexdigest()

def _claim_analysis_version(claim_row: dict) -> str:
    return _trim_text((claim_row or {}).get("analysis_version"), MAX_CLAIM_ANALYSIS_VERSION_LENGTH) or "v1"

def _llm_cache_model_name() -> str:
    provider = (_env_value("STARMAP_LLM_PROVIDER", "groq") or "groq").lower()
    if provider == "openai":
        model = "gpt-4o-mini"
    elif provider == "deepseek":
        model = "deepseek-chat"
    elif provider == "gemini":
        model = GEMINI_MODEL
    else:
        model = "llama-3.1-8b-instant"
    return f"{provider}:{model}"

def _read_claim_cache_payload(table_name: str, cache_key: str, payload_column: str) -> Optional[str]:
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT {payload_column} AS payload FROM {table_name} WHERE cache_key = ?",
        (cache_key,)
    )
    row = cursor.fetchone()
    if row:
        cursor.execute(f"UPDATE {table_name} SET last_hit_at = ? WHERE cache_key = ?", (_now_ts(), cache_key))
        conn.commit()
    conn.close()
    if not row:
        return None
    return row["payload"]

def _write_claim_candidate_cache(cache_key: str, project_id: int, claim_id: int, analysis_version: str, payload_hash: str, candidate_json: str):
    now = _now_ts()
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO claim_candidate_cache (cache_key, project_id, claim_id, analysis_version, payload_hash, candidate_json, created_at, last_hit_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(cache_key) DO UPDATE SET
               analysis_version = excluded.analysis_version,
               payload_hash = excluded.payload_hash,
               candidate_json = excluded.candidate_json,
               last_hit_at = excluded.last_hit_at''',
        (cache_key, project_id, claim_id, analysis_version, payload_hash, candidate_json, now, now)
    )
    conn.commit()
    conn.close()
    _cleanup_claim_caches(force=False)

def _write_claim_llm_batch_cache(cache_key: str, project_id: int, claim_id: int, analysis_version: str, model_name: str, payload_hash: str, response_json: str):
    now = _now_ts()
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO claim_llm_batch_cache (cache_key, project_id, claim_id, analysis_version, model_name, payload_hash, response_json, created_at, last_hit_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(cache_key) DO UPDATE SET
               analysis_version = excluded.analysis_version,
               model_name = excluded.model_name,
               payload_hash = excluded.payload_hash,
               response_json = excluded.response_json,
               last_hit_at = excluded.last_hit_at''',
        (cache_key, project_id, claim_id, analysis_version, model_name, payload_hash, response_json, now, now)
    )
    conn.commit()
    conn.close()
    _cleanup_claim_caches(force=False)

def _write_claim_snippet_cache(cache_key: str, project_id: int, claim_id: int, analysis_version: str, paper_key: str, payload_hash: str, snippet_json: str):
    now = _now_ts()
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO claim_snippet_cache (cache_key, project_id, claim_id, analysis_version, paper_key, payload_hash, snippet_json, created_at, last_hit_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(cache_key) DO UPDATE SET
               analysis_version = excluded.analysis_version,
               paper_key = excluded.paper_key,
               payload_hash = excluded.payload_hash,
               snippet_json = excluded.snippet_json,
               last_hit_at = excluded.last_hit_at''',
        (cache_key, project_id, claim_id, analysis_version, paper_key, payload_hash, snippet_json, now, now)
    )
    conn.commit()
    conn.close()
    _cleanup_claim_caches(force=False)

def _build_claim_candidate_cache_input(project_data: dict, claim_row: dict, include_statuses: List[str], max_candidates: int, prefer_fulltext: bool) -> dict:
    papers = []
    for paper in _load_project_top_papers(project_data):
        papers.append({
            "paper_key": _make_claim_paper_key(paper),
            "title": _trim_text(paper.get("title"), MAX_PAPER_TITLE_LENGTH),
            "abstract": _trim_text(_compact_whitespace(paper.get("abstract")), 2400),
            "notes": _trim_text(_compact_whitespace(paper.get("notes")), 1800),
            "current_content": _trim_text(_compact_whitespace(paper.get("current_content")), 2800),
            "status": _trim_text(paper.get("status"), 40),
            "similarity": float(paper.get("similarity") or 0),
            "citation_count": _safe_int(paper.get("citation_count"), 0),
            "year": _trim_text(paper.get("year"), 20),
            "authors": _trim_text(paper.get("authors"), MAX_PAPER_AUTHORS_LENGTH),
            "publication_venue": _trim_text(paper.get("publication_venue"), 240),
            "zotero_has_fulltext": bool(paper.get("zotero_has_fulltext")),
            "citation_cluster_id": _trim_text(paper.get("citation_cluster_id"), 200),
            "citation_cluster_theme_name": _trim_text(paper.get("citation_cluster_theme_name"), 240),
            "citation_key": _trim_text(paper.get("citation_key"), 120),
        })
    papers.sort(key=lambda item: item["paper_key"])
    return {
        "analysis_version": _claim_analysis_version(claim_row),
        "claim_id": int((claim_row or {}).get("id") or 0),
        "claim_text": _trim_text((claim_row or {}).get("claim_text"), MAX_CLAIM_TEXT_LENGTH),
        "claim_type": _trim_text((claim_row or {}).get("claim_type"), MAX_CLAIM_TYPE_LENGTH),
        "section_label": _trim_text((claim_row or {}).get("section_label"), MAX_CLAIM_SECTION_LABEL_LENGTH),
        "project_id": int(project_data.get("id") or 0),
        "target_title": _trim_text(project_data.get("target_title"), MAX_TARGET_TITLE_LENGTH),
        "target_abstract": _trim_text(_compact_whitespace(project_data.get("target_abstract")), 2400),
        "target_current_content": _trim_text(_compact_whitespace(project_data.get("target_current_content")), 2800),
        "include_statuses": sorted({str(status or "").strip().lower() for status in include_statuses if str(status or "").strip()}),
        "max_candidates": int(max_candidates),
        "prefer_fulltext": bool(prefer_fulltext),
        "papers": papers,
    }

def _build_claim_classification_payload(candidates: List[dict]) -> List[dict]:
    payload = []
    for paper in candidates:
        payload.append({
            "paper_key": paper.get("paper_key"),
            "title": _trim_text(paper.get("title"), 220),
            "authors": _trim_text(paper.get("authors"), 260),
            "year": _trim_text(paper.get("year"), 20),
            "status": _trim_text(paper.get("status"), 30),
            "citation_count": _safe_int(paper.get("citation_count"), 0),
            "publication_venue": _trim_text(paper.get("publication_venue"), 180),
            "abstract": _trim_text(_compact_whitespace(paper.get("abstract")), 1400),
            "notes": _trim_text(_compact_whitespace(paper.get("notes")), 900),
            "current_content": _trim_text(_compact_whitespace(paper.get("current_content")), 1800),
        })
    return payload

def _build_claim_llm_batch_cache_input(project_data: dict, claim_row: dict, batch_payload: List[dict]) -> dict:
    return {
        "analysis_version": _claim_analysis_version(claim_row),
        "model_name": _llm_cache_model_name(),
        "project_id": int(project_data.get("id") or 0),
        "claim_id": int((claim_row or {}).get("id") or 0),
        "claim_text": _trim_text((claim_row or {}).get("claim_text"), MAX_CLAIM_TEXT_LENGTH),
        "claim_type": _trim_text((claim_row or {}).get("claim_type"), MAX_CLAIM_TYPE_LENGTH),
        "section_label": _trim_text((claim_row or {}).get("section_label"), MAX_CLAIM_SECTION_LABEL_LENGTH),
        "target_title": _trim_text(project_data.get("target_title"), 300),
        "target_abstract": _trim_text(_compact_whitespace(project_data.get("target_abstract")), 1800),
        "target_current_content": _trim_text(_compact_whitespace(project_data.get("target_current_content")), 1800),
        "papers": batch_payload,
    }

def _build_claim_snippet_cache_input(project_id: int, claim_row: dict, paper: dict, raw_snippet: str, preferred_stance: str) -> dict:
    return {
        "analysis_version": _claim_analysis_version(claim_row),
        "project_id": int(project_id or 0),
        "claim_id": int((claim_row or {}).get("id") or 0),
        "claim_text": _trim_text((claim_row or {}).get("claim_text"), MAX_CLAIM_TEXT_LENGTH),
        "paper_key": _trim_text(paper.get("paper_key"), 160),
        "preferred_stance": _normalize_claim_stance(preferred_stance),
        "raw_snippet": _trim_text(_compact_whitespace(raw_snippet), MAX_EVIDENCE_SNIPPET_TEXT_LENGTH),
        "abstract": _trim_text(_compact_whitespace(paper.get("abstract")), 2400),
        "current_content": _trim_text(_compact_whitespace(paper.get("current_content")), 3200),
        "notes": _trim_text(_compact_whitespace(paper.get("notes")), 1800),
    }

def _claim_cache_usage_stats() -> dict:
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    stats = {"total_rows": 0, "total_bytes": 0, "tables": {}}
    for table_name, payload_column in CACHE_PRIORITY_ORDER:
        cursor.execute(
            f"""SELECT
                    COUNT(*) AS row_count,
                    COALESCE(SUM(LENGTH(cache_key)), 0)
                    + COALESCE(SUM(LENGTH(payload_hash)), 0)
                    + COALESCE(SUM(LENGTH(analysis_version)), 0)
                    + COALESCE(SUM(LENGTH({payload_column})), 0) AS approx_bytes
                FROM {table_name}"""
        )
        row = cursor.fetchone()
        row_count = int((row["row_count"] or 0) if row else 0)
        approx_bytes = int((row["approx_bytes"] or 0) if row else 0)
        if table_name == "claim_llm_batch_cache":
            cursor.execute(f"SELECT COALESCE(SUM(LENGTH(model_name)), 0) AS extra_bytes FROM {table_name}")
            extra = cursor.fetchone()
            approx_bytes += int((extra["extra_bytes"] or 0) if extra else 0)
        elif table_name == "claim_snippet_cache":
            cursor.execute(f"SELECT COALESCE(SUM(LENGTH(paper_key)), 0) AS extra_bytes FROM {table_name}")
            extra = cursor.fetchone()
            approx_bytes += int((extra["extra_bytes"] or 0) if extra else 0)
        stats["tables"][table_name] = {"rows": row_count, "bytes": approx_bytes}
        stats["total_rows"] += row_count
        stats["total_bytes"] += approx_bytes
    conn.close()
    return stats

def _delete_oldest_claim_cache_rows(table_name: str, delete_count: int) -> int:
    if delete_count <= 0:
        return 0
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute(
        f"""DELETE FROM {table_name}
            WHERE cache_key IN (
                SELECT cache_key
                FROM {table_name}
                ORDER BY last_hit_at ASC, created_at ASC, cache_key ASC
                LIMIT ?
            )""",
        (int(delete_count),)
    )
    deleted = int(cursor.rowcount or 0)
    conn.commit()
    conn.close()
    return deleted

def _cleanup_claim_caches(force: bool = False) -> dict:
    now = _now_ts()
    if not force and (now - int(CLAIM_CACHE_MAINTENANCE.get("last_checked_at") or 0)) < CACHE_CLEANUP_MIN_INTERVAL_SECONDS:
        return {"skipped": True}

    CLAIM_CACHE_MAINTENANCE["last_checked_at"] = now
    before = _claim_cache_usage_stats()
    if (
        before["total_bytes"] <= CACHE_SOFT_LIMIT_BYTES
        and before["total_rows"] <= CACHE_ROW_LIMIT
        and not force
    ):
        return {"skipped": True, "stats": before}

    target_bytes = CACHE_TARGET_LIMIT_BYTES if before["total_bytes"] > CACHE_SOFT_LIMIT_BYTES else before["total_bytes"]
    target_rows = CACHE_TARGET_ROW_LIMIT if before["total_rows"] > CACHE_ROW_LIMIT else before["total_rows"]
    if before["total_bytes"] > CACHE_HARD_LIMIT_BYTES:
        target_bytes = min(target_bytes, CACHE_TARGET_LIMIT_BYTES)
    deleted_by_table = {}

    for table_name, _payload_column in CACHE_PRIORITY_ORDER:
        current = _claim_cache_usage_stats()
        if current["total_bytes"] <= target_bytes and current["total_rows"] <= target_rows:
            break
        table_rows = int((current["tables"].get(table_name) or {}).get("rows") or 0)
        if table_rows <= 0:
            continue
        overflow_rows = max(current["total_rows"] - target_rows, 0)
        delete_count = min(
            table_rows,
            max(CACHE_CLEANUP_BATCH_SIZE, overflow_rows, math.ceil(table_rows * 0.2))
        )
        deleted = _delete_oldest_claim_cache_rows(table_name, delete_count)
        if deleted > 0:
            deleted_by_table[table_name] = deleted_by_table.get(table_name, 0) + deleted

    after = _claim_cache_usage_stats()
    return {
        "skipped": False,
        "before": before,
        "after": after,
        "deleted_by_table": deleted_by_table,
    }

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

def _get_owned_claim(project_id: int, claim_id: int, user_id: int) -> dict:
    _get_owned_project(project_id, user_id)
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM project_claims WHERE id = ? AND project_id = ?",
        (claim_id, project_id)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Claim not found.")
    return dict(row)

def _normalize_stardust_status(raw_status: Optional[str]) -> str:
    value = _trim_text(raw_status or "draft", MAX_STARDUST_STATUS_LENGTH).lower() or "draft"
    return value if value in STARDUST_STATUS_VALUES else "draft"

def _normalize_stardust_graph_mode(raw_mode: Optional[str]) -> str:
    value = _trim_text(raw_mode or "directed", 40).lower() or "directed"
    return value if value in STARDUST_GRAPH_MODE_VALUES else "directed"

def _validate_stardust_create_payload(payload: ChallengeStardustCreateRequest) -> ChallengeStardustCreateRequest:
    payload.claim_id = max(1, int(payload.claim_id or 0))
    payload.seed_evidence_id = max(1, int(payload.seed_evidence_id or 0))
    payload.name = _trim_text(payload.name, MAX_STARDUST_NAME_LENGTH)
    payload.sub_target_thesis = _trim_text(payload.sub_target_thesis, MAX_SUB_TARGET_THESIS_LENGTH)
    payload.replace_stardust_id = int(payload.replace_stardust_id) if payload.replace_stardust_id else None
    payload.max_papers = max(10, min(int(payload.max_papers or MAX_STARDUST_PAPERS), MAX_STARDUST_PAPERS))
    if not payload.name:
        raise HTTPException(status_code=400, detail="Stardust name cannot be empty.")
    if not payload.sub_target_thesis:
        raise HTTPException(status_code=400, detail="Sub target thesis cannot be empty.")
    return _apply_runtime_defaults_to_lookup(payload)

def _validate_stardust_update_payload(payload: ChallengeStardustUpdateRequest) -> ChallengeStardustUpdateRequest:
    if payload.name is not None:
        payload.name = _trim_text(payload.name, MAX_STARDUST_NAME_LENGTH)
        if not payload.name:
            raise HTTPException(status_code=400, detail="Stardust name cannot be empty.")
    if payload.sub_target_thesis is not None:
        payload.sub_target_thesis = _trim_text(payload.sub_target_thesis, MAX_SUB_TARGET_THESIS_LENGTH)
        if not payload.sub_target_thesis:
            raise HTTPException(status_code=400, detail="Sub target thesis cannot be empty.")
    if payload.status is not None:
        payload.status = _normalize_stardust_status(payload.status)
    return payload

def _validate_stardust_graph_build_payload(payload: ChallengeStardustGraphBuildRequest) -> ChallengeStardustGraphBuildRequest:
    payload.mode = _normalize_stardust_graph_mode(payload.mode)
    payload.force_rebuild = bool(payload.force_rebuild)
    return _apply_runtime_defaults_to_lookup(payload)

def _serialize_stardust_seed_summary(conn: sqlite3.Connection, stardust_row: dict) -> Optional[dict]:
    seed_evidence_id = int(stardust_row.get("seed_evidence_id") or 0)
    if not seed_evidence_id:
        return None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, paper_key, paper_title, paper_year, paper_authors, citation_key, stance, why_matched, caveat FROM claim_evidence_items WHERE id = ?",
        (seed_evidence_id,)
    )
    row = cursor.fetchone()
    if not row:
        return None
    item = dict(row)
    item["stance"] = _normalize_claim_stance(item.get("stance"))
    return item

def _serialize_stardust_claim_summary(conn: sqlite3.Connection, stardust_row: dict) -> Optional[dict]:
    claim_id = int(stardust_row.get("claim_id") or 0)
    if not claim_id:
        return None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, claim_text, claim_type, section_label, status, analysis_version, created_at, updated_at FROM project_claims WHERE id = ?",
        (claim_id,)
    )
    row = cursor.fetchone()
    if not row:
        return None
    claim = dict(row)
    claim["claim_type"] = _normalize_claim_type(claim.get("claim_type"))
    claim["status"] = _normalize_claim_status(claim.get("status"))
    return claim

def _serialize_stardust_graph_summaries(conn: sqlite3.Connection, stardust_id: int) -> List[dict]:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, graph_mode, graph_signature, created_at, updated_at FROM challenge_stardust_graph_cache WHERE stardust_id = ? ORDER BY updated_at DESC, id DESC",
        (stardust_id,)
    )
    return [
        {
            "id": int(row["id"]),
            "graph_mode": _normalize_stardust_graph_mode(row["graph_mode"]),
            "graph_signature": row["graph_signature"] or "",
            "created_at": int(row["created_at"] or 0),
            "updated_at": int(row["updated_at"] or 0),
        }
        for row in cursor.fetchall()
    ]

def _serialize_stardust_row(conn: sqlite3.Connection, row: dict, include_children: bool = False) -> dict:
    item = dict(row)
    item["status"] = _normalize_stardust_status(item.get("status"))
    item["paper_count"] = int(item.get("paper_count") or 0)
    try:
        item["source_summary"] = json.loads(item.get("source_summary_json") or "{}")
    except Exception:
        item["source_summary"] = {}
    item.pop("source_summary_json", None)
    item["seed"] = _serialize_stardust_seed_summary(conn, item)
    item["claim"] = _serialize_stardust_claim_summary(conn, item)
    item["graphs"] = _serialize_stardust_graph_summaries(conn, int(item.get("id") or 0))
    if include_children:
        item["papers"] = _load_stardust_papers(conn, int(item.get("id") or 0))
    return item

def _serialize_stardust_paper_row(row: dict) -> dict:
    item = dict(row)
    try:
        item["referenced_openalex_ids"] = json.loads(item.get("referenced_openalex_ids_json") or "[]")
    except Exception:
        item["referenced_openalex_ids"] = []
    item.pop("referenced_openalex_ids_json", None)
    item["selected_for_import"] = bool(item.get("selected_for_import"))
    item["hidden"] = bool(item.get("hidden"))
    item["hop_distance"] = int(item.get("hop_distance") or 0)
    return item

def _load_stardust_papers(conn: sqlite3.Connection, stardust_id: int, include_hidden: bool = True) -> List[dict]:
    cursor = conn.cursor()
    if include_hidden:
        cursor.execute(
            "SELECT * FROM challenge_stardust_papers WHERE stardust_id = ? ORDER BY challenge_score DESC, citation_count DESC, id DESC",
            (stardust_id,)
        )
    else:
        cursor.execute(
            "SELECT * FROM challenge_stardust_papers WHERE stardust_id = ? AND hidden = 0 ORDER BY challenge_score DESC, citation_count DESC, id DESC",
            (stardust_id,)
        )
    return [_serialize_stardust_paper_row(dict(row)) for row in cursor.fetchall()]

def _get_owned_stardust(project_id: int, stardust_id: int, user_id: int) -> dict:
    _get_owned_project(project_id, user_id)
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM challenge_stardusts WHERE id = ? AND project_id = ?",
        (stardust_id, project_id)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Challenge Stardust not found.")
    return dict(row)

def _delete_stardust_records(conn: sqlite3.Connection, stardust_id: int):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM challenge_stardust_graph_cache WHERE stardust_id = ?", (stardust_id,))
    cursor.execute("DELETE FROM challenge_stardust_papers WHERE stardust_id = ?", (stardust_id,))
    cursor.execute("DELETE FROM challenge_stardusts WHERE id = ?", (stardust_id,))

def _insert_stardust_papers(conn: sqlite3.Connection, stardust_id: int, papers: List[dict]):
    if not papers:
        return
    cursor = conn.cursor()
    now = _now_ts()
    rows = []
    for paper in papers:
        rows.append((
            stardust_id,
            _trim_text(paper.get("paper_key"), 300),
            _trim_text(paper.get("title"), MAX_PAPER_TITLE_LENGTH),
            _trim_text(paper.get("abstract"), MAX_PAPER_ABSTRACT_LENGTH),
            _trim_text(paper.get("current_content"), MAX_PAPER_CURRENT_CONTENT_LENGTH),
            _trim_text(paper.get("authors"), MAX_PAPER_AUTHORS_LENGTH),
            _trim_text(paper.get("year"), 40),
            _clean_doi(paper.get("doi")),
            _trim_text(paper.get("openalex_id"), 300),
            _trim_text(paper.get("paper_url"), 1000),
            _trim_text(paper.get("source_url"), 1000),
            _trim_text(paper.get("publication_venue"), 300),
            _safe_int(paper.get("citation_count"), 0),
            json.dumps(paper.get("referenced_openalex_ids") or [], ensure_ascii=False),
            _trim_text(paper.get("relationship_type"), 120),
            _trim_text(paper.get("discovery_source"), 120),
            max(0, min(_safe_int(paper.get("hop_distance"), 0), 9)),
            round(max(0.0, min(float(paper.get("challenge_score") or 0), 1.0)), 4),
            round(max(0.0, min(float(paper.get("seed_similarity") or 0), 1.0)), 4),
            round(max(0.0, min(float(paper.get("claim_relevance") or 0), 1.0)), 4),
            round(max(0.0, min(float(paper.get("quality_score") or 0), 1.0)), 4),
            _trim_text(paper.get("why_matched"), MAX_EVIDENCE_WHY_MATCHED_LENGTH),
            _trim_text(paper.get("caveat"), MAX_EVIDENCE_CAVEAT_LENGTH),
            0,
            0,
            now,
            now,
        ))
    cursor.executemany(
        '''INSERT INTO challenge_stardust_papers (
            stardust_id, paper_key, title, abstract, current_content, authors, year, doi,
            openalex_id, paper_url, source_url, publication_venue, citation_count,
            referenced_openalex_ids_json, relationship_type, discovery_source, hop_distance,
            challenge_score, seed_similarity, claim_relevance, quality_score, why_matched,
            caveat, selected_for_import, hidden, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        rows
    )

def _stardust_paper_to_paper_item(paper: dict) -> PaperItem:
    return PaperItem(
        filename=_trim_text(paper.get("paper_key") or f"stardust-paper-{paper.get('id') or uuid.uuid4().hex}", 300),
        title=_trim_text(paper.get("title"), MAX_PAPER_TITLE_LENGTH),
        abstract=_trim_text(paper.get("abstract"), MAX_PAPER_ABSTRACT_LENGTH),
        current_content=_trim_text(paper.get("current_content"), MAX_PAPER_CURRENT_CONTENT_LENGTH),
        authors=_trim_text(paper.get("authors"), MAX_PAPER_AUTHORS_LENGTH) or "Unknown",
        year=_trim_text(paper.get("year"), 40) or "Unknown",
        similarity=float(paper.get("challenge_score") or 0),
        status="Unread",
        doi=_clean_doi(paper.get("doi")),
        paper_url=_trim_text(paper.get("paper_url"), 1000),
        publication_venue=_trim_text(paper.get("publication_venue"), 300),
        citation_count=_safe_int(paper.get("citation_count"), 0),
        openalex_id=_trim_text(paper.get("openalex_id"), 300),
        referenced_openalex_ids=list(paper.get("referenced_openalex_ids") or []),
        source_url=_trim_text(paper.get("source_url"), 1000),
        import_source="challenge_stardust",
    )

def _update_stardust_paper_graph_metadata(conn: sqlite3.Connection, stardust_id: int, paper: dict):
    paper_id = int(paper.get("id") or 0)
    if not paper_id:
        return
    cursor = conn.cursor()
    cursor.execute(
        '''UPDATE challenge_stardust_papers SET
               doi = ?, openalex_id = ?, paper_url = ?, source_url = ?, publication_venue = ?,
               citation_count = ?, referenced_openalex_ids_json = ?, updated_at = ?
           WHERE id = ? AND stardust_id = ?''',
        (
            _clean_doi(paper.get("doi")),
            _trim_text(paper.get("openalex_id"), 300),
            _trim_text(paper.get("paper_url"), 1000),
            _trim_text(paper.get("source_url"), 1000),
            _trim_text(paper.get("publication_venue"), 300),
            _safe_int(paper.get("citation_count"), 0),
            json.dumps(paper.get("referenced_openalex_ids") or [], ensure_ascii=False),
            _now_ts(),
            paper_id,
            stardust_id,
        )
    )

def _build_stardust_graph_signature(papers: List[dict], mode: str) -> str:
    payload = [
        {
            "paper_key": _trim_text(paper.get("paper_key"), 300),
            "title": _trim_text(paper.get("title"), MAX_PAPER_TITLE_LENGTH),
            "openalex_id": _trim_text(paper.get("openalex_id"), 300),
            "citation_count": _safe_int(paper.get("citation_count"), 0),
            "referenced_openalex_ids": sorted([
                _trim_text(value, 300)
                for value in (paper.get("referenced_openalex_ids") or [])
                if _trim_text(value, 300)
            ]),
        }
        for paper in sorted(
            papers or [],
            key=lambda item: (
                _trim_text(item.get("paper_key"), 300),
                _trim_text(item.get("openalex_id"), 300),
                _trim_text(item.get("title"), MAX_PAPER_TITLE_LENGTH)
            )
        )
    ]
    return hashlib.sha1(_stable_json_dumps({"mode": _normalize_stardust_graph_mode(mode), "papers": payload}).encode("utf-8")).hexdigest()

def _load_stardust_graph_cache(conn: sqlite3.Connection, stardust_id: int, mode: str) -> Optional[dict]:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM challenge_stardust_graph_cache WHERE stardust_id = ? AND graph_mode = ?",
        (stardust_id, _normalize_stardust_graph_mode(mode))
    )
    row = cursor.fetchone()
    if not row:
        return None
    item = dict(row)
    try:
        nodes = json.loads(item.get("nodes_json") or "[]")
    except Exception:
        nodes = []
    try:
        edges = json.loads(item.get("edges_json") or "[]")
    except Exception:
        edges = []
    try:
        meta = json.loads(item.get("meta_json") or "{}")
    except Exception:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    meta["mode"] = _normalize_stardust_graph_mode(item.get("graph_mode"))
    meta["graph_signature"] = item.get("graph_signature") or ""
    return {
        "id": int(item.get("id") or 0),
        "graph_mode": meta["mode"],
        "graph_signature": item.get("graph_signature") or "",
        "nodes": nodes if isinstance(nodes, list) else [],
        "edges": edges if isinstance(edges, list) else [],
        "meta": meta,
        "created_at": int(item.get("created_at") or 0),
        "updated_at": int(item.get("updated_at") or 0),
    }

def _upsert_stardust_graph_cache(conn: sqlite3.Connection, stardust_id: int, mode: str, signature: str, nodes: List[dict], edges: List[dict], meta: dict):
    normalized_mode = _normalize_stardust_graph_mode(mode)
    now = _now_ts()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO challenge_stardust_graph_cache (
               stardust_id, graph_mode, graph_signature, nodes_json, edges_json, meta_json, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(stardust_id, graph_mode) DO UPDATE SET
               graph_signature = excluded.graph_signature,
               nodes_json = excluded.nodes_json,
               edges_json = excluded.edges_json,
               meta_json = excluded.meta_json,
               updated_at = excluded.updated_at''',
        (
            stardust_id,
            normalized_mode,
            signature,
            json.dumps(nodes, ensure_ascii=False),
            json.dumps(edges, ensure_ascii=False),
            json.dumps(meta, ensure_ascii=False),
            now,
            now,
        )
    )
    cursor.execute(
        "UPDATE challenge_stardusts SET graph_cache_signature = ?, updated_at = ? WHERE id = ?",
        (signature, now, stardust_id)
    )

def _build_stardust_graph_result(enriched_papers: List[dict], mode: str, partial_failures: Optional[List[dict]] = None) -> dict:
    normalized_mode = _normalize_stardust_graph_mode(mode)
    base_result = _build_citation_graph_result(enriched_papers)
    full_edges = list(base_result.get("edges") or [])
    edge_lookup = {
        (str(edge.get("source") or "").strip(), str(edge.get("target") or "").strip())
        for edge in full_edges
        if str(edge.get("source") or "").strip() and str(edge.get("target") or "").strip()
    }
    mutual_pairs: Dict[Tuple[str, str], dict] = {}
    directed_only_edges: List[dict] = []
    for edge in full_edges:
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if not source or not target or source == target:
            continue
        reverse_key = (target, source)
        if reverse_key in edge_lookup:
            pair_key = tuple(sorted([source, target]))
            if pair_key not in mutual_pairs:
                mutual_pairs[pair_key] = {
                    "source": pair_key[0],
                    "target": pair_key[1],
                    "relationship": "mutual",
                }
        else:
            directed_only_edges.append({
                **edge,
                "relationship": "directed"
            })

    if normalized_mode == "mutual":
        display_edges = list(mutual_pairs.values())
    elif normalized_mode == "full":
        display_edges = [
            {
                **edge,
                "relationship": "mutual_member" if tuple(sorted([str(edge.get("source") or "").strip(), str(edge.get("target") or "").strip()])) in mutual_pairs else "directed"
            }
            for edge in full_edges
        ]
    else:
        display_edges = directed_only_edges

    stats = {
        **(base_result.get("stats") or {}),
        "mode": normalized_mode,
        "full_edge_count": len(full_edges),
        "directed_only_edge_count": len(directed_only_edges),
        "mutual_pair_count": len(mutual_pairs),
        "edge_count": len(display_edges),
        "partial_failures": (partial_failures or [])[:12],
    }
    return {
        "mode": normalized_mode,
        "nodes": enriched_papers,
        "edges": display_edges,
        "stats": stats,
    }

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
    citation_cluster_id: str = ""
    citation_cluster_theme_name: str = ""
    citation_cluster_theme_summary: str = ""
    citation_cluster_indegree: Optional[int] = None
    citation_cluster_core_rank: Optional[int] = None
    citation_cluster_is_core: bool = False
    citation_cluster_size: Optional[int] = None
    citation_cluster_graph_signature: str = ""
    citation_cluster_version: str = ""

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

class SemanticClusterRequest(BaseModel):
    project_id: int = 0
    target_title: str = ""
    target_abstract: str = ""
    target_current_content: str = ""
    papers: List[PaperItem]
    seed_limit: int = SEMANTIC_CLUSTER_SEED_LIMIT
    assignment_limit: int = MAX_TOP_PAPERS

class SemanticClusterJobCreated(BaseModel):
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

class LiteratureWatchJournalSource(BaseModel):
    id: str = ""
    display_name: str = ""
    target_watch_weight: str = "standard"

class LiteratureWatchSourceSearchRequest(BaseModel):
    query: str
    limit: int = 5

class LiteratureWatchRequest(BaseModel):
    mode: str = "target"
    lookback_window: str = "3m"
    limit: int = 12
    discipline: str = ""
    discipline_scopes: List[str] = Field(default_factory=list)
    scholar_names: List[str] = Field(default_factory=list)
    journal_sources: List[LiteratureWatchJournalSource] = Field(default_factory=list)

class ClaimCreateRequest(BaseModel):
    claim_text: str
    claim_type: str = "thesis_claim"
    section_label: str = ""

class ClaimAnalyzeRequest(BaseModel):
    max_candidates: int = 36
    reanalyze_overrides: bool = False
    include_statuses: List[str] = Field(default_factory=lambda: ["Core", "Pending", "Underweight", "Unread"])
    prefer_fulltext: bool = True

class ClaimEvidencePatchRequest(BaseModel):
    stance: Optional[str] = None
    pinned: Optional[bool] = None
    hidden: Optional[bool] = None
    user_override: Optional[bool] = None
    why_matched: Optional[str] = None
    caveat: Optional[str] = None

class ChallengeStardustCreateRequest(BaseModel):
    claim_id: int
    seed_evidence_id: int
    name: str
    sub_target_thesis: str
    replace_stardust_id: Optional[int] = None
    max_papers: int = MAX_STARDUST_PAPERS
    openalex_api_key: str = ""
    contact_email: str = ""

class ChallengeStardustUpdateRequest(BaseModel):
    name: Optional[str] = None
    sub_target_thesis: Optional[str] = None
    status: Optional[str] = None

class ChallengeStardustPaperPatchRequest(BaseModel):
    selected_for_import: Optional[bool] = None
    hidden: Optional[bool] = None

class ChallengeStardustGraphBuildRequest(BaseModel):
    mode: str = "directed"
    force_rebuild: bool = False
    openalex_api_key: str = ""
    contact_email: str = ""

class ChallengeExpansionRequest(BaseModel):
    evidence_id: int
    max_references: int = MAX_CHALLENGE_EXPANSION_REFERENCES
    max_cited_by: int = MAX_CHALLENGE_EXPANSION_CITED_BY
    max_results: int = MAX_CHALLENGE_EXPANSION_RESULTS
    openalex_api_key: str = ""
    contact_email: str = ""

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

def _validate_challenge_expansion_payload(payload: ChallengeExpansionRequest) -> ChallengeExpansionRequest:
    payload.evidence_id = max(1, int(payload.evidence_id or 0))
    payload.max_references = max(4, min(int(payload.max_references or MAX_CHALLENGE_EXPANSION_REFERENCES), 20))
    payload.max_cited_by = max(4, min(int(payload.max_cited_by or MAX_CHALLENGE_EXPANSION_CITED_BY), 20))
    payload.max_results = max(4, min(int(payload.max_results or MAX_CHALLENGE_EXPANSION_RESULTS), 20))
    return _apply_runtime_defaults_to_lookup(payload)

def _tokenize_literature_watch_text(value: str) -> List[str]:
    return [
        token for token in re.findall(r"[A-Za-z0-9]+", str(value or "").lower())
        if len(token) >= 3 and token not in LITERATURE_WATCH_STOPWORDS
    ]

def _normalize_watch_discipline(raw_value: str) -> str:
    key = str(raw_value or "").strip().lower()
    if key in LITERATURE_WATCH_DISCIPLINE_ALIASES:
        key = LITERATURE_WATCH_DISCIPLINE_ALIASES[key]
    return key if key in LITERATURE_WATCH_DISCIPLINES else DEFAULT_LITERATURE_WATCH_DISCIPLINE

def _normalize_watch_discipline_scopes(raw_values) -> List[str]:
    normalized: List[str] = []
    for raw_value in raw_values or []:
        key = _normalize_watch_discipline(raw_value)
        if key not in normalized:
            normalized.append(key)
        if len(normalized) >= 3:
            break
    return normalized or [DEFAULT_LITERATURE_WATCH_DISCIPLINE]

def _discipline_config(raw_value: str) -> dict:
    return LITERATURE_WATCH_DISCIPLINES[_normalize_watch_discipline(raw_value)]

def _combined_discipline_config(raw_values) -> dict:
    scopes = _normalize_watch_discipline_scopes(raw_values)
    configs = [_discipline_config(scope) for scope in scopes]
    labels = [config.get("label", scope) for config, scope in zip(configs, scopes)]
    top_venues: List[str] = []
    venue_keywords: List[str] = []
    for config in configs:
        for venue in config.get("top_venues", []):
            if venue not in top_venues:
                top_venues.append(venue)
        for keyword in config.get("venue_keywords", []):
            if keyword not in venue_keywords:
                venue_keywords.append(keyword)
    return {
        "keys": scopes,
        "labels": labels,
        "label": " · ".join(labels),
        "top_venues": top_venues,
        "venue_keywords": venue_keywords,
    }

def _normalize_watch_mode(raw_value: str) -> str:
    mode = str(raw_value or "target").strip().lower()
    return mode if mode in {"target", "scholar", "journal"} else "target"

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

def _get_project_watch_context(project_data: dict, discipline_scopes: List[str]) -> dict:
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
        "disciplines": _normalize_watch_discipline_scopes(discipline_scopes)
    }

def _build_watch_fallback_strategy(context: dict) -> dict:
    weighted_terms: Dict[str, float] = {}
    discipline = _combined_discipline_config(context.get("disciplines", []))

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

def _semantic_cluster_hash(text: str) -> int:
    return int(hashlib.md5(str(text or "").encode("utf-8")).hexdigest(), 16)

def _semantic_cluster_tokenize(text: str) -> List[str]:
    normalized = unicodedata.normalize("NFKD", str(text or "").lower())
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return [token for token in tokens if len(token) >= 3 and token not in SEMANTIC_CLUSTER_STOPWORDS]

def _semantic_cluster_add_weighted_terms(container: Dict[str, float], text: str, weight: float, *, include_bigrams: bool = True):
    tokens = _semantic_cluster_tokenize(text)
    if not tokens:
        return
    for token in tokens:
        container[token] = container.get(token, 0.0) + weight
    if include_bigrams and len(tokens) > 1:
        for index in range(len(tokens) - 1):
            bigram = f"{tokens[index]} {tokens[index + 1]}"
            container[bigram] = container.get(bigram, 0.0) + (weight * 1.15)

def _build_semantic_cluster_term_weights(paper: dict) -> Dict[str, float]:
    weighted_terms: Dict[str, float] = {}
    title = str((paper or {}).get("title") or "").strip()
    abstract = str((paper or {}).get("abstract") or "").strip()
    current_content = str((paper or {}).get("current_content") or "").strip()[:SEMANTIC_CLUSTER_CURRENT_CONTENT_LIMIT]
    _semantic_cluster_add_weighted_terms(weighted_terms, title, 3.0, include_bigrams=True)
    _semantic_cluster_add_weighted_terms(weighted_terms, abstract, 1.8, include_bigrams=True)
    _semantic_cluster_add_weighted_terms(weighted_terms, current_content, 0.9, include_bigrams=False)
    return weighted_terms

def _normalize_vector(values: List[float]) -> List[float]:
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]

def _average_vectors(vectors: List[List[float]]) -> List[float]:
    if not vectors:
        return []
    length = len(vectors[0])
    sums = [0.0] * length
    for vector in vectors:
        for index, value in enumerate(vector):
            sums[index] += value
    return _normalize_vector([value / len(vectors) for value in sums])

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    length = min(len(a), len(b))
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for index in range(length):
        dot += a[index] * b[index]
        norm_a += a[index] * a[index]
        norm_b += b[index] * b[index]
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))

def _hash_weighted_terms_to_vector(weighted_terms: Dict[str, float], document_frequency: Dict[str, int], total_docs: int, vector_dim: int = SEMANTIC_CLUSTER_TEXT_VECTOR_DIM) -> List[float]:
    vector = [0.0] * vector_dim
    for term, weight in weighted_terms.items():
        df = document_frequency.get(term, 1)
        idf = math.log((total_docs + 1) / (df + 1)) + 1.0
        bucket_hash = _semantic_cluster_hash(term)
        bucket = bucket_hash % vector_dim
        sign = 1.0 if ((_semantic_cluster_hash(f"sign::{term}") & 1) == 0) else -1.0
        vector[bucket] += weight * idf * sign
    return _normalize_vector(vector)

def _get_cluster_size_list(assignments: List[int], cluster_count: int) -> List[int]:
    sizes = [0] * cluster_count
    for index in assignments:
        if 0 <= index < cluster_count:
            sizes[index] += 1
    return sizes

def _assign_vectors_to_centroids(vectors: List[List[float]], centroids: List[List[float]]) -> List[int]:
    assignments: List[int] = []
    for vector in vectors:
        best_index = 0
        best_score = float("-inf")
        for index, centroid in enumerate(centroids):
            score = _cosine_similarity(vector, centroid)
            if score > best_score:
                best_score = score
                best_index = index
        assignments.append(best_index)
    return assignments

def _assign_vectors_to_centroids_with_scores(vectors: List[List[float]], centroids: List[List[float]]) -> List[dict]:
    results: List[dict] = []
    for vector in vectors:
        best_index = 0
        best_score = float("-inf")
        for index, centroid in enumerate(centroids):
            score = _cosine_similarity(vector, centroid)
            if score > best_score:
                best_score = score
                best_index = index
        results.append({"clusterIndex": best_index, "score": best_score})
    return results

def _recalculate_centroids(vectors: List[List[float]], assignments: List[int], cluster_count: int, fallback_centroids: List[List[float]]) -> List[List[float]]:
    centroids: List[List[float]] = []
    for cluster_index in range(cluster_count):
        members = [vector for vector_index, vector in enumerate(vectors) if assignments[vector_index] == cluster_index]
        centroids.append(_average_vectors(members) if members else fallback_centroids[cluster_index])
    return centroids

def _initialize_kmeans_plus_plus(vectors: List[List[float]], cluster_count: int, seed_offset: int = 0) -> List[List[float]]:
    if not vectors:
        return []
    first_index = _semantic_cluster_hash(f"{seed_offset}:{len(vectors)}") % len(vectors)
    centroid_indices = [first_index]
    while len(centroid_indices) < cluster_count:
        best_index = 0
        best_distance = float("-inf")
        for index, vector in enumerate(vectors):
            if index in centroid_indices:
                continue
            nearest_similarity = max(_cosine_similarity(vector, vectors[centroid_index]) for centroid_index in centroid_indices)
            distance = 1.0 - nearest_similarity
            jitter = ((_semantic_cluster_hash(f"{seed_offset}:{index}") % 997) / 997000.0)
            if distance + jitter > best_distance:
                best_distance = distance + jitter
                best_index = index
        centroid_indices.append(best_index)
    return [vectors[index] for index in centroid_indices]

def _rebalance_undersized_clusters(vectors: List[List[float]], assignments: List[int], centroids: List[List[float]], min_size: int = SEMANTIC_CLUSTER_MIN_SIZE) -> Tuple[List[int], List[List[float]]]:
    cluster_count = len(centroids)
    if cluster_count <= 0 or len(vectors) < cluster_count * min_size:
        return assignments, centroids
    next_assignments = list(assignments)
    next_centroids = [list(centroid) for centroid in centroids]
    cluster_sizes = _get_cluster_size_list(next_assignments, cluster_count)
    guard = 0
    while any(size < min_size for size in cluster_sizes) and guard < len(vectors) * max(cluster_count, 1):
        guard += 1
        target_index = next((index for index, size in enumerate(cluster_sizes) if size < min_size), -1)
        donor_indices = [index for index, size in enumerate(cluster_sizes) if size > min_size]
        if target_index < 0 or not donor_indices:
            break
        best_vector_index = -1
        best_score = float("-inf")
        for donor_index in donor_indices:
            for vector_index, assigned_cluster in enumerate(next_assignments):
                if assigned_cluster != donor_index:
                    continue
                target_score = _cosine_similarity(vectors[vector_index], next_centroids[target_index])
                donor_score = _cosine_similarity(vectors[vector_index], next_centroids[donor_index])
                relocation_score = (target_score * 1.15) - donor_score
                if relocation_score > best_score:
                    best_score = relocation_score
                    best_vector_index = vector_index
        if best_vector_index < 0:
            break
        next_assignments[best_vector_index] = target_index
        cluster_sizes = _get_cluster_size_list(next_assignments, cluster_count)
        next_centroids = _recalculate_centroids(vectors, next_assignments, cluster_count, next_centroids)
    return next_assignments, next_centroids

def _evaluate_cluster_assignments(vectors: List[List[float]], assignments: List[int], centroids: List[List[float]]) -> float:
    if not vectors or not centroids:
        return 0.0
    cluster_sizes = _get_cluster_size_list(assignments, len(centroids))
    undersized_penalty = 0.0
    for size in cluster_sizes:
        if size < SEMANTIC_CLUSTER_MIN_SIZE:
            undersized_penalty += (SEMANTIC_CLUSTER_MIN_SIZE - size) * 0.28
    margin_total = 0.0
    for vector_index, vector in enumerate(vectors):
        own_index = assignments[vector_index]
        own_score = _cosine_similarity(vector, centroids[own_index])
        next_best = max([
            _cosine_similarity(vector, centroid)
            for centroid_index, centroid in enumerate(centroids)
            if centroid_index != own_index
        ] or [0.0])
        margin_total += (own_score - next_best)
    return (margin_total / len(vectors)) - undersized_penalty

def _extract_semantic_candidate_terms(paper: dict) -> List[str]:
    generic_terms = {
        "paper", "study", "studies", "evidence", "model", "models", "analysis", "default",
        "country", "countries", "international", "empirical", "approach", "effects", "effect",
        "role", "global", "financial", "finance", "credit", "ratings", "rating", "risk", "risks"
    }
    title_tokens = [
        token for token in _semantic_cluster_tokenize((paper or {}).get("title", ""))
        if token not in generic_terms
    ]
    phrases: List[str] = []
    for index in range(len(title_tokens) - 1):
        phrase = f"{title_tokens[index]} {title_tokens[index + 1]}"
        if not any(part in generic_terms for part in phrase.split(" ")):
            phrases.append(phrase)
    return phrases + title_tokens

def _select_distinct_semantic_terms(cluster_papers: List[dict], all_papers: List[dict], limit: int = 4) -> List[str]:
    cluster_df: Dict[str, int] = {}
    global_df: Dict[str, int] = {}
    for paper in all_papers:
        for term in set(_extract_semantic_candidate_terms(paper)):
            global_df[term] = global_df.get(term, 0) + 1
    for paper in cluster_papers:
        for term in set(_extract_semantic_candidate_terms(paper)):
            cluster_df[term] = cluster_df.get(term, 0) + 1
    total_docs = max(len(all_papers), 1)
    cluster_size = max(len(cluster_papers), 1)
    scored_terms: List[dict] = []
    for term, count in cluster_df.items():
        global_count = global_df.get(term, count)
        cluster_ratio = count / cluster_size
        global_ratio = global_count / total_docs
        if global_ratio > 0.34:
            continue
        idf = math.log((total_docs + 1) / (global_count + 1)) + 1.0
        lift = cluster_ratio / max(global_ratio, 0.0001)
        phrase_boost = 1.18 if " " in term else 1.0
        scored_terms.append({"term": term, "score": cluster_ratio * idf * lift * phrase_boost})
    scored_terms.sort(key=lambda item: item["score"], reverse=True)
    chosen: List[str] = []
    for item in scored_terms:
        term = item["term"]
        if any(existing in term or term in existing for existing in chosen):
            continue
        chosen.append(term)
        if len(chosen) >= limit:
            break
    return chosen

def _title_case_semantic_words(words: List[str]) -> List[str]:
    output: List[str] = []
    for word in words:
        output.append(" ".join(part[:1].upper() + part[1:] for part in word.split(" ") if part))
    return output

def _build_semantic_cluster_presentation(clusters: List[dict], all_papers: List[dict]) -> List[dict]:
    presented: List[dict] = []
    for index, cluster in enumerate(clusters):
        top_terms = _select_distinct_semantic_terms(cluster.get("papers", []), all_papers)
        label = " / ".join(_title_case_semantic_words(top_terms[:2])) if top_terms else f"Theme {index + 1}"
        summary = (
            f"This cluster emphasizes {', '.join(top_terms[:3])} rather than the corpus-wide baseline topics."
            if top_terms else
            "This cluster groups papers with similar semantic content."
        )
        presented.append({
            **cluster,
            "label": label,
            "summary": summary,
            "topTerms": top_terms
        })
    return presented

def _build_semantic_cluster_signature(papers: List[dict], seed_limit: int, assignment_limit: int) -> str:
    serialized = json.dumps([
        {
            "filename": str((paper or {}).get("filename") or ""),
            "title": str((paper or {}).get("title") or "").strip(),
            "abstract": str((paper or {}).get("abstract") or "").strip(),
            "current_content": str((paper or {}).get("current_content") or "").strip()[:SEMANTIC_CLUSTER_CURRENT_CONTENT_LIMIT],
            "similarity": round(float((paper or {}).get("similarity") or 0), 6),
        }
        for paper in papers
    ], ensure_ascii=False, separators=(",", ":"))
    return f"{SEMANTIC_CLUSTER_ALGORITHM_VERSION}:{seed_limit}:{assignment_limit}:{hashlib.sha1(serialized.encode('utf-8')).hexdigest()}"

def _is_semantic_cluster_paper_analyzable(paper: dict) -> bool:
    return bool(str((paper or {}).get("title") or "").strip()) and (
        bool(str((paper or {}).get("abstract") or "").strip())
        or bool(str((paper or {}).get("current_content") or "").strip())
    )

def _select_semantic_assignment_papers(papers: List[dict], assignment_limit: int) -> List[dict]:
    analyzable = [paper for paper in (papers or []) if _is_semantic_cluster_paper_analyzable(paper)]
    analyzable.sort(key=lambda paper: float((paper or {}).get("similarity") or 0), reverse=True)
    normalized_limit = max(3, min(int(assignment_limit or MAX_TOP_PAPERS), MAX_TOP_PAPERS))
    return analyzable[:normalized_limit]

def _build_semantic_cluster_result(payload: SemanticClusterRequest, progress_callback=None) -> dict:
    assignment_limit = max(3, min(int(payload.assignment_limit or MAX_TOP_PAPERS), MAX_TOP_PAPERS))
    seed_limit = max(3, min(int(payload.seed_limit or SEMANTIC_CLUSTER_SEED_LIMIT), assignment_limit))
    source_papers = [paper.model_dump() if hasattr(paper, "model_dump") else dict(paper) for paper in payload.papers[:MAX_TOP_PAPERS]]
    assignment_papers = _select_semantic_assignment_papers(source_papers, assignment_limit)
    seed_papers = assignment_papers[:seed_limit]
    signature = _build_semantic_cluster_signature(assignment_papers, seed_limit, assignment_limit)

    if progress_callback:
        progress_callback("prepare", 6, f"Preparing {len(assignment_papers)} papers for backend semantic clustering...")

    if len(seed_papers) < 3:
        return {
            "projectId": int(payload.project_id or 0),
            "clusterMode": "semantic",
            "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "signature": signature,
            "seedSignature": signature,
            "paperCount": len(seed_papers),
            "assignedPaperCount": len(assignment_papers),
            "clusterQuality": 0,
            "clusters": [],
            "usedLlmThemeNaming": False
        }

    term_weights_by_paper: List[Dict[str, float]] = []
    document_frequency: Dict[str, int] = {}
    for index, paper in enumerate(assignment_papers, start=1):
        weighted_terms = _build_semantic_cluster_term_weights(paper)
        term_weights_by_paper.append(weighted_terms)
        for term in set(weighted_terms.keys()):
            document_frequency[term] = document_frequency.get(term, 0) + 1
        if progress_callback and (index % 8 == 0 or index == len(assignment_papers)):
            percent = 10 + int((index / max(len(assignment_papers), 1)) * 38)
            progress_callback("embedding", percent, f"Building backend semantic embeddings: {index}/{len(assignment_papers)} papers")

    total_docs = max(len(term_weights_by_paper), 1)
    assignment_vectors = [
        _hash_weighted_terms_to_vector(weighted_terms, document_frequency, total_docs)
        for weighted_terms in term_weights_by_paper
    ]
    seed_vectors = assignment_vectors[:len(seed_papers)]

    max_cluster_count = min(max(3, len(seed_papers)), len(seed_papers), max(SEMANTIC_CLUSTER_COUNT_OPTIONS))
    candidate_counts = [count for count in SEMANTIC_CLUSTER_COUNT_OPTIONS if count <= max_cluster_count]
    best_result = None
    total_runs = 0
    for cluster_count in candidate_counts:
        total_runs += SEMANTIC_CLUSTER_BASE_ATTEMPTS + 1
    completed_runs = 0

    for cluster_count in candidate_counts:
        candidate_best = None
        for attempt_index in range(SEMANTIC_CLUSTER_BASE_ATTEMPTS + 1):
            if attempt_index > 0 and candidate_best:
                cluster_sizes = candidate_best.get("clusterSizes", [])
                has_undersized = len(seed_vectors) >= cluster_count * SEMANTIC_CLUSTER_MIN_SIZE and any(size < SEMANTIC_CLUSTER_MIN_SIZE for size in cluster_sizes)
                if candidate_best.get("score", 0) >= SEMANTIC_CLUSTER_QUALITY_RETRY_THRESHOLD and not has_undersized:
                    break
            if progress_callback:
                completed_runs += 1
                progress_callback(
                    "clustering",
                    50 + int((completed_runs / max(total_runs, 1)) * 28),
                    f"Testing {cluster_count} semantic themes (pass {attempt_index + 1})..."
                )
            centroids = _initialize_kmeans_plus_plus(seed_vectors, cluster_count, seed_offset=attempt_index + cluster_count)
            assignments = _assign_vectors_to_centroids(seed_vectors, centroids)
            for _ in range(8):
                centroids = _recalculate_centroids(seed_vectors, assignments, cluster_count, centroids)
                next_assignments = _assign_vectors_to_centroids(seed_vectors, centroids)
                if next_assignments == assignments:
                    break
                assignments = next_assignments
            assignments, centroids = _rebalance_undersized_clusters(seed_vectors, assignments, centroids, SEMANTIC_CLUSTER_MIN_SIZE)
            score = _evaluate_cluster_assignments(seed_vectors, assignments, centroids)
            candidate = {
                "clusterCount": cluster_count,
                "assignments": assignments,
                "centroids": centroids,
                "score": score,
                "clusterSizes": _get_cluster_size_list(assignments, cluster_count)
            }
            if not candidate_best or score > candidate_best["score"]:
                candidate_best = candidate
        if candidate_best and (not best_result or candidate_best["score"] > best_result["score"]):
            best_result = candidate_best

    if not best_result:
        return {
            "projectId": int(payload.project_id or 0),
            "clusterMode": "semantic",
            "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "signature": signature,
            "seedSignature": signature,
            "paperCount": len(seed_papers),
            "assignedPaperCount": len(assignment_papers),
            "clusterQuality": 0,
            "clusters": [],
            "usedLlmThemeNaming": False
        }

    if progress_callback:
        progress_callback("assignment", 84, f"Assigning top {len(assignment_papers)} papers using Visualization Density...")

    assignment_results = _assign_vectors_to_centroids_with_scores(assignment_vectors, best_result["centroids"])
    target_weighted_terms = {}
    _semantic_cluster_add_weighted_terms(target_weighted_terms, payload.target_title, 3.0, include_bigrams=True)
    _semantic_cluster_add_weighted_terms(target_weighted_terms, payload.target_abstract, 1.8, include_bigrams=True)
    _semantic_cluster_add_weighted_terms(target_weighted_terms, str(payload.target_current_content or "")[:SEMANTIC_CLUSTER_CURRENT_CONTENT_LIMIT], 0.9, include_bigrams=False)
    target_vector = _hash_weighted_terms_to_vector(target_weighted_terms, document_frequency, total_docs) if target_weighted_terms else []

    clusters: List[dict] = []
    for cluster_index, centroid in enumerate(best_result["centroids"]):
        assigned = []
        for paper_index, paper in enumerate(assignment_papers):
            result = assignment_results[paper_index]
            if result["clusterIndex"] != cluster_index:
                continue
            enriched = dict(paper)
            enriched["cluster_similarity"] = result["score"]
            assigned.append(enriched)
        assigned.sort(key=lambda item: (float(item.get("cluster_similarity") or 0), float(item.get("similarity") or 0)), reverse=True)
        if not assigned:
            continue
        clusters.append({
            "index": cluster_index,
            "target_relevance": max(0.0, _cosine_similarity(target_vector, centroid)) if target_vector else 0.0,
            "papers": assigned,
            "representative_papers": assigned[:SEMANTIC_CLUSTER_MAX_DISPLAY_PAPERS],
        })
    clusters.sort(key=lambda cluster: len(cluster.get("papers", [])), reverse=True)

    if progress_callback:
        progress_callback("labeling", 93, "Extracting local semantic theme labels...")

    presented_clusters = _build_semantic_cluster_presentation(clusters, assignment_papers)
    return {
        "projectId": int(payload.project_id or 0),
        "clusterMode": "semantic",
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "signature": signature,
        "seedSignature": signature,
        "paperCount": len(seed_papers),
        "assignedPaperCount": len(assignment_papers),
        "clusterQuality": best_result.get("score", 0),
        "clusters": presented_clusters,
        "usedLlmThemeNaming": False
    }

def _create_semantic_cluster_job(total: int) -> str:
    job_id = uuid.uuid4().hex
    SEMANTIC_CLUSTER_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "stage": "queued",
        "message": "Queued semantic cluster build...",
        "total": total,
        "completed": 0,
        "progress": 0,
        "result": None,
        "error": None
    }
    return job_id

def _update_semantic_cluster_job(job_id: str, **kwargs):
    job = SEMANTIC_CLUSTER_JOBS.get(job_id)
    if not job:
        return
    job.update(kwargs)

async def _run_semantic_cluster_job(job_id: str, payload: SemanticClusterRequest):
    _update_semantic_cluster_job(job_id, status="running", stage="prepare", message="Preparing backend semantic clustering...", total=min(len(payload.papers), MAX_TOP_PAPERS))
    try:
        def progress_callback(stage: str, percent: int, detail: str):
            _update_semantic_cluster_job(
                job_id,
                stage=stage,
                progress=max(0, min(100, int(percent))),
                message=detail,
                completed=max(0, min(len(payload.papers), int((max(0, min(100, int(percent))) / 100) * max(min(len(payload.papers), MAX_TOP_PAPERS), 1))))
            )
        result = await asyncio.to_thread(_build_semantic_cluster_result, payload, progress_callback)
        _update_semantic_cluster_job(
            job_id,
            status="completed",
            stage="completed",
            progress=100,
            completed=min(len(payload.papers), MAX_TOP_PAPERS),
            message="Semantic clustering complete.",
            result=result,
            error=None
        )
    except Exception as exc:
        _update_semantic_cluster_job(
            job_id,
            status="failed",
            stage="failed",
            message="Semantic clustering failed.",
            error=str(exc)
        )

def _build_literature_watch_prompt(context: dict) -> str:
    core_lines = []
    for index, paper in enumerate(context.get("core_papers", []), start=1):
        core_lines.append(
            f"{index}. Title: {paper.get('title', '')}\n"
            f"   Abstract snippet: {_trim_text(_collapse_whitespace(paper.get('abstract', '')), 180)}"
        )
    discipline_label = _combined_discipline_config(context.get("disciplines", [])).get("label", "Economics & Finance")
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
            "discipline": _combined_discipline_config(context.get("disciplines", [])).get("label", "")
        }
    except Exception:
        return _build_watch_fallback_strategy(context)

def _make_watch_lookup_payload() -> PaperLookupRequest:
    payload = PaperLookupRequest(title="watch", doi="", year="", authors="")
    return _apply_runtime_defaults_to_lookup(payload)

def _search_openalex_recent_works(query: str, lookup_payload: PaperLookupRequest, start_date: str, end_date: str, per_page: int = 24) -> List[dict]:
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

def _search_openalex_sources(query: str, lookup_payload: PaperLookupRequest, per_page: int = 5) -> List[dict]:
    safe_query = _trim_text(_collapse_whitespace(query), 160)
    if not safe_query:
        return []
    params = {
        "search": safe_query,
        "per_page": max(1, min(per_page, 10)),
        "filter": "type:journal"
    }
    if lookup_payload.openalex_api_key:
        params["api_key"] = lookup_payload.openalex_api_key
    url = _build_url("https://api.openalex.org/sources", params)
    results = (_http_get_json(url, lookup_payload.contact_email) or {}).get("results") or []
    normalized_results = []
    seen_ids = set()
    for source in results:
        source_id = _trim_text(source.get("id"), 300)
        if not source_id or source_id in seen_ids:
            continue
        seen_ids.add(source_id)
        normalized_results.append({
            "id": source_id,
            "display_name": _trim_text(source.get("display_name"), 220),
            "host_organization_name": _trim_text(source.get("host_organization_name"), 220),
            "works_count": int(source.get("works_count") or 0),
            "cited_by_count": int(source.get("cited_by_count") or 0),
            "type": _trim_text(source.get("type"), 40),
        })
    return normalized_results

def _resolve_openalex_source(source_payload: LiteratureWatchJournalSource, lookup_payload: PaperLookupRequest) -> Optional[dict]:
    source_id = _trim_text(source_payload.id, 300)
    display_name = _trim_text(_collapse_whitespace(source_payload.display_name), 220)
    if source_id:
        return {"id": source_id, "display_name": display_name or source_id}
    if not display_name:
        return None
    candidates = _search_openalex_sources(display_name, lookup_payload, per_page=5)
    if not candidates:
        return None
    best = candidates[0]
    return {
        "id": best.get("id", ""),
        "display_name": best.get("display_name") or display_name
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

def _fetch_recent_works_for_source(source: dict, lookup_payload: PaperLookupRequest, start_date: str, end_date: str, per_page: int = 40) -> List[dict]:
    source_id = _trim_text(source.get("id"), 300)
    if not source_id:
        return []
    params = {
        "per_page": max(1, min(per_page, 50)),
        "filter": f"primary_location.source.id:{source_id},from_publication_date:{start_date},to_publication_date:{end_date}",
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
        parsed["source_journal"] = source.get("display_name") or ""
        papers.append(parsed)
    return papers

def _summarize_watch_step_error(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = getattr(exc, "detail", "") or ""
        return _trim_text(str(detail), 220) or "Upstream literature metadata could not be retrieved."
    return _trim_text(str(exc), 220) or "Upstream literature metadata could not be retrieved."

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

def _venue_discipline_bonus(candidate: dict, discipline_scopes) -> float:
    venue_text = _collapse_whitespace(str((candidate or {}).get("publication_venue") or "")).lower()
    if not venue_text:
        return 0.0
    config = _combined_discipline_config(discipline_scopes)
    if any(top_venue in venue_text for top_venue in config.get("top_venues", [])):
        return 0.22
    if any(keyword in venue_text for keyword in config.get("venue_keywords", [])):
        return 0.10
    return 0.0

def _normalize_watch_venue_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _collapse_whitespace(str(value or "")).lower()).strip()

def _normalize_target_watch_weight(raw_value) -> str:
    value = _collapse_whitespace(str(raw_value or "")).lower()
    if value in {"off", "none", "no_lift", "no-lift", "0"}:
        return "off"
    if value in {"priority", "high", "strong", "2"}:
        return "priority"
    return "standard"

def _target_watch_bonus_for_weight(weight_tier: str) -> float:
    normalized = _normalize_target_watch_weight(weight_tier)
    if normalized == "off":
        return 0.0
    if normalized == "priority":
        return 0.20
    return 0.12

def _target_watch_weight_label(weight_tier: str) -> str:
    normalized = _normalize_target_watch_weight(weight_tier)
    if normalized == "off":
        return "No lift"
    if normalized == "priority":
        return "Priority lift"
    return "Standard lift"

def _watched_journal_bonus_detail(candidate: dict, watched_journals: List[dict]) -> dict:
    if not watched_journals:
        return {"bonus": 0.0, "matched_journal": "", "weight_tier": "off"}
    venue_candidates = {
        _normalize_watch_venue_key(candidate.get("publication_venue")),
        _normalize_watch_venue_key(candidate.get("source_journal"))
    }
    venue_candidates = {item for item in venue_candidates if item}
    if not venue_candidates:
        return {"bonus": 0.0, "matched_journal": "", "weight_tier": "off"}
    normalized_watched = []
    for item in watched_journals:
        display_name = _trim_text(_collapse_whitespace((item or {}).get("display_name", "")), 220)
        normalized_name = _normalize_watch_venue_key(display_name)
        if not normalized_name:
            continue
        weight_tier = _normalize_target_watch_weight((item or {}).get("target_watch_weight"))
        normalized_watched.append({
            "display_name": display_name,
            "normalized_name": normalized_name,
            "weight_tier": weight_tier,
            "bonus": _target_watch_bonus_for_weight(weight_tier)
        })
    for venue in venue_candidates:
        for watched in normalized_watched:
            normalized_name = watched.get("normalized_name", "")
            if venue == normalized_name or venue in normalized_name or normalized_name in venue:
                return {
                    "bonus": watched.get("bonus", 0.0),
                    "matched_journal": watched.get("display_name", ""),
                    "weight_tier": watched.get("weight_tier", "standard")
                }
    return {"bonus": 0.0, "matched_journal": "", "weight_tier": "off"}

def _watched_journal_bonus(candidate: dict, watched_journals: List[dict]) -> float:
    return float(_watched_journal_bonus_detail(candidate, watched_journals).get("bonus") or 0.0)

def _candidate_quality_score(candidate: dict, discipline_scopes, watched_journals: Optional[List[dict]] = None) -> float:
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
    venue_bonus = _venue_discipline_bonus(candidate, discipline_scopes)
    watched_journal_bonus = _watched_journal_bonus(candidate, watched_journals or [])
    return min((citation_score * 0.58) + (fwci_score * 0.12) + completeness_bonus + venue_bonus + watched_journal_bonus, 1.0)

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
        discipline_label = _combined_discipline_config(context.get("disciplines", [])).get("label", "Economics & Finance")
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
    discipline_scopes = _normalize_watch_discipline_scopes(request_payload.discipline_scopes or [request_payload.discipline])
    primary_discipline_key = discipline_scopes[0]
    combined_discipline = _combined_discipline_config(discipline_scopes)
    watch_mode = _normalize_watch_mode(request_payload.mode)
    context = _get_project_watch_context(project_data, discipline_scopes)
    strategy = _build_literature_watch_strategy(context)
    lookup_payload = _make_watch_lookup_payload()
    lookback_window, range_label, start_date, window_days = _normalize_watch_range(request_payload.lookback_window)
    recommendation_limit = max(3, min(int(request_payload.limit or 12), 30))
    watched_journal_sources = []
    for source in (request_payload.journal_sources or []):
        display_name = _trim_text(_collapse_whitespace(getattr(source, "display_name", "")), 220)
        if not display_name:
            continue
        watched_journal_sources.append({
            "id": _trim_text(getattr(source, "id", ""), 300),
            "display_name": display_name,
            "target_watch_weight": _normalize_target_watch_weight(getattr(source, "target_watch_weight", "standard"))
        })
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
    journal_sources: List[str] = []
    resolved_journals: List[dict] = []
    unresolved_journals: List[str] = []
    partial_failures: List[dict] = []

    def register_candidate(candidate: dict, *, matched_query: str = "", source_scholar: str = "", source_journal: str = ""):
        identity_signatures = _paper_identity_signatures(candidate)
        if any(signature in existing_signatures for signature in identity_signatures):
            return
        matched_primary = next((signature_to_primary[signature] for signature in identity_signatures if signature in signature_to_primary), None)
        incoming = {
            **candidate,
            "matched_queries": [matched_query] if matched_query else [],
            "source_scholar": source_scholar or candidate.get("source_scholar", ""),
            "source_journal": source_journal or candidate.get("source_journal", "")
        }
        if matched_primary:
            merged = _merge_watch_candidate(candidates_by_key[matched_primary], incoming)
            if source_scholar and not merged.get("source_scholar"):
                merged["source_scholar"] = source_scholar
            if source_journal and not merged.get("source_journal"):
                merged["source_journal"] = source_journal
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
            try:
                author = _resolve_openalex_author(scholar_name, lookup_payload)
            except Exception as exc:
                partial_failures.append({
                    "kind": "scholar",
                    "label": scholar_name,
                    "detail": _summarize_watch_step_error(exc)
                })
                continue
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
            try:
                scholar_candidates = _fetch_recent_works_for_author(author, lookup_payload, start_date, date.today().isoformat(), per_page=18)
            except Exception as exc:
                partial_failures.append({
                    "kind": "scholar",
                    "label": author.get("display_name") or scholar_name,
                    "detail": _summarize_watch_step_error(exc)
                })
                continue
            for candidate in scholar_candidates:
                register_candidate(candidate, source_scholar=author.get("display_name") or scholar_name)
    elif watch_mode == "journal":
        requested_journals = []
        seen_journal_ids = set()
        seen_journal_names = set()
        for raw_source in request_payload.journal_sources or []:
            source_id = _trim_text(getattr(raw_source, "id", ""), 300)
            display_name = _trim_text(_collapse_whitespace(getattr(raw_source, "display_name", "")), 220)
            dedupe_key = source_id.lower() if source_id else display_name.lower()
            if not dedupe_key:
                continue
            if source_id and source_id.lower() in seen_journal_ids:
                continue
            if not source_id and display_name.lower() in seen_journal_names:
                continue
            if source_id:
                seen_journal_ids.add(source_id.lower())
            if display_name:
                seen_journal_names.add(display_name.lower())
            requested_journals.append(LiteratureWatchJournalSource(id=source_id, display_name=display_name))
            if len(requested_journals) >= 20:
                break
        if not requested_journals:
            raise HTTPException(status_code=422, detail="At least one journal is required for Journal Watch.")

        for requested_source in requested_journals:
            try:
                source = _resolve_openalex_source(requested_source, lookup_payload)
            except Exception as exc:
                partial_failures.append({
                    "kind": "journal",
                    "label": requested_source.display_name or requested_source.id,
                    "detail": _summarize_watch_step_error(exc)
                })
                continue
            if not source:
                unresolved_journals.append(requested_source.display_name or requested_source.id)
                continue
            source_name = source.get("display_name") or requested_source.display_name or requested_source.id
            journal_sources.append(source_name)
            resolved_journals.append({
                "requested": requested_source.display_name or requested_source.id,
                "resolved": source_name,
                "id": source.get("id", "")
            })
            try:
                source_candidates = _fetch_recent_works_for_source(source, lookup_payload, start_date, date.today().isoformat(), per_page=40)
            except Exception as exc:
                partial_failures.append({
                    "kind": "journal",
                    "label": source_name,
                    "detail": _summarize_watch_step_error(exc)
                })
                continue
            for candidate in source_candidates:
                register_candidate(candidate, source_journal=source_name)
    else:
        for query in strategy.get("queries", [])[:6]:
            try:
                query_candidates = _search_openalex_recent_works(query, lookup_payload, start_date, date.today().isoformat(), per_page=24)
            except Exception as exc:
                partial_failures.append({
                    "kind": "query",
                    "label": query,
                    "detail": _summarize_watch_step_error(exc)
                })
                continue
            for candidate in query_candidates:
                register_candidate(candidate, matched_query=query)

    preliminary_candidates = []
    for candidate in candidates_by_key.values():
        relevance_score, matched_queries = _candidate_relevance_score(candidate, token_weights, strategy)
        quality_score = _candidate_quality_score(
            candidate,
            discipline_scopes,
            watched_journal_sources if watch_mode == "target" else []
        )
        freshness_score = _candidate_freshness_score(candidate, window_days)
        watched_journal_detail = _watched_journal_bonus_detail(candidate, watched_journal_sources if watch_mode == "target" else [])
        lexical_threshold = 0.12 if watch_mode == "scholar" else (0.14 if watch_mode == "journal" else 0.18)
        if relevance_score < lexical_threshold:
            continue
        candidate["lexical_relevance_score"] = round(relevance_score, 3)
        candidate["quality_score"] = round(quality_score, 3)
        candidate["freshness_score"] = round(freshness_score, 3)
        candidate["watched_journal_bonus_applied"] = (
            watch_mode == "target" and float(watched_journal_detail.get("bonus") or 0) > 0
        )
        candidate["watched_journal_bonus"] = round(float(watched_journal_detail.get("bonus") or 0), 3)
        candidate["matched_watched_journal"] = watched_journal_detail.get("matched_journal", "")
        candidate["watched_journal_weight_tier"] = watched_journal_detail.get("weight_tier", "")
        candidate["watched_journal_weight_label"] = _target_watch_weight_label(watched_journal_detail.get("weight_tier", ""))
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

    try:
        semantic_scores = _semantic_watch_rerank(context, strategy, preliminary_candidates)
    except Exception as exc:
        partial_failures.append({
            "kind": "rerank",
            "label": "semantic rerank",
            "detail": _summarize_watch_step_error(exc)
        })
        semantic_scores = {}

    scored_candidates = []
    for candidate in preliminary_candidates:
        lexical_relevance = float(candidate.get("lexical_relevance_score") or 0)
        semantic_relevance = semantic_scores.get(candidate.get("watch_candidate_id"), lexical_relevance)
        final_relevance = min((semantic_relevance * 0.72) + (lexical_relevance * 0.28), 1.0) if semantic_scores else lexical_relevance
        threshold = (
            (0.36 if semantic_scores else 0.22)
            if watch_mode == "scholar"
            else ((0.34 if semantic_scores else 0.24) if watch_mode == "journal" else (0.42 if semantic_scores else 0.28))
        )
        watch_score = min((final_relevance * 0.65) + (float(candidate.get("quality_score") or 0) * 0.30) + (float(candidate.get("freshness_score") or 0) * 0.05), 1.0)
        candidate["semantic_relevance_score"] = round(semantic_relevance, 3)
        candidate["relevance_score"] = round(final_relevance, 3)
        candidate["watch_threshold"] = round(threshold, 3)
        candidate["watch_score"] = round(watch_score, 3)
        candidate["watch_reason"] = (
            f"Matched scholar {candidate.get('source_scholar')} and remained close to the target thesis."
            if watch_mode == "scholar" and candidate.get("source_scholar")
            else (
                (
                    f"Strongest query match: {candidate['matched_queries'][0]}. Published in {candidate.get('matched_watched_journal') or 'one of your watched journals'}."
                    if candidate.get("matched_queries") and candidate.get("watched_journal_bonus_applied")
                    else (
                        f"Strongest query match: {candidate['matched_queries'][0]}"
                        if candidate.get("matched_queries")
                        else (
                            f"Matched the target thesis, Core-paper signal, and {candidate.get('matched_watched_journal') or 'one of your watched journals'}."
                            if candidate.get("watched_journal_bonus_applied")
                            else "Matched the target thesis and Core-paper signal."
                        )
                    )
                )
            )
        )
        scored_candidates.append(candidate)

    scored_candidates.sort(
        key=lambda item: (
            float(item.get("watch_score") or 0),
            float(item.get("relevance_score") or 0),
            float(item.get("quality_score") or 0),
            float(item.get("citation_count") or 0)
        ),
        reverse=True
    )

    recommendations = [
        candidate for candidate in scored_candidates
        if float(candidate.get("relevance_score") or 0) >= float(candidate.get("watch_threshold") or 0)
    ]

    minimum_recommendations = 12 if watch_mode in {"target", "journal"} else 0
    if minimum_recommendations and len(recommendations) < minimum_recommendations:
        supplemental_floor = 0.24 if watch_mode == "target" else 0.22
        chosen_ids = {
            str(candidate.get("watch_candidate_id") or "")
            for candidate in recommendations
        }
        supplemental = []
        for candidate in scored_candidates:
            candidate_id = str(candidate.get("watch_candidate_id") or "")
            if candidate_id in chosen_ids:
                continue
            if float(candidate.get("relevance_score") or 0) < supplemental_floor:
                continue
            candidate["watch_reason"] = f"{candidate.get('watch_reason', 'Relevant to the target thesis.')} Included from the next-strongest watch candidates to broaden this scan."
            supplemental.append(candidate)
            chosen_ids.add(candidate_id)
            if len(recommendations) + len(supplemental) >= minimum_recommendations:
                break
        recommendations.extend(supplemental)

    partial_failure_warning = ""
    if partial_failures:
        partial_failure_warning = "Some paper information could not be retrieved. Please run Watch again to get more complete results."

    return {
        "mode": watch_mode,
        "range": lookback_window,
        "range_label": range_label,
        "discipline": {
            "key": primary_discipline_key,
            "keys": discipline_scopes,
            "label": combined_discipline.get("label", _discipline_config(primary_discipline_key).get("label", primary_discipline_key)),
            "labels": combined_discipline.get("labels", [])
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
        "journal_sources": journal_sources[:20],
        "resolved_journals": resolved_journals[:20],
        "unresolved_journals": unresolved_journals[:20],
        "partial_failures": partial_failures[:20],
        "partial_failure_warning": partial_failure_warning,
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

@app.post("/api/projects/{project_id}/claims")
async def create_project_claim(project_id: int, payload: ClaimCreateRequest, current_user: dict = Depends(_require_session)):
    _get_owned_project(project_id, current_user["user_id"])
    payload = _validate_claim_create_payload(payload)
    now = _now_ts()
    conn = _db_connect()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO project_claims (project_id, claim_text, claim_type, section_label, status, analysis_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, payload.claim_text, payload.claim_type, payload.section_label, "active", "v1", now, now)
        )
        conn.commit()
        claim_id = int(cursor.lastrowid)
        _write_audit_log(
            "project_claim_create",
            user_id=current_user["user_id"],
            project_id=project_id,
            detail={"claim_id": claim_id, "claim_type": payload.claim_type},
            success=True
        )
        return {
            "claim": {
                "id": claim_id,
                "project_id": project_id,
                "claim_text": payload.claim_text,
                "claim_type": payload.claim_type,
                "section_label": payload.section_label,
                "status": "active",
                "analysis_version": "v1",
                "created_at": now,
                "updated_at": now,
            }
        }
    finally:
        conn.close()

@app.get("/api/projects/{project_id}/claims")
async def list_project_claims(project_id: int, current_user: dict = Depends(_require_session)):
    _get_owned_project(project_id, current_user["user_id"])
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM project_claims WHERE project_id = ? AND status != 'archived' ORDER BY updated_at DESC, id DESC",
        (project_id,)
    )
    claims = [dict(row) for row in cursor.fetchall()]
    claim_ids = [int(claim["id"]) for claim in claims]
    evidence_summary: Dict[int, dict] = {claim_id: _default_claim_summary() for claim_id in claim_ids}
    latest_runs: Dict[int, dict] = {}
    if claim_ids:
        placeholders = ",".join("?" for _ in claim_ids)
        cursor.execute(
            f"SELECT claim_id, stance, COUNT(*) AS item_count FROM claim_evidence_items WHERE hidden = 0 AND claim_id IN ({placeholders}) GROUP BY claim_id, stance",
            claim_ids
        )
        for row in cursor.fetchall():
            evidence_summary.setdefault(int(row["claim_id"]), _default_claim_summary())[row["stance"]] = int(row["item_count"] or 0)
        cursor.execute(
            f"SELECT claim_id, MAX(id) AS latest_run_id FROM claim_analysis_runs WHERE claim_id IN ({placeholders}) GROUP BY claim_id",
            claim_ids
        )
        latest_run_ids = [int(row["latest_run_id"]) for row in cursor.fetchall() if row["latest_run_id"]]
        if latest_run_ids:
            run_placeholders = ",".join("?" for _ in latest_run_ids)
            cursor.execute(
                f"SELECT * FROM claim_analysis_runs WHERE id IN ({run_placeholders})",
                latest_run_ids
            )
            latest_runs = {int(row["claim_id"]): dict(row) for row in cursor.fetchall()}
    conn.close()
    return {
        "claims": [
            {
                **claim,
                "claim_type": _normalize_claim_type(claim.get("claim_type")),
                "status": _normalize_claim_status(claim.get("status")),
                "evidence_summary": evidence_summary.get(int(claim["id"]), _default_claim_summary()),
                "latest_run": latest_runs.get(int(claim["id"]))
            }
            for claim in claims
        ]
    }

@app.post("/api/projects/{project_id}/stardusts")
async def create_project_stardust(project_id: int, payload: ChallengeStardustCreateRequest, current_user: dict = Depends(_require_session)):
    project_data = _get_owned_project(project_id, current_user["user_id"])
    payload = _validate_stardust_create_payload(payload)
    claim = _get_owned_claim(project_id, payload.claim_id, current_user["user_id"])

    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM claim_evidence_items WHERE id = ? AND claim_id = ? AND project_id = ?",
        (payload.seed_evidence_id, payload.claim_id, project_id)
    )
    evidence_row = cursor.fetchone()
    if not evidence_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Seed evidence item not found.")

    replaced_stardust_id = None
    if payload.replace_stardust_id:
        cursor.execute(
            "SELECT * FROM challenge_stardusts WHERE id = ? AND project_id = ?",
            (payload.replace_stardust_id, project_id)
        )
        replace_row = cursor.fetchone()
        if not replace_row:
            conn.close()
            raise HTTPException(status_code=404, detail="The Challenge Stardust chosen for replacement was not found.")
        replaced_stardust_id = int(replace_row["id"])

    cursor.execute(
        "SELECT COUNT(*) AS item_count FROM challenge_stardusts WHERE project_id = ?",
        (project_id,)
    )
    current_count = int((cursor.fetchone() or {"item_count": 0})["item_count"] or 0)
    if current_count >= MAX_STARDUSTS_PER_PROJECT and not replaced_stardust_id:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"This project already has {MAX_STARDUSTS_PER_PROJECT} Challenge Stardusts. Replace an existing one before creating a new one."
        )
    conn.close()

    generation_result = _generate_challenge_stardust(project_data, claim, dict(evidence_row), payload)
    papers = generation_result.get("papers") or []
    source_summary = generation_result.get("source_summary") or {}

    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    if replaced_stardust_id:
        _delete_stardust_records(conn, replaced_stardust_id)
    now = _now_ts()
    cursor.execute(
        '''INSERT INTO challenge_stardusts (
            project_id, claim_id, seed_evidence_id, seed_paper_key, name, sub_target_thesis,
            status, paper_count, graph_cache_signature, source_summary_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            project_id,
            payload.claim_id,
            payload.seed_evidence_id,
            _trim_text(evidence_row["paper_key"], 300),
            payload.name,
            payload.sub_target_thesis,
            "ready",
            len(papers),
            "",
            json.dumps(source_summary, ensure_ascii=False),
            now,
            now,
        )
    )
    stardust_id = int(cursor.lastrowid)
    _insert_stardust_papers(conn, stardust_id, papers)
    conn.commit()
    cursor.execute("SELECT * FROM challenge_stardusts WHERE id = ?", (stardust_id,))
    stardust_row = cursor.fetchone()
    serialized = _serialize_stardust_row(conn, dict(stardust_row), include_children=True)
    conn.close()

    _write_audit_log(
        "project_stardust_create",
        user_id=current_user["user_id"],
        project_id=project_id,
        detail={
            "stardust_id": stardust_id,
            "claim_id": int(claim["id"]),
            "seed_evidence_id": payload.seed_evidence_id,
            "replaced_stardust_id": replaced_stardust_id,
            "stored_count": len(papers),
        },
        success=True
    )
    return {
        "stardust": serialized,
        "seed_paper": generation_result.get("seed_paper") or {},
        "source_summary": source_summary,
    }

@app.get("/api/projects/{project_id}/stardusts")
async def list_project_stardusts(project_id: int, current_user: dict = Depends(_require_session)):
    _get_owned_project(project_id, current_user["user_id"])
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM challenge_stardusts WHERE project_id = ? ORDER BY updated_at DESC, id DESC",
        (project_id,)
    )
    stardusts = [_serialize_stardust_row(conn, dict(row), include_children=False) for row in cursor.fetchall()]
    conn.close()
    return {"stardusts": stardusts}

@app.get("/api/projects/{project_id}/stardusts/{stardust_id}")
async def get_project_stardust(project_id: int, stardust_id: int, current_user: dict = Depends(_require_session)):
    _get_owned_stardust(project_id, stardust_id, current_user["user_id"])
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM challenge_stardusts WHERE id = ?", (stardust_id,))
    row = cursor.fetchone()
    serialized = _serialize_stardust_row(conn, dict(row), include_children=True)
    conn.close()
    return {"stardust": serialized}

@app.get("/api/projects/{project_id}/stardusts/{stardust_id}/papers")
async def list_project_stardust_papers(project_id: int, stardust_id: int, include_hidden: bool = True, current_user: dict = Depends(_require_session)):
    _get_owned_stardust(project_id, stardust_id, current_user["user_id"])
    conn = _db_connect(row_factory=True)
    papers = _load_stardust_papers(conn, stardust_id, include_hidden=include_hidden)
    conn.close()
    return {"papers": papers}

@app.get("/api/projects/{project_id}/stardusts/{stardust_id}/graph")
async def get_project_stardust_graph(project_id: int, stardust_id: int, mode: str = "directed", current_user: dict = Depends(_require_session)):
    _get_owned_stardust(project_id, stardust_id, current_user["user_id"])
    normalized_mode = _normalize_stardust_graph_mode(mode)
    conn = _db_connect(row_factory=True)
    cached = _load_stardust_graph_cache(conn, stardust_id, normalized_mode)
    graphs = _serialize_stardust_graph_summaries(conn, stardust_id)
    conn.close()
    if not cached:
        raise HTTPException(status_code=404, detail="No cached Stardust graph exists for this mode yet.")
    return {
        "cache_hit": True,
        "graph": {
            "mode": normalized_mode,
            "nodes": cached.get("nodes") or [],
            "edges": cached.get("edges") or [],
            "stats": cached.get("meta") or {},
        },
        "graphs": graphs,
    }

@app.post("/api/projects/{project_id}/stardusts/{stardust_id}/graph/build")
async def build_project_stardust_graph(project_id: int, stardust_id: int, payload: ChallengeStardustGraphBuildRequest, current_user: dict = Depends(_require_session)):
    stardust_row = _get_owned_stardust(project_id, stardust_id, current_user["user_id"])
    project_data = _get_owned_project(project_id, current_user["user_id"])
    payload = _validate_stardust_graph_build_payload(payload)
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM claim_evidence_items WHERE id = ? AND project_id = ?",
        (int(stardust_row.get("seed_evidence_id") or 0), project_id)
    )
    seed_evidence_row = cursor.fetchone()
    papers = _load_stardust_papers(conn, stardust_id, include_hidden=False)
    initial_signature = _build_stardust_graph_signature(papers, payload.mode)
    cached = _load_stardust_graph_cache(conn, stardust_id, payload.mode)
    if cached and cached.get("graph_signature") == initial_signature and not payload.force_rebuild:
        graphs = _serialize_stardust_graph_summaries(conn, stardust_id)
        conn.close()
        return {
            "cache_hit": True,
            "graph": {
                "mode": payload.mode,
                "nodes": cached.get("nodes") or [],
                "edges": cached.get("edges") or [],
                "stats": cached.get("meta") or {},
            },
            "graphs": graphs,
        }

    seed_graph_paper = None
    if seed_evidence_row:
        try:
            resolved_seed = _resolve_project_paper_for_evidence(project_data, dict(seed_evidence_row))
            if resolved_seed:
                seed_graph_paper = _enrich_paper_for_citation_graph(
                    PaperItem(**resolved_seed),
                    payload.openalex_api_key,
                    payload.contact_email
                )
        except Exception:
            seed_graph_paper = None

    enriched_papers: List[dict] = []
    partial_failures: List[dict] = []
    for paper in papers:
        enriched = dict(paper)
        needs_enrichment = not _trim_text(enriched.get("openalex_id"), 300) or not (enriched.get("referenced_openalex_ids") or [])
        if needs_enrichment:
            try:
                enriched = {
                    **enriched,
                    **_enrich_paper_for_citation_graph(
                        _stardust_paper_to_paper_item(enriched),
                        payload.openalex_api_key,
                        payload.contact_email
                    )
                }
                _update_stardust_paper_graph_metadata(conn, stardust_id, enriched)
            except Exception as exc:
                partial_failures.append({
                    "paper_key": _trim_text(enriched.get("paper_key"), 300),
                    "title": _trim_text(enriched.get("title"), 180),
                    "detail": _trim_text(str(exc), 220),
                })
        enriched_papers.append(enriched)

    graph_signature = _build_stardust_graph_signature(enriched_papers, payload.mode)
    cached = _load_stardust_graph_cache(conn, stardust_id, payload.mode)
    if cached and cached.get("graph_signature") == graph_signature and not payload.force_rebuild:
        graphs = _serialize_stardust_graph_summaries(conn, stardust_id)
        conn.commit()
        conn.close()
        return {
            "cache_hit": True,
            "graph": {
                "mode": payload.mode,
                "nodes": cached.get("nodes") or [],
                "edges": cached.get("edges") or [],
                "stats": cached.get("meta") or {},
            },
            "graphs": graphs,
        }

    graph = _build_stardust_graph_result(enriched_papers, payload.mode, partial_failures)
    graph_meta = {
        **(graph.get("stats") or {}),
        "mode": payload.mode,
        "graph_signature": graph_signature,
        "seed": {
            "paper_key": _trim_text((seed_evidence_row or {}).get("paper_key"), 300),
            "paper_title": _trim_text((seed_evidence_row or {}).get("paper_title"), MAX_PAPER_TITLE_LENGTH),
            "paper_authors": _trim_text((seed_evidence_row or {}).get("paper_authors"), MAX_PAPER_AUTHORS_LENGTH),
            "paper_year": _trim_text((seed_evidence_row or {}).get("paper_year"), 40),
            "openalex_id": _trim_text((seed_graph_paper or {}).get("openalex_id"), 300),
            "doi": _clean_doi((seed_graph_paper or {}).get("doi")),
            "paper_url": _trim_text((seed_graph_paper or {}).get("paper_url"), 1000),
            "publication_venue": _trim_text((seed_graph_paper or {}).get("publication_venue"), 300),
            "citation_count": _safe_int((seed_graph_paper or {}).get("citation_count"), 0),
            "referenced_openalex_ids": list((seed_graph_paper or {}).get("referenced_openalex_ids") or []),
        },
    }
    _upsert_stardust_graph_cache(
        conn,
        stardust_id,
        payload.mode,
        graph_signature,
        graph.get("nodes") or [],
        graph.get("edges") or [],
        graph_meta,
    )
    conn.commit()
    graphs = _serialize_stardust_graph_summaries(conn, stardust_id)
    conn.close()

    _write_audit_log(
        "project_stardust_graph_build",
        user_id=current_user["user_id"],
        project_id=project_id,
        detail={"stardust_id": stardust_id, "mode": payload.mode, "edge_count": int((graph.get("stats") or {}).get("edge_count") or 0)},
        success=True
    )
    return {
        "cache_hit": False,
        "graph": graph,
        "graphs": graphs,
    }

@app.patch("/api/projects/{project_id}/stardusts/{stardust_id}")
async def update_project_stardust(project_id: int, stardust_id: int, payload: ChallengeStardustUpdateRequest, current_user: dict = Depends(_require_session)):
    _get_owned_stardust(project_id, stardust_id, current_user["user_id"])
    payload = _validate_stardust_update_payload(payload)
    fields = []
    params = []
    if payload.name is not None:
        fields.append("name = ?")
        params.append(payload.name)
    if payload.sub_target_thesis is not None:
        fields.append("sub_target_thesis = ?")
        params.append(payload.sub_target_thesis)
    if payload.status is not None:
        fields.append("status = ?")
        params.append(payload.status)
    if not fields:
        raise HTTPException(status_code=400, detail="No stardust changes were provided.")
    fields.append("updated_at = ?")
    params.append(_now_ts())
    params.append(stardust_id)

    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE challenge_stardusts SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    cursor.execute("SELECT * FROM challenge_stardusts WHERE id = ?", (stardust_id,))
    row = cursor.fetchone()
    serialized = _serialize_stardust_row(conn, dict(row), include_children=False)
    conn.close()

    _write_audit_log(
        "project_stardust_update",
        user_id=current_user["user_id"],
        project_id=project_id,
        detail={"stardust_id": stardust_id},
        success=True
    )
    return {"stardust": serialized}

@app.patch("/api/projects/{project_id}/stardusts/{stardust_id}/papers/{paper_id}")
async def patch_project_stardust_paper(project_id: int, stardust_id: int, paper_id: int, payload: ChallengeStardustPaperPatchRequest, current_user: dict = Depends(_require_session)):
    _get_owned_stardust(project_id, stardust_id, current_user["user_id"])
    fields = []
    params = []
    if payload.selected_for_import is not None:
        fields.append("selected_for_import = ?")
        params.append(1 if payload.selected_for_import else 0)
    if payload.hidden is not None:
        fields.append("hidden = ?")
        params.append(1 if payload.hidden else 0)
    if not fields:
        raise HTTPException(status_code=400, detail="No stardust paper changes were provided.")
    fields.append("updated_at = ?")
    params.append(_now_ts())
    params.extend([paper_id, stardust_id])

    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM challenge_stardust_papers WHERE id = ? AND stardust_id = ?",
        (paper_id, stardust_id)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Challenge Stardust paper not found.")

    cursor.execute(
        f"UPDATE challenge_stardust_papers SET {', '.join(fields)} WHERE id = ? AND stardust_id = ?",
        params
    )
    conn.commit()
    cursor.execute("SELECT * FROM challenge_stardust_papers WHERE id = ?", (paper_id,))
    updated = _serialize_stardust_paper_row(dict(cursor.fetchone()))
    conn.close()

    _write_audit_log(
        "project_stardust_patch_paper",
        user_id=current_user["user_id"],
        project_id=project_id,
        detail={"stardust_id": stardust_id, "paper_id": paper_id},
        success=True
    )
    return {"paper": updated}

@app.delete("/api/projects/{project_id}/stardusts/{stardust_id}")
async def delete_project_stardust(project_id: int, stardust_id: int, current_user: dict = Depends(_require_session)):
    _get_owned_stardust(project_id, stardust_id, current_user["user_id"])
    conn = _db_connect(row_factory=True)
    _delete_stardust_records(conn, stardust_id)
    conn.commit()
    conn.close()
    _write_audit_log(
        "project_stardust_delete",
        user_id=current_user["user_id"],
        project_id=project_id,
        detail={"stardust_id": stardust_id},
        success=True
    )
    return {"deleted": True, "stardust_id": stardust_id}

@app.post("/api/projects/{project_id}/claims/{claim_id}/analyze")
async def analyze_project_claim(project_id: int, claim_id: int, payload: ClaimAnalyzeRequest, current_user: dict = Depends(_require_session)):
    project_data = _get_owned_project(project_id, current_user["user_id"])
    claim = _get_owned_claim(project_id, claim_id, current_user["user_id"])
    if _normalize_claim_status(claim.get("status")) == "archived":
        raise HTTPException(status_code=409, detail="Archived claims cannot be analyzed.")
    payload = _validate_claim_analyze_payload(payload)
    lock = await _acquire_project_task_lock(project_id, f"claim_analysis_{claim_id}")
    run_id = _create_claim_analysis_run(claim_id, project_id)
    conn = None
    try:
        candidates = _build_claim_candidate_pool(
            project_data,
            claim,
            payload.include_statuses,
            payload.max_candidates,
            payload.prefer_fulltext
        )
        analyzed_items, llm_used = _analyze_claim_candidates(project_data, claim, candidates)
        now = _now_ts()
        conn = _db_connect(row_factory=True)
        cursor = conn.cursor()
        if payload.reanalyze_overrides:
            cursor.execute("DELETE FROM claim_evidence_items WHERE claim_id = ?", (claim_id,))
            manual_keys = set()
        else:
            cursor.execute("DELETE FROM claim_evidence_items WHERE claim_id = ? AND user_override = 0", (claim_id,))
            cursor.execute("SELECT paper_key FROM claim_evidence_items WHERE claim_id = ? AND user_override = 1", (claim_id,))
            manual_keys = {str(row["paper_key"]) for row in cursor.fetchall()}

        inserted_count = 0
        for item in analyzed_items:
            paper_key = str(item.get("paper_key") or "").strip()
            if not paper_key or (paper_key in manual_keys and not payload.reanalyze_overrides):
                continue
            cursor.execute(
                '''INSERT OR REPLACE INTO claim_evidence_items (
                    claim_id, project_id, paper_key, paper_title, paper_year, paper_authors, citation_key,
                    stance, strength_score, relevance_score, confidence_score, quality_score,
                    why_matched, caveat, evidence_snippets_json, source_pass, user_override,
                    pinned, hidden, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    claim_id,
                    project_id,
                    paper_key,
                    item.get("paper_title", ""),
                    item.get("paper_year", ""),
                    item.get("paper_authors", ""),
                    item.get("citation_key", ""),
                    _normalize_claim_stance(item.get("stance")),
                    float(item.get("strength_score") or 0),
                    float(item.get("relevance_score") or 0),
                    float(item.get("confidence_score") or 0),
                    float(item.get("quality_score") or 0),
                    _trim_text(item.get("why_matched"), MAX_EVIDENCE_WHY_MATCHED_LENGTH),
                    _trim_text(item.get("caveat"), MAX_EVIDENCE_CAVEAT_LENGTH),
                    json.dumps(item.get("evidence_snippets") or [], ensure_ascii=False),
                    "llm" if llm_used else "heuristic",
                    0,
                    0,
                    0,
                    now,
                    now,
                )
            )
            inserted_count += 1

        cursor.execute("UPDATE project_claims SET updated_at = ? WHERE id = ?", (now, claim_id))
        conn.commit()
        cursor.execute(
            "SELECT stance, COUNT(*) AS item_count FROM claim_evidence_items WHERE claim_id = ? AND hidden = 0 GROUP BY stance",
            (claim_id,)
        )
        summary = _default_claim_summary()
        for row in cursor.fetchall():
            summary[_normalize_claim_stance(row["stance"])] = int(row["item_count"] or 0)
        conn.close()

        _update_claim_analysis_run(
            run_id,
            candidate_count=len(candidates),
            analyzed_count=inserted_count,
            status="completed",
            summary_json=json.dumps({"summary": summary, "llm_used": llm_used}, ensure_ascii=False),
            error_text="",
            updated_at=now,
        )
        _write_audit_log(
            "project_claim_analyze",
            user_id=current_user["user_id"],
            project_id=project_id,
            detail={"claim_id": claim_id, "candidate_count": len(candidates), "inserted_count": inserted_count, "llm_used": llm_used},
            success=True
        )
        cleanup_result = _cleanup_claim_caches(force=True)
        return {
            "run": {
                "id": run_id,
                "status": "completed",
                "candidate_count": len(candidates),
                "analyzed_count": inserted_count,
            },
            "summary": summary,
            "cache_maintenance": cleanup_result
        }
    except HTTPException as exc:
        _update_claim_analysis_run(
            run_id,
            status="failed",
            error_text=_trim_text(str(exc.detail), 2000),
            updated_at=_now_ts(),
        )
        raise
    except Exception as exc:
        _update_claim_analysis_run(
            run_id,
            status="failed",
            error_text=_trim_text(str(exc), 2000),
            updated_at=_now_ts(),
        )
        raise HTTPException(status_code=502, detail=f"Claim analysis failed: {exc}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        lock.release()

@app.get("/api/projects/{project_id}/claims/{claim_id}/board")
async def get_claim_evidence_board(project_id: int, claim_id: int, current_user: dict = Depends(_require_session)):
    claim = _get_owned_claim(project_id, claim_id, current_user["user_id"])
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM claim_evidence_items WHERE claim_id = ? AND hidden = 0 ORDER BY pinned DESC, strength_score DESC, relevance_score DESC, id DESC",
        (claim_id,)
    )
    rows = [_serialize_claim_evidence_row(dict(row)) for row in cursor.fetchall()]
    cursor.execute(
        "SELECT * FROM claim_analysis_runs WHERE claim_id = ? ORDER BY id DESC LIMIT 1",
        (claim_id,)
    )
    latest_run_row = cursor.fetchone()
    conn.close()
    board = {stance: [] for stance in sorted(CLAIM_STANCE_VALUES)}
    summary = _default_claim_summary()
    for row in rows:
        stance = _normalize_claim_stance(row.get("stance"))
        board.setdefault(stance, []).append(row)
        summary[stance] = summary.get(stance, 0) + 1
    return {
        "claim": {
            **claim,
            "claim_type": _normalize_claim_type(claim.get("claim_type")),
            "status": _normalize_claim_status(claim.get("status")),
        },
        "board": board,
        "summary": summary,
        "meta": {
            "last_run": dict(latest_run_row) if latest_run_row else None
        }
    }

@app.patch("/api/projects/{project_id}/claims/{claim_id}/evidence/{evidence_id}")
async def patch_claim_evidence_item(project_id: int, claim_id: int, evidence_id: int, payload: ClaimEvidencePatchRequest, current_user: dict = Depends(_require_session)):
    _get_owned_claim(project_id, claim_id, current_user["user_id"])
    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM claim_evidence_items WHERE id = ? AND claim_id = ? AND project_id = ?",
        (evidence_id, claim_id, project_id)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Evidence item not found.")

    fields = []
    params = []
    user_override_touched = False
    if payload.stance is not None:
        fields.append("stance = ?")
        params.append(_normalize_claim_stance(payload.stance))
        user_override_touched = True
    if payload.pinned is not None:
        fields.append("pinned = ?")
        params.append(1 if payload.pinned else 0)
    if payload.hidden is not None:
        fields.append("hidden = ?")
        params.append(1 if payload.hidden else 0)
    if payload.why_matched is not None:
        fields.append("why_matched = ?")
        params.append(_trim_text(payload.why_matched, MAX_EVIDENCE_WHY_MATCHED_LENGTH))
        user_override_touched = True
    if payload.caveat is not None:
        fields.append("caveat = ?")
        params.append(_trim_text(payload.caveat, MAX_EVIDENCE_CAVEAT_LENGTH))
        user_override_touched = True
    if payload.user_override is not None:
        fields.append("user_override = ?")
        params.append(1 if payload.user_override else 0)
    elif user_override_touched:
        fields.append("user_override = ?")
        params.append(1)
    if not fields:
        conn.close()
        raise HTTPException(status_code=400, detail="No evidence changes were provided.")
    fields.append("updated_at = ?")
    params.append(_now_ts())
    params.append(evidence_id)
    cursor.execute(f"UPDATE claim_evidence_items SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    cursor.execute("SELECT * FROM claim_evidence_items WHERE id = ?", (evidence_id,))
    updated = _serialize_claim_evidence_row(dict(cursor.fetchone()))
    conn.close()
    _write_audit_log(
        "project_claim_patch_evidence",
        user_id=current_user["user_id"],
        project_id=project_id,
        detail={"claim_id": claim_id, "evidence_id": evidence_id},
        success=True
    )
    return {"evidence": updated}

@app.post("/api/projects/{project_id}/claims/{claim_id}/challenge-expand")
async def expand_claim_challenge_seed(project_id: int, claim_id: int, payload: ChallengeExpansionRequest, current_user: dict = Depends(_require_session)):
    project_data = _get_owned_project(project_id, current_user["user_id"])
    claim = _get_owned_claim(project_id, claim_id, current_user["user_id"])
    payload = _validate_challenge_expansion_payload(payload)

    conn = _db_connect(row_factory=True)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM claim_evidence_items WHERE id = ? AND claim_id = ? AND project_id = ? AND hidden = 0",
        (payload.evidence_id, claim_id, project_id)
    )
    evidence_row = cursor.fetchone()
    conn.close()
    if not evidence_row:
        raise HTTPException(status_code=404, detail="Challenge seed evidence item not found.")

    result = _expand_challenge_seed(project_data, claim, dict(evidence_row), payload)
    _write_audit_log(
        "project_claim_expand_challenge",
        user_id=current_user["user_id"],
        project_id=project_id,
        detail={"claim_id": claim_id, "evidence_id": payload.evidence_id, "returned_count": len(result.get("recommendations") or [])},
        success=True
    )
    return result

@app.delete("/api/projects/{project_id}/claims/{claim_id}")
async def archive_project_claim(project_id: int, claim_id: int, current_user: dict = Depends(_require_session)):
    _get_owned_claim(project_id, claim_id, current_user["user_id"])
    now = _now_ts()
    conn = _db_connect()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE project_claims SET status = ?, updated_at = ? WHERE id = ? AND project_id = ?",
        ("archived", now, claim_id, project_id)
    )
    conn.commit()
    conn.close()
    _write_audit_log(
        "project_claim_archive",
        user_id=current_user["user_id"],
        project_id=project_id,
        detail={"claim_id": claim_id},
        success=True
    )
    return {"message": "Claim archived"}

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

@app.post("/api/literature_watch/journal_search")
async def literature_watch_journal_search(payload: LiteratureWatchSourceSearchRequest, current_user: dict = Depends(_require_session)):
    query = _trim_text(_collapse_whitespace(payload.query), 160)
    if not query:
        raise HTTPException(status_code=422, detail="Journal search query is required.")
    lookup_payload = _make_watch_lookup_payload()
    results = _search_openalex_sources(query, lookup_payload, per_page=max(1, min(int(payload.limit or 5), 8)))
    return {"results": results}

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

@app.post("/api/papers/semantic-cluster/jobs", response_model=SemanticClusterJobCreated)
async def create_semantic_cluster_job(payload: SemanticClusterRequest, current_user: dict = Depends(_require_session)):
    normalized_total = min(len(payload.papers), MAX_TOP_PAPERS, max(int(payload.assignment_limit or MAX_TOP_PAPERS), 0))
    job_id = _create_semantic_cluster_job(normalized_total)
    _write_audit_log("semantic_cluster_create", user_id=current_user["user_id"], detail={"paper_count": len(payload.papers), "assignment_limit": payload.assignment_limit, "job_id": job_id}, success=True)
    asyncio.create_task(_run_semantic_cluster_job(job_id, payload))
    return SemanticClusterJobCreated(job_id=job_id, status="queued")

@app.get("/api/papers/semantic-cluster/jobs/{job_id}")
async def get_semantic_cluster_job(job_id: str, current_user: dict = Depends(_require_session)):
    job = SEMANTIC_CLUSTER_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Semantic cluster job not found.")
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
