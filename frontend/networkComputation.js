import { EMBEDDING_SCOPES, getNetworkEmbeddingTextSignature } from './embeddingService.js';

export const NETWORK_WORKER_TASKS = Object.freeze({
    RENDER_NETWORK: 'render_network',
    FOCUSED_CONTEXT: 'focused_context',
    NETWORK_ADJACENCY: 'network_adjacency',
    INSPECTOR_SIMILAR: 'inspector_similar'
});

export const NETWORK_DEFAULT_TOP_K = 3;
export const NETWORK_DEFAULT_INSPECTOR_THRESHOLD = 0.18;
export const NETWORK_FALLBACK_VECTOR_LENGTH = 384;

export function getStablePaperGraphKey(paper) {
    return String(
        paper?.filename
        || paper?.zotero_item_key
        || paper?.openalex_id
        || paper?.doi
        || paper?.title
        || ''
    ).trim();
}

export function getPaperNetworkSessionIdentity(paper) {
    return String(
        paper?.id
        || paper?.zotero_item_key
        || paper?.openalex_id
        || paper?.doi
        || paper?.filename
        || paper?.title
        || 'paper:unknown'
    ).trim() || 'paper:unknown';
}

export function isUsablePersistedNetworkVector(paper) {
    return (
        Array.isArray(paper?.network_vec)
        && paper.network_vec.length > 0
        && String(paper?.network_vec_embedding_scope || '').trim() === EMBEDDING_SCOPES.NETWORK_GRAPH_V2.embedding_scope
        && String(paper?.network_vec_embedding_version || '').trim() === EMBEDDING_SCOPES.NETWORK_GRAPH_V2.embedding_version
    );
}

export function getPaperNetworkComputationSignature(paper) {
    const key = getStablePaperGraphKey(paper);
    if (!key) return '';
    return `${key}:${getNetworkEmbeddingTextSignature(paper)}`;
}

export function getProjectNetworkComputationSignature(papers = []) {
    return (papers || [])
        .map(getPaperNetworkComputationSignature)
        .filter(Boolean)
        .join('|');
}

export function buildNetworkWorkerPaperPayload(paper) {
    if (!paper) return null;
    const paperIdentity = getPaperNetworkSessionIdentity(paper);
    const graphKey = getStablePaperGraphKey(paper) || paperIdentity;
    return {
        id: paper.id ?? null,
        filename: String(paper.filename || '').trim(),
        zotero_item_key: String(paper.zotero_item_key || '').trim(),
        openalex_id: String(paper.openalex_id || '').trim(),
        doi: String(paper.doi || '').trim(),
        title: paper.title || '',
        abstract: paper.abstract || '',
        current_content: paper.current_content || '',
        authors: paper.authors || '',
        similarity: Number(paper.similarity || 0),
        status: paper.status || '',
        is_new: !!paper.is_new,
        network_vec: isUsablePersistedNetworkVector(paper) ? paper.network_vec : null,
        network_vec_embedding_scope: String(paper.network_vec_embedding_scope || '').trim(),
        network_vec_embedding_version: String(paper.network_vec_embedding_version || '').trim(),
        network_signature: getNetworkEmbeddingTextSignature(paper),
        paper_identity: paperIdentity,
        graph_key: graphKey
    };
}

export function buildNetworkWorkerPaperPayloads(papers = []) {
    return (papers || [])
        .map(buildNetworkWorkerPaperPayload)
        .filter(Boolean);
}

export function buildNetworkWorkerProjectTargetPayload(project) {
    if (!project) return null;
    return {
        id: project.id ?? null,
        project_name: project.project_name || '',
        target_title: project.target_title || '',
        target_abstract: project.target_abstract || '',
        target_current_content: project.target_current_content || ''
    };
}

export function buildPairSimilarityCacheKey(sourceKey, sourceSignature, targetKey, targetSignature) {
    const left = `${String(sourceKey || '').trim()}::${String(sourceSignature || '').trim()}`;
    const right = `${String(targetKey || '').trim()}::${String(targetSignature || '').trim()}`;
    return left <= right ? `${left}<>${right}` : `${right}<>${left}`;
}

export function cosineSimilarity(a, b) {
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

export function createFallbackNetworkVector(length = NETWORK_FALLBACK_VECTOR_LENGTH) {
    return new Array(Math.max(1, Number(length) || NETWORK_FALLBACK_VECTOR_LENGTH)).fill(0.0001);
}
