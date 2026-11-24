import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

// Grouped by what the student is doing, not by how the app is built.
const NAV = [
    { label: 'Dashboard', to: '/dashboard' },
    {
        label: 'Resume', items: [
            { label: 'My resume', to: '/resume-upload', note: 'Upload and parse your PDF' },
            { label: 'ATS check', to: '/ats-check', note: 'How screening software reads it' },
            { label: 'Job analyzer', to: '/job-analyzer', note: 'Match it against a job description' },
        ],
    },
    {
        label: 'Practice', items: [
            { label: 'MCQ tests', to: '/mcq', note: 'Quick checks per skill' },
            { label: 'Coding round', to: '/coding-round', note: 'Timed DSA problems' },
        ],
    },
    {
        label: 'Interviews', items: [
            { label: 'HR interview', to: '/hr-interview', note: 'Behavioural questions, with voice' },
            { label: 'Technical interview', to: '/technical-interview', note: 'Adaptive questions by topic' },
        ],
    },
    { label: 'Learning path', to: '/learning-path' },
    { label: 'Cold email', to: '/cold-email', icon: 'mail' },
];

const isIn = (entry, path) => (entry.to ? entry.to === path : entry.items.some((i) => i.to === path));

function useOutsideClose(open, close) {
    const ref = useRef(null);
    useEffect(() => {
        if (!open) return undefined;
        const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) close(); };
        const onKey = (e) => { if (e.key === 'Escape') close(); };
        document.addEventListener('mousedown', onDown);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('mousedown', onDown);
            document.removeEventListener('keydown', onKey);
        };
    }, [open, close]);
    return ref;
}

const linkBase = 'relative h-14 inline-flex items-center gap-1 px-3 text-sm transition-colors';
// The active section is marked by a teal rule sitting on the bar's bottom edge.
const activeRule = 'after:absolute after:left-3 after:right-3 after:-bottom-px after:h-[2px] after:bg-primary';

