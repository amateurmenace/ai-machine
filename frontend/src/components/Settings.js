import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import {
  ArrowLeftIcon,
  ArrowPathIcon,
  CogIcon,
  BoltIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';

function Settings() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  const [generatingPersonality, setGeneratingPersonality] = useState(false);

  // Form state
  const [aiProvider, setAiProvider] = useState('ollama');
  const [modelName, setModelName] = useState('');
  const [customModelName, setCustomModelName] = useState('');
  const [isCustomModel, setIsCustomModel] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [temperature, setTemperature] = useState(0.7);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [showThinking, setShowThinking] = useState(false);
  const [extendedThinking, setExtendedThinking] = useState(false);
  const [availableModels, setAvailableModels] = useState([]);

  useEffect(() => {
    loadProject();
  }, [projectId]);

  useEffect(() => {
    loadModels();
  }, [aiProvider]);

  const loadProject = async () => {
    try {
      const response = await axios.get(`/api/projects/${projectId}`);
      const data = response.data;
      setProject(data);
      setAiProvider(data.ai_provider || 'ollama');
      setApiKey(data.api_key || '');
      setTemperature(data.temperature || 0.7);
      setSystemPrompt(data.system_prompt || '');
      setShowThinking(data.show_thinking || false);
      setExtendedThinking(data.extended_thinking || false);

      // Load models first to check if current model is custom
      const modelsRes = await axios.get(`/api/models/${data.ai_provider || 'ollama'}`);
      const models = modelsRes.data.models || [];
      setAvailableModels(models);

      const isPresetModel = models.some(m => m.name === data.model_name && m.name !== 'custom');
      if (isPresetModel) {
        setModelName(data.model_name || '');
        setIsCustomModel(false);
      } else {
        setModelName('custom');
        setCustomModelName(data.model_name || '');
        setIsCustomModel(true);
      }
    } catch (err) {
      setError('Failed to load project');
      console.error('Error loading project:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadModels = async () => {
    try {
      const response = await axios.get(`/api/models/${aiProvider}`);
      setAvailableModels(response.data.models || []);
      if (response.data.models?.length > 0 && !modelName) {
        setModelName(response.data.models[0].name);
      }
    } catch (err) {
      console.error('Error loading models:', err);
    }
  };

  const handleModelChange = (e) => {
    const value = e.target.value;
    setModelName(value);
    if (value === 'custom') {
      setIsCustomModel(true);
    } else {
      setIsCustomModel(false);
      setCustomModelName('');
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);

    // Use custom model name if "custom" is selected
    const finalModelName = isCustomModel ? customModelName : modelName;

    if (!finalModelName) {
      setError('Please enter a model name');
      setSaving(false);
      return;
    }

    try {
      await axios.put(`/api/projects/${projectId}`, {
        ai_provider: aiProvider,
        model_name: finalModelName,
        api_key: apiKey || null,
        temperature: temperature,
        system_prompt: systemPrompt,
        show_thinking: showThinking,
        extended_thinking: extendedThinking
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleGeneratePersonality = async () => {
    if (!apiKey && aiProvider !== 'ollama') {
      setError('API key required to generate personality');
      return;
    }

    setGeneratingPersonality(true);
    setError(null);

    try {
      const response = await axios.post(`/api/projects/${projectId}/generate-personality`, null, {
        params: {
          provider: aiProvider === 'ollama' ? 'anthropic' : aiProvider,
          api_key: apiKey || undefined
        }
      });
      setSystemPrompt(response.data.personality);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate personality');
    } finally {
      setGeneratingPersonality(false);
    }
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="h-12 w-12 border-2 border-green-500/30 border-t-green-500 rounded-full animate-spin mx-auto"></div>
        <p className="mt-4 text-gray-400 font-mono text-sm">
          <span className="text-green-400">$</span> loading settings...<span className="animate-pulse">_</span>
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
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white font-mono flex items-center space-x-2">
            <span className="text-green-400">$</span>
            <span>./settings</span>
          </h2>
          <p className="text-gray-500 font-mono text-sm mt-1">
            Configure AI model and personality
          </p>
        </div>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="mb-6 bg-red-900/30 border border-red-500/50 rounded-lg p-4 font-mono text-sm flex items-center space-x-2">
          <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
          <span className="text-red-300">{error}</span>
        </div>
      )}

      {saved && (
        <div className="mb-6 bg-green-900/30 border border-green-500/50 rounded-lg p-4 font-mono text-sm flex items-center space-x-2">
          <CheckCircleIcon className="h-5 w-5 text-green-400" />
          <span className="text-green-300">Settings saved successfully</span>
        </div>
      )}

      {/* Settings Form */}
      <div className="space-y-6">
        {/* AI Provider Section */}
        <div className="bg-gray-900 rounded-lg border border-gray-700 p-6">
          <h3 className="text-sm font-mono text-cyan-400 mb-4"># ai_provider</h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-mono text-gray-300 mb-2">--provider</label>
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
              <label className="block text-sm font-mono text-gray-300 mb-2">--model</label>
              {availableModels.length > 0 ? (
                <select
                  value={modelName}
                  onChange={handleModelChange}
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono focus:ring-2 focus:ring-green-500"
                >
                  {availableModels.map((model) => (
                    <option key={model.name} value={model.name}>
                      {model.display || model.name}
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
              {isCustomModel && (
                <div className="mt-3">
                  <label className="block text-sm font-mono text-gray-400 mb-2">--custom-model-name</label>
                  <input
                    type="text"
                    value={customModelName}
                    onChange={(e) => setCustomModelName(e.target.value)}
                    placeholder={aiProvider === 'ollama' ? 'e.g., qwen2:7b' : aiProvider === 'openai' ? 'e.g., gpt-4-0125-preview' : 'e.g., claude-3-opus-20240229'}
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono placeholder-gray-500 focus:ring-2 focus:ring-green-500"
                  />
                  <p className="mt-1 text-xs text-gray-500 font-mono">
                    # Enter the exact model identifier
                  </p>
                </div>
              )}
            </div>
          </div>

          {(aiProvider === 'openai' || aiProvider === 'anthropic') && (
            <div className="mt-4">
              <label className="block text-sm font-mono text-gray-300 mb-2">--api-key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={aiProvider === 'anthropic' ? 'sk-ant-...' : 'sk-...'}
                className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono placeholder-gray-500 focus:ring-2 focus:ring-green-500"
              />
            </div>
          )}
        </div>

        {/* Model Parameters Section */}
        <div className="bg-gray-900 rounded-lg border border-gray-700 p-6">
          <h3 className="text-sm font-mono text-cyan-400 mb-4"># model_parameters</h3>

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

          <div className="mt-4 space-y-3">
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
        </div>

        {/* Personality Section */}
        <div className="bg-gray-900 rounded-lg border border-gray-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-mono text-cyan-400"># system_prompt</h3>
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
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            rows={12}
            placeholder="Define your AI's personality, tone, and behavior..."
            className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono text-sm placeholder-gray-500 focus:ring-2 focus:ring-green-500 resize-none"
          />
          <p className="mt-2 text-xs text-gray-500 font-mono">
            # Customize how your AI responds to the community
          </p>
        </div>

        {/* Save Button */}
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full bg-green-500 text-gray-900 py-3 px-4 rounded-lg font-mono font-semibold hover:bg-green-400 disabled:bg-gray-700 disabled:text-gray-500 transition-colors flex items-center justify-center space-x-2"
        >
          {saving ? (
            <>
              <ArrowPathIcon className="h-5 w-5 animate-spin" />
              <span>Saving...</span>
            </>
          ) : (
            <>
              <CogIcon className="h-5 w-5" />
              <span>$ ./save --config</span>
              <span className="animate-pulse">_</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export default Settings;
