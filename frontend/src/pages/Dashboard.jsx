import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiCall } from '../api';
import { engineApi, linkTo } from '../services/part2Api';
import { Loading } from '../components/shared/ui';
import Analytics from '../components/dashboard/Analytics';

const todayISO = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
const avg = (list, fn) => (list.length ? list.reduce((s, x) => s + fn(x), 0) / list.length : null);

// One tool on the journey: its stage, a name, one line of status and one action.
// Every card is the same size; the action sits at the bottom.
function Tool({ stage, title, status, done, action, to, disabled }) {
    const btn = 'self-start mt-auto px-3 py-1.5 rounded-lg bg-primary text-on-primary border border-primary text-[13px] font-semibold';
    return (
        <div className={`h-full rounded-xl border border-outline-variant bg-surface-container-lowest p-4 flex flex-col ${disabled ? 'opacity-60' : ''}`}>
            <p className="text-xs text-outline">{stage}</p>
            <div className="mt-1 flex items-center gap-1.5">
                <h3 className="text-[15px] font-semibold text-on-surface">{title}</h3>
                {done && <span className="material-symbols-outlined text-base text-primary" aria-label="done">check_circle</span>}
            </div>
            <p className="text-[13px] text-on-surface-variant mt-0.5 mb-4 leading-snug">{status}</p>
            {disabled ? (
                <span className="mt-auto text-[13px] text-outline">Upload your resume first</span>
            ) : (
                <Link to={to} className={btn}>{action}</Link>
            )}
        </div>
    );
}

// The four stages as one progress line. The first stage not started yet is marked "You are here".
function Track({ stages, current }) {
    return (
        <ol className="grid grid-cols-4 gap-x-5" aria-label="Your progress through the four stages">
            {stages.map((st, i) => (
                <li key={st.name}>
                    <div className="flex items-center" aria-hidden="true">
                        <span className={`w-3 h-3 rounded-full shrink-0 border-2 ${i === current ? 'bg-accent border-accent ring-4 ring-accent-soft' : st.done ? 'bg-primary border-primary' : 'bg-surface border-outline-variant'}`} />
                        {i < stages.length - 1 && (
                            <span className={`h-0.5 flex-1 -mr-5 ${st.done && stages[i + 1].done ? 'bg-primary' : 'bg-outline-variant'}`} />
                        )}
                    </div>
                    <p className={`mt-2 text-sm ${st.done ? 'text-on-surface font-semibold' : 'text-on-surface-variant'}`}>
                        <span className="text-outline font-normal mr-1.5">{i + 1}</span>{st.name}
                        {i === current && <span className="block w-fit mt-1 sm:inline sm:mt-0 sm:ml-2 px-1.5 py-0.5 rounded text-[11px] font-semibold bg-accent-soft text-on-accent whitespace-nowrap">You are here</span>}
                        <span className="sr-only">{st.done ? ' (started)' : ' (not started)'}</span>
                    </p>
                </li>
            ))}
        </ol>
    );
}

