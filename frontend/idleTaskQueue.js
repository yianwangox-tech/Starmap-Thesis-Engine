function createDeadlineShim(budgetMs = 12) {
    const start = typeof performance !== 'undefined' && typeof performance.now === 'function'
        ? performance.now()
        : Date.now();
    return {
        didTimeout: false,
        timeRemaining() {
            const now = typeof performance !== 'undefined' && typeof performance.now === 'function'
                ? performance.now()
                : Date.now();
            return Math.max(0, budgetMs - (now - start));
        }
    };
}

function normalizePriority(priority, fallback = 99) {
    const parsed = Number(priority);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function compareTasks(a, b) {
    const priorityDiff = normalizePriority(a?.priority) - normalizePriority(b?.priority);
    if (priorityDiff !== 0) return priorityDiff;
    const enqueuedDiff = Number(a?.enqueuedAt || 0) - Number(b?.enqueuedAt || 0);
    if (enqueuedDiff !== 0) return enqueuedDiff;
    return Number(a?.order || 0) - Number(b?.order || 0);
}

export function createIdleTaskQueue(options = {}) {
    const state = {
        tasks: [],
        manualPauseReasons: new Set(),
        activeTaskId: null,
        running: false,
        order: 0,
        scheduledHandle: null,
        scheduledMode: '',
        heartbeatHandle: null,
        projectWarmups: new Map()
    };

    const heartbeatMs = Math.max(300, Number(options.heartbeatMs || 900));
    const fallbackBudgetMs = Math.max(4, Number(options.fallbackBudgetMs || 12));
    const lowChunkDelayMs = Math.max(0, Number(options.lowChunkDelayMs || 28));
    const mediumChunkDelayMs = Math.max(lowChunkDelayMs, Number(options.mediumChunkDelayMs || 180));

    function hasIdleCallback() {
        return typeof window !== 'undefined' && typeof window.requestIdleCallback === 'function';
    }

    function clearScheduledHandle() {
        if (state.scheduledHandle == null) return;
        if (state.scheduledMode === 'idle' && typeof window.cancelIdleCallback === 'function') {
            window.cancelIdleCallback(state.scheduledHandle);
        } else {
            clearTimeout(state.scheduledHandle);
        }
        state.scheduledHandle = null;
        state.scheduledMode = '';
    }

    function getLoadLevel() {
        if (typeof options.getLoadLevel !== 'function') return 'low';
        const level = String(options.getLoadLevel() || 'low').trim().toLowerCase();
        return ['high', 'medium', 'low'].includes(level) ? level : 'low';
    }

    function getSystemPauseReason() {
        if (typeof options.getSystemPauseReason !== 'function') return '';
        return String(options.getSystemPauseReason() || '').trim();
    }

    function getWarmupRemaining(projectId) {
        if (projectId == null) return 0;
        const key = String(projectId);
        const until = Number(state.projectWarmups.get(key) || 0);
        if (!until) return 0;
        const remaining = until - Date.now();
        if (remaining <= 0) {
            state.projectWarmups.delete(key);
            return 0;
        }
        return remaining;
    }

    function getDynamicPauseReasons(task = null) {
        const reasons = [...state.manualPauseReasons];
        const systemReason = getSystemPauseReason();
        if (systemReason) reasons.push(systemReason);
        const warmupRemaining = task ? getWarmupRemaining(task.projectId) : 0;
        if (warmupRemaining > 0) {
            reasons.push(`warmup:${String(task?.projectId || '')}:${Math.ceil(warmupRemaining)}`);
        }
        if (task && typeof task.shouldPause === 'function') {
            const taskReason = task.shouldPause({
                loadLevel: getLoadLevel(),
                activeTaskId: state.activeTaskId,
                queueLength: state.tasks.filter(item => !item.cancelled).length
            });
            if (taskReason) {
                reasons.push(String(taskReason));
            }
        }
        return reasons.filter(Boolean);
    }

    function getChunkDelayMs() {
        return getLoadLevel() === 'medium' ? mediumChunkDelayMs : lowChunkDelayMs;
    }

    function getIdleTimeoutMs() {
        return getLoadLevel() === 'medium' ? 1200 : 700;
    }

    function schedule(delayMs = 0) {
        clearScheduledHandle();
        const normalizedDelay = Math.max(0, Number(delayMs || 0));
        const run = () => {
            if (hasIdleCallback()) {
                state.scheduledMode = 'idle';
                state.scheduledHandle = window.requestIdleCallback(deadline => {
                    state.scheduledHandle = null;
                    state.scheduledMode = '';
                    void tick(deadline);
                }, { timeout: getIdleTimeoutMs() });
                return;
            }
            state.scheduledMode = 'timeout';
            state.scheduledHandle = window.setTimeout(() => {
                state.scheduledHandle = null;
                state.scheduledMode = '';
                void tick(createDeadlineShim(fallbackBudgetMs));
            }, 0);
        };
        if (normalizedDelay > 0) {
            state.scheduledMode = 'timeout';
            state.scheduledHandle = window.setTimeout(run, normalizedDelay);
            return;
        }
        run();
    }

    function ensureHeartbeat() {
        if (state.heartbeatHandle != null) return;
        state.heartbeatHandle = window.setInterval(() => {
            if (!state.tasks.length && !state.running && !state.manualPauseReasons.size) return;
            if (state.scheduledHandle == null) {
                schedule(Math.min(heartbeatMs, getChunkDelayMs() || heartbeatMs));
            }
        }, heartbeatMs);
    }

    function maybeStopHeartbeat() {
        if (state.heartbeatHandle == null) return;
        if (state.tasks.length || state.running || state.manualPauseReasons.size) return;
        clearInterval(state.heartbeatHandle);
        state.heartbeatHandle = null;
    }

    function removeTaskById(taskId) {
        const index = state.tasks.findIndex(task => task.id === taskId);
        if (index >= 0) {
            state.tasks.splice(index, 1);
        }
    }

    function pickNextTask() {
        const available = state.tasks.filter(task => !task.cancelled);
        if (!available.length) return null;
        available.sort(compareTasks);
        return available[0] || null;
    }

    function invalidateTaskIfNeeded(task) {
        if (!task) return true;
        if (typeof options.isTaskContextValid === 'function' && !options.isTaskContextValid(task)) {
            removeTaskById(task.id);
            return true;
        }
        return false;
    }

    async function tick(deadline = createDeadlineShim(fallbackBudgetMs)) {
        if (state.running) return;
        const task = pickNextTask();
        if (!task) {
            maybeStopHeartbeat();
            return;
        }
        if (invalidateTaskIfNeeded(task)) {
            if (state.tasks.length) schedule(0);
            else maybeStopHeartbeat();
            return;
        }
        const pauseReasons = getDynamicPauseReasons(task);
        if (pauseReasons.length) {
            const warmupReason = pauseReasons.find(reason => String(reason).startsWith('warmup:'));
            if (warmupReason) {
                const parts = String(warmupReason).split(':');
                const remaining = Number(parts[2] || 0);
                schedule(Math.max(250, Math.min(remaining || heartbeatMs, heartbeatMs)));
            }
            return;
        }

        state.running = true;
        state.activeTaskId = task.id;

        try {
            const result = await task.runChunk({
                deadline,
                didTimeout: !!deadline?.didTimeout,
                loadLevel: getLoadLevel(),
                timeRemaining() {
                    if (deadline && typeof deadline.timeRemaining === 'function') {
                        return deadline.timeRemaining();
                    }
                    return 0;
                },
                yield(delay = 0) {
                    return new Promise(resolve => window.setTimeout(resolve, Math.max(0, Number(delay || 0))));
                },
                getStatus
            });

            if (task.cancelled || invalidateTaskIfNeeded(task)) {
                removeTaskById(task.id);
            } else if (result?.done === true || result?.status === 'completed') {
                removeTaskById(task.id);
                if (typeof task.onComplete === 'function') {
                    await task.onComplete(task, result);
                }
            } else if (typeof task.onProgress === 'function' && Object.prototype.hasOwnProperty.call(result || {}, 'progress')) {
                task.onProgress(result.progress, task, result);
            }
        } catch (error) {
            removeTaskById(task.id);
            if (typeof task.onError === 'function') {
                task.onError(error, task);
            } else {
                console.warn(`Idle task "${task?.label || task?.id || 'unknown'}" failed:`, error);
            }
        } finally {
            state.running = false;
            state.activeTaskId = null;
        }

        if (state.tasks.length) {
            schedule(getChunkDelayMs());
        } else {
            maybeStopHeartbeat();
        }
    }

    function enqueue(taskInput) {
        if (!taskInput?.id) {
            throw new Error('Idle task must include an id.');
        }
        if (typeof taskInput.runChunk !== 'function') {
            throw new Error(`Idle task "${taskInput.id}" must include runChunk().`);
        }

        const normalizedTask = {
            label: String(taskInput.label || taskInput.id),
            priority: normalizePriority(taskInput.priority, 99),
            projectId: taskInput.projectId == null ? null : taskInput.projectId,
            type: String(taskInput.type || 'generic'),
            cancelled: false,
            enqueuedAt: Date.now(),
            order: ++state.order,
            ...taskInput
        };

        const existing = state.tasks.find(task => task.id === normalizedTask.id);
        if (existing) {
            const preservedOrder = existing.order;
            const preservedEnqueuedAt = existing.enqueuedAt;
            Object.assign(existing, normalizedTask, {
                cancelled: false,
                order: preservedOrder,
                enqueuedAt: preservedEnqueuedAt
            });
        } else {
            state.tasks.push(normalizedTask);
        }

        state.tasks.sort(compareTasks);
        ensureHeartbeat();
        schedule(0);
        return normalizedTask.id;
    }

    function pause(reason = 'manual') {
        state.manualPauseReasons.add(String(reason || 'manual'));
        clearScheduledHandle();
        ensureHeartbeat();
    }

    function resume(reason = 'manual') {
        state.manualPauseReasons.delete(String(reason || 'manual'));
        if (state.tasks.length) {
            schedule(0);
        } else {
            maybeStopHeartbeat();
        }
    }

    function cancel(taskId) {
        const task = state.tasks.find(item => item.id === taskId);
        if (!task) return false;
        task.cancelled = true;
        if (state.activeTaskId !== taskId) {
            removeTaskById(taskId);
        }
        if (state.tasks.length) {
            schedule(0);
        } else {
            maybeStopHeartbeat();
        }
        return true;
    }

    function clearProjectTasks(projectId) {
        if (projectId == null) return;
        const key = String(projectId);
        state.tasks.forEach(task => {
            if (String(task?.projectId ?? '') === key) {
                task.cancelled = true;
            }
        });
        state.tasks = state.tasks.filter(task => !(task.cancelled && task.id !== state.activeTaskId));
        state.projectWarmups.delete(key);
        if (state.tasks.length) {
            schedule(0);
        } else {
            maybeStopHeartbeat();
        }
    }

    function setProjectWarmup(projectId, durationMs = 0) {
        if (projectId == null) return;
        const normalizedDuration = Math.max(0, Number(durationMs || 0));
        const key = String(projectId);
        if (!normalizedDuration) {
            state.projectWarmups.delete(key);
            return;
        }
        state.projectWarmups.set(key, Date.now() + normalizedDuration);
        ensureHeartbeat();
    }

    function kick() {
        if (state.tasks.length) {
            schedule(0);
        }
    }

    function getStatus() {
        const nextTask = pickNextTask();
        const pauseReasons = getDynamicPauseReasons(nextTask);
        return {
            activeTaskId: state.activeTaskId,
            queueLength: state.tasks.filter(task => !task.cancelled).length,
            paused: pauseReasons.length > 0,
            pauseReasons,
            loadLevel: getLoadLevel(),
            usingRequestIdleCallback: hasIdleCallback(),
            tasks: state.tasks
                .filter(task => !task.cancelled)
                .sort(compareTasks)
                .map(task => ({
                    id: task.id,
                    projectId: task.projectId,
                    type: task.type,
                    priority: task.priority,
                    label: task.label,
                    active: task.id === state.activeTaskId,
                    warmupRemainingMs: getWarmupRemaining(task.projectId)
                }))
        };
    }

    return {
        enqueue,
        pause,
        resume,
        cancel,
        clearProjectTasks,
        getStatus,
        setProjectWarmup,
        kick
    };
}
