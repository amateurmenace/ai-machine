import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import {
  CheckCircleIcon,
  SparklesIcon,
  GlobeAltIcon,
  CogIcon,
  RocketLaunchIcon,
  PlayIcon,
  DocumentIcon,
  LinkIcon,
  PlusIcon,
  XMarkIcon,
  MagnifyingGlassIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  VideoCameraIcon,
  DocumentTextIcon,
  GlobeAmericasIcon,
  BoltIcon
} from '@heroicons/react/24/outline';

const steps = [
  { id: 1, name: 'Location', icon: GlobeAltIcon, cmd: 'init' },
  { id: 2, name: 'Discover', icon: SparklesIcon, cmd: 'discover' },
  { id: 3, name: 'Fine Tune', icon: DocumentTextIcon, cmd: 'finetune' },
  { id: 4, name: 'Configure', icon: CogIcon, cmd: 'config' },
  { id: 5, name: 'Launch', icon: RocketLaunchIcon, cmd: 'launch' },
];

// Loading spinner component
function LoadingSpinner({ size = 'md', text = '' }) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12'
  };

  return (
    <div className="flex flex-col items-center justify-center space-y-3">
      <div className={`${sizeClasses[size]} border-2 border-green-500/30 border-t-green-500 rounded-full animate-spin`}></div>
      {text && (
        <div className="font-mono text-sm text-gray-400">
          <span className="text-green-400">$</span> {text}<span className="animate-pulse">_</span>
        </div>
      )}
    </div>
  );
}

// Terminal output line component
function TerminalLine({ type = 'info', children }) {
  const colors = {
    info: 'text-gray-400',
    success: 'text-green-400',
    error: 'text-red-400',
    warning: 'text-yellow-400',
    command: 'text-cyan-400'
  };

  const prefixes = {
    info: '[INFO]',
    success: '[OK]',
    error: '[ERR]',
    warning: '[WARN]',
    command: '$'
  };

  return (
    <div className={`font-mono text-sm ${colors[type]}`}>
      <span className="opacity-70">{prefixes[type]}</span> {children}
    </div>
  );
}

