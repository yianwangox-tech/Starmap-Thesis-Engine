import { pipeline } from 'https://cdn.jsdelivr.net/npm/@xenova/transformers@2.16.0';

export const EMBEDDING_MODEL_NAME = 'Xenova/all-MiniLM-L6-v2';

export const EMBEDDING_SCOPES = Object.freeze({
    NETWORK_GRAPH_V2: Object.freeze({
        key: 'network_graph_v2',
        embedding_scope: 'network_graph',
        embedding_version: 'v2'
    }),
    TARGET_NETWORK_GRAPH_V2: Object.freeze({
        key: 'target_network_graph_v2',
        embedding_scope: 'target_network_graph',
        embedding_version: 'v2'
    }),
    PAPER_TITLE_V1: Object.freeze({
        key: 'paper_title_v1',
        embedding_scope: 'paper_title',
        embedding_version: 'v1'
    }),
    PAPER_ABSTRACT_V1: Object.freeze({
        key: 'paper_abstract_v1',
        embedding_scope: 'paper_abstract',
        embedding_version: 'v1'
    }),
    PAPER_CURRENT_CONTENT_V1: Object.freeze({
        key: 'paper_current_content_v1',
        embedding_scope: 'paper_current_content',
        embedding_version: 'v1'
    }),
    TARGET_TITLE_V1: Object.freeze({
        key: 'target_title_v1',
        embedding_scope: 'target_title',
        embedding_version: 'v1'
    }),
    TARGET_ABSTRACT_V1: Object.freeze({
        key: 'target_abstract_v1',
        embedding_scope: 'target_abstract',
        embedding_version: 'v1'
    }),
    TARGET_CURRENT_CONTENT_V1: Object.freeze({
        key: 'target_current_content_v1',
        embedding_scope: 'target_current_content',
        embedding_version: 'v1'
    }),
    PAPER_CLUSTER_THEME_V1: Object.freeze({
        key: 'paper_cluster_theme_v1',
        embedding_scope: 'paper_cluster_theme',
        embedding_version: 'v1'
    })
});

const EMBEDDING_SCOPE_MAP = new Map(
    Object.values(EMBEDDING_SCOPES).map(scope => [scope.key, scope])
);

function normalizeText(value) {
    return String(value ?? '').replace(/\s+/g, ' ').trim();
}

function truncateNormalizedText(value, maxLength = 0) {
    const normalized = normalizeText(value);
    if (!maxLength || normalized.length <= maxLength) return normalized;
    return normalized.slice(0, maxLength);
}

function joinEmbeddingParts(parts = []) {
    return parts.map(part => normalizeText(part)).filter(Boolean).join(' ').trim();
}

function isMeaningfulText(value) {
    return normalizeText(value).length > 0;
}

function hashText(value) {
    const source = String(value ?? '');
    let hash = 2166136261;
    for (let i = 0; i < source.length; i += 1) {
        hash ^= source.charCodeAt(i);
        hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16).padStart(8, '0');
}

export function getEmbeddingTextSignature(value) {
    return hashText(normalizeText(value) || ' ');
}

function resolveScopeDefinition(scope) {
    if (!scope) throw new Error('Embedding scope is required.');
    if (typeof scope === 'string') {
        const resolved = EMBEDDING_SCOPE_MAP.get(scope);
        if (!resolved) throw new Error(`Unknown embedding scope: ${scope}`);
        return resolved;
    }
    if (scope?.key && EMBEDDING_SCOPE_MAP.has(scope.key)) {
        return EMBEDDING_SCOPE_MAP.get(scope.key);
    }
    throw new Error(`Unknown embedding scope: ${String(scope?.key || scope)}`);
}

function getStablePaperCacheKey(paper) {
    if (!paper) return 'paper:unknown';
    return String(
        paper.id
        || paper.zotero_item_key
        || paper.openalex_id
        || paper.doi
        || paper.filename
        || paper.title
        || 'paper:unknown'
    ).trim() || 'paper:unknown';
}

function getStableProjectCacheKey(project) {
    if (!project) return 'project:unknown';
    return String(project.id || project.project_name || 'project:unknown').trim() || 'project:unknown';
}