export default function Dashboard() {
    const [data, setData] = useState({});
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const out = {};
        Promise.allSettled([
            apiCall('/dashboard/history').then((r) => { out.history = r; }),
            engineApi.profile().then((r) => { out.profile = r; }),
            engineApi.analytics().then((r) => { out.analytics = r; }),
            engineApi.roadmap().then((r) => { out.roadmap = r?.roadmap; }),
        ]).finally(() => { setData(out); setLoading(false); });
    }, []);


    if (loading) return <main className="pt-24 px-4 sm:px-6 max-w-[75rem] mx-auto"><Loading title="Loading your dashboard" /></main>;

    const stats = data.history?.stats || {};
    const mcq = data.history?.mcq_history || [];
    const profile = data.profile || {};
    const analytics = data.analytics || {};
    const roadmap = data.roadmap;
    const hasResume = !!profile.has_resume;
    const job = profile.job_analysis;
    const mcqPct = avg(mcq, (e) => (e.total ? (e.score / e.total) * 100 : 0));
    const dueToday = (roadmap?.items || []).filter((i) => i.status === 'pending' && i.scheduled_date <= todayISO()).length;
    const progress = analytics.roadmap_progress;
    const next = analytics.recommendations?.[0];
    // Without a resume nothing else is personalised, so the button always goes to the upload page,
    // even if practice sessions have already produced recommendations.
    const nextHref = !hasResume ? '/resume-upload' : next ? (linkTo(next.link) || '/learning-path') : '/mcq';

    const stages = [
        { name: 'Resume', done: hasResume },
        { name: 'Practice', done: mcq.length > 0 || stats.coding_rounds > 0 },
        { name: 'Interviews', done: stats.hr_interviews > 0 || stats.technical_interviews > 0 },
        { name: 'Plan', done: !!roadmap },
    ];

    const currentStage = stages.findIndex((st) => !st.done);

    return (
        <main className="pt-24 px-4 sm:px-6 pb-16 w-full max-w-[75rem] mx-auto">
            <header className="flex flex-wrap items-end justify-between gap-6">
                <div>
                    <h1 className="text-3xl sm:text-[2.5rem] leading-tight font-semibold text-on-surface">Your preparation</h1>
                    <p className="mt-2 text-on-surface-variant">
                        {!hasResume ? 'Start by uploading your resume. Everything else builds on it.'
                            : next ? <><span className="mr-2 px-2 py-0.5 rounded-md text-xs font-semibold bg-accent-soft text-on-accent">Next up</span><span className="text-on-surface">{next.title}</span></>
                                : 'Pick any tool below to keep practising.'}
                    </p>
                </div>
                <div className="flex items-center gap-5">
                    {analytics.readiness !== undefined && hasResume && (
                        <Link to="/learning-path" className="text-right">
                            <span className="block text-2xl font-semibold text-on-surface leading-none">{Math.round(analytics.readiness)}%</span>
                            <span className="text-xs text-on-surface-variant">readiness</span>
                        </Link>
                    )}
                    <Link to={nextHref} className="px-4 py-2.5 rounded-lg bg-primary text-on-primary text-sm font-semibold hover:bg-on-primary-fixed-variant">
                        {hasResume ? 'Start next task' : 'Upload resume'}
                    </Link>
                </div>
            </header>

            <Analytics timeline={data.history?.timeline || []} mastery={analytics.mastery || []}>
                <Track stages={stages} current={currentStage} />
            </Analytics>

            <h2 className="mt-14 text-xl font-semibold text-on-surface">Your journey</h2>
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 auto-rows-fr gap-5">
                <Tool stage="Resume" title="My resume" done={hasResume} to="/resume-upload"
                    status={hasResume ? `${profile.resume_skills?.length || 0} skills found` : 'Upload your PDF to unlock everything'}
                    action={hasResume ? 'Update' : 'Upload'} />
                <Tool stage="Resume" title="ATS check" done={stats.latest_ats_score != null} to="/ats-check" disabled={!hasResume}
                    status={stats.latest_ats_score != null ? `Last score ${stats.latest_ats_score}/100` : 'How screening software reads it'}
                    action={stats.latest_ats_score != null ? 'Check again' : 'Check'} />
                <Tool stage="Resume" title="Job match" done={!!job} to="/job-analyzer" disabled={!hasResume}
                    status={job ? `${job.title}: ${Math.round(job.score)}% match` : 'Compare your resume with a job'}
                    action={job ? 'Analyse another' : 'Analyse a job'} />
                <Tool stage="Practice" title="MCQ tests" done={mcq.length > 0} to="/mcq"
                    status={mcqPct !== null ? `Average ${Math.round(mcqPct)}% over ${mcq.length} ${mcq.length === 1 ? 'test' : 'tests'}` : 'Quick checks for each skill'}
                    action="Take a test" />
                <Tool stage="Practice" title="Coding round" done={stats.coding_rounds > 0} to="/coding-round"
                    status={stats.coding_rounds > 0 ? `Average ${stats.average_coding_score}/100` : 'Timed, real interview problems'}
                    action="Start a round" />
                <Tool stage="Interviews" title="HR interview" done={stats.hr_interviews > 0} to="/hr-interview"
                    status={stats.hr_interviews > 0 ? `Average ${Math.round(stats.average_hr_score * 10) / 10}/10` : 'Six behavioural questions'}
                    action="Practise" />
                <Tool stage="Interviews" title="Technical interview" done={stats.technical_interviews > 0} to="/technical-interview"
                    status={stats.technical_interviews > 0 ? `Average ${stats.average_technical_score}/100` : 'Adaptive questions by topic'}
                    action="Practise" />
                <Tool stage="Plan" title="Learning path" done={!!roadmap} to="/learning-path"
                    status={roadmap ? `${dueToday} ${dueToday === 1 ? 'task' : 'tasks'} today, ${progress?.percent ?? 0}% done` : 'A day-by-day plan to your deadline'}
                    action={roadmap ? 'Open' : 'Make a plan'} />
            </div>
        </main>
    );
}
