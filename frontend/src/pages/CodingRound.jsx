import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { apiCall } from '../api';
import CodeEditor from '../components/coding/CodeEditor';
import CodingReport from '../components/coding/CodingReport';
import LanguagePicker from '../components/coding/LanguagePicker';
import ProblemPanel from '../components/coding/ProblemPanel';
import RoundTimer from '../components/coding/RoundTimer';
import TestConsole from '../components/coding/TestConsole';

const DIFFICULTIES = [
    { key: 'easy', label: 'Easy', detail: '2 problems · 30 min' },
    { key: 'medium', label: 'Medium', detail: '3 problems · 45 min' },
    { key: 'hard', label: 'Hard', detail: '3 problems · 60 min' },
];

const storageKey = (sid, pid, lang) => `coding:${sid}:${pid}:${lang}`;
const readStore = (key) => { try { return localStorage.getItem(key); } catch { return null; } };
const writeStore = (key, val) => { try { localStorage.setItem(key, val); } catch { /* storage full or blocked */ } };

export default function CodingRound() {
    // phase: loading -> setup -> generating -> solving -> finishing -> report
    const [phase, setPhase] = useState('loading');
    const [error, setError] = useState('');
    const [difficulty, setDifficulty] = useState('medium');
    const [defaultLang, setDefaultLang] = useState('python');
    // {lang: what to install} for languages that can't run on this setup.
    const [missing, setMissing] = useState({});
    useEffect(() => {
        apiCall('/coding/languages', 'GET')
            .then((list) => setMissing(Object.fromEntries((list || []).filter((l) => !l.available).map((l) => [l.id, l.missing]))))
            .catch(() => { /* the picker still works; errors show when code runs */ });
    }, []);
    const [jobRole, setJobRole] = useState('');
    const [company, setCompany] = useState('');
    const [companies, setCompanies] = useState([]);
    useEffect(() => {
        apiCall('/coding/companies', 'GET').then((list) => setCompanies(list || [])).catch(() => { /* field still works as free text */ });
    }, []);
    const [searchParams] = useSearchParams();
    // Opened from the learning roadmap: /coding-round?difficulty=easy&topic=hashing
    const focusTopic = searchParams.get('topic') || '';
    useEffect(() => {
        const d = searchParams.get('difficulty');
        if (DIFFICULTIES.some((x) => x.key === d)) setDifficulty(d);
    }, [searchParams]);

    const [session, setSession] = useState(null);
    const [activeIdx, setActiveIdx] = useState(0);
    const [langs, setLangs] = useState({});
    const [codes, setCodes] = useState({});
    const [outputs, setOutputs] = useState({});
    const [busy, setBusy] = useState('');
    const [hintLoading, setHintLoading] = useState(false);
    const pasteCounts = useRef({});
    const tabSwitches = useRef(0);
    const finishing = useRef(false);

    const problems = session?.problems || [];
    const problem = problems[activeIdx];

    const langOf = useCallback((p) => {
        const lang = langs[p.id] || session?.language || 'python';
        // A problem whose data can't be typed is offered in Python and JavaScript only.
        return !p.languages || p.languages.includes(lang) ? lang : 'python';
    }, [langs, session]);

    const codeOf = useCallback((p, lang) => {
        const fromState = codes[p.id]?.[lang];
        if (fromState !== undefined) return fromState;
        return readStore(storageKey(session.session_id, p.id, lang)) ?? p.saved_code?.[lang] ?? p.starter_code[lang];
    }, [codes, session]);

    const openSession = (data) => {
        setSession(data);
        setActiveIdx(0);
        setOutputs({});
        setLangs({});
        setCodes({});
        pasteCounts.current = {};
        finishing.current = false;
    };

    const finishRound = useCallback(async (auto = false) => {
        if (!session || finishing.current) return;
        if (!auto && !window.confirm('Finish the round now? Your best submission for each problem will be scored.')) return;
        finishing.current = true;
        setPhase('finishing');
        // Submit what's in the editor for problems that were never submitted, so the work counts.
        for (const p of session.problems) {
            const lang = langOf(p);
            const code = codeOf(p, lang);
            if (!p.best && code.trim() && code !== p.starter_code[lang]) {
                try {
                    await apiCall('/coding/submit', 'POST', { problem_id: p.id, language: lang, code, paste_flags: pasteCounts.current[p.id] || 0 });
                } catch { /* time may be over; the round still finishes */ }
            }
        }
        try {
            const data = await apiCall('/coding/session/finish', 'POST', { session_id: session.session_id, tab_switches: tabSwitches.current });
            session.problems.forEach((p) => Object.keys(p.starter_code).forEach((l) => {
                try { localStorage.removeItem(storageKey(session.session_id, p.id, l)); } catch { /* ignore */ }
            }));
            setSession(data);
            setPhase('report');
        } catch (err) {
            finishing.current = false;
            setError(err.message || 'Could not finish the round. Please try again.');
            setPhase('solving');
        }
    }, [session, langOf, codeOf]);

    // Resume a round in progress after a refresh.
    useEffect(() => {
        apiCall('/coding/session/active')
            .then((data) => {
                if (data.session_id) {
                    openSession(data);
                    setPhase('solving');
                } else {
                    setPhase('setup');
                }
            })
            .catch(() => setPhase('setup'));
    }, []);

    useEffect(() => {
        if (phase !== 'solving') return;
        const onHide = () => {
            if (document.hidden) {
                tabSwitches.current += 1;
                alert(`Tab switching is monitored during the round (${tabSwitches.current} so far).`);
            }
        };
        document.addEventListener('visibilitychange', onHide);
        return () => document.removeEventListener('visibilitychange', onHide);
    }, [phase]);

    const startRound = async () => {
        setPhase('generating');
        setError('');
        try {
            const data = await apiCall('/coding/session/start', 'POST', { difficulty, language: defaultLang, job_role: jobRole, topic: focusTopic, company });
            openSession(data);
            setPhase('solving');
        } catch (err) {
            setError(err.message || 'Could not start the round.');
            setPhase('setup');
        }
    };

    const updateCode = (value) => {
        const lang = langOf(problem);
        setCodes((prev) => ({ ...prev, [problem.id]: { ...prev[problem.id], [lang]: value } }));
        writeStore(storageKey(session.session_id, problem.id, lang), value);
    };

    const changeLanguage = (lang) => {
        // The code in the old language is already saved; the new one loads its saved code or the starter.
        setLangs((prev) => ({ ...prev, [problem.id]: lang }));
        setOutputs((prev) => ({ ...prev, [problem.id]: null }));
    };

    const resetCode = () => {
        const lang = langOf(problem);
        if (window.confirm('Replace your code with the starter code?')) updateCode(problem.starter_code[lang]);
    };

    const runOrSubmit = async (kind) => {
        const lang = langOf(problem);
        setBusy(kind === 'run' ? 'Running your code on the examples...' : 'Running the hidden tests...');
        setError('');
        try {
            const body = { problem_id: problem.id, language: lang, code: codeOf(problem, lang) };
            if (kind === 'submit') body.paste_flags = pasteCounts.current[problem.id] || 0;
            const res = await apiCall(`/coding/${kind}`, 'POST', body);
            if (kind === 'submit') {
                pasteCounts.current[problem.id] = 0;
                setSession((s) => ({ ...s, problems: s.problems.map((p) => (p.id === problem.id ? { ...p, best: res.best } : p)) }));
            }
            setOutputs((prev) => ({ ...prev, [problem.id]: { ...res, kind } }));
        } catch (err) {
            setOutputs((prev) => ({ ...prev, [problem.id]: { kind: 'run', error: err.message, results: [] } }));
        } finally {
            setBusy('');
        }
    };

    const showHint = async () => {
        setHintLoading(true);
        try {
            const res = await apiCall('/coding/hint', 'POST', { problem_id: problem.id });
            setSession((s) => ({ ...s, problems: s.problems.map((p) => (p.id === problem.id ? { ...p, hints: res.hints } : p)) }));
        } catch (err) {
            setError(err.message);
        } finally {
            setHintLoading(false);
        }
    };

    const card = 'bg-surface-container-lowest rounded-2xl border border-outline-variant shadow-sm';

    return (
        <main className="pt-20 pb-12 px-4 sm:px-6 min-h-screen">
            <div className={`${phase === 'solving' ? 'max-w-[1440px]' : 'max-w-6xl'} mx-auto flex flex-col gap-6`}>
                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-5 py-3 text-sm flex items-center gap-2">
                        <span className="material-symbols-outlined text-lg">error</span>{error}
                    </div>
                )}

                {(phase === 'loading' || phase === 'generating' || phase === 'finishing') && (
                    <div className={`${card} flex flex-col items-center justify-center gap-3 h-64 text-center px-6`}>
                        <span className="material-symbols-outlined text-primary text-3xl animate-spin">sync</span>
                        <p className="font-headline font-bold text-on-surface">
                            {phase === 'loading' && 'Loading...'}
                            {phase === 'generating' && 'Preparing your problems'}
                            {phase === 'finishing' && 'Reviewing your solutions'}
                        </p>
                        {phase === 'generating' && <p className="text-sm text-on-surface-variant max-w-md">Each problem is written and then checked by running its reference solution against its tests. This usually takes 30 seconds to 2 minutes.</p>}
                        {phase === 'finishing' && <p className="text-sm text-on-surface-variant">The AI is reviewing each solution for complexity and code quality.</p>}
                    </div>
                )}

                {phase === 'setup' && (
                    <div className={`${card} p-6 sm:p-10 flex flex-col`}>
                        <h1 className="text-3xl sm:text-[2.5rem] leading-tight font-semibold text-on-surface mb-3">Coding round</h1>
                        <p className="text-on-surface-variant max-w-xl mb-8">Solve timed DSA problems in Python, JavaScript, C++, C, Java or Go. Your code is run against hidden tests, then the AI reviews its complexity and quality.</p>

                        <div className="w-full max-w-xl flex flex-col gap-6 text-left">
                            <div>
                                <p className="text-sm font-bold text-on-surface mb-2">Difficulty</p>
                                <div className="grid grid-cols-3 gap-3" role="radiogroup">
                                    {DIFFICULTIES.map((d) => (
                                        <button key={d.key} role="radio" aria-checked={difficulty === d.key} onClick={() => setDifficulty(d.key)}
                                            className={`rounded-xl p-3 border-2 text-center transition-all ${difficulty === d.key ? 'border-primary bg-primary-fixed/40' : 'border-outline-variant hover:border-outline-variant'}`}>
                                            <span className="block font-bold text-on-surface">{d.label}</span>
                                            <span className="block text-xs text-on-surface-variant mt-0.5">{d.detail}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div className="flex flex-wrap items-end gap-6">
                                <div>
                                    <p className="text-sm font-bold text-on-surface mb-2">Starting language</p>
                                    <LanguagePicker value={defaultLang} onChange={setDefaultLang} missing={missing} />
                                </div>
                                <div className="flex-1 min-w-[200px]">
                                    <label htmlFor="role" className="text-sm font-bold text-on-surface">Target role <span className="font-normal text-on-surface-variant">(optional)</span></label>
                                    <input id="role" value={jobRole} onChange={(e) => setJobRole(e.target.value)} placeholder="e.g. Backend Developer"
                                        className="mt-2 w-full px-4 py-2.5 bg-surface-container-lowest rounded-lg border border-outline-variant focus:border-primary focus:ring-1 focus:ring-primary text-on-surface" />
                                </div>
                            </div>
                            <div>
                                <label htmlFor="company" className="text-sm font-bold text-on-surface">Company <span className="font-normal text-on-surface-variant">(optional)</span></label>
                                <input id="company" list="company-list" value={company} onChange={(e) => setCompany(e.target.value)}
                                    placeholder="e.g. Amazon, Google, TCS" autoComplete="off"
                                    className="mt-2 w-full sm:w-80 px-4 py-2.5 bg-surface-container-lowest rounded-lg border border-outline-variant focus:border-primary focus:ring-1 focus:ring-primary text-on-surface" />
                                <datalist id="company-list">
                                    {companies.map((c) => <option key={c.slug} value={c.name}>{c.count} questions</option>)}
                                </datalist>
                                <p className="mt-1.5 text-xs text-on-surface-variant">
                                    Problems are real interview questions{company ? ` asked at ${company}` : ' that companies ask most often'}, rewritten with fresh tests.
                                </p>
                            </div>
                            {focusTopic && <p className="text-sm text-primary font-bold">From your learning roadmap: the first problem will focus on {focusTopic}.</p>}
                            <p className="text-xs text-on-surface-variant">You can switch language at any time during the round; your code is saved for each language.</p>
                        </div>

                        <button onClick={startRound} className="mt-8 self-start bg-primary text-on-primary px-6 py-3 rounded-lg font-semibold hover:bg-on-primary-fixed-variant">
                            Start round
                        </button>
                    </div>
                )}

                {phase === 'solving' && problem && (
                    <>
                        <div className={`${card} px-4 py-3 flex flex-wrap items-center gap-3`}>
                            <div className="flex gap-2 flex-1 flex-wrap" role="tablist">
                                {problems.map((p, i) => (
                                    <button key={p.id} role="tab" aria-selected={i === activeIdx} onClick={() => setActiveIdx(i)}
                                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold ${i === activeIdx ? 'bg-primary-fixed text-primary' : 'text-on-surface-variant hover:bg-surface-container-low'}`}>
                                        <span className={`w-2 h-2 rounded-full ${!p.best ? 'bg-outline-variant' : p.best.passed === p.best.total ? 'bg-green-500' : 'bg-amber-500'}`} />
                                        Problem {i + 1}
                                    </button>
                                ))}
                            </div>
                            <RoundTimer endsAt={session.ends_at} serverNow={session.server_now} onExpire={() => finishRound(true)} />
                            <button onClick={() => finishRound(false)} className="px-5 py-2 rounded-lg bg-primary text-white text-sm font-bold shadow">Finish Round</button>
                        </div>

                        <div className="grid grid-cols-12 gap-6">
                            <div className="col-span-12 lg:col-span-5 lg:max-h-[calc(100vh-200px)] flex">
                                <ProblemPanel key={problem.id} problem={problem} onHint={showHint} hintLoading={hintLoading} />
                            </div>
                            <div className="col-span-12 lg:col-span-7 flex flex-col gap-4">
                                <div className={`${card} p-4 flex flex-col gap-3`}>
                                    <div className="flex flex-wrap items-center justify-between gap-3">
                                        <LanguagePicker value={langOf(problem)} onChange={changeLanguage} disabled={!!busy}
                                            options={problem.languages} missing={missing} />
                                        <div className="flex items-center gap-2">
                                            <button onClick={resetCode} disabled={!!busy} className="px-3 py-2 rounded-full text-sm font-bold text-on-surface-variant hover:bg-surface-container-low" title="Reset to starter code">
                                                <span className="material-symbols-outlined text-base align-middle">restart_alt</span>
                                            </button>
                                            <button onClick={() => runOrSubmit('run')} disabled={!!busy} className="px-5 py-2 rounded-full bg-surface-container-high text-on-surface text-sm font-bold disabled:opacity-60 flex items-center gap-1">
                                                <span className="material-symbols-outlined text-base">play_arrow</span>Run
                                            </button>
                                            <button onClick={() => runOrSubmit('submit')} disabled={!!busy} className="px-5 py-2 rounded-lg bg-primary text-white text-sm font-bold shadow disabled:opacity-60 flex items-center gap-1">
                                                <span className="material-symbols-outlined text-base">send</span>Submit
                                            </button>
                                        </div>
                                    </div>
                                    <CodeEditor
                                        key={`${problem.id}-${langOf(problem)}`}
                                        language={langOf(problem)}
                                        value={codeOf(problem, langOf(problem))}
                                        onChange={updateCode}
                                        onLargePaste={() => { pasteCounts.current[problem.id] = (pasteCounts.current[problem.id] || 0) + 1; }}
                                    />
                                </div>
                                <div className={`${card} max-h-80 overflow-y-auto`} aria-live="polite">
                                    <TestConsole output={outputs[problem.id]} busy={busy} />
                                </div>
                            </div>
                        </div>
                    </>
                )}

                {phase === 'report' && session?.report && (
                    <CodingReport session={session} onNewRound={() => { setSession(null); setPhase('setup'); }} />
                )}
            </div>
        </main>
    );
}
