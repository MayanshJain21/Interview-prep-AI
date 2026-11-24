import React, { useState } from 'react';
import { Link } from 'react-router-dom';

const MODULES = [
    { key: 'mcq', label: 'MCQ tests', to: '/mcq' },
    { key: 'coding', label: 'Coding rounds', to: '/coding-round' },
    { key: 'technical', label: 'Technical interviews', to: '/technical-interview' },
    { key: 'hr', label: 'HR interviews', to: '/hr-interview' },
];

const shortDate = (d) => new Date(d).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });

// Score per session, 0-100 on a fixed scale so the four modules can be compared side by side.
function Trend({ label, to, points }) {
    const [hover, setHover] = useState(null);
    const W = 240, H = 64, PAD = 6;
    const last = points[points.length - 1];
    const prev = points[points.length - 2];
    const delta = last && prev ? last.score - prev.score : null;
    const x = (i) => (points.length === 1 ? W / 2 : PAD + (i * (W - 2 * PAD)) / (points.length - 1));
    const y = (s) => H - PAD - (s / 100) * (H - 2 * PAD);
    const shown = hover !== null ? points[hover] : last;

    return (
        <Link to={to} className="block rounded-xl border border-outline-variant bg-surface-container-lowest p-4">
            <div className="flex items-baseline justify-between gap-2">
                <p className="text-[13px] text-on-surface-variant">{label}</p>
                {points.length > 0 && <p className="text-xs text-outline">{points.length} {points.length === 1 ? 'session' : 'sessions'}</p>}
            </div>
            {points.length === 0 ? (
                <p className="mt-3 text-sm text-on-surface-variant">No sessions yet</p>
            ) : (
                <>
                    <p className="mt-1 text-2xl font-semibold text-on-surface leading-none">
                        {shown.score}<span className="text-sm font-normal text-on-surface-variant"> / 100</span>
                        {hover === null && delta !== null && delta !== 0 && (
                            <span className={`ml-2 text-xs font-semibold ${delta > 0 ? 'text-green-700' : 'text-red-700'}`}>
                                {delta > 0 ? '+' : ''}{delta} vs last
                            </span>
                        )}
                        {hover !== null && <span className="ml-2 text-xs font-normal text-on-surface-variant">{shortDate(shown.date)}</span>}
                    </p>
                    <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full h-16 overflow-visible" role="img"
                        aria-label={`${label}: ${points.map((p) => p.score).join(', ')} out of 100, oldest to newest`}
                        onMouseLeave={() => setHover(null)}>
                        <line x1={0} x2={W} y1={y(50)} y2={y(50)} className="stroke-outline-variant" strokeDasharray="3 4" strokeWidth="1" />
                        {points.length > 1 && (
                            <polyline fill="none" className="stroke-primary" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"
                                points={points.map((p, i) => `${x(i)},${y(p.score)}`).join(' ')} />
                        )}
                        {points.map((p, i) => (
                            <g key={i} onMouseEnter={() => setHover(i)}>
                                <circle cx={x(i)} cy={y(p.score)} r="12" fill="transparent" />
                                <circle cx={x(i)} cy={y(p.score)} r={hover === i || (hover === null && i === points.length - 1) ? 4.5 : 3}
                                    className={hover === i || (hover === null && i === points.length - 1) ? 'fill-accent stroke-surface-container-lowest' : 'fill-primary stroke-surface-container-lowest'}
                                    strokeWidth="2" />
                            </g>
                        ))}
                    </svg>
                </>
            )}
        </Link>
    );
}

