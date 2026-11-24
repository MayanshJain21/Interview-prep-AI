import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiCall } from '../api';
import { Loading, PageHeader } from '../components/shared/ui';
import ColdEmailCard from '../components/dashboard/ColdEmailCard';

// Writes a cold email to a recruiter from the uploaded resume. Nothing is sent from here.
export default function ColdEmail() {
    const [hasResume, setHasResume] = useState(null);

    useEffect(() => {
        apiCall('/resume/parsed').then(() => setHasResume(true)).catch(() => setHasResume(false));
    }, []);

    return (
        <main className="pt-24 pb-16 px-4 sm:px-6 max-w-[75rem] mx-auto">
            <PageHeader title="Cold email"
                subtitle="A short email to a recruiter or hiring manager, written from your resume. Copy it and send it from your own mail." />
            {hasResume === null ? (
                <Loading title="Checking your resume" />
            ) : hasResume ? (
                <div className="max-w-3xl bg-surface-container-lowest rounded-xl">
                    <ColdEmailCard defaultOpen showTitle={false} />
                </div>
            ) : (
                <div className="max-w-3xl rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
                    <p className="text-on-surface">The email is written from your resume, so upload it first.</p>
                    <Link to="/resume-upload" className="inline-block mt-4 px-4 py-2.5 rounded-lg bg-primary text-on-primary text-sm font-semibold hover:bg-on-primary-fixed-variant">
                        Upload resume
                    </Link>
                </div>
            )}
        </main>
    );
}
