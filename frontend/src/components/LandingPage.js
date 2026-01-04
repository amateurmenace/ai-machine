import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  SparklesIcon,
  GlobeAltIcon,
  CodeBracketIcon,
  HeartIcon,
  BoltIcon,
  CpuChipIcon,
  UserGroupIcon,
  CloudIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  ServerIcon,
  ChatBubbleLeftRightIcon,
  PaperAirplaneIcon,
  XMarkIcon,
  ExclamationCircleIcon
} from '@heroicons/react/24/outline';

function LandingPage() {
  const navigate = useNavigate();
  const [energyCount, setEnergyCount] = useState(0);
  const [localEnergyCount, setLocalEnergyCount] = useState(0);
  const [projects, setProjects] = useState([]);
  const [projectsHealth, setProjectsHealth] = useState({});
  const [activeChat, setActiveChat] = useState(null);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  // Animated energy counter
  useEffect(() => {
    const interval = setInterval(() => {
      setEnergyCount(prev => {
        if (prev >= 100) return 0;
        return prev + 2;
      });
      
      setLocalEnergyCount(prev => {
        if (prev >= 0.5) return 0;
        return prev + 0.01;
      });
    }, 50);

    return () => clearInterval(interval);
  }, []);

  // Load projects and check their health
  useEffect(() => {
    const loadProjects = async () => {
      try {
        const response = await axios.get('/api/projects');
        setProjects(response.data);

        // Check health for each project
        const healthStatuses = {};
        for (const project of response.data) {
          try {
            const healthRes = await axios.get(`/api/projects/${project.project_id}/health`);
            healthStatuses[project.project_id] = healthRes.data;
          } catch (err) {
            healthStatuses[project.project_id] = { ready: false, issues: ['Unable to check health'] };
          }
        }
        setProjectsHealth(healthStatuses);
      } catch (err) {
        console.error('Error loading projects:', err);
      }
    };

    loadProjects();
  }, []);

  // Scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const openChat = (project) => {
    const health = projectsHealth[project.project_id];
    if (!health?.ready) return; // Don't open if not ready

    setActiveChat(project);
    setChatMessages([{
      role: 'assistant',
      content: `Hi! I'm ${project.project_name}. Ask me anything about ${project.municipality_name}!`
    }]);
  };

  const closeChat = () => {
    setActiveChat(null);
    setChatMessages([]);
    setChatInput('');
  };

  const sendChatMessage = async () => {
    if (!chatInput.trim() || chatLoading || !activeChat) return;

    const userMessage = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setChatLoading(true);

    try {
      const response = await axios.post('/api/chat', {
        project_id: activeChat.project_id,
        message: userMessage,
        conversation_history: chatMessages.slice(-5).map(m => ({ role: m.role, content: m.content }))
      });

      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: response.data.answer,
        sources: response.data.sources
      }]);
    } catch (err) {
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        isError: true
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleChatKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  };

  const codeSnippet = `// Your community's AI assistant
const brooklineAI = {
  location: "Brookline, MA",
  model: "llama3.1:8b",  // 8GB, runs locally
  energy: "2W",          // Like a phone charger
  cost: "$0/month",      // Free forever
  privacy: "100%",       // Your server, your data
  
  sources: [
    "town-meetings.youtube",
    "brookline.news",
    "community-forums"
  ]
};

// Ask questions about your town
brooklineAI.ask("What are the rules for block parties?");
// → Cites actual town ordinances
// → Uses 0.002 kWh of energy
// → Costs $0`;

  const handleNavigateToConsole = () => {
    navigate('/console');
  };

  return (
    <div className="min-h-screen bg-white relative overflow-hidden">
      {/* Animated colorful background with network patterns */}
      <div className="fixed inset-0 pointer-events-none">
        {/* Colorful animated globs */}
        <div className="absolute top-20 left-10 w-96 h-96 bg-gradient-to-br from-blue-300/20 to-purple-300/20 rounded-full blur-3xl animate-blob"></div>
        <div className="absolute top-40 right-20 w-80 h-80 bg-gradient-to-br from-orange-300/20 to-pink-300/20 rounded-full blur-3xl animate-blob animation-delay-2000"></div>
        <div className="absolute bottom-20 left-1/4 w-72 h-72 bg-gradient-to-br from-green-300/20 to-teal-300/20 rounded-full blur-3xl animate-blob animation-delay-4000"></div>
        <div className="absolute bottom-40 right-1/3 w-64 h-64 bg-gradient-to-br from-yellow-300/20 to-orange-300/20 rounded-full blur-3xl animate-blob animation-delay-6000"></div>
        <div className="absolute top-1/2 left-1/2 w-96 h-96 bg-gradient-to-br from-rose-300/15 to-purple-300/15 rounded-full blur-3xl animate-blob animation-delay-3000"></div>
        
        {/* Weave and grid patterns */}
        <div className="absolute inset-0 opacity-[0.015]">
          <div className="bg-weave-pattern"></div>
        </div>
        <div className="absolute inset-0 opacity-[0.02]">
          <div className="bg-grid-pattern"></div>
        </div>
        
        {/* Network connection lines */}
        <svg className="absolute inset-0 w-full h-full opacity-[0.03]" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="network-pattern" x="0" y="0" width="200" height="200" patternUnits="userSpaceOnUse">
              <circle cx="0" cy="0" r="2" fill="#000" />
              <circle cx="100" cy="50" r="2" fill="#000" />
              <circle cx="200" cy="0" r="2" fill="#000" />
              <circle cx="50" cy="100" r="2" fill="#000" />
              <circle cx="150" cy="150" r="2" fill="#000" />
              <line x1="0" y1="0" x2="100" y2="50" stroke="#000" strokeWidth="1" />
              <line x1="100" y1="50" x2="200" y2="0" stroke="#000" strokeWidth="1" />
              <line x1="100" y1="50" x2="50" y2="100" stroke="#000" strokeWidth="1" />
              <line x1="100" y1="50" x2="150" y2="150" stroke="#000" strokeWidth="1" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#network-pattern)" className="animate-network-flow" />
        </svg>
      </div>

      {/* Header */}
      <header className="relative z-10 bg-gray-900/95 backdrop-blur-sm border-b border-green-500/30 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2">
                <span className="text-green-400 font-mono text-lg animate-pulse">&gt;</span>
                <h1 className="text-2xl md:text-3xl font-bold text-white font-mono tracking-tight">
                  neighborhood<span className="text-green-400">_</span>ai
                </h1>
              </div>
              <span className="hidden sm:inline-block px-2 py-0.5 bg-green-500/20 text-green-400 text-xs font-mono rounded border border-green-500/30">
                v1.0.0
              </span>
            </div>

            <nav className="flex items-center space-x-4">
              <a href="#why" className="text-gray-400 hover:text-green-400 text-sm font-mono transition-colors hidden sm:inline">why</a>
              <a href="#how" className="text-gray-400 hover:text-green-400 text-sm font-mono transition-colors hidden sm:inline">how</a>
              <a href="#values" className="text-gray-400 hover:text-green-400 text-sm font-mono transition-colors hidden sm:inline">values</a>
              {projects.length > 0 && (
                <a href="#projects" className="text-gray-400 hover:text-green-400 text-sm font-mono transition-colors hidden sm:inline">projects</a>
              )}
              <button
                onClick={() => navigate('/guide')}
                className="text-purple-400 hover:text-purple-300 px-3 py-2 font-mono text-sm transition-colors border border-purple-500/30 rounded hover:bg-purple-500/10"
              >
                guide
              </button>
              <button
                onClick={handleNavigateToConsole}
                className="bg-green-500 text-gray-900 px-4 py-2 rounded font-mono text-sm font-semibold hover:bg-green-400 transition-colors flex items-center space-x-1"
              >
                <span>./console</span>
                <span className="animate-pulse">_</span>
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <div className="relative pt-16 pb-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h1 className="text-5xl md:text-6xl font-bold mb-6 text-gray-900">
              AI for <span className="text-orange-600">Us</span>
            </h1>
            
            <p className="text-xl md:text-2xl text-gray-700 mb-4 font-light max-w-3xl mx-auto">
              Build privacy-respecting, energy-efficient AI assistants for your community
            </p>
            
            <p className="text-lg text-gray-600 max-w-3xl mx-auto mb-8">
              Run powerful AI on local hardware. Zero cloud costs. Zero surveillance. 
              1000x less energy than frontier models. 100% yours.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <button
                onClick={handleNavigateToConsole}
                className="group relative px-8 py-4 bg-gradient-to-r from-orange-500 to-rose-500 text-white rounded-lg font-semibold text-lg hover:shadow-lg hover:shadow-orange-500/50 transition-all duration-300 flex items-center space-x-2"
              >
                <span>Open Console</span>
                <ArrowRightIcon className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
              </button>
              
              <a
                href="https://github.com/amateurmenace/ai-machine"
                target="_blank"
                rel="noopener noreferrer"
                className="px-8 py-4 bg-white border-2 border-gray-900 text-gray-900 rounded-lg font-semibold text-lg hover:bg-gray-50 transition-all duration-300 flex items-center space-x-2"
              >
                <CodeBracketIcon className="h-5 w-5" />
                <span>View on GitHub</span>
              </a>
            </div>
          </div>

          {/* Code Demo */}
          <div className="max-w-4xl mx-auto mt-16">
            <div className="bg-gray-900 rounded-lg border-2 border-orange-300 shadow-2xl shadow-orange-500/20 overflow-hidden">
              <div className="flex items-center space-x-2 px-4 py-3 bg-gray-800 border-b border-gray-700">
                <div className="flex space-x-2">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                </div>
                <span className="text-gray-400 text-sm font-mono ml-4">neighborhood-ai.js</span>
              </div>
              <pre className="p-6 overflow-x-auto">
                <code className="text-sm font-mono text-green-400 whitespace-pre">
                  {codeSnippet}
                </code>
              </pre>
            </div>
          </div>
        </div>
      </div>

      {/* Energy Comparison Section */}
      <div id="why" className="relative bg-gradient-to-br from-blue-50/50 to-purple-50/50 backdrop-blur-sm py-20 border-y border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4 text-gray-900">
              The Environmental Case for <span className="text-green-600">Local AI</span>
            </h2>
            <p className="text-xl text-gray-600">
              Same question. 1000x difference in energy use.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-12 max-w-5xl mx-auto">
            {/* Frontier Model */}
            <div className="bg-gradient-to-br from-red-50 to-orange-50 border-2 border-red-200 rounded-lg p-8">
              <div className="flex items-center space-x-3 mb-6">
                <CloudIcon className="h-10 w-10 text-red-600" />
                <div>
                  <h3 className="text-2xl font-bold text-gray-900">Cloud Frontier Model</h3>
                  <p className="text-sm text-gray-600">e.g., GPT-4, Claude Opus</p>
                </div>
              </div>
              
              <div className="space-y-4 mb-6">
                <div className="bg-white rounded-lg p-4 border border-red-200">
                  <p className="text-sm text-gray-600 mb-2">Query:</p>
                  <p className="font-mono text-sm text-gray-900">"What are the rules for block parties in Brookline?"</p>
                </div>
                
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Data center processing</span>
                    <span className="font-bold text-red-600">~100W</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Network transfer</span>
                    <span className="font-bold text-red-600">Variable</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Cooling infrastructure</span>
                    <span className="font-bold text-red-600">~40W</span>
                  </div>
                </div>
              </div>

              <div className="bg-red-600 rounded-lg p-4 text-white">
                <div className="flex justify-between items-center mb-2">
                  <span className="font-semibold">Energy per query:</span>
                  <span className="text-3xl font-bold">{energyCount.toFixed(0)}W</span>
                </div>
                <div className="h-4 bg-red-800 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-red-400 transition-all duration-100"
                    style={{ width: `${energyCount}%` }}
                  ></div>
                </div>
                <p className="text-xs mt-2 text-red-100">≈ Running a bright incandescent bulb</p>
              </div>

              <div className="mt-6 space-y-2 text-sm text-gray-600">
                <p>💰 Cost: $0.003 - $0.15 per query</p>
                <p>🌍 Carbon: ~50g CO₂ per query (US grid avg)</p>
                <p>📊 Training: 1 model = 502 tons CO₂</p>
              </div>
            </div>

            {/* Local Model */}
            <div className="bg-gradient-to-br from-green-50 to-emerald-50 border-2 border-green-300 rounded-lg p-8">
              <div className="flex items-center space-x-3 mb-6">
                <ServerIcon className="h-10 w-10 text-green-600" />
                <div>
                  <h3 className="text-2xl font-bold text-gray-900">Local Neighborhood AI</h3>
                  <p className="text-sm text-gray-600">Mac Mini M4, Llama 3.1 8B</p>
                </div>
              </div>
              
              <div className="space-y-4 mb-6">
                <div className="bg-white rounded-lg p-4 border border-green-200">
                  <p className="text-sm text-gray-600 mb-2">Same query:</p>
                  <p className="font-mono text-sm text-gray-900">"What are the rules for block parties in Brookline?"</p>
                </div>
                
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Mac Mini M4 (idle: 7W)</span>
                    <span className="font-bold text-green-600">+2W</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Network transfer</span>
                    <span className="font-bold text-green-600">None</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Data center overhead</span>
                    <span className="font-bold text-green-600">None</span>
                  </div>
                </div>
              </div>

              <div className="bg-green-600 rounded-lg p-4 text-white">
                <div className="flex justify-between items-center mb-2">
                  <span className="font-semibold">Energy per query:</span>
                  <span className="text-3xl font-bold">{localEnergyCount.toFixed(2)}W</span>
                </div>
                <div className="h-4 bg-green-800 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-green-400 transition-all duration-100"
                    style={{ width: `${(localEnergyCount / 0.5) * 100}%` }}
                  ></div>
                </div>
                <p className="text-xs mt-2 text-green-100">≈ Charging a phone (barely noticeable)</p>
              </div>

              <div className="mt-6 space-y-2 text-sm text-gray-600">
                <p>💰 Cost: $0.00 per query (already running)</p>
                <p>🌍 Carbon: ~0.05g CO₂ per query</p>
                <p>📊 Training: Reuse existing model (0 CO₂)</p>
              </div>
            </div>
          </div>

          <div className="mt-12 text-center">
            <div className="inline-block bg-green-100 border-2 border-green-400 rounded-lg px-8 py-6 max-w-2xl">
              <p className="text-2xl font-bold text-green-900 mb-2">
                ~1000x less energy per query
              </p>
              <p className="text-gray-700">
                A Mac Mini M4 can handle your entire town's questions using the same energy 
                as <span className="font-semibold">a single cloud query</span>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Different Purposes, Not Evil */}
      <div className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4 text-gray-900">
              Different Tools for Different Jobs
            </h2>
            <p className="text-xl text-gray-600">
              Frontier models and local AI serve different purposes
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-lg p-6 shadow-sm">
              <CloudIcon className="h-12 w-12 text-blue-600 mb-4" />
              <h3 className="text-xl font-bold mb-3 text-gray-900">Frontier Models</h3>
              <p className="text-gray-700 mb-4">
                <span className="font-semibold">Best for:</span> Complex reasoning, multimodal tasks, 
                diverse knowledge, creative work, research
              </p>
              <p className="text-sm text-gray-600">
                Amazing technology. Just not designed for local community questions where 
                energy efficiency and privacy matter more than cutting-edge capabilities.
              </p>
            </div>

            <div className="bg-gradient-to-br from-orange-50 to-rose-50 border-2 border-orange-200 rounded-lg p-6 shadow-sm">
              <ServerIcon className="h-12 w-12 text-orange-600 mb-4" />
              <h3 className="text-xl font-bold mb-3 text-gray-900">Neighborhood AI</h3>
              <p className="text-gray-700 mb-4">
                <span className="font-semibold">Best for:</span> Local questions, community knowledge, 
                town services, energy efficiency, privacy
              </p>
              <p className="text-sm text-gray-600">
                Purpose-built for communities. Runs on modest hardware. Answers questions about 
                YOUR town using YOUR data. Zero waste.
              </p>
            </div>

            <div className="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-lg p-6 shadow-sm">
              <HeartIcon className="h-12 w-12 text-rose-600 mb-4" />
              <h3 className="text-xl font-bold mb-3 text-gray-900">The Right Tool</h3>
              <p className="text-gray-700 mb-4">
                <span className="font-semibold">Use both:</span> Frontier models for complex tasks, 
                local AI for community knowledge
              </p>
              <p className="text-sm text-gray-600">
                We're not anti-AI. We're pro-appropriate-technology. Use a Mac Mini for town questions, 
                save the big models for when you actually need them.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* How It Works */}
      <div id="how" className="relative bg-gradient-to-br from-green-50/50 to-teal-50/50 backdrop-blur-sm py-20 border-y border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4 text-gray-900">
              Four Steps to Your Own AI
            </h2>
          </div>

          <div className="grid md:grid-cols-4 gap-6">
            {[
              { step: '01', title: 'Discover Sources', desc: 'Find town meetings, news, documents', emoji: '🔍' },
              { step: '02', title: 'Ingest & Index', desc: 'Process and vectorize content', emoji: '📚' },
              { step: '03', title: 'Run Locally', desc: 'Llama 3.1 on your Mac Mini', emoji: '💻' },
              { step: '04', title: 'Serve Community', desc: 'Answer questions, cite sources', emoji: '✅' }
            ].map((item, idx) => (
              <div key={idx} className="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-lg p-6 hover:shadow-lg hover:border-gray-300 transition-all">
                <div className="text-5xl mb-4">{item.emoji}</div>
                <div className="text-3xl font-bold text-orange-500 mb-2">{item.step}</div>
                <h3 className="text-lg font-bold mb-2 text-gray-900">{item.title}</h3>
                <p className="text-sm text-gray-600">{item.desc}</p>
              </div>
            ))}
          </div>

          <div className="mt-12 text-center">
            <button
              onClick={handleNavigateToConsole}
              className="inline-flex items-center space-x-2 bg-orange-600 hover:bg-orange-700 text-white px-8 py-4 rounded-lg font-semibold text-lg transition-all duration-300"
            >
              <span>Start Building</span>
              <ArrowRightIcon className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Values */}
      <div id="values" className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4 text-gray-900">
              Built on Principles
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              { icon: HeartIcon, title: 'Community-First', desc: 'Built for people, not profit. Open source, free to run.', color: 'rose' },
              { icon: BoltIcon, title: 'Energy Efficient', desc: '1000x less energy than cloud models. Run on a Mac Mini.', color: 'yellow' },
              { icon: UserGroupIcon, title: 'Civic-Minded', desc: 'Encourages participation. Cites sources. No hallucinations.', color: 'green' },
              { icon: CpuChipIcon, title: 'Local-First', desc: 'Your data on your hardware. Cloud optional. Privacy by default.', color: 'indigo' },
              { icon: CodeBracketIcon, title: 'Open Source', desc: 'MIT license. Fork it, improve it, share it.', color: 'purple' },
              { icon: GlobeAltIcon, title: 'Community Owned', desc: 'Run by libraries, community centers, local government.', color: 'blue' }
            ].map((value, idx) => (
              <div key={idx} className="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-lg p-6 hover:border-gray-300 hover:shadow-md transition-all">
                <value.icon className={`h-10 w-10 mb-4 text-${value.color}-600`} />
                <h3 className="text-xl font-bold mb-3 text-gray-900">{value.title}</h3>
                <p className="text-gray-600">{value.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Real Example */}
      <div className="relative bg-gradient-to-br from-orange-50/50 to-rose-50/50 backdrop-blur-sm py-20 border-y border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-white/80 backdrop-blur-sm border-2 border-orange-200 rounded-lg p-12 shadow-lg">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold mb-4 text-gray-900">Real Example: Brookline AI</h2>
              <p className="text-gray-600 text-lg">
                Powered by Brookline Interactive Group, serving the community for 40+ years
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
              <div>
                <h3 className="text-xl font-bold mb-4 text-orange-600">Data Sources</h3>
                <ul className="space-y-2 text-gray-700">
                  <li className="flex items-center space-x-2">
                    <CheckCircleIcon className="h-5 w-5 text-green-500" />
                    <span>500+ hours of Select Board meetings</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircleIcon className="h-5 w-5 text-green-500" />
                    <span>Brookline.news archive</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircleIcon className="h-5 w-5 text-green-500" />
                    <span>Town website</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircleIcon className="h-5 w-5 text-green-500" />
                    <span>Community discussions</span>
                  </li>
                </ul>
              </div>

              <div>
                <h3 className="text-xl font-bold mb-4 text-green-600">Example Questions</h3>
                <div className="space-y-3">
                  {["When is trash day?", "What did the Select Board decide?", "How do I get a dog license?"].map((q, i) => (
                    <div key={i} className="bg-gray-50 rounded p-3 border border-gray-200">
                      <p className="text-gray-900 font-mono text-sm">"{q}"</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-8 text-center">
              <div className="inline-block bg-green-100 border-2 border-green-400 rounded-lg px-6 py-3">
                <span className="text-gray-700">Cost: </span>
                <span className="font-bold text-gray-900">$0.50 setup</span>
                <span className="text-gray-700"> • Monthly: </span>
                <span className="font-bold text-gray-900">$0</span>
                <span className="text-gray-700"> • Energy: </span>
                <span className="font-bold text-green-700">2W</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Projects Showcase */}
      {projects.length > 0 && (
        <div id="projects" className="relative bg-gray-50 py-20 border-y border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-16">
              <h2 className="text-4xl font-bold mb-4 text-gray-900">
                Community AIs <span className="text-green-600">in Action</span>
              </h2>
              <p className="text-xl text-gray-600">
                Try chatting with these neighborhood AI assistants
              </p>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {projects.map((project) => {
                const health = projectsHealth[project.project_id];
                const isReady = health?.ready;

                return (
                  <div
                    key={project.project_id}
                    className={`relative rounded-xl overflow-hidden border-2 transition-all duration-300 ${
                      isReady
                        ? 'bg-white border-green-300 hover:border-green-400 hover:shadow-lg cursor-pointer'
                        : 'bg-gray-100 border-gray-300 opacity-60'
                    }`}
                    onClick={() => isReady && openChat(project)}
                  >
                    {/* Project Card Header */}
                    <div className={`p-6 ${isReady ? 'bg-gradient-to-r from-green-500 to-emerald-500' : 'bg-gray-400'}`}>
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-xl font-bold text-white">{project.project_name}</h3>
                          <p className="text-green-100 text-sm">{project.municipality_name}</p>
                        </div>
                        <div className={`p-2 rounded-lg ${isReady ? 'bg-white/20' : 'bg-gray-500/30'}`}>
                          <ChatBubbleLeftRightIcon className="h-6 w-6 text-white" />
                        </div>
                      </div>
                    </div>

                    {/* Project Card Body */}
                    <div className="p-6">
                      <div className="flex items-center space-x-2 mb-4">
                        <span className={`w-2 h-2 rounded-full ${isReady ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`}></span>
                        <span className={`text-sm font-mono ${isReady ? 'text-green-600' : 'text-gray-500'}`}>
                          {isReady ? 'online' : 'offline'}
                        </span>
                      </div>

                      {!isReady && health?.issues && (
                        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                          <div className="flex items-start space-x-2">
                            <ExclamationCircleIcon className="h-5 w-5 text-yellow-500 flex-shrink-0" />
                            <div className="text-xs text-yellow-700">
                              {health.issues.slice(0, 2).map((issue, i) => (
                                <p key={i}>{issue}</p>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}

                      <div className="text-sm text-gray-600 space-y-1">
                        <p><span className="text-gray-400">Model:</span> {project.model_name}</p>
                        <p><span className="text-gray-400">Sources:</span> {project.data_sources?.length || 0}</p>
                      </div>

                      {isReady && (
                        <button className="mt-4 w-full py-2 bg-green-500 text-white rounded-lg font-semibold text-sm hover:bg-green-600 transition-colors flex items-center justify-center space-x-2">
                          <ChatBubbleLeftRightIcon className="h-4 w-4" />
                          <span>Start Chat</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-12 text-center">
              <button
                onClick={() => navigate('/console/new')}
                className="inline-flex items-center space-x-2 bg-orange-600 hover:bg-orange-700 text-white px-8 py-4 rounded-lg font-semibold text-lg transition-all duration-300"
              >
                <span>Create Your Own</span>
                <ArrowRightIcon className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Chat Modal */}
      {activeChat && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-900 rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col border-2 border-green-500/50 shadow-2xl">
            {/* Chat Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-700">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-green-500/20 rounded-lg">
                  <ChatBubbleLeftRightIcon className="h-5 w-5 text-green-400" />
                </div>
                <div>
                  <h3 className="font-bold text-white">{activeChat.project_name}</h3>
                  <p className="text-xs text-gray-400">{activeChat.municipality_name}</p>
                </div>
              </div>
              <button
                onClick={closeChat}
                className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-gray-800 transition-colors"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>

            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-[300px]">
              {chatMessages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-3 ${
                      msg.role === 'user'
                        ? 'bg-green-500/20 border border-green-500/30 text-green-100'
                        : msg.isError
                          ? 'bg-red-500/10 border border-red-500/30 text-red-300'
                          : 'bg-gray-800 border border-gray-700 text-gray-200'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-gray-700">
                        <p className="text-xs text-gray-500 mb-1">Sources:</p>
                        {msg.sources.slice(0, 2).map((s, i) => (
                          <a
                            key={i}
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block text-xs text-cyan-400 hover:text-cyan-300 truncate"
                          >
                            {s.title}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-3">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                      <div className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                      <div className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            {/* Chat Input */}
            <div className="p-4 border-t border-gray-700">
              <div className="flex space-x-3">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyPress={handleChatKeyPress}
                  placeholder="Ask a question..."
                  className="flex-1 px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-green-500 focus:border-transparent"
                />
                <button
                  onClick={sendChatMessage}
                  disabled={!chatInput.trim() || chatLoading}
                  className="px-4 py-3 bg-green-500 text-gray-900 rounded-lg font-semibold hover:bg-green-400 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed transition-colors"
                >
                  <PaperAirplaneIcon className="h-5 w-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Final CTA */}
      <div className="bg-gradient-to-r from-orange-500 via-rose-500 to-pink-500 py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-4xl font-bold mb-6 text-white">
            Ready to Build AI for Your Community?
          </h2>
          <p className="text-xl mb-8 text-orange-50">
            Open source. Free to run. 1000x more efficient. Yours to control.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={handleNavigateToConsole}
              className="bg-white text-orange-600 px-8 py-4 rounded-lg font-bold text-lg hover:bg-gray-100 transition-all duration-300 flex items-center justify-center space-x-2"
            >
              <span>Launch Console</span>
              <ArrowRightIcon className="h-5 w-5" />
            </button>
            
            <a
              href="https://github.com/amateurmenace/ai-machine"
              target="_blank"
              rel="noopener noreferrer"
              className="bg-transparent border-2 border-white text-white px-8 py-4 rounded-lg font-bold text-lg hover:bg-white/10 transition-all duration-300 flex items-center justify-center space-x-2"
            >
              <CodeBracketIcon className="h-5 w-5" />
              <span>View Source</span>
            </a>
          </div>

          <div className="mt-8 text-sm text-orange-50">
            MIT License • Community Owned • Energy Efficient
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="bg-gray-900 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <h3 className="font-bold text-white mb-4">Neighborhood AI</h3>
              <p className="text-gray-400 text-sm">
                Building AI for communities, not corporations.
              </p>
            </div>
            
            <div>
              <h4 className="font-semibold text-white mb-4">Resources</h4>
              <ul className="space-y-2 text-sm text-gray-400">
                <li><a href="https://github.com/amateurmenace/ai-machine" className="hover:text-white">Documentation</a></li>
                <li><a href="https://github.com/amateurmenace/ai-machine" className="hover:text-white">GitHub</a></li>
                <li><a href="#" className="hover:text-white">Examples</a></li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold text-white mb-4">Community</h4>
              <ul className="space-y-2 text-sm text-gray-400">
                <li><a href="#" className="hover:text-white">Forum</a></li>
                <li><a href="#" className="hover:text-white">Discord</a></li>
                <li><a href="mailto:stephen@weirdmachine.org" className="hover:text-white">Contact</a></li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold text-white mb-4">Family of Apps</h4>
              <ul className="space-y-2 text-sm text-gray-400">
                <li><a href="https://community.weirdmachine.org" className="hover:text-white">Community AI Project</a></li>
                <li><a href="#" className="hover:text-white">Community Highlighter</a></li>
              </ul>
            </div>
          </div>
          
          <div className="border-t border-gray-800 pt-8">
            {/* Attribution and Logos */}
            <div className="flex flex-col md:flex-row items-center justify-between gap-6 mb-6">
              <div className="text-center md:text-left">
                <p className="text-gray-300 text-sm mb-2">
                  A <a href="https://community.weirdmachine.org" className="text-orange-400 hover:text-orange-300">Community AI Project</a> from{' '}
                  <a href="https://brooklineinteractive.org" className="text-blue-400 hover:text-blue-300">Brookline Interactive Group</a>{' '}
                  in partnership with Neighborhood AI
                </p>
                <p className="text-gray-400 text-xs">
                  Designed and developed by <a href="https://weirdmachine.org" className="text-gray-300 hover:text-white">Stephen Walter</a> + AI
                </p>
              </div>
              
              <div className="flex items-center gap-6">
                <a href="https://weirdmachine.org" target="_blank" rel="noopener noreferrer">
                  <img src="/weirdmachine.png" alt="Weird Machine" className="h-8 w-auto opacity-80 hover:opacity-100 transition-opacity" />
                </a>
                <a href="https://brooklineinteractive.org" target="_blank" rel="noopener noreferrer">
                  <img src="/big-logo.png" alt="Brookline Interactive Group" className="h-12 w-auto opacity-80 hover:opacity-100 transition-opacity" />
                </a>
              </div>
            </div>
            
            {/* Creative Commons License */}
            <div className="flex flex-col md:flex-row items-center justify-center gap-4 pt-4 border-t border-gray-800">
              <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-gray-400 hover:text-gray-300 text-sm">
                <svg className="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/>
                </svg>
                <span>Licensed under CC BY-NC-SA 4.0</span>
              </a>
              <span className="text-gray-600 hidden md:inline">•</span>
              <p className="text-gray-500 text-xs">
                Creative Commons Attribution-NonCommercial-ShareAlike
              </p>
            </div>
            
            <div className="text-center text-gray-500 text-xs mt-6">
              Made for communities by civic technologists 🏘️
            </div>
          </div>
        </div>
      </div>

      {/* Custom CSS for animated background */}
      <style>{`
        @keyframes blob {
          0%, 100% {
            transform: translate(0, 0) scale(1);
          }
          25% {
            transform: translate(20px, -20px) scale(1.1);
          }
          50% {
            transform: translate(-20px, 20px) scale(0.9);
          }
          75% {
            transform: translate(10px, 10px) scale(1.05);
          }
        }
        
        .animate-blob {
          animation: blob 20s ease-in-out infinite;
        }
        
        .animation-delay-2000 {
          animation-delay: 2s;
        }
        
        .animation-delay-3000 {
          animation-delay: 3s;
        }
        
        .animation-delay-4000 {
          animation-delay: 4s;
        }
        
        .animation-delay-6000 {
          animation-delay: 6s;
        }
        
        .bg-weave-pattern {
          width: 100%;
          height: 100%;
          background-image:
            repeating-linear-gradient(
              45deg,
              transparent,
              transparent 10px,
              rgba(0, 0, 0, 0.1) 10px,
              rgba(0, 0, 0, 0.1) 11px
            ),
            repeating-linear-gradient(
              -45deg,
              transparent,
              transparent 10px,
              rgba(0, 0, 0, 0.1) 10px,
              rgba(0, 0, 0, 0.1) 11px
            );
        }
        
        .bg-grid-pattern {
          width: 100%;
          height: 100%;
          background-image:
            linear-gradient(rgba(0, 0, 0, 0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 0, 0, 0.1) 1px, transparent 1px);
          background-size: 50px 50px;
          animation: grid-flow 30s linear infinite;
        }
        
        @keyframes grid-flow {
          0% {
            transform: translate(0, 0);
          }
          100% {
            transform: translate(50px, 50px);
          }
        }
        
        @keyframes network-flow {
          0% {
            opacity: 0.03;
          }
          50% {
            opacity: 0.05;
          }
          100% {
            opacity: 0.03;
          }
        }
        
        .animate-network-flow {
          animation: network-flow 8s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}

export default LandingPage;
