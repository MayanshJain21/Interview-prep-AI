import React, { useState } from 'react';
import { apiCall } from '../api';
import { ErrorBanner } from '../components/shared/ui';
import Select from '../components/shared/Select';

const MAX_TIPS = 5;
const OTHER = 'Other';
// Keys match ATS_LEVELS in ai_features/views.py.
const LEVELS = [
    { value: 'student', label: 'Student / intern', hint: 'still studying' },
    { value: 'fresher', label: 'Fresher', hint: '0-1 yr' },
    { value: 'junior', label: 'Junior developer', hint: '1-3 yrs' },
    { value: 'mid', label: 'Mid-level developer', hint: '3-5 yrs' },
    { value: 'senior', label: 'Senior developer', hint: '5-8 yrs' },
    { value: 'lead', label: 'Lead / Staff', hint: '8+ yrs' },
];
const ROLES = ['Software Engineer', 'Full-Stack Developer', 'Frontend Developer', 'Backend Developer', 'AI / ML Engineer',
    'Data Scientist', 'Data Analyst', 'DevOps Engineer', 'Mobile Developer', 'QA / Test Engineer', OTHER];

// Match the weights the backend scores with (ai_features/views.py).
const CRITERIA = [
    { key: 'impact', label: 'Measurable impact', weight: 30 },
    { key: 'keywords', label: 'Keywords', weight: 20 },
    { key: 'experience', label: 'Experience', weight: 20 },
    { key: 'structure', label: 'Structure', weight: 15 },
    { key: 'education_projects', label: 'Education and projects', weight: 15 },
];
const FIT = [
    { key: 'skills_match', label: 'Skills match', weight: 35 },
    { key: 'projects_relevance', label: 'Projects', weight: 30 },
    { key: 'experience_relevance', label: 'Experience', weight: 20 },
    { key: 'level_fit', label: 'Level for your stage', weight: 15 },
];

const VERDICT_STYLE = {
    keep: 'bg-green-50 text-green-800 border-green-200',
    fix: 'bg-amber-50 text-amber-800 border-amber-200',
    cut: 'bg-red-50 text-red-800 border-red-200',
};

const read = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const write = (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage blocked */ } };

function band(score) {
    if (score >= 75) return { text: 'Strong', tone: 'text-green-700' };
    if (score >= 55) return { text: 'Good, with a few fixes', tone: 'text-amber-700' };
    return { text: 'Needs work before applying', tone: 'text-red-700' };
}

function ScorePanel({ title, score, rows, values }) {
    const b = band(score);
    return (
        <section className="h-full bg-surface-container-lowest rounded-xl border border-outline-variant p-5">
            <p className="text-sm text-on-surface-variant">{title}</p>
            <p className="mt-1 text-4xl font-semibold tracking-tight text-on-surface">
                {score}<span className="text-lg font-normal text-on-surface-variant"> / 100</span>
            </p>
            <p className={`mt-0.5 text-sm font-semibold ${b.tone}`}>{b.text}</p>
            <dl className="mt-4 pt-3 border-t border-outline-variant space-y-2">
                {rows.map((c) => {
                    const v = values?.[c.key] ?? 0;
                    return (
                        <div key={c.key}>
                            <div className="flex justify-between text-[13px]">
                                <dt className="text-on-surface">{c.label} <span className="text-outline">({c.weight}%)</span></dt>
                                <dd className="font-semibold text-on-surface">{v}/10</dd>
                            </div>
                            <div className="mt-1 h-1.5 rounded-full bg-surface-container-high overflow-hidden">
                                <div className="grow-x h-full bg-primary rounded-full" style={{ width: `${v * 10}%` }} />
                            </div>
                        </div>
                    );
                })}
            </dl>
        </section>
    );
}