function SetupWizard() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [terminalOutput, setTerminalOutput] = useState([]);

  // Wizard state
  const [municipalityName, setMunicipalityName] = useState('');
  const [projectName, setProjectName] = useState('');
  const [projectId, setProjectId] = useState('');
  const [discoveredSources, setDiscoveredSources] = useState([]);
  const [selectedSources, setSelectedSources] = useState([]);
  const [aiProvider, setAiProvider] = useState('ollama');
  const [modelName, setModelName] = useState('llama3.1:8b');
  const [apiKey, setApiKey] = useState('');
  const [personality, setPersonality] = useState('');
  const [temperature, setTemperature] = useState(0.7);
  const [showThinking, setShowThinking] = useState(false);
  const [extendedThinking, setExtendedThinking] = useState(false);

  // Frontier model settings for discovery
  const [discoveryProvider, setDiscoveryProvider] = useState('anthropic');
  const [discoveryModel, setDiscoveryModel] = useState('claude-opus-4-20250514');
  const [discoveryApiKey, setDiscoveryApiKey] = useState('');
  const [availableModels, setAvailableModels] = useState([]);

  // Discovery state
  const [discoveryPhase, setDiscoveryPhase] = useState('idle'); // idle, searching, found, selecting
  const [showCustomSourceForm, setShowCustomSourceForm] = useState(false);
  const [customSource, setCustomSource] = useState({ type: 'youtube_video', url: '', name: '' });
  const [generatingPersonality, setGeneratingPersonality] = useState(false);
  const [discoveryPrompt, setDiscoveryPrompt] = useState('');
  const [showDiscoverySettings, setShowDiscoverySettings] = useState(false);

  // Add terminal output
  const addOutput = (type, message) => {
    setTerminalOutput(prev => [...prev, { type, message, timestamp: Date.now() }]);
  };

  // Load available models when provider changes
  useEffect(() => {
    const loadModels = async () => {
      try {
        const response = await api.get(`/api/models/${aiProvider}`);
        setAvailableModels(response.data.models);

        if (response.data.models.length > 0) {
          setModelName(response.data.models[0].name);
        }
      } catch (error) {
        console.error('Error loading models:', error);
      }
    };

    loadModels();
  }, [aiProvider]);

  // Step 1: Create Project
  const handleCreateProject = async () => {
    setLoading(true);
    setError(null);
    addOutput('command', `neighborhood-ai init --location "${municipalityName}"`);

    try {
      const response = await api.post('/api/projects', null, {
        params: {
          municipality_name: municipalityName,
          project_name: projectName || undefined
        }
      });

      setProjectId(response.data.project_id);
      addOutput('success', `Project created: ${response.data.project_id}`);
      setCurrentStep(2);
    } catch (err) {
      addOutput('error', err.response?.data?.detail || 'Failed to create project');
      setError(err.response?.data?.detail || 'Failed to create project');
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Discover Sources
  const handleDiscoverSources = async () => {
    setLoading(true);
    setError(null);
    setDiscoveryPhase('searching');
    addOutput('command', `neighborhood-ai discover --location "${municipalityName}" --provider ${discoveryProvider}`);
    addOutput('info', 'Searching web for local data sources...');
    if (discoveryPrompt) {
      addOutput('info', `Custom search: "${discoveryPrompt.substring(0, 50)}..."`);
    }

    try {
      const response = await api.post(
        `/api/projects/${projectId}/discover-sources`,
        null,
        {
          params: {
            provider: discoveryProvider,
            model: discoveryModel,
            api_key: discoveryApiKey || undefined,
            custom_prompt: discoveryPrompt || undefined
          }
        }
      );

      const sources = response.data.sources || [];
      setDiscoveredSources(sources);
      // Select all sources by default
      setSelectedSources([...sources]);
      setDiscoveryPhase('found');
      addOutput('success', `Found ${sources.length} potential data sources`);
    } catch (err) {
      addOutput('error', err.response?.data?.detail || 'Failed to discover sources');
      setError(err.response?.data?.detail || 'Failed to discover sources');
      setDiscoveryPhase('idle');
    } finally {
      setLoading(false);
    }
  };

  // Add custom source
  const handleAddCustomSource = () => {
    if (!customSource.url || !customSource.name) return;

    const newSource = {
      ...customSource,
      id: `custom-${Date.now()}`,
      description: `Custom ${customSource.type} source`,
      priority: 'high',
      isCustom: true
    };

    setDiscoveredSources(prev => [newSource, ...prev]);
    setSelectedSources(prev => [newSource, ...prev]);
    setCustomSource({ type: 'youtube_video', url: '', name: '' });
    setShowCustomSourceForm(false);
    addOutput('success', `Added custom source: ${newSource.name}`);
  };

  // Generate personality using AI
  const handleGeneratePersonality = async () => {
    if (!discoveryApiKey) {
      setError('API key required to generate personality');
      return;
    }

    setGeneratingPersonality(true);
    addOutput('command', `neighborhood-ai generate-personality --location "${municipalityName}"`);

    try {
      const response = await api.post(`/api/projects/${projectId}/generate-personality`, null, {
        params: {
          provider: discoveryProvider,
          api_key: discoveryApiKey
        }
      });

      setPersonality(response.data.personality);
      addOutput('success', 'Personality generated successfully');
    } catch (err) {
      // Fallback personality
      setPersonality(`You are a helpful, knowledgeable AI assistant for ${municipalityName}.

You have deep knowledge of local government, community resources, and civic affairs. Your tone is warm but professional, like a friendly neighbor who happens to work at town hall.

Key traits:
- Accurate and well-sourced
- Community-focused
- Encourages civic participation
- Admits when you don't know something
- Always cites your sources`);
      addOutput('info', 'Using default personality template');
    } finally {
      setGeneratingPersonality(false);
    }
  };

  // Step 3: Add Sources and Configure
  const handleConfigureAI = async () => {
    setLoading(true);
    setError(null);
    addOutput('command', `neighborhood-ai config --provider ${aiProvider} --model ${modelName}`);

    try {
      // Add selected sources
      for (const source of selectedSources) {
        await api.post(`/api/projects/${projectId}/sources`, {
          id: source.id || Math.random().toString(36).substr(2, 9),
          type: source.type,
          url: source.url,
          name: source.name,
          description: source.description,
          enabled: true
        });
      }
      addOutput('success', `Added ${selectedSources.length} data sources`);

      // Update AI configuration
      await api.put(`/api/projects/${projectId}`, {
        ai_provider: aiProvider,
        model_name: modelName,
        api_key: apiKey || null,
        temperature: temperature,
        system_prompt: personality,
        show_thinking: showThinking,
        extended_thinking: extendedThinking
      });
      addOutput('success', 'AI configuration saved');

      setCurrentStep(5);
    } catch (err) {
      addOutput('error', err.response?.data?.detail || 'Failed to configure AI');
      setError(err.response?.data?.detail || 'Failed to configure AI');
    } finally {
      setLoading(false);
    }
  };

  // Step 4: Start Ingestion and Launch
  const handleLaunch = async () => {
    setLoading(true);
    setError(null);
    addOutput('command', `neighborhood-ai launch --project ${projectId}`);

    try {
      const project = await api.get(`/api/projects/${projectId}`);
      const sources = project.data.data_sources;

      addOutput('info', `Starting ingestion for ${sources.length} sources...`);

      for (const source of sources) {
        await api.post(`/api/projects/${projectId}/sources/${source.id}/ingest`);
        addOutput('info', `Queued: ${source.name}`);
      }

      addOutput('success', 'All sources queued for ingestion');
      addOutput('success', 'Launching project dashboard...');

      setTimeout(() => {
        navigate(`/console/projects/${projectId}`);
      }, 1000);
    } catch (err) {
      addOutput('error', err.response?.data?.detail || 'Failed to launch project');
      setError(err.response?.data?.detail || 'Failed to launch project');
    } finally {
      setLoading(false);
    }
  };

  const toggleSource = (source) => {
    setSelectedSources(prev => {
      const exists = prev.find(s => s.url === source.url);
      if (exists) {
        return prev.filter(s => s.url !== source.url);
      } else {
        return [...prev, source];
      }
    });
  };

  const selectAllSources = () => {
    setSelectedSources([...discoveredSources]);
  };

  const deselectAllSources = () => {
    setSelectedSources([]);
  };

  const getSourceIcon = (type) => {
    switch (type) {
      case 'youtube_playlist':
      case 'youtube_video':
        return <PlayIcon className="h-5 w-5" />;
      case 'website':
        return <GlobeAmericasIcon className="h-5 w-5" />;
      case 'pdf_url':
        return <DocumentTextIcon className="h-5 w-5" />;
      default:
        return <LinkIcon className="h-5 w-5" />;
    }
  };

  return (
    <div className="max-w-5xl mx-auto">
      {/* Progress Steps - Terminal Style */}
      <nav aria-label="Progress" className="mb-8">
        <div className="bg-gray-900 rounded-lg border border-gray-700 p-4">
          <div className="flex items-center space-x-2 mb-4 text-gray-500 text-xs font-mono">
            <span>~/projects/{projectId || 'new'}</span>
            <span>|</span>
            <span>step {currentStep}/5</span>
          </div>
          <ol className="flex items-center">
            {steps.map((step, stepIdx) => (
              <li key={step.name} className={`relative flex items-center ${stepIdx !== steps.length - 1 ? 'flex-1' : ''}`}>
                {/* Step icon and label container */}
                <div className="flex flex-col items-center z-10">
                  <div className={`flex h-10 w-10 items-center justify-center rounded border-2 bg-gray-900
                    ${currentStep > step.id
                      ? 'border-green-500 bg-green-500/20'
                      : currentStep === step.id
                        ? 'border-cyan-500 bg-cyan-500/20'
                        : 'border-gray-700 bg-gray-800'}`}>
                    {currentStep > step.id ? (
                      <CheckCircleIcon className="h-6 w-6 text-green-400" />
                    ) : currentStep === step.id ? (
                      <step.icon className="h-6 w-6 text-cyan-400" />
                    ) : (
                      <span className="text-gray-500 font-mono">{step.id}</span>
                    )}
                  </div>
                  <span className={`mt-2 text-xs font-mono whitespace-nowrap ${currentStep >= step.id ? 'text-gray-300' : 'text-gray-600'}`}>
                    ./{step.cmd}
                  </span>
                </div>
                {/* Connecting line */}
                {stepIdx !== steps.length - 1 && (
                  <div className={`flex-1 h-0.5 mx-2 mt-[-1.5rem]
                    ${currentStep > step.id ? 'bg-green-500' : 'bg-gray-700'}`} />
                )}
              </li>
            ))}
          </ol>
        </div>
      </nav>

      {/* Error Display */}
      {error && (
        <div className="mb-6 bg-red-900/30 border border-red-500/50 rounded-lg p-4 font-mono text-sm">
          <span className="text-red-400">[ERROR]</span> <span className="text-red-300">{error}</span>
        </div>
      )}

      {/* Step Content */}
      <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
        {/* Terminal Header */}
        <div className="flex items-center space-x-2 px-4 py-3 bg-gray-800 border-b border-gray-700">
          <div className="flex space-x-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
          </div>
          <span className="text-gray-400 text-sm font-mono ml-4">
            neighborhood-ai {steps[currentStep - 1]?.cmd || 'setup'}
          </span>
        </div>

        <div className="p-6">
          {currentStep === 1 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-white font-mono flex items-center space-x-2">
                  <span className="text-green-400">$</span>
                  <span>init</span>
                </h2>
                <p className="text-gray-400 mt-2">Initialize a new community AI project</p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-mono text-gray-300 mb-2">
                    --location <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={municipalityName}
                    onChange={(e) => setMunicipalityName(e.target.value)}
                    placeholder="e.g., Brookline, MA"
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono placeholder-gray-500 focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  />
                  <p className="mt-1 text-xs text-gray-500 font-mono">
                    # Municipality or neighborhood name for AI discovery
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-mono text-gray-300 mb-2">
                    --name <span className="text-gray-500">(optional)</span>
                  </label>
                  <input
                    type="text"
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                    placeholder="e.g., Brookline AI"
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono placeholder-gray-500 focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  />
                </div>

                <div className="border-t border-gray-700 pt-4 mt-4">
                  <h3 className="text-sm font-mono text-cyan-400 mb-3">
                    # AI Discovery Configuration
                  </h3>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-mono text-gray-300 mb-2">
                        --provider
                      </label>
                      <select
                        value={discoveryProvider}
                        onChange={(e) => {
                          setDiscoveryProvider(e.target.value);
                          if (e.target.value === 'anthropic') {
                            setDiscoveryModel('claude-opus-4-20250514');
                          } else {
                            setDiscoveryModel('gpt-4o');
                          }
                        }}
                        className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono focus:ring-2 focus:ring-green-500"
                      >
                        <option value="anthropic">anthropic (recommended)</option>
                        <option value="openai">openai</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-mono text-gray-300 mb-2">
                        --model
                      </label>
                      <select
                        value={discoveryModel}
                        onChange={(e) => setDiscoveryModel(e.target.value)}
                        className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono focus:ring-2 focus:ring-green-500"
                      >
                        {discoveryProvider === 'anthropic' ? (
                          <>
                            <option value="claude-opus-4-20250514">claude-opus-4.5</option>
                            <option value="claude-sonnet-4-20250514">claude-sonnet-4.5</option>
                            <option value="claude-haiku-4-20250514">claude-haiku-4</option>
                          </>
                        ) : (
                          <>
                            <option value="gpt-4o">gpt-4o</option>
                            <option value="gpt-4o-mini">gpt-4o-mini</option>
                          </>
                        )}
                      </select>
                    </div>
                  </div>

                  <div className="mt-4">
                    <label className="block text-sm font-mono text-gray-300 mb-2">
                      --api-key
                    </label>
                    <input
                      type="password"
                      value={discoveryApiKey}
                      onChange={(e) => setDiscoveryApiKey(e.target.value)}
                      placeholder={discoveryProvider === 'anthropic' ? 'sk-ant-...' : 'sk-...'}
                      className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono placeholder-gray-500 focus:ring-2 focus:ring-green-500 focus:border-transparent"
                    />
                    <p className="mt-1 text-xs text-gray-500 font-mono">
                      # Required for AI-powered source discovery
                    </p>
                  </div>
                </div>
              </div>

              <button
                onClick={handleCreateProject}
                disabled={!municipalityName || loading}
                className="w-full bg-green-500 text-gray-900 py-3 px-4 rounded-lg font-mono font-semibold hover:bg-green-400 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed transition-colors flex items-center justify-center space-x-2"
              >
                {loading ? (
                  <>
                    <ArrowPathIcon className="h-5 w-5 animate-spin" />
                    <span>Creating project...</span>
                  </>
                ) : (
                  <>
                    <span>$ ./init</span>
                    <span className="animate-pulse">_</span>
                  </>
                )}
              </button>
            </div>
          )}

          {currentStep === 2 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-white font-mono flex items-center space-x-2">
                  <span className="text-green-400">$</span>
                  <span>discover</span>
                </h2>
                <p className="text-gray-400 mt-2">Find and select data sources for {municipalityName}</p>
              </div>

              {discoveryPhase === 'idle' && (
                <div className="space-y-4">
                  <div className="text-center py-8 border-2 border-dashed border-gray-700 rounded-lg">
                    <MagnifyingGlassIcon className="h-12 w-12 mx-auto text-cyan-500 mb-4" />
                    <p className="text-gray-400 mb-4 font-mono">Ready to search for local data sources</p>

                    {/* Custom Search Prompt */}
                    <div className="max-w-lg mx-auto mb-4 px-4">
                      <button
                        onClick={() => setShowDiscoverySettings(!showDiscoverySettings)}
                        className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center justify-center space-x-1 mb-3 mx-auto"
                      >
                        <CogIcon className="h-3 w-3" />
                        <span>{showDiscoverySettings ? 'hide' : 'show'} search settings</span>
                      </button>

                      {showDiscoverySettings && (
                        <div className="bg-gray-800 rounded-lg p-4 text-left space-y-3">
                          <div>
                            <label className="block text-xs font-mono text-gray-400 mb-1">
                              --custom-search (optional)
                            </label>
                            <textarea
                              value={discoveryPrompt}
                              onChange={(e) => setDiscoveryPrompt(e.target.value)}
                              placeholder="e.g., Focus on environmental policy, include local newspapers, prioritize video content from town meetings..."
                              rows={3}
                              className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white font-mono text-sm placeholder-gray-500 focus:ring-2 focus:ring-cyan-500 resize-none"
                            />
                            <p className="mt-1 text-xs text-gray-500 font-mono">
                              # Customize what the AI searches for
                            </p>
                          </div>
                        </div>
                      )}
                    </div>

                    <button
                      onClick={handleDiscoverSources}
                      disabled={loading || !discoveryApiKey}
                      className="bg-cyan-500 text-gray-900 py-2 px-6 rounded-lg font-mono font-semibold hover:bg-cyan-400 disabled:bg-gray-700 disabled:text-gray-500 transition-colors"
                    >
                      {loading ? 'Searching...' : '$ ./discover --web-search'}
                    </button>
                    {!discoveryApiKey && (
                      <p className="mt-3 text-xs text-yellow-500 font-mono">
                        # API key required. Go back to add one, or add sources manually below.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {discoveryPhase === 'searching' && (
                <div className="text-center py-12">
                  <LoadingSpinner size="lg" text="Searching the web for data sources..." />
                  <div className="mt-6 max-w-md mx-auto">
                    <div className="bg-gray-800 rounded-lg p-4 text-left">
                      {terminalOutput.slice(-5).map((line, idx) => (
                        <TerminalLine key={idx} type={line.type}>{line.message}</TerminalLine>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {discoveryPhase === 'found' && (
                <div className="space-y-4">
                  {/* Source Selection Header */}
                  <div className="flex items-center justify-between border-b border-gray-700 pb-4">
                    <div className="font-mono text-sm text-gray-400">
                      <span className="text-green-400">{selectedSources.length}</span> / {discoveredSources.length} sources selected
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={selectAllSources}
                        className="px-3 py-1 text-xs font-mono text-gray-400 hover:text-white border border-gray-600 rounded hover:border-gray-500 transition-colors"
                      >
                        select all
                      </button>
                      <button
                        onClick={deselectAllSources}
                        className="px-3 py-1 text-xs font-mono text-gray-400 hover:text-white border border-gray-600 rounded hover:border-gray-500 transition-colors"
                      >
                        clear
                      </button>
                      <button
                        onClick={() => setShowCustomSourceForm(!showCustomSourceForm)}
                        className="px-3 py-1 text-xs font-mono bg-cyan-500/20 text-cyan-400 border border-cyan-500/50 rounded hover:bg-cyan-500/30 transition-colors flex items-center space-x-1"
                      >
                        <PlusIcon className="h-3 w-3" />
                        <span>add custom</span>
                      </button>
                    </div>
                  </div>

                  {/* Custom Source Form */}
                  {showCustomSourceForm && (
                    <div className="bg-gray-800 border border-cyan-500/50 rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-mono text-cyan-400"># Add Custom Source</h4>
                        <button onClick={() => setShowCustomSourceForm(false)} className="text-gray-500 hover:text-white">
                          <XMarkIcon className="h-4 w-4" />
                        </button>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <select
                          value={customSource.type}
                          onChange={(e) => setCustomSource({ ...customSource, type: e.target.value })}
                          className="px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white font-mono text-sm focus:ring-2 focus:ring-cyan-500"
                        >
                          <option value="youtube_video">YouTube Video</option>
                          <option value="youtube_playlist">YouTube Playlist</option>
                          <option value="website">Website</option>
                          <option value="pdf_url">PDF Document</option>
                        </select>
                        <input
                          type="text"
                          value={customSource.url}
                          onChange={(e) => setCustomSource({ ...customSource, url: e.target.value })}
                          placeholder="URL"
                          className="px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white font-mono text-sm placeholder-gray-500 focus:ring-2 focus:ring-cyan-500"
                        />
                        <input
                          type="text"
                          value={customSource.name}
                          onChange={(e) => setCustomSource({ ...customSource, name: e.target.value })}
                          placeholder="Name"
                          className="px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white font-mono text-sm placeholder-gray-500 focus:ring-2 focus:ring-cyan-500"
                        />
                      </div>
                      <button
                        onClick={handleAddCustomSource}
                        disabled={!customSource.url || !customSource.name}
                        className="w-full py-2 bg-cyan-500 text-gray-900 rounded font-mono text-sm font-semibold hover:bg-cyan-400 disabled:bg-gray-700 disabled:text-gray-500 transition-colors"
                      >
                        + Add Source
                      </button>
                    </div>
                  )}

                  {/* Sources Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-96 overflow-y-auto pr-2">
                    {discoveredSources.map((source, idx) => {
                      const isSelected = selectedSources.find(s => s.url === source.url);
                      return (
                        <div
                          key={idx}
                          onClick={() => toggleSource(source)}
                          className={`p-4 rounded-lg cursor-pointer transition-all border-2
                            ${isSelected
                              ? 'border-green-500 bg-green-500/10'
                              : 'border-gray-700 bg-gray-800 hover:border-gray-600'
                            }`}
                        >
                          <div className="flex items-start space-x-3">
                            <div className={`p-2 rounded ${isSelected ? 'bg-green-500/20 text-green-400' : 'bg-gray-700 text-gray-400'}`}>
                              {getSourceIcon(source.type)}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center space-x-2">
                                <h3 className="font-mono text-sm text-white truncate">{source.name}</h3>
                                {source.isCustom && (
                                  <span className="px-1.5 py-0.5 text-xs bg-cyan-500/20 text-cyan-400 rounded font-mono">custom</span>
                                )}
                                {source.priority === 'high' && !source.isCustom && (
                                  <span className="px-1.5 py-0.5 text-xs bg-green-500/20 text-green-400 rounded font-mono">high</span>
                                )}
                              </div>
                              <p className="text-xs text-gray-500 mt-1 line-clamp-2">{source.description}</p>
                              <p className="text-xs text-gray-600 mt-1 font-mono truncate">{source.url}</p>
                            </div>
                            {isSelected && (
                              <CheckCircleIcon className="h-5 w-5 text-green-400 flex-shrink-0" />
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <button
                    onClick={() => setCurrentStep(3)}
                    disabled={selectedSources.length === 0}
                    className="w-full bg-green-500 text-gray-900 py-3 px-4 rounded-lg font-mono font-semibold hover:bg-green-400 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed transition-colors"
                  >
                    $ ./finetune --sources {selectedSources.length}
                  </button>
                </div>
              )}

              {/* Skip Discovery Option */}
              {discoveryPhase === 'idle' && (
                <div className="text-center">
                  <button
                    onClick={() => {
                      setDiscoveryPhase('found');
                      setDiscoveredSources([]);
                    }}
                    className="text-gray-500 hover:text-gray-300 text-sm font-mono transition-colors"
                  >
                    # Skip AI discovery, add sources manually
                  </button>
                </div>
              )}
            </div>
          )}

          {currentStep === 3 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-white font-mono flex items-center space-x-2">
                  <span className="text-green-400">$</span>
                  <span>finetune</span>
                </h2>
                <p className="text-gray-400 mt-2">Add more sources to fine-tune your AI's knowledge</p>
              </div>

              {/* Current Sources Summary */}
              <div className="bg-gray-800 rounded-lg p-4 font-mono text-sm">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-cyan-400"># selected sources ({selectedSources.length})</span>
                </div>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {selectedSources.map((source, idx) => (
                    <div key={idx} className="flex items-center justify-between text-gray-400">
                      <div className="flex items-center space-x-2">
                        <span className="text-green-400">+</span>
                        <span className="text-gray-300">{source.name}</span>
                        <span className="text-gray-600">({source.type})</span>
                      </div>
                      <button
                        onClick={() => toggleSource(source)}
                        className="text-red-400 hover:text-red-300 text-xs"
                      >
                        remove
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Add More Sources */}
              <div className="border-2 border-dashed border-gray-700 rounded-lg p-6">
                <h3 className="text-sm font-mono text-cyan-400 mb-4"># add more sources</h3>

                {/* Source Type Buttons */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                  <button
                    onClick={() => {
                      setCustomSource({ type: 'youtube_video', url: '', name: '' });
                      setShowCustomSourceForm(true);
                    }}
                    className="flex flex-col items-center p-4 bg-gray-800 rounded-lg border border-gray-700 hover:border-cyan-500/50 transition-colors"
                  >
                    <VideoCameraIcon className="h-8 w-8 text-red-400 mb-2" />
                    <span className="text-xs font-mono text-gray-300">YouTube Video</span>
                  </button>
                  <button
                    onClick={() => {
                      setCustomSource({ type: 'youtube_playlist', url: '', name: '' });
                      setShowCustomSourceForm(true);
                    }}
                    className="flex flex-col items-center p-4 bg-gray-800 rounded-lg border border-gray-700 hover:border-cyan-500/50 transition-colors"
                  >
                    <PlayIcon className="h-8 w-8 text-red-400 mb-2" />
                    <span className="text-xs font-mono text-gray-300">Playlist</span>
                  </button>
                  <button
                    onClick={() => {
                      setCustomSource({ type: 'website', url: '', name: '' });
                      setShowCustomSourceForm(true);
                    }}
                    className="flex flex-col items-center p-4 bg-gray-800 rounded-lg border border-gray-700 hover:border-cyan-500/50 transition-colors"
                  >
                    <GlobeAmericasIcon className="h-8 w-8 text-blue-400 mb-2" />
                    <span className="text-xs font-mono text-gray-300">Website</span>
                  </button>
                  <button
                    onClick={() => {
                      setCustomSource({ type: 'pdf_url', url: '', name: '' });
                      setShowCustomSourceForm(true);
                    }}
                    className="flex flex-col items-center p-4 bg-gray-800 rounded-lg border border-gray-700 hover:border-cyan-500/50 transition-colors"
                  >
                    <DocumentTextIcon className="h-8 w-8 text-orange-400 mb-2" />
                    <span className="text-xs font-mono text-gray-300">PDF</span>
                  </button>
                </div>

                {/* Custom Source Form */}
                {showCustomSourceForm && (
                  <div className="bg-gray-900 border border-cyan-500/50 rounded-lg p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-mono text-cyan-400">
                        # add {customSource.type.replace('_', ' ')}
                      </h4>
                      <button onClick={() => setShowCustomSourceForm(false)} className="text-gray-500 hover:text-white">
                        <XMarkIcon className="h-4 w-4" />
                      </button>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <label className="block text-xs font-mono text-gray-400 mb-1">--url</label>
                        <input
                          type="text"
                          value={customSource.url}
                          onChange={(e) => setCustomSource({ ...customSource, url: e.target.value })}
                          placeholder={
                            customSource.type === 'youtube_video' ? 'https://youtube.com/watch?v=...' :
                            customSource.type === 'youtube_playlist' ? 'https://youtube.com/playlist?list=...' :
                            customSource.type === 'website' ? 'https://example.com' :
                            'https://example.com/document.pdf'
                          }
                          className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white font-mono text-sm placeholder-gray-500 focus:ring-2 focus:ring-cyan-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-mono text-gray-400 mb-1">--name</label>
                        <input
                          type="text"
                          value={customSource.name}
                          onChange={(e) => setCustomSource({ ...customSource, name: e.target.value })}
                          placeholder="Give this source a name"
                          className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white font-mono text-sm placeholder-gray-500 focus:ring-2 focus:ring-cyan-500"
                        />
                      </div>
                      <button
                        onClick={handleAddCustomSource}
                        disabled={!customSource.url || !customSource.name}
                        className="w-full py-2 bg-cyan-500 text-gray-900 rounded font-mono text-sm font-semibold hover:bg-cyan-400 disabled:bg-gray-700 disabled:text-gray-500 transition-colors"
                      >
                        + Add Source
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <button
                onClick={() => setCurrentStep(4)}
                disabled={selectedSources.length === 0}
                className="w-full bg-green-500 text-gray-900 py-3 px-4 rounded-lg font-mono font-semibold hover:bg-green-400 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed transition-colors flex items-center justify-center space-x-2"
              >
                <span>$ ./config --sources {selectedSources.length}</span>
                <span className="animate-pulse">_</span>
              </button>
            </div>
          )}

          {currentStep === 4 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-white font-mono flex items-center space-x-2">
                  <span className="text-green-400">$</span>
                  <span>config</span>
                </h2>
                <p className="text-gray-400 mt-2">Configure your AI model and personality</p>
              </div>

              <div className="space-y-6">
                {/* AI Provider Selection */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-mono text-gray-300 mb-2">
                      --provider
                    </label>
                    <select
                      value={aiProvider}
                      onChange={(e) => setAiProvider(e.target.value)}
                      className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono focus:ring-2 focus:ring-green-500"
                    >
                      <option value="ollama">ollama (local, free)</option>
                      <option value="openai">openai (cloud)</option>
                      <option value="anthropic">anthropic (cloud)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-mono text-gray-300 mb-2">
                      --model
                    </label>
                    {availableModels.length > 0 ? (
                      <select
                        value={modelName}
                        onChange={(e) => setModelName(e.target.value)}
                        className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono focus:ring-2 focus:ring-green-500"
                      >
                        {availableModels.map((model) => (
                          <option key={model.name} value={model.name}>
                            {model.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={modelName}
                        onChange={(e) => setModelName(e.target.value)}
                        className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono focus:ring-2 focus:ring-green-500"
                      />
                    )}
                  </div>
                </div>

                {(aiProvider === 'openai' || aiProvider === 'anthropic') && (
                  <div>
                    <label className="block text-sm font-mono text-gray-300 mb-2">
                      --api-key
                    </label>
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder={aiProvider === 'anthropic' ? 'sk-ant-...' : 'sk-...'}
                      className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono placeholder-gray-500 focus:ring-2 focus:ring-green-500"
                    />
                  </div>
                )}

                {/* Temperature Slider */}
                <div>
                  <label className="block text-sm font-mono text-gray-300 mb-2">
                    --temperature <span className="text-cyan-400">{temperature}</span>
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={temperature}
                    onChange={(e) => setTemperature(parseFloat(e.target.value))}
                    className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-green-500"
                  />
                  <div className="flex justify-between text-xs text-gray-500 font-mono mt-1">
                    <span>focused (0.0)</span>
                    <span>creative (1.0)</span>
                  </div>
                </div>

                {/* Thinking Options */}
                <div className="border border-gray-700 rounded-lg p-4 space-y-3">
                  <h4 className="text-sm font-mono text-cyan-400"># Thinking Options</h4>

                  <label className="flex items-center space-x-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={showThinking}
                      onChange={(e) => setShowThinking(e.target.checked)}
                      className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-green-500 focus:ring-green-500 focus:ring-offset-gray-900"
                    />
                    <span className="font-mono text-sm text-gray-300">--show-thinking</span>
                    <span className="text-xs text-gray-500"># Display AI reasoning process</span>
                  </label>

                  {aiProvider === 'anthropic' && (
                    <label className="flex items-center space-x-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={extendedThinking}
                        onChange={(e) => setExtendedThinking(e.target.checked)}
                        className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-green-500 focus:ring-green-500 focus:ring-offset-gray-900"
                      />
                      <span className="font-mono text-sm text-gray-300">--extended-thinking</span>
                      <span className="text-xs text-gray-500"># Claude extended thinking (beta)</span>
                    </label>
                  )}
                </div>

                {/* Personality */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-mono text-gray-300">
                      --system-prompt
                    </label>
                    <button
                      onClick={handleGeneratePersonality}
                      disabled={generatingPersonality}
                      className="px-3 py-1 text-xs font-mono bg-purple-500/20 text-purple-400 border border-purple-500/50 rounded hover:bg-purple-500/30 transition-colors flex items-center space-x-1 disabled:opacity-50"
                    >
                      {generatingPersonality ? (
                        <>
                          <ArrowPathIcon className="h-3 w-3 animate-spin" />
                          <span>generating...</span>
                        </>
                      ) : (
                        <>
                          <BoltIcon className="h-3 w-3" />
                          <span>auto-generate</span>
                        </>
                      )}
                    </button>
                  </div>
                  <textarea
                    value={personality}
                    onChange={(e) => setPersonality(e.target.value)}
                    rows={6}
                    placeholder="Define your AI's personality, tone, and behavior..."
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono text-sm placeholder-gray-500 focus:ring-2 focus:ring-green-500 resize-none"
                  />
                  <p className="mt-1 text-xs text-gray-500 font-mono">
                    # Customize how your AI responds to the community
                  </p>
                </div>
              </div>

              <button
                onClick={handleConfigureAI}
                disabled={loading}
                className="w-full bg-green-500 text-gray-900 py-3 px-4 rounded-lg font-mono font-semibold hover:bg-green-400 disabled:bg-gray-700 disabled:text-gray-500 transition-colors flex items-center justify-center space-x-2"
              >
                {loading ? (
                  <>
                    <ArrowPathIcon className="h-5 w-5 animate-spin" />
                    <span>Configuring...</span>
                  </>
                ) : (
                  <>
                    <span>$ ./launch --ready</span>
                    <span className="animate-pulse">_</span>
                  </>
                )}
              </button>
            </div>
          )}

          {currentStep === 5 && (
            <div className="space-y-6">
              <div className="text-center">
                <RocketLaunchIcon className="h-16 w-16 mx-auto text-green-400 mb-4" />
                <h2 className="text-2xl font-bold text-white font-mono">
                  <span className="text-green-400">$</span> launch
                </h2>
                <p className="text-gray-400 mt-2">
                  {projectName || `${municipalityName} AI`} is ready to deploy
                </p>
              </div>

              {/* Project Configuration Summary */}
              <div className="bg-gray-800 rounded-lg p-4 font-mono text-sm">
                <div className="flex items-center space-x-2 mb-3 text-cyan-400">
                  <span># project configuration</span>
                </div>
                <div className="space-y-1">
                  <TerminalLine type="success">project_id: {projectId}</TerminalLine>
                  <TerminalLine type="info">location: {municipalityName}</TerminalLine>
                  <TerminalLine type="info">ai_provider: {aiProvider}</TerminalLine>
                  <TerminalLine type="info">model: {modelName}</TerminalLine>
                  <TerminalLine type="info">temperature: {temperature}</TerminalLine>
                  {showThinking && <TerminalLine type="info">show_thinking: enabled</TerminalLine>}
                  {extendedThinking && <TerminalLine type="info">extended_thinking: enabled</TerminalLine>}
                </div>
              </div>

              {/* Data Sources Summary */}
              <div className="bg-gray-800 rounded-lg p-4 font-mono text-sm">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-cyan-400"># data sources ({selectedSources.length})</span>
                </div>
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {selectedSources.map((source, idx) => (
                    <div key={idx} className="flex items-center space-x-2 text-gray-400">
                      <span className="text-green-400">+</span>
                      <span className="text-gray-300">{source.name}</span>
                      <span className="text-gray-600">({source.type})</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Storage Location */}
              <div className="bg-gray-800 rounded-lg p-4 font-mono text-sm">
                <div className="flex items-center space-x-2 mb-3 text-cyan-400">
                  <span># storage paths</span>
                </div>
                <div className="space-y-1 text-gray-400">
                  <div className="flex items-start space-x-2">
                    <span className="text-yellow-400 shrink-0">config:</span>
                    <span className="text-gray-300 break-all">./data/{projectId}/config.json</span>
                  </div>
                  <div className="flex items-start space-x-2">
                    <span className="text-yellow-400 shrink-0">vectors:</span>
                    <span className="text-gray-300 break-all">./data/{projectId}/qdrant/</span>
                  </div>
                </div>
              </div>

              {/* Ingestion Estimate */}
              <div className="bg-gray-800 rounded-lg p-4 font-mono text-sm">
                <div className="flex items-center space-x-2 mb-3 text-cyan-400">
                  <span># ingestion estimate</span>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-gray-400">
                    <span>Sources to process:</span>
                    <span className="text-white">{selectedSources.length}</span>
                  </div>
                  <div className="flex items-center justify-between text-gray-400">
                    <span>Estimated time:</span>
                    <span className="text-white">
                      {selectedSources.length <= 2 ? '1-2 min' :
                       selectedSources.length <= 5 ? '2-5 min' :
                       selectedSources.length <= 10 ? '5-10 min' : '10-20 min'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-2 pt-2 border-t border-gray-700">
                    Data ingestion runs in the background. You can start chatting right away - the AI will improve as more data is processed.
                  </p>
                </div>
              </div>

              {/* Launch Progress */}
              {loading && (
                <div className="bg-gray-800 rounded-lg p-4 font-mono text-sm">
                  <div className="flex items-center space-x-2 mb-3 text-green-400">
                    <ArrowPathIcon className="h-4 w-4 animate-spin" />
                    <span>launching...</span>
                  </div>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {terminalOutput.slice(-8).map((line, idx) => (
                      <TerminalLine key={idx} type={line.type}>{line.message}</TerminalLine>
                    ))}
                  </div>
                </div>
              )}

              <button
                onClick={handleLaunch}
                disabled={loading}
                className="w-full bg-green-500 text-gray-900 py-4 px-4 rounded-lg font-mono font-bold text-lg hover:bg-green-400 disabled:bg-gray-700 disabled:text-gray-500 transition-colors flex items-center justify-center space-x-2"
              >
                {loading ? (
                  <>
                    <ArrowPathIcon className="h-6 w-6 animate-spin" />
                    <span>Deploying...</span>
                  </>
                ) : (
                  <>
                    <RocketLaunchIcon className="h-6 w-6" />
                    <span>$ ./launch --deploy</span>
                    <span className="animate-pulse">_</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default SetupWizard;
