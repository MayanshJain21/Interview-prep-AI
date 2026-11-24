import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MasteryChart from '../components/learning/MasteryChart';
import AnalysisReport from '../components/jobs/AnalysisReport';
import TechnicalReport from '../components/technical/TechnicalReport';
import { groupByWeek, localISODate, validateAnswer, validateJobForm, validateRoadmapForm } from '../utils/validation';

vi.mock('../services/part2Api', () => ({
    jobsApi: { history: vi.fn(), create: vi.fn(), analyze: vi.fn(), analysis: vi.fn(), remove: vi.fn() },
    technicalApi: { history: vi.fn(), start: vi.fn(), answer: vi.fn(), next: vi.fn(), end: vi.fn(), session: vi.fn() },
    engineApi: {},
    linkTo: (l) => (l?.path ? l.path : null),
}));
import { jobsApi, technicalApi } from '../services/part2Api';
import JobDescriptionAnalyzer from '../pages/JobDescriptionAnalyzer';
import TechnicalMockInterview from '../pages/TechnicalMockInterview';

afterEach(() => { cleanup(); vi.clearAllMocks(); });
const inRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('validation helpers', () => {
    it('validates the job form', () => {
        expect(validateJobForm({ title: '', text: 'x'.repeat(100) })).toMatch(/title/);
        expect(validateJobForm({ title: 'SDE', text: 'short' })).toMatch(/full job description/);
        expect(validateJobForm({ title: 'SDE', text: '' }, { name: 'jd.docx', size: 10 })).toMatch(/PDF/);
        expect(validateJobForm({ title: 'SDE', text: 'x'.repeat(100) })).toBe('');
    });
    it('validates the roadmap form', () => {
        const today = new Date(2026, 0, 10);
        expect(validateRoadmapForm({ deadline: '2026-01-10', minutes_per_day: 60, study_days: [0] }, today)).toMatch(/after today/);
        expect(validateRoadmapForm({ deadline: '2026-02-01', minutes_per_day: 5, study_days: [0] }, today)).toMatch(/15/);
        expect(validateRoadmapForm({ deadline: '2026-02-01', minutes_per_day: 60, study_days: [] }, today)).toMatch(/study day/);
        expect(validateRoadmapForm({ deadline: '2026-02-01', minutes_per_day: 60, study_days: [1] }, today)).toBe('');
    });
    it('groups roadmap items and formats local dates', () => {
        const weeks = groupByWeek([{ id: 1, week: 2 }, { id: 2, week: 1 }, { id: 3, week: 2 }]);
        expect(weeks.map((w) => [w.week, w.items.length])).toEqual([[1, 1], [2, 2]]);
        expect(localISODate(1, new Date(2026, 11, 31))).toBe('2027-01-01');
        expect(validateAnswer('   ')).toMatch(/answer/);
    });
});

describe('report components', () => {
    it('shows unassessed skills differently from weak ones', () => {
        render(<MasteryChart rows={[{ slug: 'a', name: 'Arrays', mastery: 30 }, { slug: 'b', name: 'Graphs', mastery: null }]} />);
        expect(screen.getByLabelText('Arrays mastery')).toBeTruthy();
        expect(screen.getByLabelText('Graphs: not assessed')).toBeTruthy();
        expect(screen.getByText('not yet')).toBeTruthy();
    });

    it('renders the job report with breakdown and filters the skill table', () => {
        const analysis = {
            id: 4, overall_score: 62.5, technical_score: 55, created_at: '2026-11-24T10:00:00Z', relevant_sections: [],
            breakdown: { formula: 'overall = ...', note: 'Not a hiring probability.', components: [
                { key: 'required', label: 'Required skills', available: true, normalized_weight: 0.7, score: 60, contribution: 42, detail: '' },
                { key: 'preferred', label: 'Preferred skills', available: false, normalized_weight: 0, score: null, contribution: 0, detail: '' }] },
            skill_matches: [
                { skill: 'Python', requirement: 'Python', importance: 'required', status: 'matched', evidence: { section: 'skills', snippet: 'Python' } },
                { skill: 'System Design', requirement: 'System Design', importance: 'required', status: 'missing', evidence: null }],
            recommendations: [{ text: 'Add System Design.', source: 'rule' }], preparation_areas: [],
        };
        inRouter(<AnalysisReport job={{ id: 1, title: 'SDE', company: 'Acme', requirements_summary: {} }} analysis={analysis} />);
        expect(screen.getByLabelText('Overall compatibility: 63 out of 100')).toBeTruthy();
        expect(screen.getByText('not used', { exact: false })).toBeTruthy();
        fireEvent.click(screen.getByRole('tab', { name: /missing/ }));
        expect(screen.queryByText('Python')).toBeNull();
        expect(screen.getAllByText('System Design').length).toBeGreaterThan(0);
    });

    it('renders next preparation priorities in the technical report', () => {
        const session = { job_role: 'SDE', difficulty: 'Medium', transcript: [{ number: 1, topic: 'Processes', difficulty: 'Medium', kind: 'core',
            question: 'Process vs thread?', answer: 'x', score: 3, evaluation: { missing_concepts: ['shared memory'] } }],
            report: { overall_score: 30, verdict: 'Needs practice', interview_type: 'Operating Systems', questions_answered: 1,
                difficulty_handled: 'None yet', communication_score: 3, topic_performance: [{ topic: 'Processes', average: 3 }],
                criteria_averages: { clarity: 3 }, strengths: [], knowledge_gaps: ['Processes'], incorrect_concepts: [],
                next_priorities: [{ skill: 'Operating Systems', title: 'Learn the fundamentals of Operating Systems', reason: 'Below 40%', mastery: 30, link: {} }] } };
        inRouter(<TechnicalReport session={session} onNew={() => {}} />);
        expect(screen.getByText('Your Next Preparation Priorities')).toBeTruthy();
        expect(screen.getByText('Learn the fundamentals of Operating Systems')).toBeTruthy();
        fireEvent.click(screen.getByText('Process vs thread?'));
        expect(screen.getByText('shared memory')).toBeTruthy();
    });
});

