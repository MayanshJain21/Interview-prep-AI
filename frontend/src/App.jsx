import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import TopBar from './components/shared/TopBar';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import ResumeUpload from './pages/ResumeUpload';
import McqTest from './pages/McqTest';
import AtsCheck from './pages/AtsCheck';
import HrMock from './pages/HrMock';
import CodingRound from './pages/CodingRound';
import JobDescriptionAnalyzer from './pages/JobDescriptionAnalyzer';
import LearningPath from './pages/LearningPath';
import TechnicalMockInterview from './pages/TechnicalMockInterview';
import ColdEmail from './pages/ColdEmail';

function MainApp({ setIsAuthenticated }) {
  const logout = () => {
    localStorage.removeItem('access_token');
    setIsAuthenticated(false);
    window.location.href = '/login';
  };

  return (
    <>
      <TopBar onLogout={logout} />
      <div className="relative min-h-screen bg-background">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/resume-upload" element={<ResumeUpload />} />
          <Route path="/mcq" element={<McqTest />} />
          <Route path="/ats-check" element={<AtsCheck />} />
          <Route path="/hr-interview" element={<HrMock />} />
          <Route path="/coding-round" element={<CodingRound />} />
          <Route path="/job-analyzer" element={<JobDescriptionAnalyzer />} />
          <Route path="/learning-path" element={<LearningPath />} />
          <Route path="/technical-interview" element={<TechnicalMockInterview />} />
          <Route path="/cold-email" element={<ColdEmail />} />
        </Routes>
      </div>
    </>
  );
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('access_token'));

  return (
    <BrowserRouter>
      {isAuthenticated ? (
        <MainApp setIsAuthenticated={setIsAuthenticated} />
      ) : (
        <Routes>
          <Route path="*" element={<Navigate to="/login" />} />
          <Route path="/login" element={<Login setAuth={setIsAuthenticated} />} />
        </Routes>
      )}
    </BrowserRouter>
  );
}

export default App;
