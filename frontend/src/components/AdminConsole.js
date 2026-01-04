import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  ArrowLeftIcon,
  ServerIcon,
  CpuChipIcon,
  CircleStackIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  KeyIcon,
  ClipboardDocumentIcon,
  EyeIcon,
  EyeSlashIcon,
  DocumentTextIcon,
  PlayIcon,
  StopIcon,
  CommandLineIcon,
  ClockIcon,
  ChartBarIcon,
  TrashIcon
} from '@heroicons/react/24/outline';

function AdminConsole() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [systemHealth, setSystemHealth] = useState(null);
  const [projectHealth, setProjectHealth] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [apiKey, setApiKey] = useState(null);
  const [showApiKey, setShowApiKey] = useState(false);
  const [generatingKey, setGeneratingKey] = useState(false);
  const [copied, setCopied] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState('');

  const loadData = useCallback(async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    try {
      const [projectRes, systemHealthRes, projectHealthRes, jobsRes] = await Promise.all([
        axios.get(`/api/projects/${projectId}`),
        axios.get('/api/health'),
        axios.get(`/api/projects/${projectId}/health`),
        axios.get('/api/admin/jobs')
      ]);

      setProject(projectRes.data);
      setSystemHealth(systemHealthRes.data);
      setProjectHealth(projectHealthRes.data);
      setJobs(jobsRes.data.jobs.filter(j => j.project_id === projectId));

      if (projectRes.data.project_api_key) {
        setApiKey(projectRes.data.project_api_key);
      }
    } catch (error) {
      console.error('Error loading admin data:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
    // Auto-refresh every 10 seconds
    const interval = setInterval(() => loadData(), 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  const generateApiKey = async () => {
    setGeneratingKey(true);
    try {
      const response = await axios.post(`/api/projects/${projectId}/generate-api-key`);
      setApiKey(response.data.api_key);
      setShowApiKey(true);
    } catch (error) {
      console.error('Error generating API key:', error);
    } finally {
      setGeneratingKey(false);
    }
  };

  const revokeApiKey = async () => {
    if (!window.confirm('Are you sure you want to revoke this API key? Any integrations using it will stop working.')) {
      return;
    }
    try {
      await axios.delete(`/api/projects/${projectId}/revoke-api-key`);
      setApiKey(null);
      setShowApiKey(false);
    } catch (error) {
      console.error('Error revoking API key:', error);
    }
  };

  const copyToClipboard = async (text) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDeleteProject = async () => {
    if (deleteConfirm !== projectId) {
      return;
    }

    setDeleting(true);
    try {
      await axios.delete(`/api/projects/${projectId}`);
      navigate('/console');
    } catch (error) {
      console.error('Error deleting project:', error);
      alert('Failed to delete project: ' + (error.response?.data?.detail || error.message));
    } finally {
      setDeleting(false);
    }
  };

  const StatusBadge = ({ status, label }) => {
    const colors = {
      healthy: 'bg-green-500/20 text-green-400 border-green-500/30',
      running: 'bg-green-500/20 text-green-400 border-green-500/30',
      completed: 'bg-green-500/20 text-green-400 border-green-500/30',
      warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      error: 'bg-red-500/20 text-red-400 border-red-500/30',
      failed: 'bg-red-500/20 text-red-400 border-red-500/30',
      offline: 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    };

    const icons = {
      healthy: <CheckCircleIcon className="h-4 w-4" />,
      running: <ArrowPathIcon className="h-4 w-4 animate-spin" />,
      completed: <CheckCircleIcon className="h-4 w-4" />,
      warning: <ExclamationTriangleIcon className="h-4 w-4" />,
      pending: <ClockIcon className="h-4 w-4" />,
      error: <XCircleIcon className="h-4 w-4" />,
      failed: <XCircleIcon className="h-4 w-4" />,
      offline: <XCircleIcon className="h-4 w-4" />
    };

    return (
      <span className={`inline-flex items-center space-x-1 px-2 py-1 rounded border text-xs font-mono ${colors[status] || colors.offline}`}>
        {icons[status]}
        <span>{label || status}</span>
      </span>
    );
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="h-12 w-12 border-2 border-green-500/30 border-t-green-500 rounded-full animate-spin mx-auto"></div>
        <p className="mt-4 text-gray-400 font-mono text-sm">
          <span className="text-green-400">$</span> loading admin console...<span className="animate-pulse">_</span>
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Back Button */}
      <Link
        to={`/console/projects/${projectId}`}
        className="inline-flex items-center text-gray-400 hover:text-green-400 font-mono text-sm mb-6 group"
      >
        <ArrowLeftIcon className="h-4 w-4 mr-2 group-hover:-translate-x-1 transition-transform" />
        <span className="text-green-400">$</span> cd ../dashboard
      </Link>

      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-purple-500/20 rounded-lg border border-purple-500/30">
            <ServerIcon className="h-6 w-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white font-mono">admin_console</h1>
            <p className="text-gray-500 text-sm font-mono">{project?.project_name}</p>
          </div>
        </div>
        <button
          onClick={() => loadData(true)}
          disabled={refreshing}
          className="flex items-center space-x-2 px-4 py-2 bg-gray-800 text-gray-300 rounded border border-gray-700 hover:border-gray-600 font-mono text-sm transition-colors disabled:opacity-50"
        >
          <ArrowPathIcon className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          <span>refresh</span>
        </button>
      </div>

      {/* System Health */}
      <div className="bg-gray-900 rounded-lg border border-gray-700 p-6 mb-6">
        <div className="flex items-center space-x-2 mb-4">
          <CpuChipIcon className="h-5 w-5 text-cyan-400" />
          <h2 className="text-lg font-bold text-white font-mono"># system_health</h2>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          {/* Ollama Status */}
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm font-mono">ollama</span>
              <StatusBadge
                status={systemHealth?.ollama_status === 'running' ? 'healthy' : 'offline'}
                label={systemHealth?.ollama_status || 'checking...'}
              />
            </div>
            {systemHealth?.ollama_status === 'running' && (
              <p className="text-xs text-gray-500">{systemHealth?.ollama_models || 0} models available</p>
            )}
            {systemHealth?.ollama_status !== 'running' && (
              <div className="mt-3 p-3 bg-yellow-500/10 rounded border border-yellow-500/30">
                <p className="text-xs text-yellow-400 font-mono mb-2">Ollama not detected. To start:</p>
                <code className="block text-xs bg-gray-900 p-2 rounded text-gray-300">
                  ollama serve
                </code>
              </div>
            )}
          </div>

          {/* Projects Count */}
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm font-mono">projects</span>
              <span className="text-2xl font-bold text-white font-mono">{systemHealth?.projects_count || 0}</span>
            </div>
            <p className="text-xs text-gray-500">Total projects on this instance</p>
          </div>

          {/* Server Status */}
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm font-mono">api_server</span>
              <StatusBadge status="healthy" label="running" />
            </div>
            <p className="text-xs text-gray-500">FastAPI backend active</p>
          </div>
        </div>
      </div>

      {/* Project Health */}
      <div className="bg-gray-900 rounded-lg border border-gray-700 p-6 mb-6">
        <div className="flex items-center space-x-2 mb-4">
          <ChartBarIcon className="h-5 w-5 text-green-400" />
          <h2 className="text-lg font-bold text-white font-mono"># project_health</h2>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* AI Provider */}
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm font-mono">ai_provider</span>
              <StatusBadge
                status={projectHealth?.ai_provider?.status === 'ready' ? 'healthy' : 'warning'}
                label={projectHealth?.ai_provider?.status}
              />
            </div>
            <p className="text-sm text-white font-mono">{projectHealth?.ai_provider?.provider}</p>
            <p className="text-xs text-gray-500">{projectHealth?.ai_provider?.model}</p>
            {projectHealth?.ai_provider?.status !== 'ready' && projectHealth?.ai_provider?.message && (
              <p className="text-xs text-yellow-400 mt-2">{projectHealth?.ai_provider?.message}</p>
            )}
          </div>

          {/* Vector Store */}
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm font-mono">vector_store</span>
              <StatusBadge
                status={projectHealth?.vector_store?.status === 'ready' ? 'healthy' : 'warning'}
                label={projectHealth?.vector_store?.status}
              />
            </div>
            <p className="text-2xl font-bold text-white font-mono">{projectHealth?.vector_store?.documents || 0}</p>
            <p className="text-xs text-gray-500">documents indexed</p>
          </div>

          {/* Data Sources */}
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm font-mono">data_sources</span>
              <StatusBadge
                status={projectHealth?.data_sources?.active > 0 ? 'healthy' : 'warning'}
                label={projectHealth?.data_sources?.active > 0 ? 'configured' : 'none'}
              />
            </div>
            <p className="text-2xl font-bold text-white font-mono">
              {projectHealth?.data_sources?.active || 0}/{projectHealth?.data_sources?.total || 0}
            </p>
            <p className="text-xs text-gray-500">active sources</p>
          </div>

          {/* Overall Status */}
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-sm font-mono">chat_ready</span>
              <StatusBadge
                status={projectHealth?.ready ? 'healthy' : 'warning'}
                label={projectHealth?.ready ? 'ready' : 'needs setup'}
              />
            </div>
            {!projectHealth?.ready && projectHealth?.issues && (
              <ul className="text-xs text-yellow-400 mt-2 space-y-1">
                {projectHealth.issues.map((issue, i) => (
                  <li key={i}>• {issue}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* API Access */}
      <div className="bg-gray-900 rounded-lg border border-gray-700 p-6 mb-6">
        <div className="flex items-center space-x-2 mb-4">
          <KeyIcon className="h-5 w-5 text-yellow-400" />
          <h2 className="text-lg font-bold text-white font-mono"># api_access</h2>
        </div>

        <p className="text-sm text-gray-400 mb-4">
          Generate an API key to allow external applications to query your AI assistant programmatically.
        </p>

        {apiKey ? (
          <div className="space-y-4">
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="flex items-center justify-between mb-2">
                <span className="text-gray-400 text-sm font-mono">api_key</span>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="text-gray-400 hover:text-white p-1"
                  >
                    {showApiKey ? <EyeSlashIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                  </button>
                  <button
                    onClick={() => copyToClipboard(apiKey)}
                    className="text-gray-400 hover:text-white p-1"
                  >
                    <ClipboardDocumentIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>
              <code className="block text-sm font-mono text-green-400 break-all">
                {showApiKey ? apiKey : '•'.repeat(40)}
              </code>
              {copied && <p className="text-xs text-green-400 mt-2">Copied to clipboard!</p>}
            </div>

            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <p className="text-sm text-gray-400 mb-2 font-mono"># example_usage</p>
              <pre className="text-xs bg-gray-900 p-3 rounded overflow-x-auto">
                <code className="text-gray-300">{`curl -X POST "http://localhost:8000/api/v1/chat" \\
  -H "Authorization: Bearer ${showApiKey ? apiKey : 'YOUR_API_KEY'}" \\
  -H "Content-Type: application/json" \\
  -d '{"message": "What are the office hours?"}'`}</code>
              </pre>
            </div>

            <button
              onClick={revokeApiKey}
              className="text-red-400 hover:text-red-300 text-sm font-mono"
            >
              revoke api key
            </button>
          </div>
        ) : (
          <button
            onClick={generateApiKey}
            disabled={generatingKey}
            className="flex items-center space-x-2 px-4 py-2 bg-yellow-500/20 text-yellow-400 rounded border border-yellow-500/30 hover:bg-yellow-500/30 font-mono text-sm transition-colors disabled:opacity-50"
          >
            {generatingKey ? (
              <ArrowPathIcon className="h-4 w-4 animate-spin" />
            ) : (
              <KeyIcon className="h-4 w-4" />
            )}
            <span>{generatingKey ? 'generating...' : 'generate api key'}</span>
          </button>
        )}
      </div>

      {/* Ingestion Jobs */}
      <div className="bg-gray-900 rounded-lg border border-gray-700 p-6 mb-6">
        <div className="flex items-center space-x-2 mb-4">
          <DocumentTextIcon className="h-5 w-5 text-cyan-400" />
          <h2 className="text-lg font-bold text-white font-mono"># ingestion_jobs</h2>
        </div>

        {jobs.length > 0 ? (
          <div className="space-y-3">
            {jobs.map((job) => (
              <div key={job.job_id} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-white font-mono">{job.source_id}</span>
                  <StatusBadge status={job.status} />
                </div>
                {job.status === 'running' && (
                  <div className="mt-2">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Progress</span>
                      <span>{job.processed_items}/{job.total_items}</span>
                    </div>
                    <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-cyan-500 transition-all duration-300"
                        style={{ width: `${job.progress * 100}%` }}
                      ></div>
                    </div>
                  </div>
                )}
                {job.error && (
                  <p className="text-xs text-red-400 mt-2">{job.error}</p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm font-mono">No active or recent jobs</p>
        )}
      </div>

      {/* Server Management */}
      <div className="bg-gray-900 rounded-lg border border-gray-700 p-6">
        <div className="flex items-center space-x-2 mb-4">
          <CommandLineIcon className="h-5 w-5 text-purple-400" />
          <h2 className="text-lg font-bold text-white font-mono"># server_management</h2>
        </div>

        <div className="space-y-4">
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-sm font-mono text-white mb-2 flex items-center">
              <PlayIcon className="h-4 w-4 text-green-400 mr-2" />
              Start Server
            </h3>
            <p className="text-xs text-gray-400 mb-2">Run the following commands in your terminal:</p>
            <pre className="text-xs bg-gray-900 p-3 rounded overflow-x-auto">
              <code className="text-gray-300">{`# Navigate to project directory
cd neighborhood-ai

# Start the backend server
python app.py

# In a new terminal, start the frontend
cd frontend && npm start`}</code>
            </pre>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-sm font-mono text-white mb-2 flex items-center">
              <StopIcon className="h-4 w-4 text-red-400 mr-2" />
              Stop Server
            </h3>
            <p className="text-xs text-gray-400 mb-2">Press Ctrl+C in the terminal running the server, or:</p>
            <pre className="text-xs bg-gray-900 p-3 rounded overflow-x-auto">
              <code className="text-gray-300">{`# Find and kill the process
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9`}</code>
            </pre>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-sm font-mono text-white mb-2 flex items-center">
              <ServerIcon className="h-4 w-4 text-cyan-400 mr-2" />
              Production Deployment
            </h3>
            <p className="text-xs text-gray-400 mb-2">For production, use Docker:</p>
            <pre className="text-xs bg-gray-900 p-3 rounded overflow-x-auto">
              <code className="text-gray-300">{`# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down`}</code>
            </pre>
          </div>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="bg-gray-900 rounded-lg border border-red-500/50 p-6 mt-6">
        <div className="flex items-center space-x-2 mb-4">
          <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
          <h2 className="text-lg font-bold text-red-400 font-mono"># danger_zone</h2>
        </div>

        <div className="bg-red-900/20 rounded-lg p-4 border border-red-500/30">
          <h3 className="text-sm font-mono text-red-300 mb-2 flex items-center">
            <TrashIcon className="h-4 w-4 mr-2" />
            Delete Project
          </h3>
          <p className="text-xs text-gray-400 mb-4">
            This will permanently delete this project and all its data including:
          </p>
          <ul className="text-xs text-gray-500 mb-4 space-y-1">
            <li>• All vector store documents and embeddings</li>
            <li>• All uploaded PDFs and files</li>
            <li>• Project configuration and settings</li>
            <li>• API keys and access credentials</li>
          </ul>
          <p className="text-xs text-red-400 font-mono mb-4">
            This action cannot be undone.
          </p>

          <div className="space-y-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1 font-mono">
                Type <span className="text-red-400">{projectId}</span> to confirm:
              </label>
              <input
                type="text"
                value={deleteConfirm}
                onChange={(e) => setDeleteConfirm(e.target.value)}
                placeholder={projectId}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white font-mono text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent"
              />
            </div>

            <button
              onClick={handleDeleteProject}
              disabled={deleteConfirm !== projectId || deleting}
              className="flex items-center space-x-2 px-4 py-2 bg-red-500/20 text-red-400 rounded border border-red-500/30 hover:bg-red-500/30 font-mono text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {deleting ? (
                <ArrowPathIcon className="h-4 w-4 animate-spin" />
              ) : (
                <TrashIcon className="h-4 w-4" />
              )}
              <span>{deleting ? 'deleting...' : 'delete project permanently'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminConsole;
