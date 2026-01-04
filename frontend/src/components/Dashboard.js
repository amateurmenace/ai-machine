import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import {
  ChartBarIcon,
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  CogIcon,
  CircleStackIcon,
  ArrowPathIcon,
  CommandLineIcon,
  ServerIcon,
  CpuChipIcon
} from '@heroicons/react/24/outline';

function Dashboard() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadProjectData();
  }, [projectId]);

  const loadProjectData = async () => {
    try {
      const [projectRes, statsRes] = await Promise.all([
        axios.get(`/api/projects/${projectId}`),
        axios.get(`/api/projects/${projectId}/stats`)
      ]);

      setProject(projectRes.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error('Error loading project:', error);
    } finally {
      setLoading(false);
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

        <div className="bg-gray-900 p-6 rounded-lg border border-gray-700 opacity-50 cursor-not-allowed">
          <CogIcon className="h-10 w-10 text-gray-600 mb-4" />
          <h3 className="text-lg font-semibold text-gray-500 font-mono mb-2">./settings</h3>
          <p className="text-sm text-gray-600">
            Configure AI model and personality
          </p>
          <span className="inline-block mt-2 px-2 py-0.5 text-xs font-mono bg-yellow-500/20 text-yellow-500 rounded border border-yellow-500/30">
            coming soon
          </span>
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
