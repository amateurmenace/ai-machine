import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import api from '../api';
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
  ExclamationCircleIcon,
  VideoCameraIcon,
  DocumentTextIcon,
  ChatBubbleLeftIcon,
  GlobeAmericasIcon,
  WrenchScrewdriverIcon,
  LockClosedIcon,
  CubeIcon,
  ShieldCheckIcon
} from '@heroicons/react/24/outline';
import Footer from './Footer';

function LandingPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [projectsHealth, setProjectsHealth] = useState({});
  const [activeChat, setActiveChat] = useState(null);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  // Load projects and check their health
  useEffect(() => {
    const loadProjects = async () => {
      try {
        const response = await api.get('/api/projects');
        setProjects(response.data);

        // Check health for each project
        const healthStatuses = {};
        for (const project of response.data) {
          try {
            const healthRes = await api.get(`/api/projects/${project.project_id}/health`);
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
      const response = await api.post('/api/chat', {
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
        {/* Colorful animated globs - more visible */}
        <div className="absolute top-20 left-10 w-96 h-96 bg-gradient-to-br from-blue-400/30 to-purple-400/30 rounded-full blur-3xl animate-blob"></div>
        <div className="absolute top-40 right-20 w-80 h-80 bg-gradient-to-br from-orange-400/35 to-pink-400/30 rounded-full blur-3xl animate-blob animation-delay-2000"></div>
        <div className="absolute bottom-20 left-1/4 w-72 h-72 bg-gradient-to-br from-green-400/30 to-teal-400/25 rounded-full blur-3xl animate-blob animation-delay-4000"></div>
        <div className="absolute bottom-40 right-1/3 w-64 h-64 bg-gradient-to-br from-yellow-400/30 to-orange-400/25 rounded-full blur-3xl animate-blob animation-delay-6000"></div>
        <div className="absolute top-1/2 left-1/2 w-96 h-96 bg-gradient-to-br from-rose-400/25 to-purple-400/25 rounded-full blur-3xl animate-blob animation-delay-3000"></div>

        {/* Blueprint grid pattern - more visible */}
        <div className="absolute inset-0 opacity-[0.08]">
          <div className="blueprint-grid"></div>
        </div>

        {/* Civic doodles / urban planning sketches - more visible */}
        <svg className="absolute inset-0 w-full h-full opacity-[0.12]" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="civic-pattern" x="0" y="0" width="400" height="400" patternUnits="userSpaceOnUse">
              {/* City grid streets */}
              <line x1="0" y1="100" x2="400" y2="100" stroke="#1e40af" strokeWidth="1.5" strokeDasharray="8 4" />
              <line x1="0" y1="200" x2="400" y2="200" stroke="#1e40af" strokeWidth="1.5" strokeDasharray="8 4" />
              <line x1="0" y1="300" x2="400" y2="300" stroke="#1e40af" strokeWidth="1.5" strokeDasharray="8 4" />
              <line x1="100" y1="0" x2="100" y2="400" stroke="#1e40af" strokeWidth="1.5" strokeDasharray="8 4" />
              <line x1="200" y1="0" x2="200" y2="400" stroke="#1e40af" strokeWidth="1.5" strokeDasharray="8 4" />
              <line x1="300" y1="0" x2="300" y2="400" stroke="#1e40af" strokeWidth="1.5" strokeDasharray="8 4" />

              {/* Building outlines - simple rectangles representing blocks */}
              <rect x="20" y="20" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <rect x="120" y="20" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <rect x="220" y="120" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <rect x="320" y="220" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <rect x="20" y="220" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <rect x="120" y="320" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1.5" />

              {/* Town hall / civic building */}
              <rect x="220" y="320" width="80" height="50" fill="none" stroke="#1e40af" strokeWidth="2" />
              <polygon points="220,320 260,290 300,320" fill="none" stroke="#1e40af" strokeWidth="2" />
              <rect x="255" y="340" width="10" height="30" fill="none" stroke="#1e40af" strokeWidth="1.5" />

              {/* Park / green space */}
              <circle cx="350" cy="50" r="30" fill="none" stroke="#16a34a" strokeWidth="1.5" strokeDasharray="4 2" />
              <circle cx="50" cy="350" r="25" fill="none" stroke="#16a34a" strokeWidth="1.5" strokeDasharray="4 2" />

              {/* Connection nodes */}
              <circle cx="100" cy="100" r="5" fill="#1e40af" />
              <circle cx="200" cy="100" r="5" fill="#1e40af" />
              <circle cx="300" cy="100" r="5" fill="#1e40af" />
              <circle cx="100" cy="200" r="5" fill="#1e40af" />
              <circle cx="200" cy="200" r="5" fill="#1e40af" />
              <circle cx="300" cy="200" r="5" fill="#1e40af" />
              <circle cx="100" cy="300" r="5" fill="#1e40af" />
              <circle cx="200" cy="300" r="5" fill="#1e40af" />
              <circle cx="300" cy="300" r="5" fill="#1e40af" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#civic-pattern)" className="animate-civic-drift" />
        </svg>
      </div>

      {/* ================= NAV ================= */}
      <nav className="relative z-20 border-b border-gray-200/60 bg-white/70 backdrop-blur-md sticky top-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-gray-900 rounded-lg">
                <CpuChipIcon className="h-5 w-5 text-green-400" />
              </div>
              <h1 className="text-xl md:text-2xl font-bold text-gray-900 font-mono tracking-tight">
                Neighborhood AI
              </h1>
            </div>
            <div className="flex items-center space-x-4 md:space-x-6">
              <a href="#how" className="text-gray-600 hover:text-gray-900 text-sm font-mono transition-colors hidden sm:inline">how</a>
              <a href="#archive" className="text-gray-600 hover:text-gray-900 text-sm font-mono transition-colors hidden md:inline">archive</a>
              <a href="#ledger" className="text-gray-600 hover:text-gray-900 text-sm font-mono transition-colors hidden md:inline">ledger</a>
              <a href="#api" className="text-gray-600 hover:text-gray-900 text-sm font-mono transition-colors hidden md:inline">api</a>
              {projects.length > 0 && (
                <a href="#projects" className="text-gray-600 hover:text-gray-900 text-sm font-mono transition-colors hidden sm:inline">live</a>
              )}
              <button
                onClick={handleNavigateToConsole}
                className="px-4 py-2 bg-gray-900 text-green-400 rounded-lg font-mono text-sm hover:bg-gray-800 transition-colors"
              >
                open console
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* ================= HERO ================= */}
      <section className="relative z-10 pt-20 pb-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center px-4 py-1.5 mb-8 rounded-full bg-gray-900 text-green-400 font-mono text-xs">
            <ServerIcon className="h-3.5 w-3.5 mr-2" />
            runs on hardware your community owns
          </div>

          <h1 className="text-5xl md:text-7xl font-black mb-6 text-gray-900 tracking-tight leading-[1.05]">
            Your town's AI,<br />
            <span className="bg-gradient-to-r from-green-600 via-teal-600 to-blue-600 bg-clip-text text-transparent">
              governed by your town
            </span>
          </h1>

          <p className="text-xl md:text-2xl text-gray-700 mb-4 max-w-3xl mx-auto leading-relaxed">
            A public-information service that happens to use a language model.
            It answers from your community's own record, cites the meeting and
            the timestamp, and follows rules your community wrote and can amend.
          </p>

          <p className="text-base text-gray-500 mb-10 max-w-2xl mx-auto font-mono">
            Not a chatbot with your logo on it.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
            <button
              onClick={handleNavigateToConsole}
              className="px-8 py-4 bg-gray-900 text-green-400 rounded-xl font-mono font-semibold hover:bg-gray-800 transition-all inline-flex items-center justify-center group"
            >
              build one for your community
              <ArrowRightIcon className="h-5 w-5 ml-2 group-hover:translate-x-1 transition-transform" />
            </button>
            <a
              href="#how"
              className="px-8 py-4 bg-white border-2 border-gray-900 text-gray-900 rounded-xl font-mono font-semibold hover:bg-gray-50 transition-all inline-flex items-center justify-center"
            >
              see how it works
            </a>
          </div>

          {/* What the community owns */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 max-w-4xl mx-auto">
            {[
              { icon: DocumentTextIcon, label: 'the rules', sub: 'a constitution' },
              { icon: VideoCameraIcon, label: 'the record', sub: 'your archive' },
              { icon: SparklesIcon, label: 'the finding', sub: 'retrieval' },
              { icon: LockClosedIcon, label: 'the proof', sub: 'citations' },
              { icon: CheckCircleIcon, label: 'the test', sub: 'evaluations' },
            ].map((item) => (
              <div key={item.label} className="p-4 bg-white/80 backdrop-blur rounded-xl border border-gray-200">
                <item.icon className="h-5 w-5 text-gray-900 mx-auto mb-2" />
                <p className="font-mono text-sm font-semibold text-gray-900">{item.label}</p>
                <p className="font-mono text-xs text-gray-500">{item.sub}</p>
              </div>
            ))}
          </div>
          <p className="mt-4 font-mono text-xs text-gray-500 max-w-2xl mx-auto">
            The model is deliberately not on that list. Swap it next year and
            everything above survives.
          </p>
        </div>
      </section>

      {/* ================= HOW IT WORKS ================= */}
      <section id="how" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-gray-900">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-4xl md:text-5xl font-black mb-4 text-white">
              What happens when someone asks
            </h2>
            <p className="text-lg text-gray-400 max-w-2xl mx-auto">
              "What has the town discussed about replacing gas heating in public buildings?"
            </p>
          </div>

          <div className="space-y-3 max-w-4xl mx-auto">
            {[
              { n: '01', t: 'Expand the question',
                d: "Residents say “the dump”; the records say “Solid Waste Transfer Station”. A civic vocabulary map adds the formal terms without dropping the original wording." },
              { n: '02', t: 'Search twice, two different ways',
                d: 'Meaning-based search finds the right topic. Keyword search finds the right identifier. Ask a meaning-only system about Article 8.4 and it hands you Article 8.1, because those two passages mean nearly the same thing.' },
              { n: '03', t: 'Merge and rerank',
                d: 'The two result lists are fused by rank, then a second model reads each question-and-passage pair together. This is where “right topic, wrong year” gets caught.' },
              { n: '04', t: 'Assemble the request',
                d: 'Four blocks: who the assistant is, the constitution verbatim, the retrieved passages, and the tools. The passages carry an explicit warning that they are evidence and never instructions.' },
              { n: '05', t: 'Answer, and use tools if needed',
                d: 'The model can search the archive again with its own filters, search the web, or read a page. At the limit it is told it is out of tool calls, so it says what it could not confirm.' },
              { n: '06', t: 'Check every citation',
                d: 'Each source marker is matched against what was actually supplied. A marker pointing at a passage that does not exist is a fabricated source; it gets stripped and flagged.' },
            ].map((step) => (
              <div key={step.n} className="flex gap-5 p-5 bg-gray-800/50 rounded-xl border border-gray-700 hover:border-green-500/40 transition-colors">
                <span className="font-mono text-2xl font-black text-green-500/60 flex-shrink-0">{step.n}</span>
                <div>
                  <h3 className="font-mono text-white font-semibold mb-1">{step.t}</h3>
                  <p className="text-gray-400 text-sm leading-relaxed">{step.d}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= LOCAL FIRST ================= */}
      <section className="relative z-10 py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-4xl font-black mb-5 text-gray-900">
                A question answered locally never leaves the building
              </h2>
              <p className="text-gray-600 mb-5 leading-relaxed">
                The default is a model on hardware your community owns, reached
                over your network or through a tunnel so a machine in a closet
                can serve a whole town without a static address.
              </p>
              <p className="text-gray-600 mb-6 leading-relaxed">
                Frontier models are here too, because sometimes they are the
                right call. The app tells residents which one answered instead of
                hiding it.
              </p>
              <div className="space-y-2">
                {[
                  ['LM Studio', 'local or tunneled', true],
                  ['Ollama', 'local', true],
                  ['Anthropic Claude', 'sends the question out', false],
                  ['OpenAI', 'sends the question out', false],
                  ['Google Gemini', 'sends the question out', false],
                ].map(([name, note, local]) => (
                  <div key={name} className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200">
                    <span className="font-mono text-sm font-semibold text-gray-900">{name}</span>
                    <span className={`font-mono text-xs ${local ? 'text-green-600' : 'text-amber-600'}`}>
                      {note}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-gray-900 rounded-2xl p-6 border border-gray-700">
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <span className="text-gray-500 text-xs font-mono ml-3">what a local model costs</span>
              </div>
              <div className="space-y-3 font-mono text-sm">
                {[
                  ['Mac Studio, 64GB', '$3,500 once', 'runs Gemma 4 26B'],
                  ['Used RTX 3090', '$1,500 once', 'same class, faster'],
                  ['Cloud GPU', '$500/month forever', 'and defeats the purpose'],
                ].map(([what, cost, note]) => (
                  <div key={what} className="p-3 bg-gray-800 rounded-lg">
                    <div className="flex justify-between items-baseline">
                      <span className="text-white">{what}</span>
                      <span className={cost.includes('month') ? 'text-amber-400' : 'text-green-400'}>{cost}</span>
                    </div>
                    <p className="text-gray-500 text-xs mt-1">{note}</p>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-gray-400 text-xs font-mono leading-relaxed">
                A one-time purchase beats the subscription inside a year, and
                keeps the property that matters.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ================= ARCHIVE ================= */}
      <section id="archive" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-blue-50 to-teal-50">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-4xl md:text-5xl font-black mb-4 text-gray-900">
              Every meeting, searchable to the second
            </h2>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              Point it at your public-access channel. It reads the board and the
              date out of each title, pulls the transcript, and keeps the
              timestamp of the moment each passage starts.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-5 mb-10">
            {[
              { icon: VideoCameraIcon, t: 'Backfill the archive',
                d: 'Walks years of meetings oldest-first, so an interrupted run leaves a contiguous record rather than a scatter.' },
              { icon: BoltIcon, t: 'Then it keeps itself current',
                d: 'A cursor means later runs list only what is new. A scan that finds nothing costs one request and writes nothing.' },
              { icon: CheckCircleIcon, t: 'Gaps are recorded, not hidden',
                d: 'A meeting with captions disabled is logged as a gap in the public record, because the assistant has to be able to say what it does not have.' },
            ].map((f) => (
              <div key={f.t} className="p-6 bg-white rounded-xl border border-gray-200">
                <f.icon className="h-6 w-6 text-blue-600 mb-3" />
                <h3 className="font-mono font-semibold text-gray-900 mb-2">{f.t}</h3>
                <p className="text-sm text-gray-600 leading-relaxed">{f.d}</p>
              </div>
            ))}
          </div>

          <div className="bg-gray-900 rounded-2xl p-6 border border-gray-700 max-w-3xl mx-auto">
            <p className="font-mono text-xs text-gray-500 mb-3"># an answer, with its evidence</p>
            <p className="text-gray-200 text-sm mb-4 leading-relaxed">
              The Select Board discussed the redesign on May 12 and several
              members expressed support, but the record does not show a vote
              approving it <span className="text-cyan-400">[1]</span>.
            </p>
            <div className="p-3 bg-gray-800 rounded-lg border border-gray-700">
              <p className="font-mono text-xs text-cyan-400 flex items-center">
                <VideoCameraIcon className="h-3.5 w-3.5 mr-1.5" />
                [1] Select Board &bull; May 12, 2026 &bull; 1:13:42
              </p>
              <p className="font-mono text-xs text-gray-500 ml-5">
                spoken by Jane Smith, Transportation Director
              </p>
              <p className="font-mono text-xs text-green-400 ml-5 mt-2">
                &#9654; watch this moment (1:13:42)
              </p>
            </div>
            <p className="font-mono text-xs text-gray-500 mt-3 leading-relaxed">
              The video plays in the app at that second. Click to load, through
              a privacy-enhanced embed, so opening an answer does not tell
              anyone who watched which meeting.
            </p>
          </div>
        </div>
      </section>

      {/* ================= LEDGER ================= */}
      <section id="ledger" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-gray-900">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <div className="inline-flex items-center px-4 py-1.5 mb-5 rounded-full bg-purple-500/20 text-purple-300 font-mono text-xs">
              <CubeIcon className="h-3.5 w-3.5 mr-2" />
              the part nobody else has
            </div>
            <h2 className="text-4xl md:text-5xl font-black mb-4 text-white">
              The rules are a signed chain
            </h2>
            <p className="text-lg text-gray-400 max-w-3xl mx-auto">
              Every adopted version of the community constitution is a block.
              Each records the hash of its own text and of the block before it.
              Ratification is an N-of-M multi-signature by named officials,
              verified rather than asserted.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 items-start mb-10">
            <div className="space-y-3">
              {[
                { h: 'block 1 · v1.1', s: 'ratified 2 of 3', c: 'f46eaefc', prev: '50c95a99', head: true },
                { h: 'block 0 · v1.0', s: 'genesis', c: '50c95a99', prev: null, head: false },
              ].map((b) => (
                <div key={b.h} className={`p-4 rounded-xl border ${b.head ? 'bg-gray-800 border-green-500/40' : 'bg-gray-800/50 border-gray-700'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-sm text-white">{b.h}</span>
                    <span className={`font-mono text-xs ${b.head ? 'text-green-400' : 'text-purple-400'}`}>{b.s}</span>
                  </div>
                  <div className="font-mono text-xs space-y-1">
                    <p className="text-gray-500">content <span className="text-cyan-400">{b.c}</span></p>
                    <p className="text-gray-500">
                      previous {b.prev
                        ? <span className="text-cyan-400">{b.prev}</span>
                        : <span className="text-purple-400">genesis &bull; none</span>}
                    </p>
                  </div>
                </div>
              ))}
              <div className="p-4 rounded-xl bg-green-500/5 border border-green-500/30">
                <p className="font-mono text-xs text-green-300 flex items-start">
                  <ShieldCheckIcon className="h-4 w-4 mr-2 flex-shrink-0" />
                  Chain verified. Every block links, every file matches its hash,
                  every signature checks out.
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="p-5 bg-gray-800/50 rounded-xl border border-gray-700">
                <h3 className="font-mono text-white font-semibold mb-2">Why it matters in practice</h3>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Every answer records the hash of the rules that produced it,
                  not just a version number. A version string can stay "1.0"
                  while the text underneath changes. A hash cannot. So "these
                  rules governed this answer" is a claim you can check a year
                  later, in a dispute, when it matters.
                </p>
              </div>
              <div className="p-5 bg-gray-800/50 rounded-xl border border-gray-700">
                <h3 className="font-mono text-white font-semibold mb-2">The best witness is your own minutes</h3>
                <p className="text-gray-400 text-sm leading-relaxed">
                  When the board votes to ratify, the motion includes the block
                  hash. It goes into the official minutes, held by the clerk,
                  outside the operator's control. That is cryptographically sound
                  and civically coherent at once, and it outlives this software.
                </p>
              </div>
              <div className="p-5 bg-amber-500/5 rounded-xl border border-amber-500/30">
                <h3 className="font-mono text-amber-300 font-semibold mb-2">What we do not claim</h3>
                <p className="text-gray-400 text-sm leading-relaxed">
                  No consensus, no mining, no token, no decentralization. One
                  operator runs one server. The chain makes tampering
                  <span className="text-amber-300"> detectable</span>, not
                  impossible. That is the guarantee that actually addresses the
                  risk here, and overclaiming it would cost more trust than
                  never claiming it.
                </p>
              </div>
            </div>
          </div>

          <div className="text-center">
            <code className="inline-block px-4 py-2 bg-gray-800 rounded-lg font-mono text-sm text-green-400 border border-gray-700">
              python3 -m community.ledger verify
            </code>
            <p className="font-mono text-xs text-gray-500 mt-3">
              Anyone can check it. That is the point.
            </p>
          </div>
        </div>
      </section>

      {/* ================= TRANSPARENCY ================= */}
      <section className="relative z-10 py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto grid md:grid-cols-2 gap-12 items-center">
          <div className="bg-gray-900 rounded-2xl p-6 border border-gray-700 order-2 md:order-1">
            <p className="font-mono text-xs text-gray-500 mb-3">
              &#9662; why did you answer this way?
            </p>
            <dl className="space-y-1.5">
              {[
                ['sources retrieved', '7'],
                ['sources used', '3'],
                ['knowledge base updated', 'September 19, 2026'],
                ['model', 'gemma-4-26b-a4b'],
                ['served by', 'LM Studio (local)'],
                ['constitution', 'version 1.1 · f46eaefc · ratified'],
                ['search', 'hybrid, reranked'],
                ['retrieval time', '142 ms'],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between font-mono text-xs gap-4">
                  <dt className="text-gray-500">{k}</dt>
                  <dd className="text-gray-300 text-right">{v}</dd>
                </div>
              ))}
            </dl>
            <p className="font-mono text-xs text-gray-600 mt-4 pt-3 border-t border-gray-800">
              This shows what the system did, not the model's private reasoning.
            </p>
          </div>

          <div className="order-1 md:order-2">
            <h2 className="text-4xl font-black mb-5 text-gray-900">
              Every answer shows its work
            </h2>
            <p className="text-gray-600 mb-4 leading-relaxed">
              Not a confidence score. Operational facts: what was retrieved, what
              was actually used, how fresh the archive is, which model answered,
              which version of the rules applied, and whether the assistant left
              your records to search the web.
            </p>
            <p className="text-gray-600 leading-relaxed">
              When something is wrong, this is what tells you whether the search
              failed or the model did. Those are different problems with
              different fixes, and conflating them wastes weeks.
            </p>
          </div>
        </div>
      </section>

      {/* ================= API ================= */}
      <section id="api" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-gray-900 to-gray-800">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl md:text-5xl font-black mb-4 text-white">
              Infrastructure, not a chatbot
            </h2>
            <p className="text-lg text-gray-400 max-w-2xl mx-auto">
              The public record, with real filters, through an API every
              application in your community can share.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-gray-950 rounded-xl p-5 border border-gray-700">
              <p className="font-mono text-xs text-green-400 mb-3">
                # switch an existing app by changing one line
              </p>
              <pre className="font-mono text-xs text-gray-300 overflow-x-auto leading-relaxed">
{`client = OpenAI(
  base_url="https://ai.yourtown.org/v1",
  api_key="cai_..."
)

client.chat.completions.create(
  model="community-ai",
  messages=[{
    "role": "user",
    "content": "Summarize tonight's meeting."
  }]
)`}
              </pre>
            </div>

            <div className="bg-gray-950 rounded-xl p-5 border border-gray-700">
              <p className="font-mono text-xs text-green-400 mb-3">
                # or query the record directly
              </p>
              <pre className="font-mono text-xs text-gray-300 overflow-x-auto leading-relaxed">
{`POST /community/ask
POST /community/search
GET  /community/meetings
GET  /community/documents
GET  /community/sources/{id}

# public, no key needed
GET  /community/{town}/constitution
GET  /community/{town}/stats
GET  /community/{town}/constitution/ledger`}
              </pre>
            </div>
          </div>

          <div className="grid sm:grid-cols-3 gap-4 mt-6">
            {[
              ['Per-application keys', 'Stored hashed, with scopes and rate limits. Revoke one app without breaking the rest.'],
              ['Your prompt cannot override the rules', "An application can send a system prompt. The gateway drops it. The constitution is the service's policy."],
              ['Questions are not logged', 'Operational metadata is. Question text is stored as a salted hash, so repeats stay countable without being readable.'],
            ].map(([t, d]) => (
              <div key={t} className="p-4 bg-gray-800/50 rounded-xl border border-gray-700">
                <h3 className="font-mono text-sm text-white font-semibold mb-1.5">{t}</h3>
                <p className="text-gray-400 text-xs leading-relaxed">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= LIVE PROJECTS ================= */}
      {projects.length > 0 && (
        <section id="projects" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8">
          <div className="max-w-6xl mx-auto">
            <div className="text-center mb-12">
              <h2 className="text-4xl font-black mb-4 text-gray-900">Running right now</h2>
              <p className="text-lg text-gray-600">
                Community assistants live on this server. Ask one something.
              </p>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
              {projects.map((project) => {
                const health = projectsHealth[project.project_id];
                const ready = health?.ready;
                return (
                  <div
                    key={project.project_id}
                    className={`p-6 bg-white rounded-xl border-2 transition-all ${
                      ready ? 'border-green-500/40 hover:border-green-500 cursor-pointer' : 'border-gray-200'
                    }`}
                    onClick={() => ready && openChat(project)}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="min-w-0">
                        <h3 className="font-mono font-bold text-gray-900 truncate">{project.project_name}</h3>
                        <p className="font-mono text-xs text-gray-500 truncate">{project.municipality_name}</p>
                      </div>
                      <span className={`flex-shrink-0 h-2.5 w-2.5 rounded-full mt-1.5 ${
                        ready ? 'bg-green-500' : 'bg-gray-300'
                      }`} />
                    </div>
                    {ready ? (
                      <p className="font-mono text-xs text-green-600 flex items-center">
                        <ChatBubbleLeftRightIcon className="h-3.5 w-3.5 mr-1.5" />
                        ready &mdash; click to ask
                      </p>
                    ) : (
                      <p className="font-mono text-xs text-gray-400">
                        {health?.issues?.[0] || 'not configured yet'}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* ================= GET STARTED ================= */}
      <section className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-gray-900">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl font-black mb-5 text-white">
            Start with one board's meetings
          </h2>
          <p className="text-lg text-gray-400 mb-10 max-w-2xl mx-auto">
            Not the whole archive. One board, a hundred documents, and the
            questions people actually ask at the counter. That is enough to find
            the real problems before you commit a town to anything.
          </p>

          <div className="bg-gray-950 rounded-xl p-6 border border-gray-700 text-left mb-10 max-w-2xl mx-auto">
            <pre className="font-mono text-sm text-gray-300 overflow-x-auto leading-relaxed">
{`git clone https://github.com/amateurmenace/ai-machine
cd ai-machine && pip install -r requirements.txt

cp community.example.yaml community.yaml
python3 -m scripts.bootstrap_community community.yaml

# or put it on Google Cloud to try it
./deploy/cloudrun.sh YOUR_PROJECT_ID`}
            </pre>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={handleNavigateToConsole}
              className="px-8 py-4 bg-green-500 text-gray-900 rounded-xl font-mono font-semibold hover:bg-green-400 transition-all inline-flex items-center justify-center group"
            >
              open the console
              <ArrowRightIcon className="h-5 w-5 ml-2 group-hover:translate-x-1 transition-transform" />
            </button>
            <a
              href="https://github.com/amateurmenace/ai-machine"
              target="_blank"
              rel="noopener noreferrer"
              className="px-8 py-4 bg-gray-800 text-white rounded-xl font-mono font-semibold hover:bg-gray-700 transition-all inline-flex items-center justify-center border border-gray-700"
            >
              <CodeBracketIcon className="h-5 w-5 mr-2" />
              read the source
            </a>
          </div>

          <p className="font-mono text-xs text-gray-600 mt-8">
            MIT licensed. Built for Brookline Interactive Group and civic
            technologists everywhere.
          </p>
        </div>
      </section>

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

      <Footer />
    </div>
  );
}

export default LandingPage;
