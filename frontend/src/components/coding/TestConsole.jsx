import React from 'react';

const VERDICT_STYLE = {
    'Passed': 'text-green-700 bg-green-50',
    'Wrong answer': 'text-red-700 bg-red-50',
    'Runtime error': 'text-red-700 bg-red-50',
    'Time limit exceeded': 'text-amber-800 bg-amber-50',
};

export default function TestConsole({ output, busy }) {
    if (busy) {
        return <div className="p-4 text-sm text-on-surface-variant flex items-center gap-2">
            <span className="material-symbols-outlined animate-spin text-base">sync</span>{busy}</div>;
    }
    if (!output) {
        return <div className="p-4 text-sm text-on-surface-variant">Run your code to test it on the examples. Submit runs the hidden tests.</div>;
    }
    if (output.error && (!output.results || output.results.length === 0) && output.kind !== 'submit') {
        return <pre className="p-4 text-sm text-red-700 whitespace-pre-wrap font-mono">{output.error}</pre>;
    }

    if (output.kind === 'submit') {
        const all = output.passed === output.total;
        return (
            <div className="p-4 text-sm flex flex-col gap-2">
                <p className={`font-bold text-base ${all ? 'text-green-700' : 'text-on-surface'}`}>
                    {all ? 'All hidden tests passed' : `${output.passed} of ${output.total} hidden tests passed`}
                </p>
                {output.first_failing && (
                    <p className="text-on-surface-variant">
                        First failure: <span className="font-bold text-on-surface">{output.first_failing.verdict}</span> on a{' '}
                        <span className="font-bold text-on-surface">{output.first_failing.category}</span> test.
                        The inputs are shown in the report after the round.
                    </p>
                )}
                {output.error && <pre className="text-red-700 whitespace-pre-wrap font-mono text-xs">{output.error}</pre>}
                {output.best && <p className="text-xs text-on-surface-variant">Best so far: {output.best.passed}/{output.best.total}. Your best submission is the one scored.</p>}
            </div>
        );
    }

    return (
        <div className="p-3 flex flex-col gap-2">
            <p className="px-1 text-sm font-bold text-on-surface">{output.passed} of {output.total} examples passed</p>
            {output.results.map((r, i) => (
                <div key={i} className="rounded-lg border border-outline-variant p-3 text-xs font-mono flex flex-col gap-1">
                    <span className={`self-start px-2 py-0.5 rounded font-sans font-bold ${VERDICT_STYLE[r.verdict] || ''}`}>Example {i + 1}: {r.verdict}</span>
                    <span className="break-all"><span className="text-on-surface-variant">Input: </span>{r.input}</span>
                    <span className="break-all"><span className="text-on-surface-variant">Expected: </span>{r.expected}</span>
                    {r.output !== null && r.output !== undefined && <span className="break-all"><span className="text-on-surface-variant">Your output: </span>{r.output}</span>}
                    {r.error && <span className="text-red-700 whitespace-pre-wrap">{r.error}</span>}
                    {r.stdout && <span className="whitespace-pre-wrap text-on-surface-variant">Printed: {r.stdout}</span>}
                </div>
            ))}
        </div>
    );
}
