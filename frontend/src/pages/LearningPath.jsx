import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import MasteryChart from '../components/learning/MasteryChart';
import RoadmapItemRow from '../components/learning/RoadmapItemRow';
import RoadmapSetup from '../components/learning/RoadmapSetup';
import { Badge, Bar, card, EmptyState, ErrorBanner, formatDate, Loading, PageHeader, primaryBtn, secondaryBtn } from '../components/shared/ui';
import { engineApi, linkTo } from '../services/part2Api';
import { groupByWeek, localISODate } from '../utils/validation';

function Stat({ label, value, sub, children }) {
    return (
        <div className={`${card} p-5 flex flex-col gap-2`}>
            <p className="text-sm text-on-surface-variant font-medium">{label}</p>
            <p className="text-3xl font-semibold text-on-surface">{value}</p>
            {children}
            {sub && <p className="text-xs text-on-surface-variant">{sub}</p>}
        </div>
    );
}

export default function LearningPath() {
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const [analytics, setAnalytics] = useState(null);
    const [roadmapData, setRoadmapData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [showSetup, setShowSetup] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [view, setView] = useState('upcoming');

    const load = useCallback(async () => {
        setError('');
        try {
            const [a, r] = await Promise.all([engineApi.analytics(), engineApi.roadmap()]);
            setAnalytics(a);
            setRoadmapData(r);
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);
    // Arriving from the job analyzer (?analysis=ID) opens the setup with that job selected.
    useEffect(() => { if (searchParams.get('analysis')) setShowSetup(true); }, [searchParams]);

    const generate = async (body) => {
        setGenerating(true);
        setError('');
        try {
            await engineApi.generate(body);
            setShowSetup(false);
            setSearchParams({});
            await load();
        } catch (e) {
            setError(e.message);
        } finally {
            setGenerating(false);
        }
    };

    if (loading) return <main className="pt-20 px-4 sm:px-8"><Loading title="Loading your learning path" /></main>;

    const roadmap = roadmapData?.roadmap;
    const today = localISODate();
    const items = roadmap?.items || [];
    const visible = items.filter((i) => (view === 'upcoming' ? i.status === 'pending' : view === 'completed' ? i.status !== 'pending' : true));
    const weeks = groupByWeek(visible);
    const next = analytics?.recommendations?.[0];
    const todayItems = items.filter((i) => i.status === 'pending' && i.scheduled_date <= today);

    const setupInitial = {
        target_role: analytics?.target_role || roadmap?.target_role || '',
        job_analysis_id: searchParams.get('analysis') || roadmap?.job_analysis || '',
        minutes_per_day: roadmap?.minutes_per_day, study_days: roadmap?.study_days,
    };

    return (
        <main className="pt-20 pb-12 px-4 sm:px-6 min-h-screen">
            <div className="max-w-6xl mx-auto flex flex-col gap-6">
                <PageHeader title="Learning path"
                    subtitle={analytics?.target_role ? `Personalised preparation for ${analytics.target_role}, updated automatically after every MCQ, coding round and technical interview.`
                        : 'Your personalised preparation plan, updated after every assessment.'}
                    action={roadmap && !showSetup && <button onClick={() => setShowSetup(true)} className={`${secondaryBtn} px-5 py-2.5 text-sm`}>Regenerate roadmap</button>} />
                <ErrorBanner message={error} onRetry={load} />

                {(showSetup || !roadmap) && (
                    <RoadmapSetup initial={setupInitial} onSubmit={generate} busy={generating}
                                  onCancel={roadmap ? () => { setShowSetup(false); setSearchParams({}); } : null} />
                )}

                {analytics && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                        <Stat label="Preparation readiness" value={`${Math.round(analytics.readiness)}%`}
                              sub="Mastery weighted by how important each skill is for your goal. Unassessed skills count as 0.">
                            <Bar value={analytics.readiness} label="Readiness" />
                        </Stat>
                        <Stat label="Roadmap completion" value={analytics.roadmap_progress ? `${analytics.roadmap_progress.percent}%` : '–'}
                              sub={analytics.roadmap_progress ? `${analytics.roadmap_progress.completed} of ${analytics.roadmap_progress.total} tasks` : 'No roadmap yet'}>
                            <Bar value={analytics.roadmap_progress?.percent || 0} tone="bg-green-600" label="Roadmap completion" />
                        </Stat>
                        <Stat label="Skills assessed" value={`${analytics.assessed_skills}/${analytics.relevant_skills}`}
                              sub="Unassessed skills get a short diagnostic first." />
                        <div className={`${card} p-5 flex flex-col gap-2 border-primary/30`}>
                            <p className="text-sm text-primary font-bold flex items-center gap-1"><span className="material-symbols-outlined text-base">bolt</span>Recommended next</p>
                            {next ? (
                                <>
                                    <p className="font-bold text-on-surface">{next.title}</p>
                                    <p className="text-xs text-on-surface-variant">{next.reason}</p>
                                    {linkTo(next.link) && !linkTo(next.link).startsWith('/learning-path') && (
                                        <button onClick={() => navigate(linkTo(next.link))} className={`${primaryBtn} self-start px-4 py-2 text-xs mt-auto`}>Start · {next.duration_min} min</button>
                                    )}
                                </>
                            ) : <p className="text-sm text-on-surface-variant">Everything relevant is mastered. Keep revising.</p>}
                        </div>
                    </div>
                )}

                {roadmap && (
                    <div className="grid grid-cols-12 gap-6">
                        <section className={`${card} p-6 col-span-12 xl:col-span-8 flex flex-col gap-4`}>
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <h2 className="font-headline text-lg font-bold text-on-surface">Your roadmap</h2>
                                    <p className="text-xs text-on-surface-variant">
                                        {roadmap.target_role || 'General'}{roadmap.job_title ? ` · ${roadmap.job_title}` : ''} · until {formatDate(roadmap.deadline)} · {roadmap.minutes_per_day} min/day
                                    </p>
                                </div>
                                <div className="flex gap-1" role="tablist">
                                    {['upcoming', 'completed', 'all'].map((v) => (
                                        <button key={v} role="tab" aria-selected={view === v} onClick={() => setView(v)}
                                                className={`px-3 py-1.5 rounded-lg text-xs font-bold capitalize ${view === v ? 'bg-primary-fixed text-primary' : 'text-on-surface-variant hover:bg-surface-container-low'}`}>{v}</button>
                                    ))}
                                </div>
                            </div>
                            {todayItems.length > 0 && view === 'upcoming' && (
                                <p className="text-sm text-on-surface bg-primary-fixed/30 rounded-xl px-4 py-2">
                                    <span className="font-bold">Today:</span> {todayItems.length} task{todayItems.length > 1 ? 's' : ''} ({todayItems.reduce((s, i) => s + i.duration_min, 0)} min) due or overdue.
                                </p>
                            )}
                            {weeks.length === 0 && <EmptyState icon="task_alt" title={view === 'completed' ? 'Nothing completed yet' : 'No upcoming tasks'}
                                detail={view === 'completed' ? 'Finish a task or take an assessment; matching tasks complete automatically.' : 'Regenerate the roadmap to plan the next stretch.'} />}
                            {weeks.map(({ week, items: list }) => {
                                const milestone = roadmap.summary?.milestones?.find((m) => m.week === week);
                                return (
                                    <div key={week}>
                                        <h3 className="text-sm font-bold text-on-surface mb-2">{milestone?.title || `Week ${week}`}</h3>
                                        <ul className="flex flex-col gap-2">{list.map((item) => <RoadmapItemRow key={item.id} item={item} onChange={load} />)}</ul>
                                    </div>
                                );
                            })}
                            {roadmap.summary?.unscheduled?.length > 0 && (
                                <details className="text-sm text-on-surface-variant">
                                    <summary className="cursor-pointer font-bold">{roadmap.summary.unscheduled.length} task(s) didn't fit before your deadline</summary>
                                    <ul className="list-disc pl-6 mt-2">{roadmap.summary.unscheduled.slice(0, 15).map((u, i) => <li key={i}>{u.title}: {u.why}</li>)}</ul>
                                    <p className="mt-1">Add study time, more study days or a later date, then regenerate.</p>
                                </details>
                            )}
                        </section>

                        <div className="col-span-12 xl:col-span-4 flex flex-col gap-6">
                            <section className={`${card} p-6`}>
                                <h2 className="font-headline text-lg font-bold text-on-surface mb-4">Skill mastery</h2>
                                {analytics?.mastery?.length ? <MasteryChart rows={analytics.mastery} /> : <p className="text-sm text-on-surface-variant">No skills yet.</p>}
                            </section>
                            <section className={`${card} p-6 flex flex-col gap-3`}>
                                <h2 className="font-headline text-lg font-bold text-on-surface">Weakest and strongest</h2>
                                {analytics.weakest.length === 0 ? <p className="text-sm text-on-surface-variant">Take a diagnostic to see your levels.</p> : (
                                    <>
                                        {analytics.weakest.slice(0, 3).map((r) => <p key={r.slug} className="text-sm flex justify-between"><span>{r.name}</span><Badge kind={r.status}>{Math.round(r.mastery)}%</Badge></p>)}
                                        <hr className="border-outline-variant" />
                                        {analytics.strongest.slice(0, 3).map((r) => <p key={r.slug} className="text-sm flex justify-between"><span>{r.name}</span><Badge kind={r.status}>{Math.round(r.mastery)}%</Badge></p>)}
                                    </>
                                )}
                            </section>
                            {analytics.recent_improvement.length > 0 && (
                                <section className={`${card} p-6`}>
                                    <h2 className="font-headline text-lg font-bold text-on-surface mb-3">Last 14 days</h2>
                                    {analytics.recent_improvement.map((e) => (
                                        <p key={e.skill} className="text-sm flex justify-between py-1">
                                            <span>{e.skill}</span>
                                            <span className={`font-bold ${e.change >= 0 ? 'text-green-700' : 'text-red-700'}`}>{e.change >= 0 ? '+' : ''}{e.change}</span>
                                        </p>
                                    ))}
                                </section>
                            )}
                            {analytics.job_progress && (
                                <section className={`${card} p-6`}>
                                    <h2 className="font-headline text-lg font-bold text-on-surface mb-3">Progress on job requirements</h2>
                                    {analytics.job_progress.map((j) => (
                                        <div key={j.skill} className="py-1.5">
                                            <div className="flex justify-between text-sm"><span>{j.skill}</span>
                                                <span className="text-xs text-on-surface-variant">{j.mastery === null ? 'not assessed' : `${Math.round(j.mastery)}%`} · resume {j.resume_status}</span></div>
                                            <Bar value={j.mastery} label={`${j.skill} mastery`} tone={j.mastery >= 60 ? 'bg-green-600' : 'bg-amber-500'} />
                                        </div>
                                    ))}
                                </section>
                            )}
                        </div>
                    </div>
                )}

                {roadmapData?.history?.length > 0 && (
                    <section className={`${card} p-6`}>
                        <h2 className="font-headline text-lg font-bold text-on-surface mb-3">Earlier roadmaps</h2>
                        <ul className="text-sm divide-y divide-outline-variant">
                            {roadmapData.history.map((h) => (
                                <li key={h.id} className="py-2 flex justify-between"><span>{h.target_role || 'General'} · created {formatDate(h.created_at)}</span>
                                    <span className="text-on-surface-variant">{h.completed}/{h.total} completed</span></li>
                            ))}
                        </ul>
                    </section>
                )}
                {!roadmap && !showSetup && analytics && <p className="text-sm text-on-surface-variant">No roadmap yet. <Link to="/job-analyzer" className="text-primary font-bold">Analyse a job description</Link> first for a more targeted plan.</p>}
            </div>
        </main>
    );
}
