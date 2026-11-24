import React, { useEffect, useId, useRef, useState } from 'react';

// A dropdown that matches the site: white list, the hovered or keyboard-focused option in the primary
// colour. Works with the keyboard (arrows, Home/End, Enter, Escape, Tab) like a native select.
// `options` are strings, or {value, label, hint} where the hint shows on the right (e.g. "0-1 yrs").
const norm = (o) => (typeof o === 'string' ? { value: o, label: o } : o);

export default function Select({ value, options, onChange, disabled, className = '', buttonClassName = 'py-2', label }) {
    const items = options.map(norm);
    const index = Math.max(0, items.findIndex((o) => o.value === value));
    const [open, setOpen] = useState(false);
    const [active, setActive] = useState(index);
    const ref = useRef(null);
    const listRef = useRef(null);
    const id = useId();
    const current = items[index];

    useEffect(() => {
        if (!open) return undefined;
        const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
        document.addEventListener('mousedown', close);
        return () => document.removeEventListener('mousedown', close);
    }, [open]);

    useEffect(() => {
        if (open) listRef.current?.children[active]?.scrollIntoView({ block: 'nearest' });
    }, [open, active]);

    const openList = () => {
        setActive(index);
        setOpen(true);
    };
    const pick = (i) => {
        onChange(items[i].value);
        setOpen(false);
    };

    const onKeyDown = (e) => {
        if (disabled) return;
        if (!open) {
            if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) { e.preventDefault(); openList(); }
            return;
        }
        if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(items.length - 1, i + 1)); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(0, i - 1)); }
        else if (e.key === 'Home') { e.preventDefault(); setActive(0); }
        else if (e.key === 'End') { e.preventDefault(); setActive(items.length - 1); }
        else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(active); }
        else if (e.key === 'Escape' || e.key === 'Tab') setOpen(false);
    };

    return (
        <div className={`relative ${className}`} ref={ref}>
            <button type="button" disabled={disabled} onClick={() => (open ? setOpen(false) : openList())} onKeyDown={onKeyDown}
                aria-haspopup="listbox" aria-expanded={open} aria-controls={`${id}-list`}
                aria-label={label ? `${label}: ${current?.label}` : undefined}
                aria-activedescendant={open ? `${id}-${active}` : undefined}
                className={`w-full flex items-center justify-between gap-2 px-3 rounded-lg border bg-surface-container-lowest text-sm text-on-surface text-left disabled:opacity-60 ${buttonClassName} ${open ? 'border-primary ring-1 ring-primary' : 'border-outline-variant hover:border-primary'}`}>
                <span className="truncate">{current?.label}</span>
                <span className="flex items-center gap-2 shrink-0">
                    {current?.hint && <span className="text-xs text-on-surface-variant">{current.hint}</span>}
                    <span className={`material-symbols-outlined text-lg text-on-surface-variant transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true">expand_more</span>
                </span>
            </button>
            {open && (
                <ul role="listbox" id={`${id}-list`} ref={listRef} tabIndex={-1}
                    className="absolute z-30 mt-1.5 w-full min-w-max max-h-72 overflow-y-auto rounded-xl border border-outline-variant bg-surface-container-lowest p-1 shadow-[0_12px_32px_-16px_rgba(20,32,34,0.35)]">
                    {items.map((opt, i) => {
                        const selected = i === index;
                        const isActive = i === active;
                        return (
                            <li key={opt.value} id={`${id}-${i}`} role="option" aria-selected={selected}
                                onMouseEnter={() => setActive(i)} onMouseDown={(e) => { e.preventDefault(); pick(i); }}
                                className={`flex items-center justify-between gap-4 px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors ${isActive ? 'bg-primary text-on-primary' : 'text-on-surface'} ${selected && !isActive ? 'font-semibold' : ''}`}>
                                <span className="flex items-center gap-2">
                                    {opt.label}
                                    {selected && <span className="material-symbols-outlined text-base" aria-hidden="true">check</span>}
                                </span>
                                {opt.hint && <span className={`text-xs ${isActive ? 'text-on-primary-container' : 'text-on-surface-variant'}`}>{opt.hint}</span>}
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
}
