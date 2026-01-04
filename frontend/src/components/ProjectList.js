import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { PlusIcon, MapPinIcon, CalendarIcon, FolderIcon, CommandLineIcon } from '@heroicons/react/24/outline';

function ProjectList() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      const response = await axios.get('/api/projects');
      setProjects(response.data.projects);
    } catch (error) {
      console.error('Error loading projects:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="h-12 w-12 border-2 border-green-500/30 border-t-green-500 rounded-full animate-spin mx-auto"></div>
        <p className="mt-4 text-gray-400 font-mono text-sm">
          <span className="text-green-400">$</span> ls ~/projects<span className="animate-pulse">_</span>
        </p>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="bg-gray-900 rounded-lg border border-gray-700 p-8 max-w-lg mx-auto">
          <CommandLineIcon className="h-16 w-16 text-green-400 mx-auto mb-6" />
          <h2 className="text-2xl font-bold text-white font-mono mb-4">
            <span className="text-green-400">$</span> init
          </h2>
          <p className="text-gray-400 mb-8 font-mono text-sm">
            No projects found. Create your first community AI assistant.
          </p>
          <Link
            to="/console/new"
            className="inline-flex items-center px-6 py-3 bg-green-500 text-gray-900 rounded-lg font-mono font-semibold hover:bg-green-400 transition-colors"
          >
            <PlusIcon className="h-5 w-5 mr-2" />
            ./new-project
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white font-mono flex items-center space-x-2">
            <span className="text-green-400">$</span>
            <span>ls ~/projects</span>
          </h2>
          <p className="text-gray-500 font-mono text-sm mt-1">
            {projects.length} project{projects.length !== 1 ? 's' : ''} found
          </p>
        </div>
        <Link
          to="/console/new"
          className="inline-flex items-center px-4 py-2 bg-green-500 text-gray-900 rounded-lg font-mono font-semibold hover:bg-green-400 transition-colors"
        >
          <PlusIcon className="h-5 w-5 mr-2" />
          + new
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <Link
            key={project.project_id}
            to={`/console/projects/${project.project_id}`}
            className="block bg-gray-900 rounded-lg border border-gray-700 hover:border-green-500/50 transition-all p-6 group"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center space-x-2 mb-2">
                  <FolderIcon className="h-5 w-5 text-cyan-400 group-hover:text-cyan-300" />
                  <h3 className="text-lg font-semibold text-white font-mono group-hover:text-green-400 transition-colors">
                    {project.project_name}
                  </h3>
                </div>
                <div className="flex items-center text-sm text-gray-500 font-mono">
                  <MapPinIcon className="h-4 w-4 mr-1" />
                  {project.municipality_name}
                </div>
              </div>
            </div>

            <div className="flex items-center text-xs text-gray-600 font-mono pt-3 border-t border-gray-800">
              <CalendarIcon className="h-4 w-4 mr-1" />
              created: {new Date(project.created_at).toLocaleDateString()}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default ProjectList;
