import React, { useEffect, useRef, useState } from 'react';
import { LANGUAGES, LANGUAGE_IDS, languageLabel } from './languages';

function LangIcon({ lang }) {
    const l = LANGUAGES[lang] || LANGUAGES.python;
    return (
        <span className={`w-6 h-6 rounded-md text-[10px] font-semibold flex items-center justify-center ${l.className}`}>
            {l.badge}
        </span>
    );
}

// options: languages this problem supports. missing: {lang: what to install} for ones that can't run here.
export default function LanguagePicker({ value, onChange, disabled, options = LANGUAGE_IDS, missing = {} }) {
    const [open, setOpen] = useState(false);
    const ref = useRef(null);

    useEffect(() => {
        const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
        document.addEventListener('mousedown', close);
        return () => document.removeEventListener('mousedown', close);
    }, []);

    return (
        <div className="relative" ref={ref}>
            <button
                type="button"
                disabled={disabled}
                onClick={() => setOpen(!open)}
                className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-lg bg-surface-container-high text-sm font-bold text-on-surface disabled:opacity-60"
                aria-haspopup="listbox"
                aria-expanded={open}
            >
                <LangIcon lang={value} />
                {languageLabel(value)}
                <span className="material-symbols-outlined text-base">expand_more</span>
            </button>
            {open && (
                <ul role="listbox" className="absolute z-20 mt-1 w-56 bg-surface-container-lowest border border-outline-variant rounded-xl shadow-lg py-1">
                    {options.map((lang) => {
                        const unavailable = missing[lang];
                        return (
                            <li key={lang}>
                                <button
                                    type="button"
                                    role="option"
                                    aria-selected={lang === value}
                                    aria-disabled={!!unavailable}
                                    disabled={!!unavailable}
                                    title={unavailable ? `Needs ${unavailable}` : undefined}
                                    onClick={() => { onChange(lang); setOpen(false); }}
                                    className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-surface-container-low disabled:opacity-50 disabled:cursor-not-allowed ${lang === value ? 'font-bold text-primary' : 'text-on-surface'}`}
                                >
                                    <LangIcon lang={lang} />
                                    <span className="flex-1">{languageLabel(lang)}</span>
                                    {unavailable && <span className="text-[10px] text-on-surface-variant">not installed</span>}
                                </button>
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
}
