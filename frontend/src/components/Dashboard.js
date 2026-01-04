import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api';
import {
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  CogIcon,
  CircleStackIcon,
  ArrowPathIcon,
  CommandLineIcon,
  ServerIcon,
  CpuChipIcon,
  RocketLaunchIcon,
  BeakerIcon,
  PaintBrushIcon,
  QuestionMarkCircleIcon,
  ArrowLeftIcon,
  CodeBracketIcon,
  XMarkIcon,
  ExclamationTriangleIcon,
  PlayIcon
} from '@heroicons/react/24/outline';

function Dashboard() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showConfigEditor, setShowConfigEditor] = useState(false);
  const [configContent, setConfigContent] = useState('');
  const [savingConfig, setSavingConfig] = useState(false);
  const [configError, setConfigError] = useState(null);
  const [pendingSources, setPendingSources] = useState([]);
  const [activeJobs, setActiveJobs] = useState([]);

  const loadProjectData = useCallback(async () => {
    try {
      const [projectRes, statsRes, jobsRes] = await Promise.all([
        api.get(`/api/projects/${projectId}`),
        api.get(`/api/projects/${projectId}/stats`),
        api.get('/api/admin/jobs')
      ]);

      setProject(projectRes.data);
      setStats(statsRes.data);

      // Find sources that haven't been synced (no documents and status not 'synced')
      const sources = projectRes.data.data_sources || [];
      const pending = sources.filter(s => {
        const hasNoDocuments = !s.document_count || s.document_count === 0;
        const isNotSynced = s.status !== 'synced' && s.status !== 'error';
        return hasNoDocuments && isNotSynced && s.enabled;
      });
      setPendingSources(pending);

      // Find active jobs for this project
      const jobs = (jobsRes.data.jobs || []).filter(
        j => j.project_id === projectId && (j.status === 'running' || j.status === 'pending')
      );
      setActiveJobs(jobs);
    } catch (error) {
      console.error('Error loading project:', error);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadProjectData();
    // Poll for updates if there are pending sources
    const interval = setInterval(() => {
      if (pendingSources.length > 0 || activeJobs.length > 0) {
        loadProjectData();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [loadProjectData, pendingSources.length, activeJobs.length]);

  const openConfigEditor = async () => {
    try {
      const response = await api.get(`/api/projects/${projectId}/config`);
      setConfigContent(response.data.config);
      setShowConfigEditor(true);
      setConfigError(null);
    } catch (error) {
      console.error('Error loading config:', error);
    }
  };

  const saveConfig = async () => {
    setSavingConfig(true);
    setConfigError(null);
    try {
      await api.put(`/api/projects/${projectId}/config`, { config: configContent });
      setShowConfigEditor(false);
      loadProjectData();
    } catch (error) {
      setConfigError(error.response?.data?.detail || 'Failed to save configuration');
    } finally {
      setSavingConfig(false);
    }
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="h-12 w-12 border-2 border-green-500/30 border-t-green-500 rounded-full animate-spin mx-auto"></div>
        <p className="mt-4 text-gray-400 font-mono text-sm">
          <span className="text-green-400">$</span> loading project...<span className="animate-pulse">_</span>
        </p>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-12">
        <p className="text-red-400 font-mono">[ERROR] Project not found</p>
      </div>
    );
  }

  return (
    <div>
      {/* Back Button */}
      <Link
        to="/console"
        className="inline-flex items-center text-gray-400 hover:text-green-400 font-mono text-sm mb-6 group"
      >
        <ArrowLeftIcon className="h-4 w-4 mr-2 group-hover:-translate-x-1 transition-transform" />
        <span className="text-green-400">$</span> cd ../projects
      </Link>

      {/* Header */}
      <div className="mb-8 bg-gray-900 rounded-lg border border-gray-700 p-6">
        <div className="flex items-center space-x-3 mb-2">
          <CommandLineIcon className="h-8 w-8 text-green-400" />
          <h1 className="text-3xl font-bold text-white font-mono">{project.project_name}</h1>
        </div>
        <p className="text-gray-400 font-mono text-sm">
          <span className="text-gray-500">location:</span> {project.municipality_name}
        </p>
      </div>

      {/* Pending Sources Notification */}
      {pendingSources.length > 0 && (
        <div className="mb-6 bg-yellow-500/10 border border-yellow-500/50 rounded-lg p-4">
          <div className="flex items-start space-x-3">
            <ExclamationTriangleIcon className="h-6 w-6 text-yellow-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-mono text-sm text-yellow-300 font-semibold mb-1">
                Data Sources Need Syncing
              </h3>
              <p className="text-xs text-yellow-200/70 mb-3">
                {pendingSources.length} source{pendingSources.length > 1 ? 's' : ''} ha{pendingSources.length > 1 ? 've' : 's'} not been downloaded yet.
                YouTube transcripts, website content, and PDFs need to be synced before they can be used for chat.
              </p>
              <div className="space-y-2 mb-3">
                {pendingSources.slice(0, 3).map((source, idx) => (
                  <div key={idx} className="flex items-center space-x-2 text-xs font-mono text-yellow-200/80">
                    <PlayIcon className="h-3 w-3" />
                    <span>{source.name}</span>
                    <span className="text-yellow-500/60">({source.type})</span>
                  </div>
                ))}
                {pendingSources.length > 3 && (
                  <div className="text-xs font-mono text-yellow-500/60">
                    ... and {pendingSources.length - 3} more
                  </div>
                )}
              </div>
              <Link
                to={`/console/projects/${projectId}/data`}
                className="inline-flex items-center px-3 py-1.5 bg-yellow-500/20 text-yellow-300 rounded font-mono text-xs font-semibold hover:bg-yellow-500/30 transition-colors"
              >
                <ArrowPathIcon className="h-3 w-3 mr-1" />
                Go to Data Manager to Sync
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Active Ingestion Jobs */}
      {activeJobs.length > 0 && (
        <div className="mb-6 bg-cyan-500/10 border border-cyan-500/50 rounded-lg p-4">
          <div className="flex items-start space-x-3">
            <ArrowPathIcon className="h-6 w-6 text-cyan-400 flex-shrink-0 mt-0.5 animate-spin" />
            <div className="flex-1">
              <h3 className="font-mono text-sm text-cyan-300 font-semibold mb-1">
                Ingestion in Progress
              </h3>
              <p className="text-xs text-cyan-200/70 mb-3">
                {activeJobs.length} job{activeJobs.length > 1 ? 's' : ''} currently processing. You can chat while data is being ingested.
              </p>
              <div className="space-y-2">
                {activeJobs.map((job, idx) => (
                  <div key={idx} className="bg-cyan-500/10 rounded p-2">
                    <div className="flex items-center justify-between text-xs font-mono mb-1">
                      <span className="text-cyan-200">{job.source_id}</span>
                      <span className="text-cyan-400">{Math.round(job.progress * 100)}%</span>
                    </div>
                    <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-cyan-500 transition-all duration-300"
                        style={{ width: `${job.progress * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Quick Stats */}
      <div className="grid gap-4 md:grid-cols-3 mb-8">
        <div className="bg-gray-900 p-5 rounded-lg border border-gray-700">
          <div className="flex items-center">
            <div className="p-3 bg-cyan-500/20 rounded-lg border border-cyan-500/30">
              <CircleStackIcon className="h-6 w-6 text-cyan-400" />
            </div>
            <div className="ml-4">
              <p className="text-xs font-mono text-gray-500">documents</p>
              <p className="text-2xl font-bold text-white font-mono">{stats?.total_documents || 0}</p>
            </div>
          </div>
        </div>

        <div className="bg-gray-900 p-5 rounded-lg border border-gray-700">
          <div className="flex items-center">
            <div className="p-3 bg-green-500/20 rounded-lg border border-green-500/30">
              <DocumentTextIcon className="h-6 w-6 text-green-400" />
            </div>
            <div className="ml-4">
              <p className="text-xs font-mono text-gray-500">sources</p>
              <p className="text-2xl font-bold text-white font-mono">{stats?.active_sources || 0}</p>
            </div>
          </div>
        </div>

        <div className="bg-gray-900 p-5 rounded-lg border border-gray-700">
          <div className="flex items-center">
            <div className="p-3 bg-purple-500/20 rounded-lg border border-purple-500/30">
              <CpuChipIcon className="h-6 w-6 text-purple-400" />
            </div>
            <div className="ml-4">
              <p className="text-xs font-mono text-gray-500">provider</p>
              <p className="text-lg font-bold text-white font-mono">{stats?.ai_provider}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Action Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 mb-8">
        <Link
          to={`/console/projects/${projectId}/chat`}
          className="bg-gray-900 p-6 rounded-lg border border-gray-700 hover:border-cyan-500/50 transition-all group"
        >
          <ChatBubbleLeftRightIcon className="h-10 w-10 text-cyan-400 mb-4 group-hover:scale-110 transition-transform" />
          <h3 className="text-lg font-semibold text-white font-mono mb-2">./chat</h3>
          <p className="text-sm text-gray-500">
            Test your AI assistant and have conversations
          </p>
        </Link>

        <Link
          to={`/console/projects/${projectId}/data`}
          className="bg-gray-900 p-6 rounded-lg border border-gray-700 hover:border-green-500/50 transition-all group"
        >
          <DocumentTextIcon className="h-10 w-10 text-green-400 mb-4 group-hover:scale-110 transition-transform" />
          <h3 className="text-lg font-semibold text-white font-mono mb-2">./data</h3>
          <p className="text-sm text-gray-500">
            Add, remove, or sync data sources
          </p>
        </Link>

        <Link
          to={`/console/projects/${projectId}/settings`}
          className="bg-gray-900 p-6 rounded-lg border border-gray-700 hover:border-purple-500/50 transition-all group"
        >
          <CogIcon className="h-10 w-10 text-purple-400 mb-4 group-hover:scale-110 transition-transform" />
          <h3 className="text-lg font-semibold text-white font-mono mb-2">./settings</h3>
          <p className="text-sm text-gray-500">
            Configure AI model and personality
          </p>
        </Link>

        <Link
          to={`/console/projects/${projectId}/admin`}
          className="bg-gray-900 p-6 rounded-lg border border-gray-700 hover:border-yellow-500/50 transition-all group"
        >
          <ServerIcon className="h-10 w-10 text-yellow-400 mb-4 group-hover:scale-110 transition-transform" />
          <h3 className="text-lg font-semibold text-white font-mono mb-2">./admin</h3>
          <p className="text-sm text-gray-500">
            Monitor health, jobs, and manage API keys
          </p>
        </Link>

        <Link
          to={`/console/projects/${projectId}/help`}
          className="bg-gray-900 p-6 rounded-lg border border-gray-700 hover:border-pink-500/50 transition-all group"
        >
          <QuestionMarkCircleIcon className="h-10 w-10 text-pink-400 mb-4 group-hover:scale-110 transition-transform" />
          <h3 className="text-lg font-semibold text-white font-mono mb-2">./help</h3>
          <p className="text-sm text-gray-500">
            Setup guides, troubleshooting, and documentation
          </p>
        </Link>

        <button
          onClick={openConfigEditor}
          className="bg-gray-900 p-6 rounded-lg border border-gray-700 hover:border-orange-500/50 transition-all group text-left"
        >
          <CodeBracketIcon className="h-10 w-10 text-orange-400 mb-4 group-hover:scale-110 transition-transform" />
          <h3 className="text-lg font-semibold text-white font-mono mb-2">./code</h3>
          <p className="text-sm text-gray-500">
            Edit raw config.json directly
          </p>
        </button>
      </div>

      {/* Config Editor Modal */}
      {showConfigEditor && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 rounded-lg border border-gray-700 w-full max-w-4xl max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700 rounded-t-lg">
              <div className="flex items-center space-x-2">
                <div className="flex space-x-2">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                </div>
                <span className="text-gray-400 text-sm font-mono ml-4">config.json</span>
              </div>
              <button
                onClick={() => setShowConfigEditor(false)}
                className="text-gray-400 hover:text-white p-1"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-hidden p-4">
              <textarea
                value={configContent}
                onChange={(e) => setConfigContent(e.target.value)}
                className="w-full h-full min-h-[400px] bg-gray-950 text-green-400 font-mono text-sm p-4 rounded border border-gray-700 focus:ring-2 focus:ring-orange-500 focus:border-transparent resize-none"
                spellCheck={false}
              />
            </div>

            {configError && (
              <div className="px-4 pb-2">
                <p className="text-sm text-red-400 font-mono">{configError}</p>
              </div>
            )}

            <div className="flex justify-end space-x-3 px-4 py-3 bg-gray-800 border-t border-gray-700 rounded-b-lg">
              <button
                onClick={() => setShowConfigEditor(false)}
                className="px-4 py-2 text-gray-400 hover:text-white font-mono text-sm"
              >
                cancel
              </button>
              <button
                onClick={saveConfig}
                disabled={savingConfig}
                className="px-4 py-2 bg-orange-500 text-gray-900 rounded font-mono font-semibold hover:bg-orange-400 disabled:opacity-50"
              >
                {savingConfig ? 'saving...' : 'save config'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Next Steps Guide */}
      <div className="bg-gray-900 rounded-lg border border-gray-700 p-6 mb-8">
        <div className="flex items-center space-x-2 mb-4">
          <RocketLaunchIcon className="h-5 w-5 text-cyan-400" />
          <h2 className="text-lg font-bold text-white font-mono"># next_steps</h2>
        </div>

        <div className="space-y-4">
          {/* Step 1: Test Your AI */}
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-cyan-500/20 border border-cyan-500/50 flex items-center justify-center">
              <span className="text-cyan-400 text-xs font-mono">1</span>
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-mono text-white mb-1">Test your AI assistant</h3>
              <p className="text-xs text-gray-500 mb-2">
                Head to the chat interface and ask questions about {project.municipality_name}.
                Try different queries to see how your AI responds.
              </p>
              <Link
                to={`/console/projects/${projectId}/chat`}
                className="inline-flex items-center text-xs font-mono text-cyan-400 hover:text-cyan-300"
              >
                <BeakerIcon className="h-3 w-3 mr-1" />
                $ ./chat --test
              </Link>
            </div>
          </div>

          {/* Step 2: Add More Data */}
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-green-500/20 border border-green-500/50 flex items-center justify-center">
              <span className="text-green-400 text-xs font-mono">2</span>
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-mono text-white mb-1">Add more data sources</h3>
              <p className="text-xs text-gray-500 mb-2">
                Improve your AI's knowledge by adding more sources: YouTube videos, websites, PDFs,
                or other community resources.
              </p>
              <Link
                to={`/console/projects/${projectId}/data`}
                className="inline-flex items-center text-xs font-mono text-green-400 hover:text-green-300"
              >
                <DocumentTextIcon className="h-3 w-3 mr-1" />
                $ ./data --add
              </Link>
            </div>
          </div>

          {/* Step 3: Customize Personality */}
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-purple-500/20 border border-purple-500/50 flex items-center justify-center">
              <span className="text-purple-400 text-xs font-mono">3</span>
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-mono text-white mb-1">Customize AI personality</h3>
              <p className="text-xs text-gray-500 mb-2">
                Fine-tune how your AI responds. Adjust the system prompt, tone, and behavior
                to match your community's voice.
              </p>
              <Link
                to={`/console/projects/${projectId}/settings`}
                className="inline-flex items-center text-xs font-mono text-purple-400 hover:text-purple-300"
              >
                <PaintBrushIcon className="h-3 w-3 mr-1" />
                $ ./settings --personality
              </Link>
            </div>
          </div>

          {/* Step 4: Deploy */}
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-yellow-500/20 border border-yellow-500/50 flex items-center justify-center">
              <span className="text-yellow-400 text-xs font-mono">4</span>
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-mono text-white mb-1">Deploy for your community</h3>
              <p className="text-xs text-gray-500 mb-2">
                Run with Docker for production, set up API access, or embed the chat widget
                on your community website.
              </p>
              <div className="bg-gray-800 rounded p-2 mt-2">
                <code className="text-xs font-mono text-gray-400">
                  <span className="text-green-400">$</span> docker-compose up -d
                </code>
              </div>
            </div>
          </div>
        </div>

        {/* Help Links */}
        <div className="mt-6 pt-4 border-t border-gray-700">
          <p className="text-xs text-gray-500 font-mono mb-2"># resources</p>
          <div className="flex flex-wrap gap-3 text-xs font-mono">
            <a href="https://github.com/amateurmenace/ai-machine" target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white">
              github
            </a>
            <span className="text-gray-700">|</span>
            <a href="https://community.weirdmachine.org" target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white">
              community
            </a>
            <span className="text-gray-700">|</span>
            <span className="text-gray-500">docs (coming soon)</span>
          </div>
        </div>
      </div>

      {/* Configuration */}
      <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
        <div className="flex items-center space-x-2 px-4 py-3 bg-gray-800 border-b border-gray-700">
          <div className="flex space-x-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
          </div>
          <span className="text-gray-400 text-sm font-mono ml-4">config.json</span>
        </div>
        <div className="p-4 font-mono text-sm">
          <div className="text-gray-400">{'{'}</div>
          <div className="pl-4">
            <span className="text-purple-400">"model"</span>: <span className="text-green-400">"{project.model_name}"</span>,
          </div>
          <div className="pl-4">
            <span className="text-purple-400">"temperature"</span>: <span className="text-cyan-400">{project.temperature}</span>,
          </div>
          <div className="pl-4">
            <span className="text-purple-400">"context_window"</span>: <span className="text-cyan-400">{project.context_window}</span>,
          </div>
          <div className="pl-4">
            <span className="text-purple-400">"citations"</span>: <span className="text-yellow-400">{project.enable_citations ? 'true' : 'false'}</span>,
          </div>
          <div className="pl-4">
            <span className="text-purple-400">"show_thinking"</span>: <span className="text-yellow-400">{project.show_thinking ? 'true' : 'false'}</span>
          </div>
          <div className="text-gray-400">{'}'}</div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
