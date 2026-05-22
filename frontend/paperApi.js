function buildApiError(actionLabel, status, detail) {
    const normalized = String(detail || '').trim();
    return new Error(normalized || `Failed to ${actionLabel} (${status}).`);
}

async function parseResponseDetail(res) {
    try {
        const data = await res.clone().json();
        return data?.detail || data?.message || '';
    } catch {
        try {
            return (await res.text()).trim();
        } catch {
            return '';
        }
    }
}

export function createPaperApi({ getApiBase, ensureWritableApiSuccess, fetchImpl = fetch }) {
    const requireApiBase = () => {
        const apiBase = typeof getApiBase === 'function' ? getApiBase() : getApiBase;
        if (!apiBase) throw new Error('Paper API base is not configured.');
        return apiBase;
    };

    const ensureReadableApiSuccess = async (res, actionLabel) => {
        if (res.ok) return res;
        const detail = await parseResponseDetail(res);
        throw buildApiError(actionLabel, res.status, detail);
    };

    const ensureWritable = async (res, actionLabel) => {
        if (typeof ensureWritableApiSuccess === 'function') {
            return ensureWritableApiSuccess(res, actionLabel);
        }
        return ensureReadableApiSuccess(res, actionLabel);
    };

    return {
        async fetchProjectMetadata(projectId) {
            const res = await fetchImpl(`${requireApiBase()}/projects/${projectId}`);
            await ensureReadableApiSuccess(res, 'load project metadata');
            return res.json();
        },

        async fetchProjectPapers(projectId) {
            const res = await fetchImpl(`${requireApiBase()}/projects/${projectId}/papers`);
            if (!res.ok && (res.status === 404 || res.status === 405)) {
                const legacyRes = await fetchImpl(`${requireApiBase()}/projects/${projectId}`);
                await ensureReadableApiSuccess(legacyRes, 'load project papers');
                const legacyProject = await legacyRes.json();
                return Array.isArray(legacyProject?.top_papers) ? legacyProject.top_papers : [];
            }
            await ensureReadableApiSuccess(res, 'load project papers');
            const data = await res.json();
            return Array.isArray(data?.papers) ? data.papers : [];
        },

        async loadProject(projectId) {
            const project = await this.fetchProjectMetadata(projectId);
            if (Array.isArray(project?.top_papers)) {
                return project;
            }
            const papers = await this.fetchProjectPapers(projectId);
            return { ...project, top_papers: papers };
        },

        async mergeProjectPapers(projectId, newPapers) {
            const res = await fetchImpl(`${requireApiBase()}/projects/${projectId}/merge_papers`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_papers: newPapers || [] })
            });
            await ensureWritable(res, 'save imported papers');
            return res.json();
        },

        async replaceProjectPapers(projectId, papers) {
            const res = await fetchImpl(`${requireApiBase()}/projects/${projectId}/papers`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ top_papers: papers || [] })
            });
            await ensureWritable(res, 'save paper updates');
            return res.json();
        },

        async patchProjectPaper(projectId, paperId, changes) {
            const res = await fetchImpl(`${requireApiBase()}/projects/${projectId}/papers/${paperId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ changes: changes || {} })
            });
            await ensureWritable(res, 'save this paper change');
            return res.json();
        },

        async patchProjectPapers(projectId, patches) {
            const res = await fetchImpl(`${requireApiBase()}/projects/${projectId}/papers/batch_patch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ patches: patches || [] })
            });
            await ensureWritable(res, 'save paper updates');
            return res.json();
        },

        async upsertProjectPapers(projectId, papers) {
            const res = await fetchImpl(`${requireApiBase()}/projects/${projectId}/papers/batch_upsert`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ papers: papers || [] })
            });
            await ensureWritable(res, 'save paper updates');
            return res.json();
        },

        async deleteProjectPaper(projectId, paperId) {
            const res = await fetchImpl(`${requireApiBase()}/projects/${projectId}/papers/${paperId}`, {
                method: 'DELETE'
            });
            await ensureWritable(res, 'delete this paper');
            return res.json();
        },

        async clearProjectPapers(projectId) {
            const res = await fetchImpl(`${requireApiBase()}/projects/${projectId}/papers`, {
                method: 'DELETE'
            });
            await ensureWritable(res, 'clear project papers');
            return res.json();
        }
    };
}
