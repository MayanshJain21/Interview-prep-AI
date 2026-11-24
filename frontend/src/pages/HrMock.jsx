import React, { useState, useEffect, useRef } from 'react';
import { apiCall } from '../api';

const TIPS = [
    { icon: 'crisis_alert', title: 'Talking too much', desc: "If you're still talking after 2 minutes, you've lost them. Practice keeping answers tight and to the point." },
    { icon: 'sentiment_dissatisfied', title: 'Badmouthing past employers', desc: "Even if your last boss was terrible, keep it professional." },
    { icon: 'help', title: 'Not asking any questions', desc: "No questions signals you're not that interested in the role. So to signal interest, try to ask 2-3 questions to the interviewer." },
    { icon: 'volume_off', title: 'Underselling yourself', desc: "Being humble is great, but this isn't the time. Own your wins, make sure to tell them about your achievements and accomplishments." },
];

const VERDICT_STYLES = {
    'Interview ready': 'bg-green-100/60 text-green-800 border-green-200',
    'Almost there': 'bg-amber-100/60 text-amber-800 border-amber-200',
    'Needs practice': 'bg-red-100/60 text-red-800 border-red-200',
};

function scoreColor(score) {
    if (score >= 7) return 'bg-green-100/60 text-green-800 border-green-200';
    if (score >= 5) return 'bg-amber-100/60 text-amber-800 border-amber-200';
    return 'bg-red-100/60 text-red-800 border-red-200';
}

function PointList({ title, icon, items }) {
    if (!items || items.length === 0) return null;
    return (
        <div>
            <h4 className="font-headline text-base font-bold text-on-surface flex items-center gap-2 mb-2">
                <span className="material-symbols-outlined text-primary text-xl">{icon}</span>
                {title}
            </h4>
            <ul className="list-disc pl-6 space-y-1 text-on-surface text-sm leading-relaxed">
                {items.map((item, i) => <li key={i}>{item}</li>)}
            </ul>
        </div>
    );
}

