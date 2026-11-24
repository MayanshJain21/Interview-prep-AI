import React from 'react';

const BAND_TONE = (m) => (m === null ? '' : m >= 75 ? 'bg-green-600' : m >= 60 ? 'bg-primary' : m >= 40 ? 'bg-amber-500' : 'bg-red-500');

// Horizontal bars of mastery per skill. Unassessed skills are drawn as an empty dashed track,
// so "unknown" never looks like "weak".
export default function MasteryChart({ rows, limit = 14 }) {
    const shown = rows.slice(0, limit);
    return (
        <div className="flex flex-col gap-2.5">
            {shown.map((r) => (
                <div key={r.slug} className="grid grid-cols-[minmax(110px,170px)_1fr_52px] items-center gap-3 text-sm">
                    <span className="truncate text-on-surface font-medium" title={r.reasons?.join('; ')}>{r.name}</span>
                    {r.mastery === null ? (
                        <div className="h-3 rounded-full border border-dashed border-outline-variant" aria-label={`${r.name}: not assessed`} />
                    ) : (
                        <div className="h-3 bg-surface-container-high rounded-full overflow-hidden" role="progressbar"
                             aria-valuenow={r.mastery} aria-valuemin={0} aria-valuemax={100} aria-label={`${r.name} mastery`}>
                            <div className={`h-full rounded-full ${BAND_TONE(r.mastery)}`} style={{ width: `${r.mastery}%` }} />
                        </div>
                    )}
                    <span className={`text-right tabular-nums ${r.mastery === null ? 'text-xs text-on-surface-variant' : 'font-bold text-on-surface'}`}>
                        {r.mastery === null ? 'not yet' : `${Math.round(r.mastery)}%`}
                    </span>
                </div>
            ))}
            <div className="flex flex-wrap gap-4 text-xs text-on-surface-variant pt-2">
                {[['bg-red-500', 'below 40'], ['bg-amber-500', '40–59'], ['bg-primary', '60–74'], ['bg-green-600', '75+']].map(([c, l]) => (
                    <span key={l} className="flex items-center gap-1.5"><span className={`w-3 h-3 rounded ${c}`} />{l}</span>
                ))}
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded border border-dashed border-outline-variant" />not assessed</span>
            </div>
        </div>
    );
}