describe('pages', () => {
    it('job analyzer: validation and API failure states', async () => {
        jobsApi.history.mockResolvedValue({ results: [], page: 1, pages: 1 });
        jobsApi.create.mockResolvedValue({ id: 9 });
        jobsApi.analyze.mockRejectedValue(new Error('Upload your resume first: the analysis compares it with this job.'));
        inRouter(<JobDescriptionAnalyzer />);
        fireEvent.click(screen.getByText('Analyse against my resume'));
        expect(screen.getByRole('alert').textContent).toMatch(/job title/);

        fireEvent.change(screen.getByPlaceholderText(/Software Development Engineer/), { target: { value: 'SDE' } });
        fireEvent.change(screen.getByLabelText('Job description'), { target: { value: 'We need Python and SQL. '.repeat(8) } });
        fireEvent.click(screen.getByText('Analyse against my resume'));
        await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/Upload your resume/));
        expect(screen.getByText('Upload your resume')).toBeTruthy();
        expect(jobsApi.create).toHaveBeenCalled();
    });

    it('technical interview: start, answer, and finish with a report', async () => {
        technicalApi.history.mockResolvedValue({ results: [] });
        jobsApi.history.mockResolvedValue({ results: [] });
        const q = (n) => ({ number: n, topic: 'Processes', difficulty: 'Medium', kind: 'core', question: `Question ${n}?`, answer: '', state: 'open' });
        technicalApi.start.mockResolvedValue({ id: 1, status: 'in_progress', num_questions: 2, answered: 0, interview_label: 'OS',
            current_question: q(1), transcript: [q(1)], awaiting_question: false });
        technicalApi.answer.mockResolvedValueOnce({ id: 1, status: 'in_progress', num_questions: 2, answered: 1, interview_label: 'OS',
            current_question: q(2), transcript: [{ ...q(1), answer: 'A1', state: 'answered' }, q(2)], awaiting_question: false });
        technicalApi.answer.mockResolvedValueOnce({ id: 1, status: 'completed', num_questions: 2, answered: 2, difficulty: 'Medium',
            transcript: [], report: { overall_score: 80, verdict: 'Interview ready', interview_type: 'OS', questions_answered: 2,
                difficulty_handled: 'Medium', communication_score: 8, topic_performance: [], criteria_averages: {}, strengths: [],
                knowledge_gaps: [], incorrect_concepts: [], next_priorities: [] } });

        inRouter(<TechnicalMockInterview />);
        await waitFor(() => screen.getByText('Start technical interview'));
        fireEvent.click(screen.getByText('Start technical interview'));
        await waitFor(() => screen.getAllByText('Question 1?'));
        fireEvent.change(screen.getByLabelText('Your answer'), { target: { value: 'A1' } });
        fireEvent.click(screen.getByText('Submit answer'));
        await waitFor(() => screen.getAllByText('Question 2?'));
        fireEvent.change(screen.getByLabelText('Your answer'), { target: { value: 'A2' } });
        fireEvent.click(screen.getByText('Submit and finish'));
        await waitFor(() => screen.getByText('Your Next Preparation Priorities'));
        expect(technicalApi.answer).toHaveBeenCalledTimes(2);
    });
});
