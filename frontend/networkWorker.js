import { createEmbeddingService, EMBEDDING_SCOPES } from './embeddingService.js';
import {
    NETWORK_DEFAULT_INSPECTOR_THRESHOLD,
    NETWORK_DEFAULT_TOP_K,
    NETWORK_WORKER_TASKS,
    buildPairSimilarityCacheKey,
    cosineSimilarity,
    createFallbackNetworkVector
} from './networkComputation.js';

const embeddingService = createEmbeddingService();
const resolvedPaperVectorCache = new Map();
const pairSimilarityCache = new Map();
const graphResultCache = new Map();
const focusedContextCache = new Map();
const inspectorSimilarCache = new Map();

function postTaskProgress(requestId, message, percent = 0, detail = '') {
    self.postMessage({
        type: 'progress',
        requestId,
        progress: {
            message,
            percent,
            detail
        }
    });
}

function buildMaterializedSignature(papers = []) {
    return (papers || [])
        .map(paper => `${paper.graph_key}:${paper.network_signature}`)
        .filter(Boolean)
        .join('|');
}

async function resolvePaperVector(paper) {
    const graphKey = String(paper?.graph_key || '').trim();
    const signature = String(paper?.network_signature || '').trim();
    if (!graphKey || !signature) {
        return {
            key: graphKey,
            signature,
            vector: createFallbackNetworkVector()
        };
    }
    const cacheKey = `${String(paper?.paper_identity || graphKey).trim()}::${signature}`;
    if (resolvedPaperVectorCache.has(cacheKey)) {
        return {
            key: graphKey,
            signature,
            vector: await resolvedPaperVectorCache.get(cacheKey)
        };
    }
    const persistedVector = (
        Array.isArray(paper?.network_vec)
        && paper.network_vec.length > 0
        && String(paper?.network_vec_embedding_scope || '').trim() === EMBEDDING_SCOPES.NETWORK_GRAPH_V2.embedding_scope
        && String(paper?.network_vec_embedding_version || '').trim() === EMBEDDING_SCOPES.NETWORK_GRAPH_V2.embedding_version
    )
        ? paper.network_vec
        : null;
    if (persistedVector) {
        resolvedPaperVectorCache.set(cacheKey, persistedVector);
        return {
            key: graphKey,
            signature,
            vector: persistedVector
        };
    }
    const pending = embeddingService.getPaperNetworkVector({
        id: paper.id,
        zotero_item_key: paper.zotero_item_key,
        openalex_id: paper.openalex_id,
        doi: paper.doi,
        filename: paper.filename,
        title: paper.title,
        abstract: paper.abstract,
        current_content: paper.current_content,
        authors: paper.authors
    }).catch(() => createFallbackNetworkVector());
    resolvedPaperVectorCache.set(cacheKey, pending);
    const vector = await pending;
    resolvedPaperVectorCache.set(cacheKey, vector);
    return {
        key: graphKey,
        signature,
        vector
    };
}

async function materializePapers(papers = [], { requestId = 0, progressMessage = 'Preparing network vectors...' } = {}) {
    const materialized = [];
    const total = Math.max(1, papers.length);
    for (let index = 0; index < papers.length; index += 1) {
        const paper = papers[index];
        const resolved = await resolvePaperVector(paper);
        materialized.push({
            ...paper,
            graph_key: resolved.key,
            network_signature: resolved.signature,
            vector: resolved.vector
        });
        const percent = 8 + Math.round(((index + 1) / total) * 44);
        postTaskProgress(
            requestId,
            progressMessage,
            percent,
            `Embedding ${index + 1}/${papers.length} papers`
        );
    }
    return materialized;
}

function computeSimilarity(sourcePaper, targetPaper) {
    const cacheKey = buildPairSimilarityCacheKey(
        sourcePaper.graph_key,
        sourcePaper.network_signature,
        targetPaper.graph_key,
        targetPaper.network_signature
    );
    if (pairSimilarityCache.has(cacheKey)) {
        return pairSimilarityCache.get(cacheKey);
    }
    const similarity = cosineSimilarity(sourcePaper.vector, targetPaper.vector);
    pairSimilarityCache.set(cacheKey, similarity);
    return similarity;
}

