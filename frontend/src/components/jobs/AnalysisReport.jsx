import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Bar, card, formatDate, primaryBtn, ScoreRing, secondaryBtn } from '../shared/ui';

const STATUS_ORDER = { missing: 0, partial: 1, matched: 2 };

function Evidence({ match }) {
    if (match.evidence) {
        return <span className="text-on-surface-variant"><span className="font-semibold capitalize">{match.evidence.section}:</span> "{match.evidence.snippet}"</span>;
    }
    if (match.related_evidence) {
        return <span className="text-on-surface-variant">Related: <span className="font-semibold">{match.related_evidence.via}</span> in {match.related_evidence.section}</span>;
    }
    return <span className="text-on-surface-variant italic">Not found on the resume</span>;
}

export default function AnalysisReport({ job, analysis }) {
    const [filter, setFilter] = useState('all');
    const matches = [...analysis.skill_matches].sort((a, b) =>
        (a.importance !== b.importance ? (a.importance === 'required' ? -1 : 1) : 0) || STATUS_ORDER[a.status] - STATUS_ORDER[b.status]);
    const shown = filter === 'all' ? matches : matches.filter((m) => m.status === filter);
    const counts = matches.reduce((acc, m) => ({ ...acc, [m.status]: (acc[m.status] || 0) + 1 }), {});
    const req = job.requirements_summary || {};
    const b = analysis.breakdown;

    return (
        <div className="flex flex-col gap-6">
            {/* Score summary */}
            <section className={`${card} p-6 sm:p-8 flex flex-col lg:flex-row gap-8`}>
                <div className="flex items-center gap-6">
                    <ScoreRing score={analysis.overall_score} size={132} label="Overall compatibility" />
                    <div>
                        <p className="text-xs font-bold text-primary">Resume–job compatibility</p>
                        <h2 className="font-headline text-2xl font-semibold text-on-surface">{job.title}</h2>
                        <p className="text-sm text-on-surface-variant">{job.company || 'Company not given'} · analysed {formatDate(analysis.created_at)}</p>
                        <p className="text-sm text-on-surface mt-2">Technical skills match: <span className="font-bold">{Math.round(analysis.technical_score)}%</span></p>
                    </div>
                </div>
                <div className="flex-1 flex flex-col gap-3 justify-center">
                    {b.components.map((c) => (
                        <div key={c.key}>
                            <div className="flex justify-between text-sm mb-1">
                                <span className="font-bold text-on-surface">{c.label}
                                    <span className="font-normal text-on-surface-variant"> · weight {c.available ? `${Math.round(c.normalized_weight * 100)}%` : 'not used'}</span></span>
                                <span className="text-on-surface-variant">{c.available ? `${c.score}% → +${c.contribution}` : 'no data'}</span>
                            </div>
                            <Bar value={c.score} label={c.label} tone={c.available ? 'bg-primary' : 'bg-outline-variant'} />
                            <p className="text-xs text-on-surface-variant mt-1">{c.detail}</p>
                        </div>
                    ))}
                    <p className="text-xs text-on-surface-variant border-t border-outline-variant pt-3">{b.formula} {b.note}</p>
                </div>
            </section>

            {/* Skill comparison */}
            <section className={`${card} p-6`}>
                <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                    <h3 className="font-headline text-lg font-bold text-on-surface">Skill comparison</h3>
                    <div className="flex gap-1" role="tablist">
                        {['all', 'matched', 'partial', 'missing'].map((f) => (
                            <button key={f} role="tab" aria-selected={filter === f} onClick={() => setFilter(f)}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-bold capitalize ${filter === f ? 'bg-primary-fixed text-primary' : 'text-on-surface-variant hover:bg-surface-container-low'}`}>
                                {f}{f !== 'all' && ` (${counts[f] || 0})`}
                            </button>
                        ))}
                    </div>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-left text-xs text-on-surface-variant border-b border-outline-variant">
                                <th className="py-2 pr-4">Skill</th><th className="py-2 pr-4">Job requirement</th>
                                <th className="py-2 pr-4">Resume status</th><th className="py-2">Evidence</th>
                            </tr>
                        </thead>
                        <tbody>
                            {shown.map((m, i) => (
                                <tr key={i} className="border-b border-outline-variant align-top">
                                    <td className="py-3 pr-4 font-bold text-on-surface">{m.skill}
                                        {m.requirement !== m.skill && <span className="block text-xs font-normal text-on-surface-variant">as "{m.requirement}"</span>}</td>
                                    <td className="py-3 pr-4"><Badge kind={m.importance} /></td>
                                    <td className="py-3 pr-4"><Badge kind={m.status}>{m.status === 'partial' ? 'Partially matched' : m.status}</Badge></td>
                                    <td className="py-3 text-xs max-w-md"><Evidence match={m} /></td>
                                </tr>
                            ))}
                            {shown.length === 0 && <tr><td colSpan={4} className="py-6 text-center text-on-surface-variant">Nothing in this group.</td></tr>}
                        </tbody>
                    </table>
                </div>
            </section>

            <div className="grid lg:grid-cols-2 gap-6">
                <section className={`${card} p-6 flex flex-col gap-3`}>
                    <h3 className="font-headline text-lg font-bold text-on-surface">Resume improvements</h3>
                    {analysis.recommendations.length === 0 && <p className="text-sm text-on-surface-variant">Your resume covers every listed skill.</p>}
                    <ul className="flex flex-col gap-2">
                        {analysis.recommendations.map((r, i) => (
                            <li key={i} className="text-sm text-on-surface flex gap-2">
                                <span className="material-symbols-outlined text-base text-primary mt-0.5">{r.source === 'ai' ? 'auto_awesome' : 'check_circle'}</span>
                                <span>{r.text}</span>
                            </li>
                        ))}
                    </ul>
                    {analysis.relevant_sections.length > 0 && (
                        <p className="text-xs text-on-surface-variant mt-2">Evidence came from: {analysis.relevant_sections.map((s) => `${s.section} (${s.matches})`).join(', ')}</p>
                    )}
                </section>

                <section className={`${card} p-6 flex flex-col gap-3`}>
                    <h3 className="font-headline text-lg font-bold text-on-surface">Suggested areas of preparation</h3>
                    {analysis.preparation_areas.length === 0 ? <p className="text-sm text-on-surface-variant">No gaps found.</p> : (
                        <div className="flex flex-wrap gap-2">
                            {analysis.preparation_areas.map((p, i) => (
                                <span key={i} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface-container-low text-sm">
                                    <span className={`w-2 h-2 rounded-full ${p.status === 'missing' ? 'bg-red-500' : 'bg-amber-500'}`} />
                                    {p.skill}<span className="text-xs text-on-surface-variant">· {p.importance}</span>
                                </span>
                            ))}
                        </div>
                    )}
                    <div className="flex flex-wrap gap-3 mt-auto pt-3">
                        <Link to={`/learning-path?analysis=${analysis.id}`} className={`${primaryBtn} px-5 py-2.5 text-sm`}>Build my learning roadmap</Link>
                        <Link to={`/technical-interview?job=${job.id}`} className={`${secondaryBtn} px-5 py-2.5 text-sm`}>Practise a technical interview</Link>
                    </div>
                </section>
            </div>

            {(req.role_summary || req.responsibilities?.length) && (
                <section className={`${card} p-6`}>
                    <h3 className="font-headline text-lg font-bold text-on-surface mb-3">Job requirements summary</h3>
                    {req.role_summary && <p className="text-sm text-on-surface mb-4">{req.role_summary}</p>}
                    <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-3 text-sm">
                        {[['Responsibilities', req.responsibilities], ['Education', req.education], ['Soft skills', req.soft_skills],
                          ['Domain knowledge', req.domain_knowledge], ['Experience', req.experience_summary ? [req.experience_summary] : []]]
                            .filter(([, v]) => v && v.length).map(([k, v]) => (
                                <div key={k}>
                                    <dt className="text-xs font-bold text-on-surface-variant">{k}</dt>
                                    <dd className="text-on-surface">{v.join(' · ')}</dd>
                                </div>
                            ))}
                    </dl>
                </section>
            )}
        </div>
    );
}
