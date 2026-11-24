import { useCallback, useEffect, useRef, useState } from 'react';

// Browser speech: text-to-speech for questions and speech-to-text for answers.
// Both are optional; `supported` tells the UI what to show.
export default function useSpeech({ onTranscript } = {}) {
    const Recognition = typeof window !== 'undefined' ? (window.SpeechRecognition || window.webkitSpeechRecognition) : null;
    const supported = {
        tts: typeof window !== 'undefined' && 'speechSynthesis' in window,
        stt: !!Recognition,
    };
    const [speaking, setSpeaking] = useState(false);
    const [listening, setListening] = useState(false);
    const [error, setError] = useState('');
    const recognitionRef = useRef(null);
    const baseTextRef = useRef('');
    const transcriptCb = useRef(onTranscript);
    useEffect(() => { transcriptCb.current = onTranscript; }, [onTranscript]);

    const speak = useCallback((text) => {
        if (!supported.tts || !text) return;
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.onstart = () => setSpeaking(true);
        u.onend = () => setSpeaking(false);
        u.onerror = () => setSpeaking(false);
        window.speechSynthesis.speak(u);
    }, [supported.tts]);

    const stopSpeaking = useCallback(() => {
        if (supported.tts) window.speechSynthesis.cancel();
        setSpeaking(false);
    }, [supported.tts]);

    const stopListening = useCallback(() => {
        recognitionRef.current?.stop();
        setListening(false);
    }, []);

    const startListening = useCallback((currentText = '') => {
        if (!Recognition) {
            setError('Voice input is not supported in this browser. Use Chrome or Edge, or type your answer.');
            return;
        }
        setError('');
        baseTextRef.current = currentText;
        const rec = new Recognition();
        rec.continuous = true;
        rec.interimResults = true;
        rec.lang = 'en-US';
        rec.onstart = () => setListening(true);
        rec.onend = () => setListening(false);
        rec.onerror = (e) => {
            setListening(false);
            setError(e.error === 'not-allowed' ? 'Microphone access was denied. Allow it in your browser, or type your answer.'
                : `Voice input stopped (${e.error}). You can keep typing.`);
        };
        rec.onresult = (event) => {
            let text = '';
            for (let i = 0; i < event.results.length; i++) text += event.results[i][0].transcript;
            const base = baseTextRef.current;
            transcriptCb.current?.(base + (base && text ? ' ' : '') + text);
        };
        try {
            rec.start();
            recognitionRef.current = rec;
        } catch {
            setError('Could not start the microphone.');
        }
    }, [Recognition]);

    useEffect(() => () => {
        recognitionRef.current?.stop();
        if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel();
    }, []);

    return { supported, speaking, listening, error, speak, stopSpeaking, startListening, stopListening };
}