function cloneGraphResult(result = {}) {
    return {
        signature: result.signature || '',
        nodes: Array.isArray(result.nodes) ? result.nodes.map(node => ({ ...node })) : [],
        links: Array.isArray(result.links) ? result.links.map(link => ({ ...link })) : [],
        adjacency: result.adjacency ? Object.fromEntries(Object.entries(result.adjacency).map(([key, values]) => [key, [...values]])) : {},
        adjacencyByKey: result.adjacencyByKey ? Object.fromEntries(Object.entries(result.adjacencyByKey).map(([key, values]) => [key, [...values]])) : {},
        neighborPairsByKey: result.neighborPairsByKey
            ? Object.fromEntries(
                Object.entries(result.neighborPairsByKey).map(([key, values]) => [
                    key,
                    (values || []).map(item => ({ ...item }))
                ])
            )
            : {},
        nodeNameByKey: result.nodeNameByKey ? { ...result.nodeNameByKey } : {},
        nodeKeyByName: result.nodeKeyByName ? { ...result.nodeKeyByName } : {}
    };
}

function computeGraphResult(materializedPapers = [], topK = NETWORK_DEFAULT_TOP_K, requestId = 0) {
    const signature = buildMaterializedSignature(materializedPapers);
    const cacheKey = `${topK}::${signature}`;
    if (graphResultCache.has(cacheKey)) {
        return cloneGraphResult(graphResultCache.get(cacheKey));
    }
    const nodes = materializedPapers.map((paper, index) => ({
        name: `PAPER_${index}`,
        paperKey: paper.graph_key,
        similarity: Number(paper.similarity || 0)
    }));
    const nodeNameByKey = Object.fromEntries(nodes.map(node => [node.paperKey, node.name]));
    const nodeKeyByName = Object.fromEntries(nodes.map(node => [node.name, node.paperKey]));
    const adjacency = Object.fromEntries(nodes.map(node => [node.name, []]));
    const adjacencyByKey = Object.fromEntries(nodes.map(node => [node.paperKey, []]));
    const neighborPairsByKey = Object.fromEntries(nodes.map(node => [node.paperKey, []]));
    const uniquePairwiseLinks = new Map();
    const normalizedTopK = Math.max(1, Number(topK) || NETWORK_DEFAULT_TOP_K);

    for (let sourceIndex = 0; sourceIndex < materializedPapers.length; sourceIndex += 1) {
        const sourcePaper = materializedPapers[sourceIndex];
        const neighbors = [];
        for (let targetIndex = 0; targetIndex < materializedPapers.length; targetIndex += 1) {
            if (sourceIndex === targetIndex) continue;
            const targetPaper = materializedPapers[targetIndex];
            const similarity = computeSimilarity(sourcePaper, targetPaper);
            if (!Number.isFinite(similarity) || similarity <= 0) continue;
            neighbors.push({
                sourceKey: sourcePaper.graph_key,
                targetKey: targetPaper.graph_key,
                sourceIndex,
                targetIndex,
                similarity
            });
        }
        neighbors.sort((left, right) => Number(right.similarity || 0) - Number(left.similarity || 0));
        const topNeighbors = neighbors.slice(0, normalizedTopK);
        neighborPairsByKey[sourcePaper.graph_key] = topNeighbors.map(neighbor => ({
            targetKey: neighbor.targetKey,
            similarity: neighbor.similarity
        }));
        topNeighbors.forEach(neighbor => {
            const sourceNodeName = `PAPER_${sourceIndex}`;
            const targetNodeName = `PAPER_${neighbor.targetIndex}`;
            if (!adjacency[sourceNodeName].includes(targetNodeName)) adjacency[sourceNodeName].push(targetNodeName);
            if (!adjacency[targetNodeName].includes(sourceNodeName)) adjacency[targetNodeName].push(sourceNodeName);
            if (!adjacencyByKey[sourcePaper.graph_key].includes(neighbor.targetKey)) adjacencyByKey[sourcePaper.graph_key].push(neighbor.targetKey);
            if (!adjacencyByKey[neighbor.targetKey].includes(sourcePaper.graph_key)) adjacencyByKey[neighbor.targetKey].push(sourcePaper.graph_key);
            const edgeKey = sourceIndex < neighbor.targetIndex
                ? `${sourceIndex}-${neighbor.targetIndex}`
                : `${neighbor.targetIndex}-${sourceIndex}`;
            if (!uniquePairwiseLinks.has(edgeKey)) {
                uniquePairwiseLinks.set(edgeKey, {
                    source: sourceIndex < neighbor.targetIndex ? sourceNodeName : targetNodeName,
                    target: sourceIndex < neighbor.targetIndex ? targetNodeName : sourceNodeName,
                    sourceKey: sourceIndex < neighbor.targetIndex ? sourcePaper.graph_key : neighbor.targetKey,
                    targetKey: sourceIndex < neighbor.targetIndex ? neighbor.targetKey : sourcePaper.graph_key,
                    weight: neighbor.similarity,
                    isTargetLine: false
                });
            }
        });
        const percent = 56 + Math.round(((sourceIndex + 1) / Math.max(1, materializedPapers.length)) * 40);
        postTaskProgress(requestId, 'Computing network relationships...', percent, `Comparing ${sourceIndex + 1}/${materializedPapers.length} papers`);
    }

    const result = {
        signature,
        nodes,
        links: Array.from(uniquePairwiseLinks.values()),
        adjacency,
        adjacencyByKey,
        neighborPairsByKey,
        nodeNameByKey,
        nodeKeyByName
    };
    graphResultCache.set(cacheKey, result);
    return cloneGraphResult(result);
}

