import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import AnalysisReport from '../components/jobs/AnalysisReport';
import { card, EmptyState, ErrorBanner, formatDate, inputCls, Loading, PageHeader, primaryBtn, scoreTone, secondaryBtn } from '../components/shared/ui';
import { jobsApi } from '../services/part2Api';
import { validateJobForm } from '../utils/validation';

const ROLES = ['Software Engineer', 'Backend Developer', 'Frontend Developer', 'Full Stack Developer', 'Data Scientist'];

export default function JobDescriptionAnalyzer() {
    const [searchParams, setSearchParams] = useSearchParams();
    const [form, setForm] = useState({ title: '', company: '', target_role: '', text: '' });
    const [file, setFile] = useState(null);
    const [mode, setMode] = useState('paste');
    const [history, setHistory] = useState({ results: [], page: 1, pages: 1 });
    const [report, setReport] = useState(null); // { job, analysis }
    const [phase, setPhase] = useState('form'); // form | analyzing | report | loading
    const [error, setError] = useState('');
    const [errorCode, setErrorCode] = useState('');

    const loadHistory = useCallback((page = 1) => {
        jobsApi.history(page).then(setHistory).catch(() => {});
    }, []);

    useEffect(() => { loadHistory(); }, [loadHistory]);

    // Deep link: /job-analyzer?analysis=12 (also used when opening an item from the history list)
    const linkedId = searchParams.get('analysis');
    const waitingForLink = !!linkedId && String(report?.analysis.id) !== linkedId;
    useEffect(() => {
        if (!linkedId) return;
        let cancelled = false;
        jobsApi.analysis(linkedId)
            .then((data) => { if (!cancelled) { setReport(data); setPhase('report'); } })
            .catch((e) => { if (!cancelled) { setError(e.message); setSearchParams({}); } });
        return () => { cancelled = true; };
    }, [linkedId, setSearchParams]);

    const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

    const submit = async (e) => {
        e.preventDefault();
        const problem = validateJobForm(form, mode === 'pdf' ? file : null);
        if (problem) { setError(problem); return; }
        setError(''); setErrorCode('');
        setPhase('analyzing');
        try {
            const job = await jobsApi.create(form, mode === 'pdf' ? file : null);
            await runAnalysis(job.id);
        } catch (err) {
            setError(err.message);
            setPhase('form');
        }
    };

    const runAnalysis = async (jobId) => {
        setPhase('analyzing');
        setError('');
        try {
            const data = await jobsApi.analyze(jobId);
            setReport(data);
            setPhase('report');
            setSearchParams({ analysis: data.analysis.id });
            loadHistory();
        } catch (err) {
            setError(err.message);
            setErrorCode(err.message.includes('resume') ? 'no_resume' : '');
            setPhase(report ? 'report' : 'form');
            loadHistory();
        }
    };

    const openJob = async (item) => {
        if (!item.latest_analysis_id) { runAnalysis(item.id); return; }
        setSearchParams({ analysis: item.latest_analysis_id });
    };

    const removeJob = async (item) => {
        if (!window.confirm(`Delete "${item.title}" and its reports?`)) return;
        try {
            await jobsApi.remove(item.id);
            if (report?.job.id === item.id) { setReport(null); setPhase('form'); setSearchParams({}); }
            loadHistory(history.page);
        } catch (err) { setError(err.message); }
    };

    const newAnalysis = () => {
        setReport(null); setPhase('form'); setSearchParams({});
        setForm({ title: '', company: '', target_role: '', text: '' }); setFile(null);
    };

    return (
        <main className="pt-20 pb-12 px-4 sm:px-6 min-h-screen">
            <div className="max-w-6xl mx-auto">
                <PageHeader title="Job description analyzer"
                    subtitle="Compare your resume with a real job description: see which required skills you match, what is missing, and what to prepare next."
                    action={phase === 'report' && <button onClick={newAnalysis} className={`${secondaryBtn} px-5 py-2.5 text-sm`}>Analyse another job</button>} />

                <div className="grid grid-cols-12 gap-6">
                    <div className="col-span-12 lg:col-span-8 flex flex-col gap-6">
                        <ErrorBanner message={error} />
                        {errorCode === 'no_resume' && (
                            <Link to="/resume-upload" className={`${primaryBtn} self-start px-5 py-2.5 text-sm`}>Upload your resume</Link>
                        )}

                        {phase === 'analyzing' && <Loading title="Analysing the job description"
                            detail="Extracting requirements, normalising skills and comparing them with the evidence in your resume. This takes 5 to 20 seconds." />}
                        {waitingForLink && phase !== 'analyzing' && <Loading title="Loading report" />}

                        {phase === 'form' && !waitingForLink && (
                            <form onSubmit={submit} className={`${card} p-6 sm:p-8 flex flex-col gap-5`} noValidate>
                                <div className="grid sm:grid-cols-2 gap-4">
                                    <label className="text-sm font-bold text-on-surface">Job title *
                                        <input className={`${inputCls} mt-1.5 font-normal`} value={form.title} onChange={update('title')} placeholder="e.g. Software Development Engineer I" maxLength={150} required />
                                    </label>
                                    <label className="text-sm font-bold text-on-surface">Company
                                        <input className={`${inputCls} mt-1.5 font-normal`} value={form.company} onChange={update('company')} placeholder="Optional" maxLength={150} />
                                    </label>
                                </div>
                                <label className="text-sm font-bold text-on-surface">Target role
                                    <input className={`${inputCls} mt-1.5 font-normal`} list="role-options" value={form.target_role} onChange={update('target_role')} placeholder="Choose or type a role" maxLength={150} />
                                    <datalist id="role-options">{ROLES.map((r) => <option key={r} value={r} />)}</datalist>
                                </label>

                                <div>
                                    <div className="flex gap-1 mb-2" role="tablist">
                                        {[['paste', 'Paste text', 'content_paste'], ['pdf', 'Upload PDF', 'upload_file']].map(([k, label, icon]) => (
                                            <button type="button" key={k} role="tab" aria-selected={mode === k} onClick={() => setMode(k)}
                                                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-bold ${mode === k ? 'bg-primary-fixed text-primary' : 'text-on-surface-variant hover:bg-surface-container-low'}`}>
                                                <span className="material-symbols-outlined text-base">{icon}</span>{label}
                                            </button>
                                        ))}
                                    </div>
                                    {mode === 'paste' ? (
                                        <>
                                            <textarea className={`${inputCls} min-h-[260px] resize-y leading-relaxed`} value={form.text} onChange={update('text')}
                                                placeholder="Paste the complete job description: responsibilities, required and preferred skills, qualifications..." aria-label="Job description" maxLength={20000} />
                                            <p className="text-xs text-on-surface-variant mt-1">{form.text.length.toLocaleString()} / 20,000 characters</p>
                                        </>
                                    ) : (
                                        <label className="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-outline-variant rounded-xl py-10 cursor-pointer hover:bg-surface-container-low">
                                            <span className="material-symbols-outlined text-3xl text-primary">picture_as_pdf</span>
                                            <span className="text-sm font-bold text-on-surface">{file ? file.name : 'Choose a PDF (max 2 MB)'}</span>
                                            <span className="text-xs text-on-surface-variant">Text-based PDFs only; scanned images can't be read.</span>
                                            <input type="file" accept="application/pdf,.pdf" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] || null)} />
                                        </label>
                                    )}
                                </div>
                                <button type="submit" className={`${primaryBtn} self-start px-8 py-3`}>Analyse against my resume</button>
                            </form>
                        )}

                        {phase === 'report' && report && !waitingForLink && <AnalysisReport job={report.job} analysis={report.analysis} />}
                    </div>

                    <aside className="col-span-12 lg:col-span-4">
                        <div className={`${card} p-5`}>
                            <h2 className="font-headline font-bold text-on-surface mb-3">Previous analyses</h2>
                            {history.results.length === 0 ? (
                                <EmptyState icon="work_history" title="No analyses yet" detail="Your analysed job descriptions will appear here." />
                            ) : (
                                <ul className="flex flex-col gap-2">
                                    {history.results.map((item) => {
                                        const tone = scoreTone(item.latest_score);
                                        const active = report?.job.id === item.id;
                                        return (
                                            <li key={item.id} className={`flex items-center gap-3 p-3 rounded-xl border ${active ? 'border-primary/40 bg-primary-fixed/20' : 'border-outline-variant hover:bg-surface-container-low'}`}>
                                                <button onClick={() => openJob(item)} className="flex-1 flex items-center gap-3 text-left min-w-0">
                                                    <span className={`w-11 h-11 rounded-lg flex items-center justify-center font-semibold text-sm ${tone.bg} ${tone.text}`}>
                                                        {item.latest_score === null ? '–' : Math.round(item.latest_score)}
                                                    </span>
                                                    <span className="min-w-0">
                                                        <span className="block font-bold text-sm text-on-surface truncate">{item.title}</span>
                                                        <span className="block text-xs text-on-surface-variant truncate">{item.company || 'No company'} · {formatDate(item.created_at)}</span>
                                                    </span>
                                                </button>
                                                <button onClick={() => removeJob(item)} className="text-on-surface-variant hover:text-red-600" aria-label={`Delete ${item.title}`}>
                                                    <span className="material-symbols-outlined text-lg">delete</span>
                                                </button>
                                            </li>
                                        );
                                    })}
                                </ul>
                            )}
                            {history.pages > 1 && (
                                <div className="flex justify-between items-center mt-3 text-sm">
                                    <button disabled={history.page <= 1} onClick={() => loadHistory(history.page - 1)} className="font-bold text-primary disabled:opacity-40">Previous</button>
                                    <span className="text-on-surface-variant">Page {history.page} of {history.pages}</span>
                                    <button disabled={history.page >= history.pages} onClick={() => loadHistory(history.page + 1)} className="font-bold text-primary disabled:opacity-40">Next</button>
                                </div>
                            )}
                        </div>
                    </aside>
                </div>
            </div>
        </main>
    );
}
