import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiCall } from '../api';
import GoogleSignIn from '../components/shared/GoogleSignIn';

// The same four stages as the dashboard journey, so the first screen already explains the product.
const STEPS = [
    { name: 'Resume', text: 'Upload it once; every test and interview is tailored to it.' },
    { name: 'Practice', text: 'MCQ tests and timed coding rounds with real interview questions.' },
    { name: 'Interviews', text: 'HR and technical mock interviews that adapt to your answers.' },
    { name: 'Plan', text: 'A day-by-day learning path that updates after every attempt.' },
];

const field = 'mt-1.5 block w-full h-12 px-4 rounded-lg border border-outline-variant bg-surface-container-lowest text-[15px] text-on-surface placeholder:text-outline focus:border-primary focus:ring-1 focus:ring-primary';

function Mark({ className = '' }) {
    return <span className={`inline-block w-3 h-3 rounded-sm bg-accent rotate-45 ${className}`} aria-hidden="true" />;
}

export default function Login({ setAuth }) {
    const [isLoginMode, setIsLoginMode] = useState(true);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [name, setName] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [errorMessage, setErrorMessage] = useState(null);
    const [serverDown, setServerDown] = useState(false);
    const navigate = useNavigate();

    const signedIn = (response) => {
        localStorage.setItem('access_token', response.tokens.access);
        setAuth(true);
        navigate('/dashboard');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setErrorMessage(null);
        const endpoint = isLoginMode ? '/auth/login' : '/auth/signup';
        const payload = isLoginMode ? { email, password } : { email, password, name };
        try {
            signedIn(await apiCall(endpoint, 'POST', payload));
        } catch (err) {
            setErrorMessage(err.message);
        } finally {
            setIsLoading(false);
        }
    };

    const toggleMode = () => {
        setIsLoginMode(!isLoginMode);
        setErrorMessage(null);
    };

    return (
        <div className="min-h-screen flex bg-background">
            {/* Brand panel: desktop only */}
            <aside className="hidden lg:flex w-[44%] max-w-[640px] flex-col justify-between bg-primary text-on-primary px-14 py-12">
                <p className="flex items-center gap-3 text-[22px] font-semibold tracking-tight">
                    <Mark className="w-[14px] h-[14px]" />PeakCV
                </p>
                <div>
                    <h2 className="text-[2.1rem] leading-tight font-semibold max-w-md">Get placement-ready, one step at a time.</h2>
                    <ol className="mt-10 space-y-6 max-w-md">
                        {STEPS.map((s, i) => (
                            <li key={s.name} className="flex gap-4">
                                <span className="shrink-0 w-7 h-7 rounded-full border border-on-primary/40 text-sm flex items-center justify-center">{i + 1}</span>
                                <div>
                                    <p className="font-semibold">{s.name}</p>
                                    <p className="text-sm text-on-primary-container mt-0.5 leading-relaxed">{s.text}</p>
                                </div>
                            </li>
                        ))}
                    </ol>
                </div>
                <p className="text-sm text-on-primary-container">Built for students preparing for campus placements.</p>
            </aside>

            {/* Form */}
            <main className="flex-1 flex items-center justify-center px-5 py-10 sm:px-8">
                <div className="w-full max-w-[400px]">
                    <p className="lg:hidden flex items-center gap-2.5 text-xl font-semibold tracking-tight text-on-surface mb-10">
                        <Mark />PeakCV
                    </p>

                    <h1 className="text-[1.9rem] leading-tight font-semibold text-on-surface">
                        {isLoginMode ? 'Welcome back' : 'Create your account'}
                    </h1>
                    <p className="mt-2 text-on-surface-variant">
                        {isLoginMode ? 'Log in to continue your preparation.' : 'It takes less than a minute.'}
                    </p>

                    <div className="mt-8">
                        {serverDown && (
                            <div role="alert" className="mb-6 px-4 py-3 rounded-lg border border-amber-200 bg-amber-50 text-sm text-amber-900">
                                Can't reach the PeakCV server. If you are running it locally, start the backend
                                with <code className="font-mono text-[13px]">python manage.py runserver</code> and refresh.
                            </div>
                        )}
                        {errorMessage && (
                            <div role="alert" className="mb-6 px-4 py-3 rounded-lg border border-red-200 bg-red-50 text-sm text-red-800">
                                {errorMessage}
                            </div>
                        )}

                        <GoogleSignIn onSignedIn={signedIn} onError={setErrorMessage} onUnavailable={() => setServerDown(true)} />

                        <form className="space-y-5" onSubmit={handleSubmit}>
                            {!isLoginMode && (
                                <label className="block text-sm font-medium text-on-surface">Name
                                    <input className={field} placeholder="Your full name" type="text" autoComplete="name"
                                        value={name} onChange={(e) => setName(e.target.value)} required />
                                </label>
                            )}
                            <label className="block text-sm font-medium text-on-surface">Email
                                <input className={field} placeholder="you@college.edu" type="email" autoComplete="email"
                                    value={email} onChange={(e) => setEmail(e.target.value)} required />
                            </label>
                            <label className="block text-sm font-medium text-on-surface">Password
                                <span className="relative block">
                                    <input className={`${field} pr-12`} placeholder={isLoginMode ? 'Your password' : 'At least 8 characters'}
                                        type={showPassword ? 'text' : 'password'} autoComplete={isLoginMode ? 'current-password' : 'new-password'}
                                        value={password} onChange={(e) => setPassword(e.target.value)} required minLength={isLoginMode ? undefined : 8} />
                                    <button type="button" onClick={() => setShowPassword(!showPassword)}
                                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                                        className="absolute right-2 top-1/2 -translate-y-1/2 mt-[3px] w-9 h-9 inline-flex items-center justify-center rounded-md text-on-surface-variant hover:text-on-surface">
                                        <span className="material-symbols-outlined text-xl">{showPassword ? 'visibility_off' : 'visibility'}</span>
                                    </button>
                                </span>
                            </label>

                            <button type="submit" disabled={isLoading}
                                className="w-full h-12 rounded-lg bg-primary text-on-primary border border-primary text-[15px] font-semibold disabled:opacity-60">
                                {isLoading ? 'Please wait...' : isLoginMode ? 'Log in' : 'Create account'}
                            </button>
                        </form>

                        <p className="mt-8 text-center text-sm text-on-surface-variant">
                            {isLoginMode ? "Don't have an account? " : 'Already have an account? '}
                            <button type="button" onClick={toggleMode} className="plain font-semibold text-primary hover:underline underline-offset-4">
                                {isLoginMode ? 'Create one' : 'Log in'}
                            </button>
                        </p>
                    </div>
                </div>
            </main>
        </div>
    );
}
