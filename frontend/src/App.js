import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import './App.css';
import LandingPage from './components/LandingPage';
import SetupWizard from './components/SetupWizard';
import Dashboard from './components/Dashboard';
import DataManager from './components/DataManager';
import ChatInterface from './components/ChatInterface';
import ConstitutionLedger from './components/ConstitutionLedger';
import ProjectList from './components/ProjectList';
import Settings from './components/Settings';
import AdminConsole from './components/AdminConsole';
import HelpPage from './components/HelpPage';
import Guide from './components/Guide';
import AboutUs from './components/AboutUs';
import Footer from './components/Footer';
import { apiAvailable, NO_PUBLIC_API_MESSAGE } from './api';

function ConsoleHeader() {
  return (
    <header className="bg-gray-900 border-b border-green-500/30 shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex items-center justify-between">
          <Link to="/console" className="flex items-center space-x-3 group">
            <div className="flex items-center space-x-2">
              <span className="text-green-400 font-mono text-lg animate-pulse">&gt;</span>
              <h1 className="text-xl md:text-2xl font-bold text-white font-mono tracking-tight">
                neighborhood<span className="text-green-400">_</span>ai
              </h1>
            </div>
            <span className="px-2 py-0.5 bg-cyan-500/20 text-cyan-400 text-xs font-mono rounded border border-cyan-500/30">
              console
            </span>
          </Link>

          <nav className="flex items-center space-x-2">
            <Link to="/console" className="text-gray-400 hover:text-green-400 px-3 py-2 rounded font-mono text-sm transition-colors">
              ~/projects
            </Link>
            <Link to="/guide" className="text-purple-400 hover:text-purple-300 px-3 py-2 rounded font-mono text-sm transition-colors border border-purple-500/30 hover:bg-purple-500/10">
              guide
            </Link>
            <Link to="/console/new" className="bg-green-500 text-gray-900 px-4 py-2 rounded font-mono text-sm font-semibold hover:bg-green-400 transition-colors flex items-center space-x-1">
              <span>+ new</span>
            </Link>
            <Link to="/" className="text-gray-500 hover:text-gray-300 px-3 py-2 rounded font-mono text-sm transition-colors">
              cd ..
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
}

function ConsoleLayout({ children }) {
  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      <ConsoleHeader />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full">
        {children}
      </main>
      <Footer />
    </div>
  );
}

// The console manages an assistant, and the public site has no API behind it
// (src/api.js). Every console page says so plainly instead of failing request
// by request.
function NotOpenYet() {
  return (
    <div className="max-w-2xl mx-auto bg-gray-900 rounded-lg border border-gray-700 p-8 font-mono">
      <p className="text-green-400 text-sm mb-4">$ connect --api</p>
      <h2 className="text-xl font-bold text-white mb-4">not open to the public yet</h2>
      <p className="text-gray-300 text-sm leading-relaxed mb-4">{NO_PUBLIC_API_MESSAGE}</p>
      <p className="text-gray-400 text-sm leading-relaxed mb-6">
        The console manages an assistant that runs on hardware its community controls, and it
        is used on that machine.
      </p>
      <Link to="/guide" className="text-purple-400 hover:text-purple-300 text-sm">
        read the guide &rarr;
      </Link>
    </div>
  );
}

function Console({ children }) {
  return <ConsoleLayout>{apiAvailable ? children : <NotOpenYet />}</ConsoleLayout>;
}

function App() {
  return (
    <Router>
      <Routes>
        {/* Landing page */}
        <Route path="/" element={<LandingPage />} />

        {/* Guide page (standalone) */}
        <Route path="/guide" element={<Guide />} />

        {/* About Us page (standalone) */}
        <Route path="/about" element={<AboutUs />} />

        {/* Console routes */}
        <Route path="/console" element={<Console><ProjectList /></Console>} />
        <Route path="/console/new" element={<Console><SetupWizard /></Console>} />
        <Route path="/console/projects/:projectId" element={<Console><Dashboard /></Console>} />
        <Route path="/console/projects/:projectId/data" element={<Console><DataManager /></Console>} />
        <Route path="/console/projects/:projectId/ledger" element={<Console><ConstitutionLedger /></Console>} />
        <Route path="/console/projects/:projectId/chat" element={<Console><ChatInterface /></Console>} />
        <Route path="/console/projects/:projectId/settings" element={<Console><Settings /></Console>} />
        <Route path="/console/projects/:projectId/admin" element={<Console><AdminConsole /></Console>} />
        <Route path="/console/projects/:projectId/help" element={<Console><HelpPage /></Console>} />
      </Routes>
    </Router>
  );
}

export default App;