async function handleRenderNetwork(message = {}) {
    const materializedPapers = await materializePapers(message.papers || [], {
        requestId: message.requestId,
        progressMessage: 'Preparing paper embeddings...'
    });
    return computeGraphResult(materializedPapers, message?.options?.topK, message.requestId);
}

async function handleFocusedContext(message = {}) {
    const focusPaperKey = String(message?.options?.focusPaperKey || '').trim();
    if (!focusPaperKey) {
        return {
            focalKey: '',
            rankedPapers: [],
            originalTargetSimilarity: 0
        };
    }
    const materializedPapers = await materializePapers(message.papers || [], {
        requestId: message.requestId,
        progressMessage: 'Preparing embeddings for the focused StarMap...'
    });
    const signature = buildMaterializedSignature(materializedPapers);
    const targetCacheKey = `${String(message?.currentProjectTarget?.id || message?.currentProjectTarget?.project_name || 'project:unknown').trim()}::${signature}::${focusPaperKey}`;
    if (focusedContextCache.has(targetCacheKey)) {
        return {
            ...focusedContextCache.get(targetCacheKey),
            rankedPapers: focusedContextCache.get(targetCacheKey).rankedPapers.map(item => ({ ...item }))
        };
    }
    const focalPaper = materializedPapers.find(paper => paper.graph_key === focusPaperKey) || null;
    if (!focalPaper) {
        return {
            focalKey: focusPaperKey,
            rankedPapers: [],
            originalTargetSimilarity: 0
        };
    }
    postTaskProgress(message.requestId, 'Embedding the original target thesis...', 72, 'Preparing the focused comparison target');
    const targetVector = await embeddingService.getTargetVector(message.currentProjectTarget || {}, EMBEDDING_SCOPES.TARGET_NETWORK_GRAPH_V2)
        .catch(() => createFallbackNetworkVector());
    postTaskProgress(message.requestId, 'Ranking focused neighbors...', 84, `Comparing ${materializedPapers.length - 1} related papers`);
    const rankedPapers = materializedPapers
        .filter(paper => paper.graph_key && paper.graph_key !== focusPaperKey)
        .map(paper => ({
            paperKey: paper.graph_key,
            similarity: computeSimilarity(focalPaper, paper)
        }))
        .sort((left, right) => Number(right.similarity || 0) - Number(left.similarity || 0));
    const result = {
        focalKey: focusPaperKey,
        rankedPapers,
        originalTargetSimilarity: cosineSimilarity(focalPaper.vector, targetVector)
    };
    focusedContextCache.set(targetCacheKey, result);
    return {
        ...result,
        rankedPapers: rankedPapers.map(item => ({ ...item }))
    };
}