export default function AtsCheck() {
    const savedRole = read('ats:role', ROLES[0]);
    const [role, setRole] = useState(ROLES.includes(savedRole) ? savedRole : OTHER);
    const [customRole, setCustomRole] = useState(ROLES.includes(savedRole) ? read('ats:customRole', '') : savedRole);
    const savedLevel = read('ats:level', 'student');
    const [level, setLevel] = useState(LEVELS.some((l) => l.value === savedLevel) ? savedLevel : 'student');
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState('');

    const targetRole = role === OTHER ? customRole.trim() : role;
    const missingRole = role === OTHER && !targetRole;

    const runAnalysis = async () => {
        if (missingRole) { setError('Type the role you are targeting.'); return; }
        setIsLoading(true);
        setError('');
        write('ats:role', targetRole);
        write('ats:level', level);
        try {
            setResult(await apiCall('/ats/check', 'POST', { role: targetRole, level }));
        } catch (err) {
            setError(err.message || 'The ATS check failed. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    const chooseRole = (value) => {
        setRole(value);
        setError('');
    };
    const typeRole = (value) => {
        setCustomRole(value);
        write('ats:customRole', value);
    };

    const tips = (result?.tips || []).slice(0, MAX_TIPS);
    const review = result?.review || [];

    return (
        <main className="pt-20 pb-10 px-4 sm:px-6 max-w-[75rem] mx-auto">
            <header className="flex flex-wrap items-end justify-between gap-4 mb-6">
                <div>
                    <h1 className="text-3xl leading-tight font-semibold text-on-surface">ATS check</h1>
                    <p className="text-on-surface-variant mt-1">An honest review of your resume for the role you are targeting, with an ATS score and a role fit score.</p>
                </div>
            </header>

            <form onSubmit={(e) => { e.preventDefault(); runAnalysis(); }}
                className="flex flex-wrap items-end justify-center gap-x-5 gap-y-3 px-4 py-5 mb-5 bg-surface-container-lowest rounded-xl border border-outline-variant">
                <div className="text-xs text-on-surface-variant">
                    <span aria-hidden="true">Target role</span>
                    <Select value={role} options={ROLES} onChange={chooseRole} disabled={isLoading} label="Target role"
                        className="mt-1.5 w-60" buttonClassName="h-11" />
                </div>
                <div className="text-xs text-on-surface-variant">
                    <span aria-hidden="true">Experience level</span>
                    <Select value={level} options={LEVELS} onChange={setLevel} disabled={isLoading} label="Experience level"
                        className="mt-1.5 w-64" buttonClassName="h-11" />
                </div>
                {role === OTHER && (
                    <label className="text-xs text-on-surface-variant">Your role
                        <input value={customRole} onChange={(e) => typeRole(e.target.value)} disabled={isLoading}
                            placeholder="e.g. Cloud Engineer" maxLength={80} required autoFocus aria-invalid={missingRole}
                            className={`mt-1.5 block w-60 h-11 px-3 rounded-lg border bg-surface-container-lowest text-sm text-on-surface focus:ring-1 focus:ring-primary ${missingRole ? 'border-error focus:border-error' : 'border-outline-variant focus:border-primary'}`} />
                    </label>
                )}
                <button type="submit" disabled={isLoading || missingRole}
                    className="h-11 px-6 rounded-lg bg-primary text-on-primary border border-primary text-sm font-semibold disabled:opacity-50">
                    {isLoading ? 'Checking...' : result ? 'Check again' : 'Check my resume'}
                </button>
                {missingRole && <p className="w-full text-center text-xs text-error">Type the role you are targeting to run the check.</p>}
            </form>

            {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

            {!result && !isLoading && (
                <p className="text-center text-on-surface-variant">Pick your target role and experience level, then run the check. It takes about 15 seconds.</p>
            )}

            {isLoading && (
                <div className="flex items-center gap-3 p-5 bg-surface-container-lowest rounded-xl border border-outline-variant" role="status">
                    <span className="material-symbols-outlined text-primary animate-spin">progress_activity</span>
                    <p className="text-on-surface-variant">Reviewing your resume line by line for {targetRole}...</p>
                </div>
            )}

            {result && !isLoading && (
                <>
                    {result.verdict && (
                        <p className="mb-4 text-[15px] text-on-surface">
                            <span className="mr-2 px-2 py-0.5 rounded-md text-xs font-semibold bg-accent-soft text-on-accent">{result.role}</span>
                            {result.verdict}
                        </p>
                    )}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-4 items-stretch">
                        <div className="lg:col-span-3 h-full"><ScorePanel title="ATS score" score={result.score} rows={CRITERIA} values={result.criteria} /></div>
                        <div className="lg:col-span-3 h-full"><ScorePanel title={`Fit for ${result.role}`} score={result.role_fit?.score ?? 0} rows={FIT} values={result.role_fit?.components} /></div>
                        <section className="md:col-span-2 lg:col-span-6 bg-surface-container-lowest rounded-xl border border-outline-variant p-5">
                            <h2 className="text-base font-semibold text-on-surface">What to fix first</h2>
                            <ol className="mt-2 divide-y divide-outline-variant">
                                {tips.map((tip, i) => (
                                    <li key={i} className="flex gap-3 py-2.5 last:pb-0">
                                        <span className="w-5 shrink-0 text-sm font-semibold text-primary">{i + 1}</span>
                                        <p className="text-[14px] leading-snug text-on-surface">{tip}</p>
                                    </li>
                                ))}
                            </ol>
                        </section>
                    </div>

                    {review.length > 0 && (
                        <details className="mt-4 bg-surface-container-lowest rounded-xl border border-outline-variant group">
                            <summary className="cursor-pointer list-none px-5 py-3.5 flex items-center justify-between text-sm font-semibold text-on-surface">
                                Line-by-line review ({review.length})
                                <span className="material-symbols-outlined text-base transition-transform group-open:rotate-180">expand_more</span>
                            </summary>
                            <ul className="px-5 pb-4 divide-y divide-outline-variant">
                                {review.map((r, i) => (
                                    <li key={i} className="py-3 flex gap-3">
                                        <span className={`shrink-0 h-fit px-2 py-0.5 rounded border text-[11px] font-semibold capitalize ${VERDICT_STYLE[r.verdict]}`}>{r.verdict}</span>
                                        <div className="min-w-0">
                                            <p className="text-[13px] text-on-surface-variant italic">"{r.quote}"</p>
                                            <p className="text-[14px] text-on-surface mt-0.5">{r.comment}</p>
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        </details>
                    )}
                </>
            )}
        </main>
    );
}
