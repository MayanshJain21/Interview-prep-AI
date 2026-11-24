import React, { useState } from 'react';
import CodeEditor from './CodeEditor';
import { languageLabel } from './languages';

const VERDICT_STYLES = {
    'Interview ready': 'bg-green-100/60 text-green-800 border-green-200',
    'Almost there': 'bg-amber-100/60 text-amber-800 border-amber-200',
    'Needs practice': 'bg-red-100/60 text-red-800 border-red-200',
};

const EFFICIENCY_LABEL = { optimal: 'Optimal', one_slower: 'One step slower than optimal', slower: 'Slower than optimal' };

function List({ title, items }) {
    if (!items || items.length === 0) return null;
    return (
        <div>
            <p className="text-xs font-bold text-on-surface-variant mb-1">{title}</p>
            <ul className="list-disc pl-5 text-sm space-y-0.5">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </div>
    );
}

function ProblemResult({ item, index }) {
    const [showCode, setShowCode] = useState(false);
    const s = item.score;
    return (
        <div className="bg-surface-container-lowest rounded-2xl p-6 border border-outline-variant shadow-sm flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-4">
                <div className="w-16 h-16 rounded-xl bg-primary-fixed text-primary flex flex-col items-center justify-center">
                    <span className="font-semibold text-xl leading-none">{s.total}</span>
                    <span className="text-[10px] font-bold opacity-70">/ 100</span>
                </div>
                <div className="flex-1 min-w-[200px]">
                    <p className="text-xs font-bold text-primary">Problem {index + 1} · {item.topic}</p>
                    <h3 className="font-headline text-lg font-bold text-on-surface">{item.title}</h3>
                    <p className="text-sm text-on-surface-variant">
                        {item.attempted ? `${item.passed}/${item.total} hidden tests passed · ${languageLabel(item.language)}` : 'Not submitted'}
                        {item.hints_used > 0 && ` · ${item.hints_used} hint${item.hints_used > 1 ? 's' : ''} used`}
                    </p>
                </div>
            </div>

            {item.attempted && (
                <>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-sm">
                        {[['Correctness', s.correctness, 60], ['Efficiency', s.efficiency, 25], ['Code quality', s.quality, 15], ['Hints', -s.hint_penalty, null]].map(([label, val, max]) => (
                            <div key={label} className="bg-surface-container-low rounded-lg py-2">
                                <p className="font-semibold text-on-surface">{val}{max ? `/${max}` : ''}</p>
                                <p className="text-xs text-on-surface-variant">{label}</p>
                            </div>
                        ))}
                    </div>
                    <div className="text-sm text-on-surface">
                        <p><span className="font-bold">Your complexity:</span> time {item.review.time_complexity || '?'}, space {item.review.space_complexity || '?'}
                            {' '}({EFFICIENCY_LABEL[item.review.efficiency]})</p>
                        <p><span className="font-bold">Optimal:</span> time {item.complexity.time || '?'}, space {item.complexity.space || '?'}</p>
                    </div>
                    <p className="text-sm leading-relaxed text-on-surface">{item.review.feedback}</p>
                    <div className="grid sm:grid-cols-2 gap-4">
                        <List title="Edge cases missed" items={item.review.edge_cases_missed} />
                        <List title="Suggestions" items={item.review.suggestions} />
                    </div>
                    {item.failed_tests.length > 0 && (
                        <div>
                            <p className="text-xs font-bold text-on-surface-variant mb-1">Hidden tests you failed</p>
                            <div className="flex flex-col gap-2">
                                {item.failed_tests.map((t, i) => (
                                    <div key={i} className="rounded-lg border border-outline-variant p-3 text-xs font-mono flex flex-col gap-1">
                                        <span className="font-sans font-bold text-red-700">{t.verdict} · {t.category}</span>
                                        <span className="break-all">Input: {t.input}</span>
                                        <span className="break-all">Expected: {t.expected}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </>
            )}

            <button onClick={() => setShowCode(!showCode)} className="self-start text-sm font-bold text-primary flex items-center gap-1">
                <span className="material-symbols-outlined text-base">{showCode ? 'expand_less' : 'code'}</span>
                {showCode ? 'Hide code' : (item.attempted ? 'Compare your code with the reference' : 'Show the reference solution')}
            </button>
            {showCode && (
                <div className={`grid gap-4 ${item.attempted ? 'lg:grid-cols-2' : ''}`}>
                    {item.attempted && (
                        <div>
                            <p className="text-xs font-bold text-on-surface-variant mb-1">Your final submission</p>
                            <CodeEditor language={item.language} value={item.code} readOnly height="300px" />
                        </div>
                    )}
                    <div>
                        <p className="text-xs font-bold text-on-surface-variant mb-1">Reference solution (Python)</p>
                        <CodeEditor language="python" value={item.reference_solution} readOnly height="300px" />
                    </div>
                </div>
            )}
        </div>
    );
}

export default function CodingReport({ session, onNewRound }) {
    const report = session.report;
    return (
        <div className="flex flex-col gap-6">
            <div className="bg-surface-container-lowest rounded-2xl p-8 border border-outline-variant shadow-sm flex flex-wrap items-center gap-6">
                <div className="w-24 h-24 bg-primary-fixed rounded-2xl flex flex-col items-center justify-center text-primary">
                    <span className="font-semibold text-3xl leading-none">{session.overall_score}</span>
                    <span className="text-xs font-bold opacity-70 mt-1">/ 100</span>
                </div>
                <div className="flex-1 min-w-[220px]">
                    <h2 className="font-headline text-2xl font-semibold text-on-surface">Coding Round Report</h2>
                    <p className="text-sm text-on-surface-variant capitalize">{session.difficulty} round{session.job_role ? ` · ${session.job_role}` : ''}</p>
                    <span className={`inline-block mt-2 px-3 py-1 rounded-full text-xs font-bold border ${VERDICT_STYLES[report.verdict] || ''}`}>{report.verdict}</span>
                </div>
                {(report.paste_flags > 0 || report.tab_switches > 0) && (
                    <p className="text-xs text-on-surface-variant">
                        {report.paste_flags > 0 && `${report.paste_flags} large paste${report.paste_flags > 1 ? 's' : ''}`}
                        {report.paste_flags > 0 && report.tab_switches > 0 && ' · '}
                        {report.tab_switches > 0 && `${report.tab_switches} tab switch${report.tab_switches > 1 ? 'es' : ''}`}
                    </p>
                )}
            </div>
            {report.problems.map((item, i) => <ProblemResult key={i} item={item} index={i} />)}
            <div className="flex justify-end gap-3">
                <a href="/dashboard" className="bg-surface-container text-on-surface px-6 py-2.5 rounded-full font-bold border border-outline-variant text-sm">Dashboard</a>
                <button onClick={onNewRound} className="bg-primary text-white px-6 py-2.5 rounded-lg font-bold shadow-lg text-sm">New Round</button>
            </div>
        </div>
    );
}