export function buildNetworkEmbeddingText(paper) {
    return joinEmbeddingParts([
        paper?.title || '',
        truncateNormalizedText(paper?.abstract || '', 1600),
        truncateNormalizedText(paper?.current_content || '', 2400),
        paper?.authors || ''
    ]);
}

export function getNetworkEmbeddingTextSignature(paper) {
    return getEmbeddingTextSignature(buildNetworkEmbeddingText(paper));
}

export function buildPaperClusterThemeText(paper) {
    const title = normalizeText(paper?.title || '');
    return joinEmbeddingParts([
        title,
        title,
        truncateNormalizedText(paper?.abstract || '', 1200),
        truncateNormalizedText(paper?.current_content || '', 2200)
    ]);
}

function buildPaperFieldText(paper, scopeDefinition) {
    switch (scopeDefinition.key) {
        case EMBEDDING_SCOPES.NETWORK_GRAPH_V2.key:
            return buildNetworkEmbeddingText(paper);
        case EMBEDDING_SCOPES.PAPER_TITLE_V1.key:
            return normalizeText(paper?.title || '');
        case EMBEDDING_SCOPES.PAPER_ABSTRACT_V1.key:
            return normalizeText(paper?.abstract || '');
        case EMBEDDING_SCOPES.PAPER_CURRENT_CONTENT_V1.key:
            return normalizeText(paper?.current_content || '');
        case EMBEDDING_SCOPES.PAPER_CLUSTER_THEME_V1.key:
            return buildPaperClusterThemeText(paper);
        default:
            throw new Error(`Unsupported paper embedding scope: ${scopeDefinition.key}`);
    }
}

function buildTargetFieldText(project, scopeDefinition) {
    switch (scopeDefinition.key) {
        case EMBEDDING_SCOPES.TARGET_NETWORK_GRAPH_V2.key:
            return buildNetworkEmbeddingText({
                title: project?.target_title || '',
                abstract: project?.target_abstract || '',
                current_content: project?.target_current_content || '',
                authors: ''
            });
        case EMBEDDING_SCOPES.TARGET_TITLE_V1.key:
            return normalizeText(project?.target_title || '');
        case EMBEDDING_SCOPES.TARGET_ABSTRACT_V1.key:
            return normalizeText(project?.target_abstract || '');
        case EMBEDDING_SCOPES.TARGET_CURRENT_CONTENT_V1.key:
            return normalizeText(project?.target_current_content || '');
        default:
            throw new Error(`Unsupported target embedding scope: ${scopeDefinition.key}`);
    }
}

