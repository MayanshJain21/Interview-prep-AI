import React, { useEffect, useRef, useState } from 'react';
import { apiCall } from '../../api';

const SCRIPT_SRC = 'https://accounts.google.com/gsi/client';

function loadScript() {
    if (window.google?.accounts?.id) return Promise.resolve();
    return new Promise((resolve, reject) => {
        let s = document.querySelector(`script[src="${SCRIPT_SRC}"]`);
        if (!s) {
            s = document.createElement('script');
            s.src = SCRIPT_SRC;
            s.async = true;
            s.defer = true;
            document.head.appendChild(s);
        }
        s.addEventListener('load', () => resolve(), { once: true });
        s.addEventListener('error', () => reject(new Error('Could not load Google sign-in.')), { once: true });
    });
}

// "Sign in with Google". Shown only when the server has a Google client ID configured.
// Google gives the browser a signed ID token; the backend verifies it and returns our own login token.
export default function GoogleSignIn({ onSignedIn, onError, onUnavailable }) {
    const [clientId, setClientId] = useState(null);
    const [busy, setBusy] = useState(false);
    const box = useRef(null);
    const handlers = useRef({ onSignedIn, onError, onUnavailable });
    handlers.current = { onSignedIn, onError, onUnavailable };

    useEffect(() => {
        apiCall('/auth/google/config').then((r) => setClientId(r?.client_id || null)).catch(() => {
            setClientId(null);
            handlers.current.onUnavailable?.();  // the backend can't be reached
        });
    }, []);

    useEffect(() => {
        if (!clientId) return;
        let cancelled = false;
        loadScript().then(() => {
            if (cancelled || !box.current) return;
            window.google.accounts.id.initialize({
                client_id: clientId,
                callback: async ({ credential }) => {
                    setBusy(true);
                    try {
                        const res = await apiCall('/auth/google', 'POST', { credential });
                        handlers.current.onSignedIn(res);
                    } catch (err) {
                        handlers.current.onError(err.message || 'Google sign-in failed. Please try again.');
                    } finally {
                        setBusy(false);
                    }
                },
                ux_mode: 'popup',
                cancel_on_tap_outside: true,
            });
            window.google.accounts.id.renderButton(box.current, {
                type: 'standard', theme: 'outline', size: 'large', text: 'continue_with', shape: 'rectangular',
                logo_alignment: 'center', width: Math.min(400, box.current.offsetWidth || 400),
            });
        }).catch((err) => handlers.current.onError(err.message));
        return () => { cancelled = true; };
    }, [clientId]);

    if (!clientId) return null;
    return (
        <div className="mb-6">
            <div ref={box} className={`flex justify-center min-h-[44px] ${busy ? 'opacity-50 pointer-events-none' : ''}`} aria-busy={busy} />
            {busy && <p className="mt-2 text-center text-xs text-on-surface-variant">Signing you in...</p>}
            <div className="mt-6 flex items-center gap-3 text-xs text-outline" aria-hidden="true">
                <span className="h-px flex-1 bg-outline-variant" />or use your email<span className="h-px flex-1 bg-outline-variant" />
            </div>
        </div>
    );
}
