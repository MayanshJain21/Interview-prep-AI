/* eslint-disable react-refresh/only-export-components -- shared styles and small components live together */
import React from 'react';

export const card = 'bg-surface-container-lowest rounded-2xl border border-outline-variant';
export const primaryBtn = 'bg-primary text-on-primary rounded-lg font-semibold transition-colors hover:bg-on-primary-fixed-variant disabled:opacity-50 disabled:cursor-not-allowed';
export const secondaryBtn = 'bg-primary text-on-primary border border-primary rounded-lg font-semibold disabled:opacity-50';
export const inputCls = 'w-full px-3.5 py-2.5 bg-surface-container-lowest rounded-lg border border-outline-variant focus:border-primary focus:ring-1 focus:ring-primary text-on-surface placeholder:text-outline';

export function scoreTone(score) {
    if (score === null || score === undefined) return { ring: 'stroke-outline-variant', text: 'text-on-surface-variant', bg: 'bg-surface-container-high' };
    if (score >= 75) return { ring: 'stroke-green-600', text: 'text-green-700', bg: 'bg-green-50' };
    if (score >= 55) return { ring: 'stroke-amber-500', text: 'text-amber-700', bg: 'bg-amber-50' };
    return { ring: 'stroke-red-500', text: 'text-red-700', bg: 'bg-red-50' };
}

// Circular score out of 100.
export function ScoreRing({ score, size = 120, label }) {
    const r = 52;
    const c = 2 * Math.PI * r;
    const value = Math.max(0, Math.min(100, score ?? 0));
    const tone = scoreTone(score);
    return (
        <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}
             role="img" aria-label={`${label || 'Score'}: ${Math.round(value)} out of 100`}>
            <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
                <circle cx="60" cy="60" r={r} fill="none" className="stroke-surface-container-high" strokeWidth="10" />
                <circle cx="60" cy="60" r={r} fill="none" className={tone.ring} strokeWidth="10" strokeLinecap="round"
                        strokeDasharray={c} strokeDashoffset={c * (1 - value / 100)} />
            </svg>
            <div className="absolute flex flex-col items-center">
                <span className={`font-semibold text-2xl leading-none ${tone.text}`}>{Math.round(value)}</span>
                <span className="text-[10px] font-bold text-on-surface-variant mt-0.5">/ 100</span>
            </div>
        </div>
    );
}

export function Bar({ value, max = 100, tone = 'bg-primary', label }) {
    const pct = value === null || value === undefined ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
    return (
        <div className="h-2 w-full bg-surface-container-high rounded-full overflow-hidden" role="progressbar"
             aria-valuenow={value ?? 0} aria-valuemin={0} aria-valuemax={max} aria-label={label}>
            <div className={`h-full rounded-full ${tone} transition-all duration-500`} style={{ width: `${pct}%` }} />
        </div>
    );
}

const BADGE = {
    matched: 'bg-green-50 text-green-800 border-green-200',
    partial: 'bg-amber-50 text-amber-800 border-amber-200',
    missing: 'bg-red-50 text-red-800 border-red-200',
    required: 'bg-primary-fixed/50 text-primary border-primary/20',
    preferred: 'bg-surface-container-high text-on-surface-variant border-outline-variant',
    completed: 'bg-green-50 text-green-800 border-green-200',
    skipped: 'bg-surface-container-high text-on-surface-variant border-outline-variant',
    pending: 'bg-primary-fixed/40 text-primary border-primary/20',
    in_progress: 'bg-amber-50 text-amber-800 border-amber-200',
    unassessed: 'bg-surface-container-high text-on-surface-variant border-outline-variant',
    weak: 'bg-red-50 text-red-800 border-red-200',
    developing: 'bg-amber-50 text-amber-800 border-amber-200',
    strong: 'bg-green-50 text-green-800 border-green-200',
    mastered: 'bg-green-100 text-green-900 border-green-300',
};

export function Badge({ kind, children }) {
    return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold border capitalize ${BADGE[kind] || BADGE.preferred}`}>{children || kind?.replace('_', ' ')}</span>;
}

export function ErrorBanner({ message, onRetry }) {
    if (!message) return null;
    return (
        <div role="alert" className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-5 py-3 text-sm flex items-center gap-3">
            <span className="material-symbols-outlined text-lg">error</span>
            <span className="flex-1">{message}</span>
            {onRetry && <button onClick={onRetry} className="font-bold underline">Try again</button>}
        </div>
    );
}

export function Loading({ title, detail }) {
    return (
        <div className={`${card} flex flex-col items-center justify-center gap-3 py-16 px-6 text-center`} aria-live="polite">
            <span className="material-symbols-outlined text-primary text-3xl animate-spin">sync</span>
            <p className="font-headline font-bold text-on-surface">{title}</p>
            {detail && <p className="text-sm text-on-surface-variant max-w-md">{detail}</p>}
        </div>
    );
}

export function EmptyState({ icon, title, detail, action }) {
    return (
        <div className={`${card} flex flex-col items-center justify-center text-center py-12 px-6 gap-2`}>
            <span className="material-symbols-outlined text-4xl text-outline">{icon}</span>
            <p className="font-headline font-bold text-on-surface">{title}</p>
            {detail && <p className="text-sm text-on-surface-variant max-w-md">{detail}</p>}
            {action}
        </div>
    );
}

export function PageHeader({ title, subtitle, action }) {
    return (
        <header className="flex flex-wrap items-end justify-between gap-4 mb-8">
            <div>
                <h1 className="text-3xl sm:text-[2.5rem] leading-tight font-semibold text-on-surface font-headline">{title}</h1>
                {subtitle && <p className="text-on-surface-variant mt-2 max-w-2xl">{subtitle}</p>}
            </div>
            {action}
        </header>
    );
}

export const formatDate = (d) => (d ? new Date(d).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '');
