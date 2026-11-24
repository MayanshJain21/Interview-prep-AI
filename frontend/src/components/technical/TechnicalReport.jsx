import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { linkTo } from '../../services/part2Api';
import { Badge, Bar, card, primaryBtn, ScoreRing, scoreTone, secondaryBtn } from '../shared/ui';

const CRITERIA = {
    technical_correctness: 'Technical correctness', conceptual_understanding: 'Conceptual understanding',
    completeness: 'Completeness', logical_reasoning: 'Logical reasoning', practical_application: 'Practical application',
    clarity: 'Clarity of explanation',
};

function List({ title, items, tone = 'text-on-surface' }) {
    if (!items?.length) return null;
    return (
        <div>
            <p className="text-xs font-bold text-on-surface-variant mb-1">{title}</p>
            <ul className={`list-disc pl-5 text-sm space-y-0.5 ${tone}`}>{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </div>
    );
}

function TurnDetail({ turn }) {
    const [open, setOpen] = useState(false);
    const e = turn.evaluation || {};
    const tone = scoreTone((turn.score ?? 0) * 10);
    return (
        <div className="border border-outline-variant rounded-xl overflow-hidden">
            <button onClick={() => setOpen(!open)} aria-expanded={open} className="w-full flex items-center gap-4 p-4 text-left hover:bg-surface-container-low">
                <span className={`w-12 h-12 shrink-0 rounded-xl flex items-center justify-center font-semibold ${tone.bg} ${tone.text}`}>
                    {turn.score ?? '–'}<span className="text-[10px] opacity-70">/10</span>
                </span>
                <span className="flex-1 min-w-0">
                    <span className="block text-xs font-bold text-primary">Q{turn.number} · {turn.topic} · {turn.difficulty}{turn.kind !== 'core' ? ` · ${turn.kind} follow-up` : ''}</span>
                    <span className={`block text-sm text-on-surface ${open ? '' : 'truncate'}`}>{turn.question}</span>
                </span>
                <span className="material-symbols-outlined text-on-surface-variant">{open ? 'expand_less' : 'expand_more'}</span>
            </button>
            {open && (
                <div className="px-4 pb-5 pt-2 border-t border-outline-variant flex flex-col gap-4">
                    <div><p className="text-xs font-bold text-on-surface-variant mb-1">Your answer</p>
                        <p className="text-sm whitespace-pre-wrap">{turn.answer}</p></div>
                    <div className="grid sm:grid-cols-2 gap-4">
                        <List title="What was correct" items={e.correct_points} />
                        <List title="Missing concepts" items={e.missing_concepts} />
                        <List title="Incorrect statements" items={e.incorrect_statements} tone="text-red-800" />
                        <List title="How to improve" items={e.suggestions} />
                    </div>
                    {e.example_answer && (
                        <div className="bg-surface-container-low rounded-xl p-4">
                            <p className="text-xs font-bold text-on-surface-variant mb-1">A stronger answer</p>
                            <p className="text-sm whitespace-pre-wrap">{e.example_answer}</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default function TechnicalReport({ session, onNew }) {
    const navigate = useNavigate();
    const r = session.report;
    return (
        <div className="flex flex-col gap-6">
            <section className={`${card} p-6 sm:p-8 flex flex-wrap items-center gap-6`}>
                <ScoreRing score={r.overall_score} size={124} label="Technical interview score" />
                <div className="flex-1 min-w-[220px]">
                    <p className="text-xs font-bold text-primary">Technical interview report</p>
                    <h2 className="font-headline text-2xl font-semibold text-on-surface">{r.interview_type}</h2>
                    <p className="text-sm text-on-surface-variant">{session.job_role || 'Software Engineer'}{session.company ? ` · ${session.company}` : ''} · {session.difficulty} start · {r.questions_answered} questions</p>
                    <div className="flex flex-wrap gap-2 mt-2">
                        <Badge kind={r.overall_score >= 75 ? 'strong' : r.overall_score >= 55 ? 'developing' : 'weak'}>{r.verdict}</Badge>
                        <span className="text-xs text-on-surface-variant">Hardest level handled: <b>{r.difficulty_handled}</b></span>
                        {r.communication_score !== null && <span className="text-xs text-on-surface-variant">Explanation quality: <b>{r.communication_score}/10</b></span>}
                    </div>
                </div>
            </section>

            <section className={`${card} p-6 border-primary/30`}>
                <h3 className="font-headline text-lg font-bold text-on-surface mb-1">Your Next Preparation Priorities</h3>
                <p className="text-xs text-on-surface-variant mb-4">From the learning engine, which already includes this interview's results.</p>
                {r.next_priorities.length === 0 ? <p className="text-sm text-on-surface-variant">No gaps found. Try a harder interview.</p> : (
                    <ol className="grid sm:grid-cols-2 gap-3">
                        {r.next_priorities.map((p, i) => (
                            <li key={i} className="p-4 rounded-xl bg-surface-container-low flex flex-col gap-1">
                                <span className="text-xs font-bold text-primary">#{i + 1} · {p.skill}{p.mastery !== null ? ` · ${Math.round(p.mastery)}%` : ''}</span>
                                <span className="font-bold text-sm text-on-surface">{p.title}</span>
                                <span className="text-xs text-on-surface-variant">{p.reason}</span>
                                {linkTo(p.link) && !linkTo(p.link).startsWith('/learning-path') && (
                                    <button onClick={() => navigate(linkTo(p.link))} className="self-start mt-1 px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-bold">Practise now</button>
                                )}
                            </li>
                        ))}
                    </ol>
                )}
                <button onClick={() => navigate('/learning-path')} className={`${secondaryBtn} mt-4 px-5 py-2 text-sm`}>Open my learning path</button>
            </section>

            <div className="grid lg:grid-cols-2 gap-6">
                <section className={`${card} p-6`}>
                    <h3 className="font-headline text-lg font-bold text-on-surface mb-4">Topic-wise performance</h3>
                    <div className="flex flex-col gap-3">
                        {r.topic_performance.map((t) => (
                            <div key={t.topic}>
                                <div className="flex justify-between text-sm mb-1"><span>{t.topic}</span><span className="font-bold">{t.average}/10</span></div>
                                <Bar value={t.average} max={10} label={t.topic} tone={t.average >= 7 ? 'bg-green-600' : t.average >= 5 ? 'bg-amber-500' : 'bg-red-500'} />
                            </div>
                        ))}
                    </div>
                </section>
                <section className={`${card} p-6`}>
                    <h3 className="font-headline text-lg font-bold text-on-surface mb-4">Rubric averages</h3>
                    <div className="flex flex-col gap-3">
                        {Object.entries(r.criteria_averages).map(([k, v]) => (
                            <div key={k}>
                                <div className="flex justify-between text-sm mb-1"><span>{CRITERIA[k] || k}</span><span className="font-bold">{v}/10</span></div>
                                <Bar value={v} max={10} label={CRITERIA[k]} />
                            </div>
                        ))}
                    </div>
                </section>
            </div>

            <section className={`${card} p-6 grid sm:grid-cols-3 gap-6`}>
                <List title="Technical strengths" items={r.strengths.length ? r.strengths : ['None yet: no topic averaged 7 or more']} />
                <List title="Knowledge gaps" items={r.knowledge_gaps.length ? r.knowledge_gaps : ['No topic below 5']} />
                <List title="Incorrect concepts" items={r.incorrect_concepts.length ? r.incorrect_concepts : ['None found']} tone="text-red-800" />
            </section>

            <section className={`${card} p-6 flex flex-col gap-3`}>
                <h3 className="font-headline text-lg font-bold text-on-surface">Questions and feedback</h3>
                {session.transcript.map((t) => <TurnDetail key={t.number} turn={t} />)}
            </section>

            <div className="flex justify-end">
                <button onClick={onNew} className={`${primaryBtn} px-6 py-2.5 text-sm`}>New interview</button>
            </div>
        </div>
    );
}