async function handleNetworkAdjacency(message = {}) {
    const materializedPapers = await materializePapers(message.papers || [], {
        requestId: message.requestId,
        progressMessage: 'Preparing network neighbor adjacency...'
    });
    const graphResult = computeGraphResult(materializedPapers, message?.options?.topK, message.requestId);
    return {
        signature: graphResult.signature,
        adjacencyByKey: graphResult.adjacencyByKey,
        neighborPairsByKey: graphResult.neighborPairsByKey
    };
}

async function handleInspectorSimilar(message = {}) {
    const focusPaperKey = String(message?.options?.focusPaperKey || '').trim();
    if (!focusPaperKey) return { focalKey: '', items: [] };
    const materializedPapers = await materializePapers(message.papers || [], {
        requestId: message.requestId,
        progressMessage: 'Preparing inspector similarity data...'
    });
    const signature = buildMaterializedSignature(materializedPapers);
    const threshold = Number(message?.options?.similarityThreshold ?? NETWORK_DEFAULT_INSPECTOR_THRESHOLD);
    const limit = Math.max(0, Number(message?.options?.limit || 0));
    const cacheKey = `${focusPaperKey}::${signature}::${threshold}::${limit}`;
    if (inspectorSimilarCache.has(cacheKey)) {
        return {
            focalKey: focusPaperKey,
            items: inspectorSimilarCache.get(cacheKey).map(item => ({ ...item }))
        };
    }
    const focalPaper = materializedPapers.find(paper => paper.graph_key === focusPaperKey) || null;
    if (!focalPaper) return { focalKey: focusPaperKey, items: [] };
    postTaskProgress(message.requestId, 'Ranking similar papers for the inspector...', 88, 'Sorting cached network similarities');
    const items = materializedPapers
        .filter(paper => paper.graph_key && paper.graph_key !== focusPaperKey)
        .map(paper => ({
            paperKey: paper.graph_key,
            similarity: computeSimilarity(focalPaper, paper)
        }))
        .filter(item => Number.isFinite(item.similarity) && item.similarity > threshold)
        .sort((left, right) => Number(right.similarity || 0) - Number(left.similarity || 0));
    const normalizedItems = limit > 0 ? items.slice(0, limit) : items;
    inspectorSimilarCache.set(cacheKey, normalizedItems);
    return {
        focalKey: focusPaperKey,
        items: normalizedItems.map(item => ({ ...item }))
    };
}

async function handleTask(message = {}) {
    switch (String(message.taskType || '').trim()) {
        case NETWORK_WORKER_TASKS.RENDER_NETWORK:
            return handleRenderNetwork(message);
        case NETWORK_WORKER_TASKS.FOCUSED_CONTEXT:
            return handleFocusedContext(message);
        case NETWORK_WORKER_TASKS.NETWORK_ADJACENCY:
            return handleNetworkAdjacency(message);
        case NETWORK_WORKER_TASKS.INSPECTOR_SIMILAR:
            return handleInspectorSimilar(message);
        default:
            throw new Error(`Unsupported network worker task: ${String(message.taskType || '')}`);
    }
}

self.addEventListener('message', event => {
    const message = event?.data || {};
    const requestId = Number(message.requestId || 0);
    Promise.resolve(handleTask(message))
        .then(result => {
            self.postMessage({
                type: 'result',
                requestId,
                result
            });
        })
        .catch(error => {
            self.postMessage({
                type: 'error',
                requestId,
                error: String(error?.message || error || 'Unknown network worker error')
            });
        });
});