export function createEmbeddingService() {
    let embeddingModel = null;
    let embeddingModelPromise = null;

    const textVectorCache = new Map();
    const paperVectorCache = new Map();
    const targetVectorCache = new Map();

    function isModelLoaded() {
        return !!embeddingModel;
    }

    async function getEmbeddingModel() {
        if (embeddingModel) return embeddingModel;
        if (!embeddingModelPromise) {
            embeddingModelPromise = pipeline('feature-extraction', EMBEDDING_MODEL_NAME)
                .then(model => {
                    embeddingModel = model;
                    return model;
                })
                .catch(error => {
                    embeddingModelPromise = null;
                    throw error;
                });
        }
        return embeddingModelPromise;
    }

    function buildTextCacheKey(scopeDefinition, normalizedText) {
        const textSignature = hashText(normalizedText || ' ');
        return [
            EMBEDDING_MODEL_NAME,
            scopeDefinition.embedding_scope,
            scopeDefinition.embedding_version,
            textSignature
        ].join('::');
    }

    async function embedText(scope, text) {
        const scopeDefinition = resolveScopeDefinition(scope);
        const normalizedText = normalizeText(text) || ' ';
        const textCacheKey = buildTextCacheKey(scopeDefinition, normalizedText);
        if (textVectorCache.has(textCacheKey)) {
            return await textVectorCache.get(textCacheKey);
        }
        const pending = (async () => {
            const model = await getEmbeddingModel();
            const output = await model(normalizedText, { pooling: 'mean', normalize: true });
            return Array.from(output?.data || []);
        })();
        textVectorCache.set(textCacheKey, pending);
        try {
            const vector = await pending;
            textVectorCache.set(textCacheKey, vector);
            return vector;
        } catch (error) {
            textVectorCache.delete(textCacheKey);
            throw error;
        }
    }

    async function getPaperVector(paper, scope) {
        const scopeDefinition = resolveScopeDefinition(scope);
        const normalizedText = buildPaperFieldText(paper, scopeDefinition);
        const paperIdentity = getStablePaperCacheKey(paper);
        const cacheKey = [
            EMBEDDING_MODEL_NAME,
            scopeDefinition.key,
            paperIdentity,
            hashText(normalizedText || ' ')
        ].join('::');
        if (paperVectorCache.has(cacheKey)) {
            return await paperVectorCache.get(cacheKey);
        }
        const pending = embedText(scopeDefinition, normalizedText);
        paperVectorCache.set(cacheKey, pending);
        try {
            const vector = await pending;
            paperVectorCache.set(cacheKey, vector);
            return vector;
        } catch (error) {
            paperVectorCache.delete(cacheKey);
            throw error;
        }
    }

    async function getTargetVector(project, scope) {
        const scopeDefinition = resolveScopeDefinition(scope);
        const normalizedText = buildTargetFieldText(project, scopeDefinition);
        const projectIdentity = getStableProjectCacheKey(project);
        const cacheKey = [
            EMBEDDING_MODEL_NAME,
            scopeDefinition.key,
            projectIdentity,
            hashText(normalizedText || ' ')
        ].join('::');
        if (targetVectorCache.has(cacheKey)) {
            return await targetVectorCache.get(cacheKey);
        }
        const pending = embedText(scopeDefinition, normalizedText);
        targetVectorCache.set(cacheKey, pending);
        try {
            const vector = await pending;
            targetVectorCache.set(cacheKey, vector);
            return vector;
        } catch (error) {
            targetVectorCache.delete(cacheKey);
            throw error;
        }
    }

    async function getPaperNetworkVector(paper) {
        return getPaperVector(paper, EMBEDDING_SCOPES.NETWORK_GRAPH_V2);
    }

    async function getProjectTargetFieldVectors(project) {
        return {
            title: await getTargetVector(project, EMBEDDING_SCOPES.TARGET_TITLE_V1),
            abstract: await getTargetVector(project, EMBEDDING_SCOPES.TARGET_ABSTRACT_V1),
            currentContent: isMeaningfulText(project?.target_current_content)
                ? await getTargetVector(project, EMBEDDING_SCOPES.TARGET_CURRENT_CONTENT_V1)
                : null
        };
    }

    async function getPaperFieldVectors(paper) {
        const abstractText = normalizeText(paper?.abstract || '');
        const currentContentText = normalizeText(paper?.current_content || '');
        return {
            title: await getPaperVector(paper, EMBEDDING_SCOPES.PAPER_TITLE_V1),
            abstract: await getPaperVector(paper, EMBEDDING_SCOPES.PAPER_ABSTRACT_V1),
            abstractText,
            currentContent: currentContentText
                ? await getPaperVector(paper, EMBEDDING_SCOPES.PAPER_CURRENT_CONTENT_V1)
                : null,
            currentContentText
        };
    }

    function cosineSimilarity(a, b) {
        if (!Array.isArray(a) || !Array.isArray(b) || !a.length || !b.length) return 0;
        const length = Math.min(a.length, b.length);
        let dot = 0;
        let normA = 0;
        let normB = 0;
        for (let i = 0; i < length; i += 1) {
            dot += a[i] * b[i];
            normA += a[i] ** 2;
            normB += b[i] ** 2;
        }
        if (!normA || !normB) return 0;
        return dot / (Math.sqrt(normA) * Math.sqrt(normB));
    }

    return {
        isModelLoaded,
        getEmbeddingModel,
        embedText,
        getPaperVector,
        getTargetVector,
        getPaperNetworkVector,
        getProjectTargetFieldVectors,
        getPaperFieldVectors,
        cosineSimilarity,
        buildNetworkEmbeddingText,
        buildPaperClusterThemeText
    };
}
