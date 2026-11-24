import React, { useEffect, useRef, useState } from 'react';

// endsAt and serverNow come from the backend; the offset corrects for a wrong PC clock.
export default function RoundTimer({ endsAt, serverNow, onExpire }) {
    const offset = useRef(new Date(serverNow).getTime() - Date.now());
    const fired = useRef(false);
    const remainingMs = () => new Date(endsAt).getTime() - (Date.now() + offset.current);
    const [left, setLeft] = useState(remainingMs());

    useEffect(() => {
        const id = setInterval(() => {
            const ms = remainingMs();
            setLeft(ms);
            if (ms <= 0 && !fired.current) {
                fired.current = true;
                onExpire();
            }
        }, 1000);
        return () => clearInterval(id);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [endsAt]);

    const secs = Math.max(0, Math.floor(left / 1000));
    const mm = String(Math.floor(secs / 60)).padStart(2, '0');
    const ss = String(secs % 60).padStart(2, '0');
    const urgent = secs <= 300;

    return (
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-bold tabular-nums text-sm ${urgent ? 'bg-red-50 text-red-700' : 'bg-surface-container-high text-on-surface'}`}
             aria-live="polite" aria-label={`Time left ${mm} minutes ${ss} seconds`}>
            <span className="material-symbols-outlined text-base">timer</span>
            {mm}:{ss}
        </div>
    );
}