// Mastery of the skills that matter most for the target role.
function Mastery({ rows }) {
    const top = rows.slice(0, 6);
    return (
        <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5 h-full">
            <div className="flex items-baseline justify-between mb-4">
                <h3 className="text-[15px] font-semibold text-on-surface">Skill mastery</h3>
                <Link to="/learning-path" className="text-[13px] font-semibold text-primary hover:underline">All skills</Link>
            </div>
            {top.length === 0 ? (
                <p className="text-sm text-on-surface-variant">Take an MCQ test or a coding round to see your skills here.</p>
            ) : (
                <ul className="space-y-3">
                    {top.map((r, i) => (
                        <li key={r.slug} title={r.mastery === null ? `${r.name}: not assessed yet` : `${r.name}: ${Math.round(r.mastery)}% mastery`}>
                            <div className="flex justify-between text-[13px]">
                                <span className="text-on-surface truncate pr-3">{r.name}</span>
                                <span className={r.mastery === null ? 'text-outline' : 'font-semibold text-on-surface'}>
                                    {r.mastery === null ? 'not yet' : `${Math.round(r.mastery)}%`}
                                </span>
                            </div>
                            <div className="mt-1 h-1.5 rounded-full bg-surface-container-high overflow-hidden">
                                {r.mastery !== null && (
                                    <div className="grow-x h-full rounded-full bg-primary" style={{ width: `${Math.max(r.mastery, 2)}%`, animationDelay: `${i * 40}ms` }} />
                                )}
                            </div>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}

// Sessions per week for the last 8 weeks (weeks start on Monday). This week is highlighted.
function Activity({ timeline }) {
    const monday = (d) => {
        const x = new Date(d);
        x.setHours(0, 0, 0, 0);
        x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
        return x.getTime();
    };
    const thisWeek = monday(new Date());
    const weeks = Array.from({ length: 8 }, (_, i) => thisWeek - (7 - i) * 7 * 86400000);
    const counts = weeks.map((w) => timeline.filter((p) => monday(p.date) === w).length);
    const max = Math.max(...counts, 1);
    const total = counts.reduce((a, b) => a + b, 0);

    return (
        <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5 h-full flex flex-col">
            <div className="flex items-baseline justify-between mb-4">
                <h3 className="text-[15px] font-semibold text-on-surface">Weekly activity</h3>
                <p className="text-[13px] text-on-surface-variant">{total} {total === 1 ? 'session' : 'sessions'} in 8 weeks</p>
            </div>
            <div className="flex items-end gap-2 h-44 mt-auto" role="img"
                aria-label={`Sessions per week, oldest to newest: ${counts.join(', ')}`}>
                {counts.map((c, i) => {
                    const current = i === counts.length - 1;
                    return (
                        <div key={weeks[i]} className="flex-1 flex flex-col items-center justify-end h-full group"
                            title={`${current ? 'This week' : `Week of ${shortDate(weeks[i])}`}: ${c} ${c === 1 ? 'session' : 'sessions'}`}>
                            <span className="text-[11px] text-on-surface-variant mb-1 opacity-0 group-hover:opacity-100 transition-opacity">{c}</span>
                            <div className={`grow-y w-full max-w-8 rounded-t-[4px] ${c === 0 ? 'bg-surface-container-high' : current ? 'bg-accent' : 'bg-primary'}`}
                                style={{ height: c === 0 ? '3px' : `${(c / max) * 100}%`, animationDelay: `${i * 40}ms` }} />
                        </div>
                    );
                })}
            </div>
            <div className="flex gap-2 mt-2">
                {weeks.map((w, i) => (
                    <span key={w} className={`flex-1 text-center text-[11px] ${i === weeks.length - 1 ? 'text-on-accent font-semibold' : 'text-outline'}`}>
                        {i === weeks.length - 1 ? 'This week' : i % 2 === 1 ? shortDate(w) : ''}
                    </span>
                ))}
            </div>
        </div>
    );
}

export default function Analytics({ timeline = [], mastery = [], children }) {
    const byModule = Object.fromEntries(MODULES.map((m) => [m.key, timeline.filter((p) => p.module === m.key).slice(-10)]));
    return (
        <section className="mt-10" aria-labelledby="analytics-title">
            <h2 id="analytics-title" className="text-xl font-semibold text-on-surface">Your progress</h2>
            {children && <div className="mt-6 mb-8">{children}</div>}
            <p className="text-sm text-on-surface-variant mt-1">Scores from your last 10 sessions in each module, all out of 100.</p>
            <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {MODULES.map((m) => <Trend key={m.key} label={m.label} to={m.to} points={byModule[m.key]} />)}
            </div>
            <div className="mt-4 grid grid-cols-1 lg:grid-cols-12 gap-4">
                <div className="lg:col-span-7"><Activity timeline={timeline} /></div>
                <div className="lg:col-span-5"><Mastery rows={mastery} /></div>
            </div>
        </section>
    );
}
