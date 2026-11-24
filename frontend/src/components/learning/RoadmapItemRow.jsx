import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { engineApi, linkTo } from '../../services/part2Api';
import { Badge } from '../shared/ui';
import { localISODate } from '../../utils/validation';

const ICONS = { diagnostic: 'troubleshoot', learn: 'menu_book', mcq: 'quiz', coding: 'code', interview: 'record_voice_over',
                revision: 'history_edu', assessment: 'assignment_turned_in', self_study: 'school' };

export default function RoadmapItemRow({ item, onChange }) {
    const navigate = useNavigate();
    const [busy, setBusy] = useState(false);
    const [rescheduling, setRescheduling] = useState(false);
    const [date, setDate] = useState(item.scheduled_date);
    const [notes, setNotes] = useState(null);
    const [message, setMessage] = useState('');
    const href = linkTo(item.link);
    const today = localISODate();

    const act = async (fn) => {
        setBusy(true); setMessage('');
        try { await fn(); } catch (e) { setMessage(e.message); } finally { setBusy(false); }
    };

    const setStatus = (status) => act(async () => { await engineApi.setStatus(item.id, status); onChange(); });
    const reschedule = () => act(async () => {
        const res = await engineApi.reschedule(item.id, date);
        setRescheduling(false);
        if (res.warning) setMessage(res.warning);
        onChange();
    });
    const loadNotes = () => act(async () => setNotes(await engineApi.notes(item.skill_slug)));

    const done = item.status !== 'pending';
    return (
        <li className={`p-4 rounded-xl border ${done ? 'border-outline-variant bg-surface-container-low/60' : 'border-outline-variant/25'}`}>
            <div className="flex flex-wrap items-start gap-3">
                <span className={`material-symbols-outlined w-10 h-10 rounded-xl flex items-center justify-center ${done ? 'bg-surface-container-high text-on-surface-variant' : 'bg-primary-fixed text-primary'}`}>
                    {ICONS[item.activity_type] || 'task'}
                </span>
                <div className="flex-1 min-w-[200px]">
                    <div className="flex flex-wrap items-center gap-2">
                        <span className={`font-bold text-sm ${item.status === 'completed' ? 'line-through text-on-surface-variant' : 'text-on-surface'}`}>{item.title}</span>
                        <Badge kind={item.status} />
                        {item.difficulty && <span className="text-xs text-on-surface-variant capitalize">{item.difficulty}</span>}
                    </div>
                    <p className="text-xs text-on-surface-variant mt-1">
                        {new Date(`${item.scheduled_date}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })} · {item.duration_min} min
                    </p>
                    <p className="text-xs text-on-surface mt-1"><span className="font-semibold">Why: </span>{item.reason}</p>
                </div>
                {item.status === 'pending' ? (
                    <div className="flex flex-wrap gap-2">
                        {href && href !== '/learning-path' && !href.startsWith('/learning-path?') && (
                            <button onClick={() => navigate(href)} className="px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-bold">Start</button>
                        )}
                        {item.activity_type === 'learn' && item.skill_slug && (
                            <button onClick={loadNotes} disabled={busy} className="px-3 py-1.5 rounded-full bg-surface-container-high text-xs font-bold">Study notes</button>
                        )}
                        <button onClick={() => setStatus('completed')} disabled={busy} className="px-3 py-1.5 rounded-full bg-green-50 text-green-800 text-xs font-bold">Done</button>
                        <button onClick={() => setStatus('skipped')} disabled={busy} className="px-3 py-1.5 rounded-full bg-surface-container-high text-xs font-bold">Skip</button>
                        <button onClick={() => setRescheduling(!rescheduling)} disabled={busy} className="px-3 py-1.5 rounded-full bg-surface-container-high text-xs font-bold">Reschedule</button>
                    </div>
                ) : (
                    <button onClick={() => setStatus('pending')} disabled={busy} className="px-3 py-1.5 rounded-full bg-surface-container-high text-xs font-bold">Undo</button>
                )}
            </div>
            {rescheduling && (
                <div className="flex flex-wrap items-center gap-2 mt-3 pl-[52px]">
                    <input type="date" value={date} min={today} onChange={(e) => setDate(e.target.value)}
                           className="px-3 py-1.5 rounded-lg bg-surface-container-high text-sm" aria-label="New date" />
                    <button onClick={reschedule} disabled={busy || !date} className="px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-bold">Save</button>
                </div>
            )}
            {message && <p className="text-xs text-amber-800 mt-2 pl-[52px]" role="status">{message}</p>}
            {notes && (
                <div className="mt-3 ml-[52px] p-4 rounded-xl bg-surface-container-low text-sm flex flex-col gap-2">
                    <p className="text-on-surface">{notes.summary}</p>
                    {[['Key concepts', notes.key_concepts], ['Practice ideas', notes.practice_ideas], ['Common mistakes', notes.common_mistakes]].map(([t, list]) => list?.length > 0 && (
                        <div key={t}><p className="text-xs font-bold text-on-surface-variant">{t}</p>
                            <ul className="list-disc pl-5">{list.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
                    ))}
                    <p className="text-[11px] text-on-surface-variant">Notes are AI-generated; check important details against a textbook.</p>
                </div>
            )}
        </li>
    );
}
