import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import TechnicalReport from '../components/technical/TechnicalReport';
import { Badge, card, EmptyState, ErrorBanner, formatDate, inputCls, Loading, PageHeader, primaryBtn, scoreTone, secondaryBtn } from '../components/shared/ui';
import useSpeech from '../hooks/useSpeech';
import { jobsApi, technicalApi } from '../services/part2Api';
import { validateAnswer } from '../utils/validation';

const TYPES = [
    ['dsa', 'DSA', 'account_tree'], ['programming', 'Programming Languages', 'terminal'], ['oop', 'OOP', 'category'],
    ['dbms', 'DBMS', 'database'], ['os', 'Operating Systems', 'memory'], ['networks', 'Computer Networks', 'lan'],
    ['web', 'Web Development', 'web'], ['system_design', 'System Design', 'hub'], ['project', 'Project-based', 'folder_open'],
    ['mixed', 'Mixed Technical', 'shuffle'],
];
const VALID_TYPES = TYPES.map((t) => t[0]);

export default function TechnicalMockInterview() {
    const [searchParams] = useSearchParams();
    const [phase, setPhase] = useState('loading'); // loading | setup | starting | interview | report
    const [config, setConfig] = useState({ interview_type: 'mixed', difficulty: 'Medium', num_questions: 6, job_role: '', company: '', job_id: '' });
    const [jobs, setJobs] = useState([]);
    const [history, setHistory] = useState([]);
    const [session, setSession] = useState(null);
    const [answer, setAnswer] = useState('');
    const [busy, setBusy] = useState('');
    const [error, setError] = useState('');
    const [voiceOn, setVoiceOn] = useState(true);
    const lastSpoken = useRef(null);
    const speech = useSpeech({ onTranscript: setAnswer });

    const loadHistory = useCallback(() => technicalApi.history().then((h) => { setHistory(h.results); return h.results; }).catch(() => []), []);

    useEffect(() => {
        jobsApi.history().then((h) => setJobs(h.results)).catch(() => {});
        const type = searchParams.get('type');
        const difficulty = searchParams.get('difficulty');
        const job = searchParams.get('job');
        setConfig((c) => ({
            ...c,
            interview_type: VALID_TYPES.includes(type) ? type : c.interview_type,
            difficulty: ['Easy', 'Medium', 'Hard'].includes(difficulty) ? difficulty : c.difficulty,
            job_id: job || c.job_id,
        }));
        loadHistory().then(() => setPhase('setup'));
    }, [searchParams, loadHistory]);

    // Speak each new question once (optional voice).
    useEffect(() => {
        const q = session?.current_question;
        if (voiceOn && q && lastSpoken.current !== `${session.id}-${q.number}`) {
            lastSpoken.current = `${session.id}-${q.number}`;
            speech.speak(q.question);
        }
    }, [session, voiceOn, speech]);

    const show = (data) => {
        setSession(data);
        setPhase(data.status === 'completed' ? 'report' : 'interview');
    };

    const start = async () => {
        setError(''); setPhase('starting');
        try {
            const body = { ...config, num_questions: Number(config.num_questions), job_id: config.job_id ? Number(config.job_id) : null };
            show(await technicalApi.start(body));
            setAnswer('');
        } catch (e) { setError(e.message); setPhase('setup'); }
    };

    const submit = async () => {
        const problem = validateAnswer(answer);
        if (problem) { setError(problem); return; }
        speech.stopListening(); speech.stopSpeaking();
        setError(''); setBusy('Evaluating your answer and preparing the next question...');
        try {
            const data = await technicalApi.answer(session.id, answer);
            if (data.warning) setError(data.warning);
            setAnswer('');
            if (data.status === 'completed') loadHistory();
            show(data);
        } catch (e) { setError(e.message); } finally { setBusy(''); }
    };

    const nextQuestion = async () => {
        setError(''); setBusy('Preparing the next question...');
        try { show(await technicalApi.next(session.id)); } catch (e) { setError(e.message); } finally { setBusy(''); }
    };

    const endEarly = async () => {
        if (!window.confirm('End the interview now? The report will cover the questions you answered.')) return;
        speech.stopListening(); speech.stopSpeaking();
        setBusy('Building your report...');
        try { show(await technicalApi.end(session.id)); loadHistory(); } catch (e) { setError(e.message); } finally { setBusy(''); }
    };

    const open = async (id) => {
        setError(''); setPhase('loading');
        try { show(await technicalApi.session(id)); } catch (e) { setError(e.message); setPhase('setup'); }
    };

    const reset = () => { setSession(null); setAnswer(''); setError(''); setPhase('setup'); };

    const inProgress = history.filter((h) => h.status === 'in_progress');
    const q = session?.current_question;

    return (
        <main className="pt-20 pb-12 px-4 sm:px-6 min-h-screen">
            <div className="max-w-6xl mx-auto">
                <PageHeader title="Technical interview"
                    subtitle="An AI interviewer asks one question at a time, adapts to your answers, and scores each one on a technical rubric. Separate from the HR interview." />
                <div className="flex flex-col gap-6">
                    <ErrorBanner message={error} />
                    {(phase === 'loading' || phase === 'starting') && <Loading title={phase === 'starting' ? 'Preparing your interview' : 'Loading'} detail={phase === 'starting' ? 'Planning topics from your choices, resume and job description.' : ''} />}

                    {phase === 'setup' && (
                        <div className="grid grid-cols-12 gap-6">
                            <section className={`${card} p-6 sm:p-8 col-span-12 lg:col-span-8 flex flex-col gap-5`}>
                                {inProgress.length > 0 && (
                                    <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm flex flex-wrap items-center gap-3">
                                        <span className="flex-1">You have an unfinished interview ({inProgress[0].interview_label}, {formatDate(inProgress[0].created_at)}).</span>
                                        <button onClick={() => open(inProgress[0].id)} className="font-bold text-amber-900 underline">Resume it</button>
                                    </div>
                                )}
                                <div>
                                    <p className="text-sm font-bold text-on-surface mb-2">Interview type</p>
                                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2" role="radiogroup">
                                        {TYPES.map(([k, label, icon]) => (
                                            <button key={k} role="radio" aria-checked={config.interview_type === k} onClick={() => setConfig({ ...config, interview_type: k })}
                                                className={`flex flex-col items-center gap-1 p-3 rounded-xl border-2 text-xs font-bold text-center ${config.interview_type === k ? 'border-primary bg-primary-fixed/40 text-primary' : 'border-outline-variant text-on-surface-variant hover:border-outline-variant'}`}>
                                                <span className="material-symbols-outlined">{icon}</span>{label}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                                <div className="grid sm:grid-cols-3 gap-4">
                                    <label className="text-sm font-bold text-on-surface">Difficulty
                                        <select className={`${inputCls} mt-1.5 font-normal`} value={config.difficulty} onChange={(e) => setConfig({ ...config, difficulty: e.target.value })}>
                                            {['Easy', 'Medium', 'Hard'].map((d) => <option key={d}>{d}</option>)}
                                        </select>
                                    </label>
                                    <label className="text-sm font-bold text-on-surface">Questions
                                        <select className={`${inputCls} mt-1.5 font-normal`} value={config.num_questions} onChange={(e) => setConfig({ ...config, num_questions: e.target.value })}>
                                            {[5, 6, 8].map((n) => <option key={n} value={n}>{n}</option>)}
                                        </select>
                                    </label>
                                    <label className="text-sm font-bold text-on-surface">Job description
                                        <select className={`${inputCls} mt-1.5 font-normal`} value={config.job_id} onChange={(e) => setConfig({ ...config, job_id: e.target.value })}>
                                            <option value="">None</option>
                                            {jobs.map((j) => <option key={j.id} value={j.id}>{j.title}{j.company ? ` · ${j.company}` : ''}</option>)}
                                        </select>
                                    </label>
                                    <label className="text-sm font-bold text-on-surface">Target role
                                        <input className={`${inputCls} mt-1.5 font-normal`} value={config.job_role} maxLength={150} placeholder="e.g. Software Engineer"
                                               onChange={(e) => setConfig({ ...config, job_role: e.target.value })} />
                                    </label>
                                    <label className="text-sm font-bold text-on-surface">Company
                                        <input className={`${inputCls} mt-1.5 font-normal`} value={config.company} maxLength={150} placeholder="Optional"
                                               onChange={(e) => setConfig({ ...config, company: e.target.value })} />
                                    </label>
                                    <label className="text-sm font-bold text-on-surface flex items-center gap-2 sm:mt-7">
                                        <input type="checkbox" checked={voiceOn} onChange={(e) => setVoiceOn(e.target.checked)} disabled={!speech.supported.tts} />
                                        Read questions aloud{!speech.supported.tts && ' (not supported)'}
                                    </label>
                                </div>
                                <button onClick={start} className={`${primaryBtn} self-start px-8 py-3`}>Start technical interview</button>
                            </section>
                            <aside className={`${card} p-5 col-span-12 lg:col-span-4`}>
                                <h2 className="font-headline font-bold text-on-surface mb-3">Interview history</h2>
                                {history.length === 0 ? <EmptyState icon="history" title="No interviews yet" detail="Completed interviews and their reports appear here." /> : (
                                    <ul className="flex flex-col gap-2">
                                        {history.map((h) => {
                                            const tone = scoreTone(h.overall_score);
                                            return (
                                                <li key={h.id}>
                                                    <button onClick={() => open(h.id)} className="w-full flex items-center gap-3 p-3 rounded-xl border border-outline-variant hover:bg-surface-container-low text-left">
                                                        <span className={`w-11 h-11 rounded-lg flex items-center justify-center font-semibold text-sm ${tone.bg} ${tone.text}`}>{h.overall_score === null ? '–' : Math.round(h.overall_score)}</span>
                                                        <span className="flex-1 min-w-0"><span className="block text-sm font-bold truncate">{h.interview_label} · {h.difficulty}</span>
                                                            <span className="block text-xs text-on-surface-variant">{formatDate(h.created_at)}</span></span>
                                                        <Badge kind={h.status} />
                                                    </button>
                                                </li>
                                            );
                                        })}
                                    </ul>
                                )}
                            </aside>
                        </div>
                    )}

                    {phase === 'interview' && session && (
                        <div className="grid grid-cols-12 gap-6">
                            <div className="col-span-12 lg:col-span-8 flex flex-col gap-4">
                                <section className={`${card} p-6`}>
                                    <div className="flex items-center justify-between mb-3">
                                        <span className="text-sm font-bold text-primary">Question {Math.min(session.answered + 1, session.num_questions)} of {session.num_questions} · {session.interview_label}</span>
                                        {q && speech.supported.tts && (
                                            <button onClick={() => (speech.speaking ? speech.stopSpeaking() : speech.speak(q.question))} aria-label={speech.speaking ? 'Stop reading' : 'Read question aloud'}
                                                    className={`w-10 h-10 rounded-full flex items-center justify-center ${speech.speaking ? 'bg-primary text-white' : 'bg-surface-container-high text-on-surface-variant'}`}>
                                                <span className="material-symbols-outlined">{speech.speaking ? 'volume_up' : 'volume_down'}</span>
                                            </button>
                                        )}
                                    </div>
                                    <div className="h-1.5 bg-surface-container-high rounded-full overflow-hidden mb-5">
                                        <div className="h-full bg-primary rounded-lg transition-all" style={{ width: `${(session.answered / session.num_questions) * 100}%` }} />
                                    </div>
                                    {q ? (
                                        <>
                                            <p className="text-xs font-bold text-on-surface-variant mb-1">{q.topic} · {q.difficulty}{q.kind !== 'core' ? ' · follow-up' : ''}</p>
                                            <h2 className="font-headline text-xl font-semibold text-on-surface leading-relaxed">{q.question}</h2>
                                        </>
                                    ) : session.awaiting_question ? (
                                        <div className="flex flex-wrap items-center gap-3">
                                            <p className="text-sm text-on-surface-variant">Your answer was saved. The next question isn't ready yet.</p>
                                            <button onClick={nextQuestion} disabled={!!busy} className={`${primaryBtn} px-5 py-2 text-sm`}>Get next question</button>
                                        </div>
                                    ) : <p className="text-sm text-on-surface-variant">Evaluating...</p>}
                                </section>

                                {q && (
                                    <section className={`${card} p-6 flex flex-col gap-3`}>
                                        <label htmlFor="tech-answer" className="font-headline font-bold text-on-surface">Your answer</label>
                                        <div className="relative">
                                            <textarea id="tech-answer" value={answer} onChange={(e) => setAnswer(e.target.value)} disabled={!!busy} maxLength={6000}
                                                      className={`${inputCls} min-h-[200px] pb-14 resize-y leading-relaxed`} placeholder="Type your answer, or use the microphone..." />
                                            {speech.supported.stt && (
                                                <button onClick={() => (speech.listening ? speech.stopListening() : speech.startListening(answer))} disabled={!!busy}
                                                        aria-label={speech.listening ? 'Stop voice input' : 'Start voice input'}
                                                        className={`absolute bottom-3 right-3 w-11 h-11 rounded-full flex items-center justify-center shadow ${speech.listening ? 'bg-red-500 text-white animate-pulse' : 'bg-primary text-white'}`}>
                                                    <span className="material-symbols-outlined">{speech.listening ? 'mic_off' : 'mic'}</span>
                                                </button>
                                            )}
                                        </div>
                                        {speech.error && <p className="text-xs text-amber-800">{speech.error}</p>}
                                        {!speech.supported.stt && <p className="text-xs text-on-surface-variant">Voice input isn't available in this browser; typing works fine.</p>}
                                        <div className="flex flex-wrap items-center justify-between gap-3">
                                            <span className="text-xs text-on-surface-variant">{answer.length} / 6000</span>
                                            <div className="flex gap-2">
                                                <button onClick={endEarly} disabled={!!busy || session.answered === 0} className={`${secondaryBtn} px-5 py-2.5 text-sm`}>End interview</button>
                                                <button onClick={submit} disabled={!!busy || !answer.trim()} className={`${primaryBtn} px-6 py-2.5 text-sm`}>
                                                    {busy || (session.answered + 1 >= session.num_questions ? 'Submit and finish' : 'Submit answer')}
                                                </button>
                                            </div>
                                        </div>
                                    </section>
                                )}
                            </div>

                            <aside className={`${card} p-5 col-span-12 lg:col-span-4 max-h-[70vh] overflow-y-auto`}>
                                <h2 className="font-headline font-bold text-on-surface mb-3">Transcript</h2>
                                <ol className="flex flex-col gap-4 text-sm" aria-live="polite">
                                    {session.transcript.map((t) => (
                                        <li key={t.number}>
                                            <p className="font-bold text-on-surface">Q{t.number}. {t.question}</p>
                                            {t.answer ? <p className="text-on-surface-variant mt-1 whitespace-pre-wrap">{t.answer}</p>
                                                : <p className="text-xs text-on-surface-variant mt-1 italic">Waiting for your answer</p>}
                                        </li>
                                    ))}
                                </ol>
                                <p className="text-xs text-on-surface-variant mt-4">Scores and feedback appear in the report at the end, like a real interview.</p>
                            </aside>
                        </div>
                    )}

                    {phase === 'report' && session?.report && <TechnicalReport session={session} onNew={reset} />}
                </div>
            </div>
        </main>
    );
}
