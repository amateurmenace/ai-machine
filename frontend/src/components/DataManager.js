import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import {
  PlusIcon,
  TrashIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  PlayIcon,
  GlobeAmericasIcon,
  DocumentTextIcon,
  LinkIcon,
  ArrowLeftIcon,
  CloudArrowUpIcon,
  EyeIcon,
  XMarkIcon,
  DocumentDuplicateIcon,
  InformationCircleIcon,
  ExclamationTriangleIcon,
  BoltIcon
} from '@heroicons/react/24/outline';

function DataManager() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [sources, setSources] = useState([]);
  const [jobs, setJobs] = useState({});
  const [loading, setLoading] = useState(true);
  const [showAddSource, setShowAddSource] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [viewingDocuments, setViewingDocuments] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [syncingAll, setSyncingAll] = useState(false);
  const [syncErrors, setSyncErrors] = useState({});
  const fileInputRef = useRef(null);

  // Add source form
  const [newSource, setNewSource] = useState({
    type: 'youtube_playlist',
    url: '',
    name: '',
    description: ''
  });

  useEffect(() => {
    loadProject();
    const interval = setInterval(updateJobStatuses, 2000);
    return () => clearInterval(interval);
  }, [projectId]);

  const loadProject = async () => {
    try {
      const response = await axios.get(`/api/projects/${projectId}`);
      setProject(response.data);
      setSources(response.data.data_sources || []);
    } catch (error) {
      console.error('Error loading project:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateJobStatuses = async () => {
    const runningJobs = Object.values(jobs).filter(j => j.status === 'running' || j.status === 'pending');
    for (const job of runningJobs) {
      try {
        const response = await axios.get(`/api/jobs/${job.job_id}`);
        setJobs(prev => ({ ...prev, [job.source_id]: response.data }));
      } catch (error) {
        console.error('Error updating job:', error);
      }
    }
  };

  const handleAddSource = async () => {
    try {
      await axios.post(`/api/projects/${projectId}/sources`, {
        ...newSource,
        id: Math.random().toString(36).substr(2, 9),
        enabled: true
      });

      await loadProject();
      setShowAddSource(false);
      setNewSource({ type: 'youtube_playlist', url: '', name: '', description: '' });
    } catch (error) {
      console.error('Error adding source:', error);
      alert('Failed to add source');
    }
  };

  const handleRemoveSource = async (sourceId) => {
    if (!window.confirm('Remove this data source?')) return;

    try {
      await axios.delete(`/api/projects/${projectId}/sources/${sourceId}`);
      await loadProject();
    } catch (error) {
      console.error('Error removing source:', error);
      alert('Failed to remove source');
    }
  };

  const handleSyncSource = async (sourceId) => {
    // Clear any previous errors for this source
    setSyncErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[sourceId];
      return newErrors;
    });

    try {
      const response = await axios.post(`/api/projects/${projectId}/sources/${sourceId}/ingest`);
      const jobId = response.data.job_id;

      setJobs(prev => ({
        ...prev,
        [sourceId]: {
          job_id: jobId,
          status: 'pending',
          progress: 0,
          source_id: sourceId,
          message: 'Starting ingestion...'
        }
      }));
    } catch (error) {
      console.error('Error syncing source:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to start sync';
      setSyncErrors(prev => ({ ...prev, [sourceId]: errorMessage }));
    }
  };

  const handleSyncAll = async () => {
    if (sources.length === 0) return;

    setSyncingAll(true);
    setSyncErrors({});

    // Sync all sources sequentially to avoid overwhelming the server
    for (const source of sources) {
      // Skip sources that are already syncing
      if (jobs[source.id]?.status === 'running' || jobs[source.id]?.status === 'pending') {
        continue;
      }

      await handleSyncSource(source.id);

      // Small delay between starting syncs
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    setSyncingAll(false);
  };

  const handlePdfUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`/api/projects/${projectId}/upload-pdf`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setJobs(prev => ({
        ...prev,
        [response.data.source_id]: { job_id: response.data.job_id, status: 'pending', progress: 0, source_id: response.data.source_id }
      }));

      await loadProject();
    } catch (error) {
      console.error('Error uploading PDF:', error);
      alert(error.response?.data?.detail || 'Failed to upload PDF');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const viewSourceDocuments = async (source) => {
    setViewingDocuments(source);
    setDocumentsLoading(true);
    setDocuments([]);

    try {
      const response = await axios.get(`/api/projects/${projectId}/documents?source_id=${source.id}&limit=50`);
      setDocuments(response.data.documents || []);
    } catch (error) {
      console.error('Error loading documents:', error);
    } finally {
      setDocumentsLoading(false);
    }
  };

  const getCollectionMethodLabel = (source) => {
    const method = source.metadata?.collection_method;
    const methodLabels = {
      'youtube_transcript_api': 'Auto-transcription via YouTube API',
      'web_scraper': 'Web page scraping',
      'pdf_url_download': 'PDF download & text extraction',
      'pdf_upload': 'Direct PDF upload',
      'unknown': 'Data collection'
    };
    return methodLabels[method] || methodLabels['unknown'];
  };

  const getSourceIcon = (type) => {
    switch (type) {
      case 'youtube_playlist':
      case 'youtube_video':
        return <PlayIcon className="h-5 w-5" />;
      case 'website':
        return <GlobeAmericasIcon className="h-5 w-5" />;
      case 'pdf_url':
      case 'pdf_upload':
        return <DocumentTextIcon className="h-5 w-5" />;
      default:
        return <LinkIcon className="h-5 w-5" />;
    }
  };

  const getSourceTypeLabel = (type) => {
    const labels = {
      'youtube_playlist': 'youtube/playlist',
      'youtube_video': 'youtube/video',
      'website': 'website',
      'pdf_url': 'pdf',
      'pdf_upload': 'pdf/upload',
      'rss_feed': 'rss',
      'reddit': 'reddit'
    };
    return labels[type] || type;
  };

  const getJobStatus = (sourceId) => {
    const job = jobs[sourceId];
    const error = syncErrors[sourceId];

    // Show error if there's one
    if (error && !job) {
      return (
        <div className="flex items-center space-x-2 px-2 py-1 rounded bg-red-500/20 border border-red-500/30">
          <ExclamationTriangleIcon className="h-4 w-4 text-red-500" />
          <span className="text-xs font-mono text-red-400 max-w-xs truncate" title={error}>
            {error.length > 40 ? error.substring(0, 40) + '...' : error}
          </span>
        </div>
      );
    }

    if (!job) return null;

    const statusConfig = {
      'pending': { icon: ClockIcon, color: 'text-yellow-500', bg: 'bg-yellow-500/20', border: 'border-yellow-500/30' },
      'running': { icon: ArrowPathIcon, color: 'text-cyan-500', bg: 'bg-cyan-500/20', border: 'border-cyan-500/30', spin: true },
      'completed': { icon: CheckCircleIcon, color: 'text-green-500', bg: 'bg-green-500/20', border: 'border-green-500/30' },
      'failed': { icon: XCircleIcon, color: 'text-red-500', bg: 'bg-red-500/20', border: 'border-red-500/30' }
    };

    const config = statusConfig[job.status] || statusConfig.pending;
    const Icon = config.icon;

    // Build status text
    let statusText = job.status;
    if (job.status === 'running') {
      statusText = `${Math.round(job.progress)}%`;
      if (job.processed_items && job.total_items) {
        statusText += ` (${job.processed_items}/${job.total_items})`;
      }
    } else if (job.status === 'failed' && job.error) {
      statusText = job.error.length > 30 ? job.error.substring(0, 30) + '...' : job.error;
    }

    return (
      <div className="flex flex-col">
        <div className={`flex items-center space-x-2 px-2 py-1 rounded ${config.bg} border ${config.border}`}>
          <Icon className={`h-4 w-4 ${config.color} ${config.spin ? 'animate-spin' : ''}`} />
          <span className={`text-xs font-mono ${config.color}`}>
            {statusText}
          </span>
        </div>
        {job.status === 'running' && job.message && (
          <span className="text-xs text-gray-500 mt-1 font-mono">{job.message}</span>
        )}
        {job.status === 'running' && (
          <div className="w-full bg-gray-700 rounded-full h-1 mt-1">
            <div
              className="bg-cyan-500 h-1 rounded-full transition-all duration-300"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="h-12 w-12 border-2 border-green-500/30 border-t-green-500 rounded-full animate-spin mx-auto"></div>
        <p className="mt-4 text-gray-400 font-mono text-sm">
          <span className="text-green-400">$</span> loading sources...<span className="animate-pulse">_</span>
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

      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white font-mono flex items-center space-x-2">
            <span className="text-green-400">$</span>
            <span>ls ./sources</span>
          </h2>
          <p className="text-gray-500 font-mono text-sm mt-1">
            {sources.length} source{sources.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        <div className="flex space-x-3">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handlePdfUpload}
            accept=".pdf"
            className="hidden"
          />
          {sources.length > 0 && (
            <button
              onClick={handleSyncAll}
              disabled={syncingAll || Object.values(jobs).some(j => j.status === 'running' || j.status === 'pending')}
              className="inline-flex items-center px-4 py-2 bg-orange-500/20 text-orange-400 border border-orange-500/50 rounded-lg font-mono hover:bg-orange-500/30 transition-colors disabled:opacity-50"
            >
              <BoltIcon className="h-5 w-5 mr-2" />
              {syncingAll ? 'syncing...' : 'sync all'}
            </button>
          )}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center px-4 py-2 bg-purple-500/20 text-purple-400 border border-purple-500/50 rounded-lg font-mono hover:bg-purple-500/30 transition-colors disabled:opacity-50"
          >
            <CloudArrowUpIcon className="h-5 w-5 mr-2" />
            {uploading ? 'uploading...' : 'upload PDF'}
          </button>
          <button
            onClick={() => setShowAddSource(!showAddSource)}
            className="inline-flex items-center px-4 py-2 bg-green-500 text-gray-900 rounded-lg font-mono font-semibold hover:bg-green-400 transition-colors"
          >
            <PlusIcon className="h-5 w-5 mr-2" />
            + add
          </button>
        </div>
      </div>

      {/* Add Source Form */}
      {showAddSource && (
        <div className="bg-gray-900 border border-cyan-500/50 rounded-lg p-6 mb-6">
          <div className="flex items-center space-x-2 mb-4">
            <div className="flex space-x-2">
              <div className="w-3 h-3 rounded-full bg-red-500"></div>
              <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
              <div className="w-3 h-3 rounded-full bg-green-500"></div>
            </div>
            <span className="text-cyan-400 text-sm font-mono ml-4"># add new source</span>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-mono text-gray-300 mb-2">--type</label>
                <select
                  value={newSource.type}
                  onChange={(e) => setNewSource({ ...newSource, type: e.target.value })}
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono focus:ring-2 focus:ring-cyan-500"
                >
                  <option value="youtube_playlist">youtube/playlist</option>
                  <option value="youtube_video">youtube/video</option>
                  <option value="website">website</option>
                  <option value="pdf_url">pdf</option>
                  <option value="rss_feed">rss</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-mono text-gray-300 mb-2">--name</label>
                <input
                  type="text"
                  value={newSource.name}
                  onChange={(e) => setNewSource({ ...newSource, name: e.target.value })}
                  placeholder="e.g., Town Meeting Videos"
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono placeholder-gray-500 focus:ring-2 focus:ring-cyan-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-mono text-gray-300 mb-2">--url</label>
              <input
                type="text"
                value={newSource.url}
                onChange={(e) => setNewSource({ ...newSource, url: e.target.value })}
                placeholder="https://..."
                className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono placeholder-gray-500 focus:ring-2 focus:ring-cyan-500"
              />
            </div>

            <div>
              <label className="block text-sm font-mono text-gray-300 mb-2">--description <span className="text-gray-500">(optional)</span></label>
              <textarea
                value={newSource.description}
                onChange={(e) => setNewSource({ ...newSource, description: e.target.value })}
                rows={2}
                className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono placeholder-gray-500 focus:ring-2 focus:ring-cyan-500 resize-none"
              />
            </div>
          </div>

          <div className="flex space-x-3 mt-4">
            <button
              onClick={handleAddSource}
              disabled={!newSource.url || !newSource.name}
              className="px-4 py-2 bg-cyan-500 text-gray-900 rounded-lg font-mono font-semibold hover:bg-cyan-400 disabled:bg-gray-700 disabled:text-gray-500 transition-colors"
            >
              $ add --source
            </button>
            <button
              onClick={() => setShowAddSource(false)}
              className="px-4 py-2 border border-gray-600 text-gray-400 rounded-lg font-mono hover:text-white hover:border-gray-500 transition-colors"
            >
              cancel
            </button>
          </div>
        </div>
      )}

      {/* Sources List */}
      {sources.length === 0 ? (
        <div className="bg-gray-900 p-12 rounded-lg border border-gray-700 text-center">
          <DocumentTextIcon className="h-12 w-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400 mb-4 font-mono"># no sources configured</p>
          <button
            onClick={() => setShowAddSource(true)}
            className="text-cyan-400 hover:text-cyan-300 font-mono transition-colors"
          >
            + add your first data source
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {sources.map((source) => (
            <div key={source.id} className="bg-gray-900 p-5 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors">
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-4 flex-1">
                  <div className="p-2 bg-gray-800 rounded-lg border border-gray-700 text-cyan-400">
                    {getSourceIcon(source.type)}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-3 mb-1">
                      <h3 className="font-mono text-white font-semibold">{source.name}</h3>
                      <span className="px-2 py-0.5 text-xs font-mono bg-gray-800 text-gray-400 rounded border border-gray-700">
                        {getSourceTypeLabel(source.type)}
                      </span>
                    </div>

                    {source.description && (
                      <p className="text-sm text-gray-500 mb-2">{source.description}</p>
                    )}

                    <p className="text-xs text-gray-600 font-mono truncate">{source.url}</p>

                    <div className="flex items-center flex-wrap gap-x-4 gap-y-1 mt-3 text-xs text-gray-500 font-mono">
                      {source.word_count > 0 && (
                        <span className="text-cyan-400">
                          {source.word_count.toLocaleString()} words
                        </span>
                      )}
                      {source.document_count > 0 && (
                        <span className="text-gray-400">
                          {source.document_count} chunks
                        </span>
                      )}
                      {source.last_synced && (
                        <span>synced: {new Date(source.last_synced).toLocaleString()}</span>
                      )}
                      {getJobStatus(source.id)}
                    </div>

                    {/* Collection method info */}
                    {source.metadata?.collection_method && (
                      <div className="flex items-center mt-2 text-xs text-gray-600">
                        <InformationCircleIcon className="h-3 w-3 mr-1" />
                        {getCollectionMethodLabel(source)}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex space-x-2 ml-4">
                  {source.document_count > 0 && (
                    <button
                      onClick={() => viewSourceDocuments(source)}
                      className="p-2 text-purple-400 hover:bg-purple-500/20 rounded-lg transition-colors"
                      title="View documents"
                    >
                      <EyeIcon className="h-5 w-5" />
                    </button>
                  )}
                  <button
                    onClick={() => handleSyncSource(source.id)}
                    disabled={jobs[source.id]?.status === 'running' || jobs[source.id]?.status === 'pending'}
                    className="p-2 text-cyan-400 hover:bg-cyan-500/20 rounded-lg disabled:text-gray-600 disabled:hover:bg-transparent transition-colors"
                    title="Sync data"
                  >
                    <ArrowPathIcon className={`h-5 w-5 ${jobs[source.id]?.status === 'running' ? 'animate-spin' : ''}`} />
                  </button>
                  <button
                    onClick={() => handleRemoveSource(source.id)}
                    className="p-2 text-red-400 hover:bg-red-500/20 rounded-lg transition-colors"
                    title="Remove source"
                  >
                    <TrashIcon className="h-5 w-5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Document Viewer Modal */}
      {viewingDocuments && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 rounded-lg border border-gray-700 w-full max-w-5xl max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700 rounded-t-lg">
              <div className="flex items-center space-x-3">
                <DocumentDuplicateIcon className="h-5 w-5 text-purple-400" />
                <div>
                  <h3 className="text-white font-mono">{viewingDocuments.name}</h3>
                  <p className="text-xs text-gray-500 font-mono">
                    {documents.length} document chunks • {viewingDocuments.word_count?.toLocaleString() || 0} total words
                  </p>
                </div>
              </div>
              <button
                onClick={() => { setViewingDocuments(null); setSelectedDoc(null); }}
                className="text-gray-400 hover:text-white p-1"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-hidden flex">
              {/* Document List */}
              <div className="w-1/3 border-r border-gray-700 overflow-y-auto">
                {documentsLoading ? (
                  <div className="flex items-center justify-center h-32">
                    <ArrowPathIcon className="h-6 w-6 text-gray-500 animate-spin" />
                  </div>
                ) : documents.length === 0 ? (
                  <div className="p-4 text-gray-500 text-sm font-mono text-center">
                    No documents found
                  </div>
                ) : (
                  documents.map((doc, idx) => (
                    <button
                      key={doc.id}
                      onClick={() => setSelectedDoc(doc)}
                      className={`w-full text-left p-3 border-b border-gray-800 hover:bg-gray-800 transition-colors ${
                        selectedDoc?.id === doc.id ? 'bg-gray-800 border-l-2 border-l-purple-500' : ''
                      }`}
                    >
                      <div className="flex items-start space-x-2">
                        <span className="text-xs text-gray-600 font-mono">{idx + 1}</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-gray-400 font-mono truncate">{doc.title || 'Untitled'}</p>
                          <p className="text-xs text-gray-600 line-clamp-2 mt-1">{doc.text}</p>
                        </div>
                      </div>
                    </button>
                  ))
                )}
              </div>

              {/* Document Content */}
              <div className="flex-1 overflow-y-auto p-4">
                {selectedDoc ? (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <h4 className="font-mono text-white">{selectedDoc.title || 'Untitled'}</h4>
                      {selectedDoc.url && (
                        <a href={selectedDoc.url} target="_blank" rel="noopener noreferrer"
                           className="text-xs text-cyan-400 hover:underline font-mono block truncate">
                          {selectedDoc.url}
                        </a>
                      )}
                      <div className="flex flex-wrap gap-2 text-xs font-mono">
                        <span className="px-2 py-1 bg-gray-800 text-gray-400 rounded">
                          {selectedDoc.source_type}
                        </span>
                        {selectedDoc.metadata?.collection_method && (
                          <span className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded">
                            {selectedDoc.metadata.collection_method}
                          </span>
                        )}
                        {selectedDoc.metadata?.timestamp !== undefined && (
                          <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded">
                            @{Math.floor(selectedDoc.metadata.timestamp / 60)}:{String(Math.floor(selectedDoc.metadata.timestamp % 60)).padStart(2, '0')}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                      <p className="text-sm text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">
                        {selectedDoc.full_text || selectedDoc.text}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-500 text-sm font-mono">
                    Select a document to view its content
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DataManager;
