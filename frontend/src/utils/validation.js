// Client-side checks that mirror the backend validation (the backend stays the source of truth).

export function validateJobForm({ title, text }, file) {
    if (!title.trim()) return 'Enter the job title.';
    if (!file && text.trim().length < 80) return 'Paste the full job description (at least a few sentences), or upload a PDF.';
    if (file && !file.name.toLowerCase().endsWith('.pdf')) return 'Only PDF files are supported.';
    if (file && file.size > 2 * 1024 * 1024) return 'The PDF is too large (max 2 MB).';
    return '';
}

export function validateRoadmapForm({ deadline, minutes_per_day, study_days }, today = new Date()) {
    if (!deadline) return 'Pick a target date.';
    const d = new Date(`${deadline}T00:00:00`);
    const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    if (!(d > start)) return 'The target date must be after today.';
    if (!(minutes_per_day >= 15 && minutes_per_day <= 600)) return 'Study time must be between 15 and 600 minutes a day.';
    if (!study_days.length) return 'Choose at least one study day.';
    return '';
}

export function validateAnswer(text) {
    if (!text.trim()) return 'Write or speak an answer first.';
    if (text.length > 6000) return 'That answer is too long (6000 characters max).';
    return '';
}

// Groups roadmap items by week number, keeping date order.
export function groupByWeek(items) {
    const weeks = new Map();
    for (const item of items) {
        if (!weeks.has(item.week)) weeks.set(item.week, []);
        weeks.get(item.week).push(item);
    }
    return [...weeks.entries()].sort((a, b) => a[0] - b[0]).map(([week, list]) => ({ week, items: list }));
}

// Today (or today + n days) as YYYY-MM-DD in the user's local time zone (toISOString would use UTC).
export function localISODate(offsetDays = 0, base = new Date()) {
    const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() + offsetDays);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
