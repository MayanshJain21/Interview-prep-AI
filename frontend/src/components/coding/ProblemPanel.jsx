import React, { useState } from 'react';

// Small formatter for the statement: `code` and **bold** only, no HTML injection.
export function RichText({ text }) {
    const parts = String(text || '').split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
        if (part.startsWith('`') && part.endsWith('`') && part.length > 1) {
            return <code key={i} className="px-1.5 py-0.5 rounded bg-surface-container-high text-[0.9em] font-mono">{part.slice(1, -1)}</code>;
        }
        if (part.startsWith('**') && part.endsWith('**') && part.length > 3) {
            return <strong key={i}>{part.slice(2, -2)}</strong>;
        }
        return <React.Fragment key={i}>{part}</React.Fragment>;
    });
}

const fmtArgs = (params, args) => params.map((p, i) => `${p} = ${JSON.stringify(args[i])}`).join(', ');

export default function ProblemPanel({ problem, onHint, hintLoading }) {
    const [tab, setTab] = useState('description');
    const hintsLeft = problem.hints_total - problem.hints.length;

    return (
        <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant shadow-sm flex flex-col min-h-0">
            <div className="flex gap-1 p-2 border-b border-outline-variant" role="tablist">
                {['description', 'hints'].map((t) => (
                    <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
                        className={`px-4 py-2 rounded-lg text-sm font-bold capitalize ${tab === t ? 'bg-primary-fixed text-primary' : 'text-on-surface-variant hover:bg-surface-container-low'}`}>
                        {t}{t === 'hints' && problem.hints.length > 0 ? ` (${problem.hints.length})` : ''}
                    </button>
                ))}
            </div>

            <div className="p-6 overflow-y-auto">
                {tab === 'description' ? (
                    <div className="flex flex-col gap-5 text-on-surface">
                        <div>
                            <span className="text-xs font-bold text-primary">{problem.topic}</span>
                            <h2 className="font-headline text-xl font-semibold mt-1">{problem.title}</h2>
                            {problem.source && (
                                <p className="mt-1 text-xs text-on-surface-variant">
                                    Asked at {problem.source.companies.join(', ')}.{' '}
                                    <a href={problem.source.url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                                        LeetCode{problem.source.leetcode_id ? ` #${problem.source.leetcode_id}` : ''}
                                    </a>
                                </p>
                            )}
                        </div>
                        <p className="leading-relaxed whitespace-pre-wrap text-[15px]"><RichText text={problem.statement} /></p>

                        {problem.examples.map((ex, i) => (
                            <div key={i} className="bg-surface-container-low rounded-xl p-4 text-sm">
                                <p className="font-bold mb-2">Example {i + 1}</p>
                                <p className="font-mono text-[13px] break-all"><span className="text-on-surface-variant">Input:</span> {fmtArgs(problem.params, ex.args)}</p>
                                <p className="font-mono text-[13px] break-all"><span className="text-on-surface-variant">Output:</span> {JSON.stringify(ex.expected)}</p>
                                {ex.explanation && <p className="mt-2 text-on-surface-variant">{ex.explanation}</p>}
                            </div>
                        ))}

                        {problem.constraints.length > 0 && (
                            <div>
                                <p className="font-bold text-sm mb-1">Constraints</p>
                                <ul className="list-disc pl-5 text-sm space-y-0.5 font-mono">
                                    {problem.constraints.map((c, i) => <li key={i}><RichText text={c} /></li>)}
                                </ul>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="flex flex-col gap-4">
                        <p className="text-sm text-on-surface-variant">Each hint costs 5 points on this problem.</p>
                        {problem.hints.map((h, i) => (
                            <div key={i} className="bg-amber-50 border border-amber-200 text-amber-900 rounded-xl p-4 text-sm">
                                <span className="font-bold">Hint {i + 1}:</span> <RichText text={h} />
                            </div>
                        ))}
                        {hintsLeft > 0 ? (
                            <button onClick={onHint} disabled={hintLoading}
                                className="self-start px-5 py-2 rounded-full bg-surface-container-high text-on-surface text-sm font-bold disabled:opacity-60">
                                {hintLoading ? 'Loading...' : `Show hint ${problem.hints.length + 1} of ${problem.hints_total}`}
                            </button>
                        ) : (
                            <p className="text-sm text-on-surface-variant">No more hints for this problem.</p>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
