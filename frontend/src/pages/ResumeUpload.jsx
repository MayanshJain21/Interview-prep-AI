import React, { useState, useEffect } from 'react';
import { apiCall } from '../api';
import { useNavigate } from 'react-router-dom';
import { groupSkills } from '../utils/skillGroups';

export default function ResumeUpload() {
    const [selectedFile, setSelectedFile] = useState(null);
    const [isUploading, setIsUploading] = useState(false);
    const [resumeData, setResumeData] = useState(null);
    const [errorMessage, setErrorMessage] = useState(null);
    const navigate = useNavigate();

    useEffect(() => {
        apiCall('/resume/parsed')
            .then(response => {
                if (response && response.parsed_data) {
                    setResumeData(response.parsed_data);
                }
            })
            .catch(() => console.log('No prior resume'));
    }, []);

    const handleFileSelect = (e) => {
        const file = e.target.files[0];
        if (file) setSelectedFile(file);
    };

    const uploadResume = async () => {
        if (!selectedFile) return;

        setIsUploading(true);
        setErrorMessage(null);

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const response = await apiCall('/resume/upload', 'POST', formData);
            setResumeData(response.data);
        } catch (err) {
            setErrorMessage(err.message);
        } finally {
            setIsUploading(false);
        }
    };

    const deleteResume = async () => {
        const confirmed = confirm('Delete resume and ALL associated data (MCQ scores, ATS results, HR history)?');
        if (!confirmed) return;

        try {
            await apiCall('/resume/delete', 'DELETE');
            setResumeData(null);
            setSelectedFile(null);
        } catch (err) {
            setErrorMessage(err.message);
        }
    };

    const hasResume = !!resumeData;
    const skills = resumeData?.skills || [];
    const hasSkills = skills.length > 0;
    const difficultyLevel = resumeData?.difficulty_level || 'Medium';

    const fileStatusLabel = selectedFile
        ? selectedFile.name
        : hasResume
            ? 'Current resume'
            : 'No Resume Uploaded';

    const fileStatusDetail = hasResume
        ? `Level detected: ${difficultyLevel}`
        : 'Upload a PDF to get started.';

    const browseLabel = selectedFile ? "Choose another file" : "Choose PDF";
    const uploadLabel = isUploading ? 'Reading your resume...' : 'Upload and analyse';

    return (
        <main className="pt-24 px-4 sm:px-6 pb-16 min-h-screen max-w-[75rem] mx-auto">
            <header className="mb-12 max-w-4xl">
                <h2 className="text-3xl sm:text-[2.5rem] leading-tight font-semibold text-on-surface mb-3">Your resume</h2>
                <p className="text-on-surface-variant text-lg leading-relaxed max-w-2xl">Upload your resume once. Its skills and projects are used to tailor your tests, interviews and learning path.</p>
            </header>

            <div className="grid grid-cols-12 gap-8 items-start">
                <div className="col-span-12 lg:col-span-8">
                    <section className="bg-surface-container-lowest rounded-xl p-10 border-2 border-dashed border-outline-variant hover:border-primary/40 transition-all flex flex-col items-center justify-center min-h-[400px] relative overflow-hidden group">
                        <div className="relative z-10 flex flex-col items-center text-center w-full">
                            <div className="w-20 h-20 bg-primary-fixed flex items-center justify-center rounded-full mb-6 group-hover:scale-110 transition-transform duration-300 shadow-sm">
                                <span className="material-symbols-outlined text-primary text-4xl">cloud_upload</span>
                            </div>

                            <h3 className="text-2xl font-bold text-on-surface mb-2 headline">Upload a new resume</h3>
                            <p className="text-on-surface-variant mb-8 font-medium">PDF, up to 5 MB</p>

                            <input type="file" id="resume-upload" accept=".pdf" onChange={handleFileSelect} className="hidden" />

                            <div className="flex gap-4 items-center mb-10">
                                <label htmlFor="resume-upload" className="px-6 py-3 rounded-lg bg-primary text-on-primary border border-primary cursor-pointer font-semibold">
                                    {browseLabel}
                                </label>

                                {selectedFile && (
                                    <button onClick={uploadResume} disabled={isUploading} className="px-8 py-3 bg-primary text-white rounded-xl font-bold shadow-lg transition-all">
                                        {uploadLabel}
                                    </button>
                                )}
                            </div>
                            {errorMessage && <p className="text-error bg-error-container p-2 rounded-lg mt-4 w-full text-left font-bold">{errorMessage}</p>}

                            <p className="mt-8 text-sm text-on-surface-variant">
                                Text-based PDFs only. Your resume is visible only to your account.
                            </p>
                        </div>
                    </section>

                    <div className="mt-8 flex gap-6">
                        <div className="flex-1 bg-surface-container-low rounded-xl p-6 flex items-center gap-4 border border-outline-variant">
                            <div className="w-12 h-12 bg-white rounded-lg flex items-center justify-center shadow-sm">
                                <span className="material-symbols-outlined text-primary">picture_as_pdf</span>
                            </div>
                            <div>
                                <p className="text-sm font-bold text-on-surface">{fileStatusLabel}</p>
                                <p className="text-xs text-on-surface-variant">{fileStatusDetail}</p>
                            </div>
                            {hasResume && <>
                                <button className="ml-auto px-3 py-2 rounded-lg bg-primary text-on-primary border border-primary text-sm font-semibold" onClick={() => navigate('/dashboard')}>Back to dashboard</button>
                                <button className="text-error text-sm font-bold bg-error-container p-2 rounded-lg ml-2" onClick={deleteResume}>
                                    <span className="material-symbols-outlined text-sm align-middle mr-1">delete</span>Delete
                                </button>
                            </>}
                        </div>
                    </div>
                </div>

                <div className="col-span-12 lg:col-span-4 space-y-8">
                    <section className="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant">
                        <div className="flex items-baseline justify-between mb-4">
                            <h3 className="text-lg font-semibold">Skills found</h3>
                            {hasSkills && <span className="text-sm text-on-surface-variant">{skills.length}</span>}
                        </div>

                        {hasSkills ? (
                            <div className="space-y-4">
                                {groupSkills(skills).map((group) => (
                                    <div key={group.name}>
                                        <p className="text-xs font-semibold text-on-surface-variant mb-1.5">
                                            {group.name} <span className="font-normal text-outline">{group.skills.length}</span>
                                        </p>
                                        <ul className="flex flex-wrap gap-1.5" aria-label={group.name}>
                                            {group.skills.map((skill) => (
                                                <li key={skill} className="px-2.5 py-1 rounded-md border border-outline-variant bg-surface-container-low text-[13px] leading-tight text-on-surface">
                                                    {skill}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="h-32 flex items-center justify-center rounded-xl bg-surface-container-low text-on-surface-variant text-center">
                                Upload your resume to see the skills found in it.
                            </div>
                        )}
                    </section>
                </div>
            </div>
        </main>
    );
}
