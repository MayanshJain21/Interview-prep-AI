import React, { useState } from 'react';
import { apiCall } from '../../api';

const field = 'w-full px-3 py-2 rounded-lg border border-outline-variant bg-surface-container-lowest text-sm text-on-surface focus:border-primary focus:ring-1 focus:ring-primary';

function CopyButton({ text, label }) {
    const [copied, setCopied] = useState(false);
    const copy = async () => {
        try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        } catch {
            setCopied(false);
        }
    };
    return (
        <button type="button" onClick={copy}
            className="px-3 py-1.5 rounded-lg bg-primary text-on-primary border border-primary text-xs font-semibold">
            {copied ? 'Copied' : label}
        </button>
    );
}

// Writes a cold email to a recruiter from the uploaded resume. Nothing is sent: the student copies it.
export default function ColdEmailCard({ defaultOpen = false, onClose, showTitle = true }) {
    const [open, setOpen] = useState(defaultOpen);
    const [form, setForm] = useState({ role: '', company: '', recipient_name: '' });
    const [email, setEmail] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

    const generate = async (e) => {
        e.preventDefault();
        if (!form.role.trim()) { setError('Enter the role you are applying for.'); return; }
        setLoading(true);
        setError('');
        try {
            setEmail(await apiCall('/cold-email', 'POST', form));
        } catch (err) {
            setError(err.message || 'Could not write the email. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <section className="rounded-xl border border-outline-variant p-5">
            <div className={`flex items-start justify-between gap-4 ${showTitle ? '' : 'hidden'}`}>
                <div>
                    <h2 className="text-base font-semibold text-on-surface">Cold email</h2>
                    <p className="text-sm text-on-surface-variant mt-0.5">A short email to a recruiter, written from your resume. Copy it and send it from your own mail.</p>
                </div>
                {!open && (
                    <button type="button" onClick={() => setOpen(true)}
                        className="shrink-0 px-3.5 py-2 rounded-lg bg-primary text-on-primary text-sm font-semibold hover:bg-on-primary-fixed-variant">
                        Write one
                    </button>
                )}
                {onClose && (
                    <button type="button" onClick={onClose} aria-label="Close"
                        className="shrink-0 w-8 h-8 inline-flex items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container-high">
                        <span className="material-symbols-outlined text-xl">close</span>
                    </button>
                )}
            </div>

            {open && (
                <form onSubmit={generate} className={`${showTitle ? 'mt-4' : ''} grid grid-cols-1 sm:grid-cols-3 gap-3`}>
                    <label className="text-xs text-on-surface-variant">Role
                        <input value={form.role} onChange={set('role')} placeholder="e.g. SDE Intern" className={`${field} mt-1`} maxLength={100} />
                    </label>
                    <label className="text-xs text-on-surface-variant">Company <span className="text-outline">(optional)</span>
                        <input value={form.company} onChange={set('company')} placeholder="e.g. Amazon" className={`${field} mt-1`} maxLength={100} />
                    </label>
                    <label className="text-xs text-on-surface-variant">Recruiter's name <span className="text-outline">(optional)</span>
                        <input value={form.recipient_name} onChange={set('recipient_name')} placeholder="e.g. Priya Sharma" className={`${field} mt-1`} maxLength={100} />
                    </label>
                    <div className="sm:col-span-3 flex items-center gap-3">
                        <button type="submit" disabled={loading}
                            className="px-3.5 py-2 rounded-lg bg-primary text-on-primary text-sm font-semibold hover:bg-on-primary-fixed-variant disabled:opacity-50">
                            {loading ? 'Writing...' : email ? 'Write again' : 'Write email'}
                        </button>
                        {error && <p role="alert" className="text-sm text-error">{error}</p>}
                    </div>
                </form>
            )}

            {email && (
                <div className="mt-4 border-t border-outline-variant pt-4 space-y-3">
                    <div className="flex items-center justify-between gap-3">
                        <p className="text-sm text-on-surface"><span className="text-on-surface-variant">Subject:</span> {email.subject}</p>
                        <CopyButton text={email.subject} label="Copy subject" />
                    </div>
                    <pre className="whitespace-pre-wrap font-[inherit] text-sm leading-relaxed text-on-surface bg-surface-container-low rounded-lg p-4 max-h-80 overflow-y-auto">{email.body}</pre>
                    <CopyButton text={`Subject: ${email.subject}\n\n${email.body}`} label="Copy email" />
                </div>
            )}
        </section>
    );
}