function Group({ entry, path, openLabel, setOpenLabel }) {
    const open = openLabel === entry.label;
    const ref = useOutsideClose(open, () => setOpenLabel(null));
    const active = isIn(entry, path);
    return (
        <div className="relative" ref={ref}>
            <button
                type="button"
                aria-expanded={open}
                aria-haspopup="menu"
                onClick={() => setOpenLabel(open ? null : entry.label)}
                className={`${linkBase} ${active ? `text-on-surface font-semibold ${activeRule}` : 'text-on-surface-variant hover:text-on-surface'}`}
            >
                {entry.label}
                <span className={`material-symbols-outlined text-base transition-transform ${open ? 'rotate-180' : ''}`}>expand_more</span>
            </button>
            {open && (
                <div role="menu" className="absolute left-0 top-full mt-px w-72 bg-surface-container-lowest border border-outline-variant rounded-xl p-1.5 z-50">
                    {entry.items.map((item) => (
                        <Link
                            key={item.to}
                            to={item.to}
                            role="menuitem"
                            onClick={() => setOpenLabel(null)}
                            className={`block px-3 py-2.5 rounded-lg hover:bg-surface-container-low ${item.to === path ? 'bg-primary-fixed' : ''}`}
                        >
                            <span className={`block text-sm ${item.to === path ? 'font-semibold text-primary' : 'text-on-surface'}`}>{item.label}</span>
                            <span className="block text-xs text-on-surface-variant mt-0.5">{item.note}</span>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    );
}

export default function TopBar({ onLogout }) {
    const { pathname } = useLocation();
    const [openLabel, setOpenLabel] = useState(null);
    const [mobileOpen, setMobileOpen] = useState(false);
    const [accountOpen, setAccountOpen] = useState(false);
    const accountRef = useOutsideClose(accountOpen, () => setAccountOpen(false));

    // Close every menu after navigating.
    const [lastPath, setLastPath] = useState(pathname);
    if (lastPath !== pathname) {
        setLastPath(pathname);
        setOpenLabel(null);
        setMobileOpen(false);
        setAccountOpen(false);
    }

    return (
        <header className="fixed top-0 inset-x-0 z-40 px-4 sm:px-6 bg-surface/95 backdrop-blur-sm border-b border-outline-variant">
            <div className="max-w-6xl mx-auto h-14 flex items-center gap-6">
                <Link to="/dashboard" className="flex items-center gap-2.5 text-[18.75px] font-semibold tracking-tight text-on-surface whitespace-nowrap">
                    <span className="w-[12.5px] h-[12.5px] rounded-sm bg-accent rotate-45" aria-hidden="true" />
                    PeakCV
                </Link>

                <nav className="hidden md:flex items-center" aria-label="Main">
                    {NAV.map((entry) => (entry.to ? (
                        <Link key={entry.to} to={entry.to}
                            className={`${linkBase} ${entry.to === pathname ? `text-on-surface font-semibold ${activeRule}` : 'text-on-surface-variant hover:text-on-surface'}`}>
                            {entry.icon && <span className="material-symbols-outlined text-[18px]" aria-hidden="true">{entry.icon}</span>}{entry.label}
                        </Link>
                    ) : (
                        <Group key={entry.label} entry={entry} path={pathname} openLabel={openLabel} setOpenLabel={setOpenLabel} />
                    )))}
                </nav>

                <div className="ml-auto flex items-center gap-1">
                    <div className="relative" ref={accountRef}>
                        <button type="button" onClick={() => setAccountOpen(!accountOpen)} aria-expanded={accountOpen} aria-haspopup="menu"
                            aria-label="Account" className="w-9 h-9 inline-flex items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface">
                            <span className="material-symbols-outlined">account_circle</span>
                        </button>
                        {accountOpen && (
                            <div role="menu" className="absolute right-0 top-full mt-2 w-44 bg-surface-container-lowest border border-outline-variant rounded-xl p-1.5 z-50">
                                <button type="button" role="menuitem" onClick={onLogout}
                                    className="w-full text-left px-3 py-2 rounded-lg text-sm text-on-surface hover:bg-surface-container-low">
                                    Log out
                                </button>
                            </div>
                        )}
                    </div>
                    <button type="button" onClick={() => setMobileOpen(!mobileOpen)} aria-expanded={mobileOpen} aria-label="Menu"
                        className="md:hidden w-9 h-9 inline-flex items-center justify-center rounded-full text-on-surface hover:bg-surface-container-high">
                        <span className="material-symbols-outlined">{mobileOpen ? 'close' : 'menu'}</span>
                    </button>
                </div>
            </div>

            {mobileOpen && (
                <nav className="md:hidden -mx-4 sm:-mx-6 border-t border-outline-variant bg-surface px-4 sm:px-6 pb-4 max-h-[calc(100vh-3.5rem)] overflow-y-auto" aria-label="Main">
                    {NAV.map((entry) => (entry.to ? (
                        <Link key={entry.to} to={entry.to}
                            className={`block py-3 border-b border-outline-variant/60 text-[15px] ${entry.to === pathname ? 'font-semibold text-primary' : 'text-on-surface'}`}>
                            <span className="inline-flex items-center gap-2">{entry.icon && <span className="material-symbols-outlined text-[18px]" aria-hidden="true">{entry.icon}</span>}{entry.label}</span>
                        </Link>
                    ) : (
                        <div key={entry.label} className="py-3 border-b border-outline-variant/60">
                            <p className="text-xs text-on-surface-variant mb-1">{entry.label}</p>
                            {entry.items.map((item) => (
                                <Link key={item.to} to={item.to}
                                    className={`block py-1.5 text-[15px] ${item.to === pathname ? 'font-semibold text-primary' : 'text-on-surface'}`}>
                                    {item.label}
                                </Link>
                            ))}
                        </div>
                    )))}
                </nav>
            )}
        </header>
    );
}
