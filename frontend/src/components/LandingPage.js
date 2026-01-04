import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
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
import Footer from './Footer';

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
      {/* Animated colorful background with blueprint/urban planning patterns */}
      <div className="fixed inset-0 pointer-events-none">
        {/* Colorful animated globs */}
        <div className="absolute top-20 left-10 w-96 h-96 bg-gradient-to-br from-blue-300/20 to-purple-300/20 rounded-full blur-3xl animate-blob"></div>
        <div className="absolute top-40 right-20 w-80 h-80 bg-gradient-to-br from-orange-300/20 to-pink-300/20 rounded-full blur-3xl animate-blob animation-delay-2000"></div>
        <div className="absolute bottom-20 left-1/4 w-72 h-72 bg-gradient-to-br from-green-300/20 to-teal-300/20 rounded-full blur-3xl animate-blob animation-delay-4000"></div>
        <div className="absolute bottom-40 right-1/3 w-64 h-64 bg-gradient-to-br from-yellow-300/20 to-orange-300/20 rounded-full blur-3xl animate-blob animation-delay-6000"></div>
        <div className="absolute top-1/2 left-1/2 w-96 h-96 bg-gradient-to-br from-rose-300/15 to-purple-300/15 rounded-full blur-3xl animate-blob animation-delay-3000"></div>

        {/* Blueprint grid pattern */}
        <div className="absolute inset-0 opacity-[0.03]">
          <div className="blueprint-grid"></div>
        </div>

        {/* Civic doodles / urban planning sketches */}
        <svg className="absolute inset-0 w-full h-full opacity-[0.04]" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="civic-pattern" x="0" y="0" width="400" height="400" patternUnits="userSpaceOnUse">
              {/* City grid streets */}
              <line x1="0" y1="100" x2="400" y2="100" stroke="#1e40af" strokeWidth="1" strokeDasharray="8 4" />
              <line x1="0" y1="200" x2="400" y2="200" stroke="#1e40af" strokeWidth="1" strokeDasharray="8 4" />
              <line x1="0" y1="300" x2="400" y2="300" stroke="#1e40af" strokeWidth="1" strokeDasharray="8 4" />
              <line x1="100" y1="0" x2="100" y2="400" stroke="#1e40af" strokeWidth="1" strokeDasharray="8 4" />
              <line x1="200" y1="0" x2="200" y2="400" stroke="#1e40af" strokeWidth="1" strokeDasharray="8 4" />
              <line x1="300" y1="0" x2="300" y2="400" stroke="#1e40af" strokeWidth="1" strokeDasharray="8 4" />

              {/* Building outlines - simple rectangles representing blocks */}
              <rect x="20" y="20" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1" />
              <rect x="120" y="20" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1" />
              <rect x="220" y="120" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1" />
              <rect x="320" y="220" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1" />
              <rect x="20" y="220" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1" />
              <rect x="120" y="320" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1" />

              {/* Town hall / civic building */}
              <rect x="220" y="320" width="80" height="50" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <polygon points="220,320 260,290 300,320" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <rect x="255" y="340" width="10" height="30" fill="none" stroke="#1e40af" strokeWidth="1" />

              {/* Park / green space */}
              <circle cx="350" cy="50" r="30" fill="none" stroke="#16a34a" strokeWidth="1" strokeDasharray="4 2" />
              <circle cx="50" cy="350" r="25" fill="none" stroke="#16a34a" strokeWidth="1" strokeDasharray="4 2" />

              {/* Connection nodes */}
              <circle cx="100" cy="100" r="4" fill="#1e40af" />
              <circle cx="200" cy="100" r="4" fill="#1e40af" />
              <circle cx="300" cy="100" r="4" fill="#1e40af" />
              <circle cx="100" cy="200" r="4" fill="#1e40af" />
              <circle cx="200" cy="200" r="4" fill="#1e40af" />
              <circle cx="300" cy="200" r="4" fill="#1e40af" />
              <circle cx="100" cy="300" r="4" fill="#1e40af" />
              <circle cx="200" cy="300" r="4" fill="#1e40af" />
              <circle cx="300" cy="300" r="4" fill="#1e40af" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#civic-pattern)" className="animate-civic-drift" />
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
              <Link
                to="/about"
                className="text-gray-400 hover:text-orange-400 text-sm font-mono transition-colors hidden sm:inline"
              >
                about
              </Link>
              <Link
                to="/guide"
                className="text-purple-400 hover:text-purple-300 px-3 py-2 font-mono text-sm transition-colors border border-purple-500/30 rounded hover:bg-purple-500/10"
              >
                guide
              </Link>
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

              <Link
                to="/guide"
                className="px-8 py-4 bg-purple-600 text-white rounded-lg font-semibold text-lg hover:bg-purple-500 transition-all duration-300 flex items-center space-x-2"
              >
                <SparklesIcon className="h-5 w-5" />
                <span>Read the Guide</span>
              </Link>

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

      {/* Architecture Diagram */}
      <div id="architecture" className="py-20 bg-gradient-to-br from-slate-900 to-gray-900 relative overflow-hidden">
        {/* Blueprint background for this section */}
        <div className="absolute inset-0 opacity-10">
          <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id="blueprint-grid-arch" x="0" y="0" width="50" height="50" patternUnits="userSpaceOnUse">
                <line x1="0" y1="0" x2="50" y2="0" stroke="#3b82f6" strokeWidth="0.5" />
                <line x1="0" y1="0" x2="0" y2="50" stroke="#3b82f6" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#blueprint-grid-arch)" />
          </svg>
        </div>

        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold mb-4 text-white font-mono">
              <span className="text-blue-400">#</span> system_architecture
            </h2>
            <p className="text-xl text-gray-400">
              How Neighborhood AI turns your data into answers
            </p>
          </div>

          {/* Architecture Diagram as SVG */}
          <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl border-2 border-blue-500/30 p-8 shadow-2xl">
            <svg viewBox="0 0 900 320" className="w-full h-auto" xmlns="http://www.w3.org/2000/svg">
              {/* Connection lines */}
              <defs>
                <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                  <polygon points="0 0, 10 3.5, 0 7" fill="#22d3ee" />
                </marker>
                <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.3" />
                  <stop offset="50%" stopColor="#22d3ee" stopOpacity="1" />
                  <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.3" />
                </linearGradient>
              </defs>

              {/* Arrows connecting boxes */}
              <line x1="155" y1="160" x2="225" y2="160" stroke="#22d3ee" strokeWidth="2" markerEnd="url(#arrowhead)" className="animate-flow-line" />
              <line x1="365" y1="160" x2="435" y2="160" stroke="#22d3ee" strokeWidth="2" markerEnd="url(#arrowhead)" className="animate-flow-line animation-delay-1" />
              <line x1="575" y1="160" x2="645" y2="160" stroke="#22d3ee" strokeWidth="2" markerEnd="url(#arrowhead)" className="animate-flow-line animation-delay-2" />
              <line x1="785" y1="160" x2="855" y2="160" stroke="#22d3ee" strokeWidth="2" markerEnd="url(#arrowhead)" className="animate-flow-line animation-delay-3" />

              {/* Box 1: Data Sources */}
              <g transform="translate(20, 80)">
                <rect x="0" y="0" width="130" height="160" rx="8" fill="#1e293b" stroke="#3b82f6" strokeWidth="2" />
                <text x="65" y="30" textAnchor="middle" fill="#3b82f6" fontSize="12" fontFamily="monospace" fontWeight="bold">DATA SOURCES</text>
                {/* Icons inside */}
                <rect x="15" y="50" width="45" height="30" rx="4" fill="#374151" stroke="#60a5fa" strokeWidth="1" />
                <text x="37" y="70" textAnchor="middle" fill="#60a5fa" fontSize="10" fontFamily="monospace">YouTube</text>
                <rect x="70" y="50" width="45" height="30" rx="4" fill="#374151" stroke="#60a5fa" strokeWidth="1" />
                <text x="92" y="70" textAnchor="middle" fill="#60a5fa" fontSize="10" fontFamily="monospace">Web</text>
                <rect x="15" y="90" width="45" height="30" rx="4" fill="#374151" stroke="#60a5fa" strokeWidth="1" />
                <text x="37" y="110" textAnchor="middle" fill="#60a5fa" fontSize="10" fontFamily="monospace">PDFs</text>
                <rect x="70" y="90" width="45" height="30" rx="4" fill="#374151" stroke="#60a5fa" strokeWidth="1" />
                <text x="92" y="110" textAnchor="middle" fill="#60a5fa" fontSize="10" fontFamily="monospace">RSS</text>
                <text x="65" y="145" textAnchor="middle" fill="#9ca3af" fontSize="9" fontFamily="monospace">Community Data</text>
              </g>

              {/* Box 2: Ingestion */}
              <g transform="translate(230, 80)">
                <rect x="0" y="0" width="130" height="160" rx="8" fill="#1e293b" stroke="#22c55e" strokeWidth="2" />
                <text x="65" y="30" textAnchor="middle" fill="#22c55e" fontSize="12" fontFamily="monospace" fontWeight="bold">INGESTION</text>
                {/* Process steps */}
                <rect x="15" y="50" width="100" height="25" rx="4" fill="#374151" stroke="#4ade80" strokeWidth="1" />
                <text x="65" y="67" textAnchor="middle" fill="#4ade80" fontSize="10" fontFamily="monospace">Extract Text</text>
                <rect x="15" y="85" width="100" height="25" rx="4" fill="#374151" stroke="#4ade80" strokeWidth="1" />
                <text x="65" y="102" textAnchor="middle" fill="#4ade80" fontSize="10" fontFamily="monospace">Chunk Content</text>
                <rect x="15" y="120" width="100" height="25" rx="4" fill="#374151" stroke="#4ade80" strokeWidth="1" />
                <text x="65" y="137" textAnchor="middle" fill="#4ade80" fontSize="10" fontFamily="monospace">Embed Vectors</text>
              </g>

              {/* Box 3: Vector Store */}
              <g transform="translate(440, 80)">
                <rect x="0" y="0" width="130" height="160" rx="8" fill="#1e293b" stroke="#a855f7" strokeWidth="2" />
                <text x="65" y="30" textAnchor="middle" fill="#a855f7" fontSize="12" fontFamily="monospace" fontWeight="bold">VECTOR STORE</text>
                {/* Database visualization */}
                <ellipse cx="65" cy="70" rx="45" ry="15" fill="#374151" stroke="#c084fc" strokeWidth="1" />
                <rect x="20" y="70" width="90" height="40" fill="#374151" stroke="#c084fc" strokeWidth="1" />
                <ellipse cx="65" cy="110" rx="45" ry="15" fill="#374151" stroke="#c084fc" strokeWidth="1" />
                <text x="65" y="95" textAnchor="middle" fill="#c084fc" fontSize="10" fontFamily="monospace">Qdrant</text>
                <text x="65" y="145" textAnchor="middle" fill="#9ca3af" fontSize="9" fontFamily="monospace">Semantic Search</text>
              </g>

              {/* Box 4: RAG + LLM */}
              <g transform="translate(650, 80)">
                <rect x="0" y="0" width="130" height="160" rx="8" fill="#1e293b" stroke="#f97316" strokeWidth="2" />
                <text x="65" y="30" textAnchor="middle" fill="#f97316" fontSize="12" fontFamily="monospace" fontWeight="bold">RAG + LLM</text>
                {/* Query flow */}
                <rect x="15" y="50" width="100" height="25" rx="4" fill="#374151" stroke="#fb923c" strokeWidth="1" />
                <text x="65" y="67" textAnchor="middle" fill="#fb923c" fontSize="10" fontFamily="monospace">Query Match</text>
                <rect x="15" y="85" width="100" height="25" rx="4" fill="#374151" stroke="#fb923c" strokeWidth="1" />
                <text x="65" y="102" textAnchor="middle" fill="#fb923c" fontSize="10" fontFamily="monospace">Build Context</text>
                <rect x="15" y="120" width="100" height="25" rx="4" fill="#374151" stroke="#fb923c" strokeWidth="1" />
                <text x="65" y="137" textAnchor="middle" fill="#fb923c" fontSize="10" fontFamily="monospace">Ollama/Claude</text>
              </g>

              {/* Box 5: Response */}
              <g transform="translate(820, 100)">
                <rect x="0" y="0" width="70" height="120" rx="8" fill="#1e293b" stroke="#22d3ee" strokeWidth="2" />
                <text x="35" y="25" textAnchor="middle" fill="#22d3ee" fontSize="11" fontFamily="monospace" fontWeight="bold">ANSWER</text>
                {/* Chat bubble */}
                <rect x="10" y="40" width="50" height="35" rx="6" fill="#374151" stroke="#67e8f9" strokeWidth="1" />
                <line x1="20" y1="52" x2="50" y2="52" stroke="#67e8f9" strokeWidth="1" />
                <line x1="20" y1="60" x2="45" y2="60" stroke="#67e8f9" strokeWidth="1" />
                <line x1="20" y1="68" x2="40" y2="68" stroke="#67e8f9" strokeWidth="1" />
                <text x="35" y="98" textAnchor="middle" fill="#9ca3af" fontSize="8" fontFamily="monospace">+ Sources</text>
              </g>

              {/* User icon at start */}
              <g transform="translate(-15, 145)">
                <circle cx="20" cy="15" r="10" fill="#374151" stroke="#60a5fa" strokeWidth="2" />
                <text x="20" y="18" textAnchor="middle" fill="#60a5fa" fontSize="10">?</text>
              </g>

              {/* Labels below */}
              <text x="85" y="270" textAnchor="middle" fill="#6b7280" fontSize="10" fontFamily="monospace">Collect</text>
              <text x="295" y="270" textAnchor="middle" fill="#6b7280" fontSize="10" fontFamily="monospace">Process</text>
              <text x="505" y="270" textAnchor="middle" fill="#6b7280" fontSize="10" fontFamily="monospace">Store</text>
              <text x="715" y="270" textAnchor="middle" fill="#6b7280" fontSize="10" fontFamily="monospace">Generate</text>
              <text x="855" y="270" textAnchor="middle" fill="#6b7280" fontSize="10" fontFamily="monospace">Respond</text>

              {/* Flow description */}
              <text x="450" y="305" textAnchor="middle" fill="#9ca3af" fontSize="11" fontFamily="monospace">
                Question → Semantic Search → Relevant Context → LLM → Cited Answer
              </text>
            </svg>
          </div>

          <div className="mt-8 grid md:grid-cols-3 gap-6 text-center">
            <div className="bg-gray-800/30 rounded-lg p-4 border border-gray-700">
              <div className="text-2xl font-bold text-blue-400 font-mono mb-1">Local</div>
              <p className="text-gray-400 text-sm">All processing on your hardware</p>
            </div>
            <div className="bg-gray-800/30 rounded-lg p-4 border border-gray-700">
              <div className="text-2xl font-bold text-green-400 font-mono mb-1">2W</div>
              <p className="text-gray-400 text-sm">Energy per query (vs 100W cloud)</p>
            </div>
            <div className="bg-gray-800/30 rounded-lg p-4 border border-gray-700">
              <div className="text-2xl font-bold text-purple-400 font-mono mb-1">Private</div>
              <p className="text-gray-400 text-sm">Your data never leaves your server</p>
            </div>
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
      <Footer />

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

        .animation-delay-1 {
          animation-delay: 0.5s;
        }

        .animation-delay-2 {
          animation-delay: 1s;
        }

        .animation-delay-3 {
          animation-delay: 1.5s;
        }

        /* Blueprint grid pattern */
        .blueprint-grid {
          width: 100%;
          height: 100%;
          background-image:
            linear-gradient(rgba(30, 64, 175, 0.3) 1px, transparent 1px),
            linear-gradient(90deg, rgba(30, 64, 175, 0.3) 1px, transparent 1px),
            linear-gradient(rgba(30, 64, 175, 0.15) 1px, transparent 1px),
            linear-gradient(90deg, rgba(30, 64, 175, 0.15) 1px, transparent 1px);
          background-size: 100px 100px, 100px 100px, 20px 20px, 20px 20px;
        }

        /* Civic pattern animation */
        @keyframes civic-drift {
          0% {
            transform: translate(0, 0);
          }
          100% {
            transform: translate(40px, 40px);
          }
        }

        .animate-civic-drift {
          animation: civic-drift 60s linear infinite;
        }

        /* Flow line animation for architecture diagram */
        @keyframes flow-pulse {
          0%, 100% {
            opacity: 0.5;
            stroke-dashoffset: 0;
          }
          50% {
            opacity: 1;
            stroke-dashoffset: -10;
          }
        }

        .animate-flow-line {
          stroke-dasharray: 5 3;
          animation: flow-pulse 2s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}

export default LandingPage;
