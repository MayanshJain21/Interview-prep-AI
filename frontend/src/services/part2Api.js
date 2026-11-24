// API helpers for the job analyzer, learning engine and technical interview.
// All calls go through the existing apiCall (adds the JWT, normalises errors).
import { apiCall } from '../api';

export const jobsApi = {
    create: (fields, file) => {
        if (file) {
            const form = new FormData();
            Object.entries(fields).forEach(([k, v]) => form.append(k, v ?? ''));
            form.append('file', file);
            return apiCall('/jobs/create', 'POST', form);
        }
        return apiCall('/jobs/create', 'POST', fields);
    },
    analyze: (jobId) => apiCall('/jobs/analyze', 'POST', { job_id: jobId }),
    history: (page = 1) => apiCall(`/jobs/history/?page=${page}`),
    job: (id) => apiCall(`/jobs/${id}`),
    analysis: (id) => apiCall(`/jobs/analysis/${id}`),
    remove: (id) => apiCall(`/jobs/${id}`, 'DELETE'),
};

export const engineApi = {
    analytics: () => apiCall('/engine/analytics'),
    profile: () => apiCall('/engine/profile'),
    recommendations: (limit = 3) => apiCall(`/engine/recommendations/?limit=${limit}`),
    roadmap: () => apiCall('/engine/roadmap'),
    generate: (body) => apiCall('/engine/roadmap/generate', 'POST', body),
    setStatus: (itemId, status) => apiCall('/engine/roadmap/complete', 'POST', { item_id: itemId, status }),
    reschedule: (itemId, date) => apiCall('/engine/roadmap/reschedule', 'POST', { item_id: itemId, date }),
    notes: (skill) => apiCall('/engine/notes', 'POST', { skill }),
};

export const technicalApi = {
    start: (body) => apiCall('/technical/session/start', 'POST', body),
    answer: (sessionId, answer) => apiCall('/technical/session/answer', 'POST', { session_id: sessionId, answer }),
    next: (sessionId) => apiCall('/technical/session/continue', 'POST', { session_id: sessionId }),
    end: (sessionId) => apiCall('/technical/session/end', 'POST', { session_id: sessionId }),
    session: (id) => apiCall(`/technical/session/${id}`),
    history: (page = 1) => apiCall(`/technical/history/?page=${page}`),
};

// Turns a roadmap/recommendation link {path, params} into a URL.
export const linkTo = (link) => {
    if (!link?.path) return null;
    const qs = new URLSearchParams(Object.entries(link.params || {}).filter(([, v]) => v)).toString();
    return qs ? `${link.path}?${qs}` : link.path;
};
