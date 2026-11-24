import React, { useEffect, useState } from 'react';
import { jobsApi } from '../../services/part2Api';
import { localISODate as inDays, validateRoadmapForm } from '../../utils/validation';
import { card, inputCls, primaryBtn, secondaryBtn } from '../shared/ui';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const ROLES = ['Software Engineer', 'Backend Developer', 'Frontend Developer', 'Full Stack Developer', 'Data Scientist'];


export default function RoadmapSetup({ initial, onSubmit, onCancel, busy }) {
    const [form, setForm] = useState({
        target_role: initial?.target_role || '',
        job_analysis_id: initial?.job_analysis_id || '',
        deadline: initial?.deadline || inDays(28),
        minutes_per_day: initial?.minutes_per_day || 60,
        study_days: initial?.study_days || [0, 1, 2, 3, 4, 5],
    });
    const [jobs, setJobs] = useState([]);
    const [error, setError] = useState('');

    useEffect(() => {
        jobsApi.history(1).then((h) => setJobs(h.results.filter((j) => j.latest_analysis_id))).catch(() => {});
    }, []);

    const toggleDay = (d) => setForm((f) => ({
        ...f, study_days: f.study_days.includes(d) ? f.study_days.filter((x) => x !== d) : [...f.study_days, d].sort(),
    }));

    const submit = (e) => {
        e.preventDefault();
        const problem = validateRoadmapForm(form);
        if (problem) { setError(problem); return; }
        setError('');
        onSubmit({ ...form, job_analysis_id: form.job_analysis_id ? Number(form.job_analysis_id) : null,
                   minutes_per_day: Number(form.minutes_per_day) });
    };

    return (
        <form onSubmit={submit} className={`${card} p-6 sm:p-8 flex flex-col gap-5`} noValidate>
            <div>
                <h2 className="font-headline text-xl font-semibold text-on-surface">Plan your preparation</h2>
                <p className="text-sm text-on-surface-variant mt-1">The engine ranks skills by how far you are from mastery and how much the role needs them, puts prerequisites first, and fits the plan into your available time.</p>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
                <label className="text-sm font-bold text-on-surface">Target role
                    <input list="lp-roles" className={`${inputCls} mt-1.5 font-normal`} value={form.target_role}
                           onChange={(e) => setForm({ ...form, target_role: e.target.value })} placeholder="e.g. Software Engineer" maxLength={150} />
                    <datalist id="lp-roles">{ROLES.map((r) => <option key={r} value={r} />)}</datalist>
                </label>
                <label className="text-sm font-bold text-on-surface">Job description (optional)
                    <select className={`${inputCls} mt-1.5 font-normal`} value={form.job_analysis_id}
                            onChange={(e) => setForm({ ...form, job_analysis_id: e.target.value })}>
                        <option value="">None: use the role profile</option>
                        {jobs.map((j) => <option key={j.id} value={j.latest_analysis_id}>{j.title}{j.company ? ` · ${j.company}` : ''} ({Math.round(j.latest_score)}%)</option>)}
                    </select>
                </label>
                <label className="text-sm font-bold text-on-surface">Target date
                    <input type="date" className={`${inputCls} mt-1.5 font-normal`} value={form.deadline} min={inDays(1)}
                           onChange={(e) => setForm({ ...form, deadline: e.target.value })} />
                </label>
                <label className="text-sm font-bold text-on-surface">Study time per day
                    <select className={`${inputCls} mt-1.5 font-normal`} value={form.minutes_per_day}
                            onChange={(e) => setForm({ ...form, minutes_per_day: Number(e.target.value) })}>
                        {[30, 45, 60, 90, 120, 180, 240].map((m) => <option key={m} value={m}>{m >= 60 ? `${m / 60} hour${m > 60 ? 's' : ''}` : `${m} minutes`}</option>)}
                    </select>
                </label>
            </div>
            <fieldset>
                <legend className="text-sm font-bold text-on-surface mb-2">Study days</legend>
                <div className="flex flex-wrap gap-2">
                    {DAYS.map((d, i) => (
                        <button type="button" key={d} onClick={() => toggleDay(i)} aria-pressed={form.study_days.includes(i)}
                                className={`w-12 py-2 rounded-lg text-sm font-bold border ${form.study_days.includes(i) ? 'bg-primary text-white border-primary' : 'border-outline-variant text-on-surface-variant'}`}>{d}</button>
                    ))}
                </div>
            </fieldset>
            {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
            <div className="flex gap-3">
                <button type="submit" disabled={busy} className={`${primaryBtn} px-8 py-3`}>{busy ? 'Building your roadmap...' : 'Generate roadmap'}</button>
                {onCancel && <button type="button" onClick={onCancel} className={`${secondaryBtn} px-6 py-3`}>Cancel</button>}
            </div>
        </form>
    );
}