export default function HrMock() {
    // phase: 'start' -> 'interview' -> 'report'
    const [phase, setPhase] = useState('start');
    const [jobRole, setJobRole] = useState('');
    const [session, setSession] = useState(null); // { session_id, question_number, total_questions, stage, question }
    const [report, setReport] = useState(null);
    const [openTurn, setOpenTurn] = useState(null);
    const [userAnswer, setUserAnswer] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [isRecording, setIsRecording] = useState(false);
    const [, setTabSwitches] = useState(0);  // the updater callback counts switches and warns
    const [useVoice, setUseVoice] = useState(true);

    const recognitionRef = useRef(null);
    const textBeforeRecordingRef = useRef('');

    const speakText = (text, toggle = false) => {
        if (!window.speechSynthesis) return;
        if (toggle && isSpeaking) {
            window.speechSynthesis.cancel();
            setIsSpeaking(false);
            return;
        }
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.onstart = () => setIsSpeaking(true);
        utterance.onend = () => setIsSpeaking(false);
        window.speechSynthesis.speak(utterance);
    };

    const stopRecording = () => {
        recognitionRef.current?.stop();
        setIsRecording(false);
    };

    const showQuestion = (data) => {
        setSession(data);
        setUserAnswer('');
        if (useVoice) speakText(data.question);
    };

    const startInterview = async () => {
        setIsLoading(true);
        setError('');
        setReport(null);
        setTabSwitches(0);
        try {
            const data = await apiCall('/hr/session/start', 'POST', { job_role: jobRole });
            showQuestion(data);
            setPhase('interview');
        } catch (err) {
            setError(err.message || 'Failed to start the interview.');
        } finally {
            setIsLoading(false);
        }
    };

    const submitUserAnswer = async () => {
        if (!userAnswer.trim() || !session) return;
        if (isRecording) stopRecording();
        window.speechSynthesis?.cancel();
        setIsLoading(true);
        setError('');
        try {
            const data = await apiCall('/hr/session/answer', 'POST', {
                session_id: session.session_id,
                answer: userAnswer,
            });
            if (data.done) {
                setReport(data);
                setOpenTurn(null);
                setPhase('report');
            } else {
                showQuestion(data);
            }
        } catch (err) {
            // The backend saves nothing on failure, so the same answer can be resubmitted.
            setError(err.message || 'Failed to submit your answer. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    const resetInterview = () => {
        window.speechSynthesis?.cancel();
        setPhase('start');
        setSession(null);
        setReport(null);
        setUserAnswer('');
        setError('');
    };

    const toggleRecording = () => {
        if (isRecording) {
            stopRecording();
            return;
        }
        textBeforeRecordingRef.current = userAnswer;
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            alert("Speech recognition not supported in this browser. Please use Chrome or Edge.");
            return;
        }
        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onstart = () => setIsRecording(true);

        recognition.onresult = (event) => {
            let speechTranscript = '';
            for (let i = 0; i < event.results.length; ++i) {
                speechTranscript += event.results[i][0].transcript;
            }
            const initialText = textBeforeRecordingRef.current;
            setUserAnswer(initialText + (initialText && speechTranscript ? " " : "") + speechTranscript);
        };

        recognition.onerror = (event) => {
            if (event.error === 'not-allowed') {
                alert("Microphone access denied. Please allow microphone permissions in your browser.");
            } else if (event.error === 'network') {
                alert("Network error. Speech recognition requires an internet connection.");
            } else {
                alert(`Speech recognition error: ${event.error}`);
            }
            setIsRecording(false);
        };

        recognition.onend = () => setIsRecording(false);

        try {
            recognition.start();
            recognitionRef.current = recognition;
        } catch (err) {
            console.error("Recognition start failed:", err);
        }
    };

    useEffect(() => {
        const stopAudioOnVisibilityChange = () => {
            if (document.hidden && window.speechSynthesis) {
                window.speechSynthesis.cancel();
                setIsSpeaking(false);
            }
        };
        document.addEventListener('visibilitychange', stopAudioOnVisibilityChange);
        return () => {
            document.removeEventListener('visibilitychange', stopAudioOnVisibilityChange);
            window.speechSynthesis?.cancel();
            recognitionRef.current?.stop();
        };
    }, []);

    useEffect(() => {
        if (phase !== 'interview') return;

        const handleVisibilityChange = () => {
            if (document.hidden) {
                setTabSwitches(prev => {
                    const newCount = prev + 1;
                    if (newCount >= 3) {
                        alert("Warning: Multiple tab switches detected. Please stay on this page.");
                    } else {
                        alert(`Warning: Tab switching is monitored. Warning ${newCount}/3`);
                    }
                    return newCount;
                });
            }
        };

        document.addEventListener('visibilitychange', handleVisibilityChange);
        return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
    }, [phase]);

    const card = "bg-surface-container-lowest rounded-2xl p-8 shadow-sm border border-outline-variant";
    const primaryBtn = "bg-primary text-on-primary rounded-lg font-semibold transition-colors hover:bg-on-primary-fixed-variant disabled:opacity-50";
    const progress = session ? ((session.question_number - 1) / session.total_questions) * 100 : 0;

    return (
        <main className="pt-20 pb-12 px-8 min-h-screen">
            <section className="flex-1 grid grid-cols-12 gap-8 max-w-6xl mx-auto w-full">

                <div className="col-span-12 lg:col-span-8 flex flex-col gap-8">
                    {error && (
                        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-5 py-3 text-sm flex items-center gap-2">
                            <span className="material-symbols-outlined text-lg">error</span>
                            {error}
                        </div>
                    )}

                    {phase === 'start' && (
                        <div className="bg-surface-container-lowest rounded-2xl p-10  border border-outline-variant flex flex-col">
                            <h1 className="text-3xl sm:text-[2.5rem] leading-tight font-semibold text-on-surface mb-3">HR interview</h1>
                            <p className="text-on-surface-variant text-base max-w-xl mb-8">
                                A 6-question interview based on your resume. Each question builds on your previous answers,
                                and you get a full report at the end.
                            </p>
                            <div className="w-full max-w-md text-left mb-8">
                                <label htmlFor="job-role" className="text-sm font-bold text-on-surface">Target role <span className="font-normal text-on-surface-variant">(optional)</span></label>
                                <input
                                    id="job-role"
                                    type="text"
                                    value={jobRole}
                                    onChange={(e) => setJobRole(e.target.value)}
                                    placeholder="e.g. Backend Developer"
                                    className="mt-2 w-full px-4 py-3 bg-surface-container-lowest rounded-lg border border-outline-variant focus:border-primary focus:ring-1 focus:ring-primary text-on-surface"
                                    disabled={isLoading}
                                />
                            </div>
                            <button onClick={startInterview} disabled={isLoading} className={`${primaryBtn} self-start px-6 py-3 flex items-center gap-2`}>
                                {isLoading && <span className="material-symbols-outlined text-lg animate-spin">sync</span>}
                                {isLoading ? 'Preparing your interview...' : 'Start interview'}
                            </button>
                        </div>
                    )}

                    {phase === 'interview' && session && (
                        <>
                            <div className={`${card} relative overflow-hidden`}>
                                <div className="flex items-center justify-between mb-3">
                                    <span className="text-sm font-bold text-primary">
                                        Question {session.question_number} of {session.total_questions} · {session.stage}
                                    </span>
                                    <button
                                        onClick={() => speakText(session.question, true)}
                                        className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${isSpeaking ? 'bg-primary text-white animate-pulse' : 'bg-surface-container-high text-on-surface-variant'}`}
                                        title={isSpeaking ? "Stop Speaking" : "Speak Question"}
                                    >
                                        <span className="material-symbols-outlined">{isSpeaking ? 'volume_up' : 'volume_down'}</span>
                                    </button>
                                </div>
                                <div className="h-1.5 bg-surface-container-high rounded-full overflow-hidden mb-5">
                                    <div className="h-full bg-primary rounded-lg transition-all duration-500" style={{ width: `${progress}%` }}></div>
                                </div>
                                <h2 className="font-headline text-xl font-semibold text-on-surface leading-relaxed">"{session.question}"</h2>
                            </div>

                            <div className={`${card} flex flex-col gap-4`}>
                                <h3 className="font-headline text-lg font-bold text-on-surface">Your Answer</h3>
                                <div className="relative">
                                    <textarea
                                        className="w-full min-h-[220px] p-5 pb-16 bg-surface-container-lowest rounded-lg border border-outline-variant focus:border-primary focus:ring-1 focus:ring-primary text-on-surface text-base leading-relaxed transition-all resize-none"
                                        placeholder="Type or speak your answer here..."
                                        value={userAnswer}
                                        onChange={(e) => setUserAnswer(e.target.value)}
                                        disabled={isLoading}
                                    ></textarea>
                                    <button
                                        onClick={toggleRecording}
                                        disabled={isLoading}
                                        className={`absolute bottom-4 right-4 w-12 h-12 rounded-full flex items-center justify-center shadow-lg transition-all z-10 ${isRecording ? 'bg-red-500 text-white animate-pulse scale-110' : 'bg-primary text-white hover:scale-105'}`}
                                        title={isRecording ? 'Stop Recording' : 'Start Recording'}
                                    >
                                        <span className="material-symbols-outlined">{isRecording ? 'mic_off' : 'mic'}</span>
                                    </button>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="text-xs text-on-surface-variant font-medium">{userAnswer.length} characters</span>
                                    <button
                                        onClick={submitUserAnswer}
                                        disabled={isLoading || !userAnswer.trim()}
                                        className={`${primaryBtn} px-8 py-3 text-sm flex items-center gap-2`}
                                    >
                                        {isLoading
                                            ? (session.question_number >= session.total_questions ? 'Preparing your report...' : 'Interviewer is thinking...')
                                            : (session.question_number >= session.total_questions ? 'Finish Interview' : 'Submit Answer')}
                                        {!isLoading && <span className="material-symbols-outlined text-sm">send</span>}
                                    </button>
                                </div>
                            </div>
                        </>
                    )}

                    {phase === 'report' && report && (
                        <>
                            <div className={`${card} flex flex-col gap-6`}>
                                <div className="flex flex-wrap items-center gap-5 border-b border-outline-variant pb-6">
                                    <div className="w-24 h-24 bg-primary-fixed rounded-2xl flex flex-col items-center justify-center text-primary shadow-sm">
                                        <span className="font-semibold text-3xl leading-none">{report.overall_score}</span>
                                        <span className="text-xs font-bold opacity-70 mt-1">/ 100</span>
                                    </div>
                                    <div className="flex-1 min-w-[200px]">
                                        <h2 className="font-headline text-2xl font-semibold text-on-surface">Interview Report</h2>
                                        {report.job_role && <p className="text-on-surface-variant text-sm mt-0.5">Target role: {report.job_role}</p>}
                                        {report.report?.verdict && (
                                            <span className={`inline-block mt-2 px-3 py-1 rounded-full text-xs font-bold border ${VERDICT_STYLES[report.report.verdict] || ''}`}>
                                                {report.report.verdict}
                                            </span>
                                        )}
                                    </div>
                                </div>
                                {report.report?.summary && (
                                    <p className="text-on-surface text-base leading-relaxed">{report.report.summary}</p>
                                )}
                                <div className="grid sm:grid-cols-2 gap-6">
                                    <PointList title="What went well" icon="thumb_up" items={report.report?.strengths} />
                                    <PointList title="What to work on" icon="trending_up" items={report.report?.improvements} />
                                </div>
                            </div>

                            <div className={`${card} flex flex-col gap-3`}>
                                <h3 className="font-headline text-lg font-bold text-on-surface mb-1">Question by question</h3>
                                {report.turns.map((turn) => {
                                    const isOpen = openTurn === turn.question_number;
                                    return (
                                        <div key={turn.question_number} className="border border-outline-variant rounded-xl overflow-hidden">
                                            <button
                                                onClick={() => setOpenTurn(isOpen ? null : turn.question_number)}
                                                className="w-full flex items-center gap-4 p-4 text-left hover:bg-surface-container-low transition-colors"
                                            >
                                                <span className={`flex-shrink-0 w-12 h-12 rounded-xl border flex items-center justify-center font-semibold ${scoreColor(turn.score)}`}>
                                                    {turn.score}<span className="text-[10px] opacity-70">/10</span>
                                                </span>
                                                <span className="flex-1 min-w-0">
                                                    <span className="block text-xs font-bold text-primary">Q{turn.question_number} · {turn.stage}</span>
                                                    <span className={`block text-sm text-on-surface ${isOpen ? '' : 'truncate'}`}>{turn.question}</span>
                                                </span>
                                                <span className="material-symbols-outlined text-on-surface-variant">{isOpen ? 'expand_less' : 'expand_more'}</span>
                                            </button>
                                            {isOpen && (
                                                <div className="px-4 pb-5 pt-1 flex flex-col gap-4 border-t border-outline-variant">
                                                    <div>
                                                        <h5 className="text-xs font-bold text-on-surface-variant mb-1 mt-3">Your answer</h5>
                                                        <p className="text-sm text-on-surface leading-relaxed whitespace-pre-wrap">{turn.answer}</p>
                                                    </div>
                                                    {turn.feedback && (
                                                        <div>
                                                            <h5 className="text-xs font-bold text-on-surface-variant mb-1">Feedback</h5>
                                                            <p className="text-sm text-on-surface leading-relaxed">{turn.feedback}</p>
                                                        </div>
                                                    )}
                                                    <div className="grid sm:grid-cols-2 gap-4">
                                                        <PointList title="Strengths" icon="check_circle" items={turn.strengths} />
                                                        <PointList title="Improve" icon="build" items={turn.improvements} />
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>

                            <div className="flex justify-end gap-3">
                                <button onClick={() => window.location.href = '/dashboard'} className="bg-surface-container text-on-surface px-6 py-2.5 rounded-full font-bold border border-outline-variant text-sm">
                                    Dashboard
                                </button>
                                <button onClick={resetInterview} className="bg-primary text-white px-6 py-2.5 rounded-lg font-bold shadow-lg text-sm">
                                    New Interview
                                </button>
                            </div>
                        </>
                    )}
                </div>

                <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
                    <div className="bg-surface-container-lowest rounded-2xl p-6 border border-outline-variant">
                        <h2 className="text-base font-semibold text-on-surface">Settings</h2>
                        <div className="flex items-start justify-between gap-4 py-4 mt-2 mb-6 border-y border-outline-variant">
                            <div>
                                <p id="voice-label" className="text-sm font-semibold text-on-surface">Voice</p>
                                <p className="text-sm text-on-surface-variant">Questions are read aloud and you answer by microphone.</p>
                            </div>
                            <button
                                type="button"
                                role="switch"
                                aria-checked={useVoice}
                                aria-labelledby="voice-label"
                                onClick={() => setUseVoice(!useVoice)}
                                className={`mt-0.5 w-10 h-6 shrink-0 rounded-full relative transition-colors ${useVoice ? 'bg-primary' : 'bg-outline-variant'}`}
                            >
                                <span className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-all ${useVoice ? 'left-5' : 'left-1'}`}></span>
                            </button>
                        </div>

                        <h2 className="text-base font-semibold text-on-surface mb-3">Common mistakes</h2>
                        <ul className="space-y-4">
                            {TIPS.map((tip) => (
                                <li key={tip.icon}>
                                    <p className="text-sm font-semibold text-on-surface">{tip.title}</p>
                                    <p className="text-sm text-on-surface-variant leading-relaxed mt-0.5">{tip.desc}</p>
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>

            </section>
        </main>
    );
}
