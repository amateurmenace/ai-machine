import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import api, { apiAvailable } from '../api';
import {
  CpuChipIcon,
  ArrowRightIcon,
  ArrowDownIcon,
  PlayCircleIcon,
  BoltIcon,
  ScaleIcon,
  LockClosedIcon,
  CodeBracketIcon,
  VideoCameraIcon,
  DocumentTextIcon,
  SparklesIcon,
  CheckCircleIcon,
  ShieldCheckIcon,
  CubeIcon,
  ServerIcon,
  ChatBubbleLeftRightIcon,
  PaperAirplaneIcon,
  XMarkIcon,
  BuildingLibraryIcon,
  UserGroupIcon,
  SunIcon,
  GlobeAltIcon,
  KeyIcon,
  SignalIcon,
  LanguageIcon,
  DevicePhoneMobileIcon,
  CommandLineIcon,
  CircleStackIcon,
  ComputerDesktopIcon,
  HandRaisedIcon,
  EyeSlashIcon,
  MagnifyingGlassIcon,
  BookOpenIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline';
import Footer from './Footer';
import ConsoleDemo from './ConsoleDemo';

const REPO_URL = 'https://github.com/amateurmenace/ai-machine';
// The constitution lives in the repository. Update the branch here when this
// work lands on main.
const REPO_BRANCH = 'claude/neighborhood-ai-update-6s4s38';
const CONSTITUTION_URL = `${REPO_URL}/blob/${REPO_BRANCH}/constitution/constitution-v1.0.md`;

// A small uppercase label above a section, the way a printed brief does it.
function Label({ children, tone = 'text-orange-600' }) {
  return (
    <p className={`font-mono text-[11px] tracking-[0.3em] uppercase mb-4 ${tone}`}>{children}</p>
  );
}

function NodeBox({ tone, icon: Icon, title, text, chips, muted }) {
  return (
    <div className={`rounded-xl border p-3.5 h-full ${muted ? 'border-dashed border-gray-700 bg-gray-900/40' : 'border-gray-700 bg-gray-800/70'}`}>
      <div className={`h-1 w-10 rounded mb-3 ${tone}`} />
      <div className="flex items-center mb-1.5">
        <Icon className="h-4 w-4 mr-2 text-gray-300 flex-shrink-0" />
        <p className="font-mono text-sm text-white font-semibold">{title}</p>
      </div>
      <p className="text-xs text-gray-400 leading-relaxed">{text}</p>
      {chips && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {chips.map((c) => (
            <span key={c} className="px-1.5 py-0.5 rounded bg-gray-900 border border-gray-700 font-mono text-[10px] text-gray-300">{c}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function LandingPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [projectsHealth, setProjectsHealth] = useState({});
  const [activeChat, setActiveChat] = useState(null);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  // Load projects and check their health. The public site has no API to ask
  // (src/api.js), so it does not ask.
  useEffect(() => {
    const loadProjects = async () => {
      if (!apiAvailable) return;
      try {
        const response = await api.get('/api/projects');
        const list = response.data.projects || [];
        setProjects(list);

        const healthStatuses = {};
        for (const project of list) {
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

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const openChat = (project) => {
    const health = projectsHealth[project.project_id];
    if (!health?.ready) return;
    setActiveChat(project);
    setChatMessages([{
      role: 'assistant',
      content: `Hi! I'm ${project.project_name}. Ask me anything about ${project.municipality_name}!`,
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
    setChatMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setChatLoading(true);
    try {
      const response = await api.post('/api/chat', {
        project_id: activeChat.project_id,
        message: userMessage,
        conversation_history: chatMessages.slice(-5).map((m) => ({ role: m.role, content: m.content })),
      });
      setChatMessages((prev) => [...prev, {
        role: 'assistant',
        content: response.data.answer,
        sources: response.data.sources,
      }]);
    } catch (err) {
      setChatMessages((prev) => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        isError: true,
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

  const handleNavigateToConsole = () => {
    navigate('/console');
  };

  const navLinks = [
    ['#what', 'what it is', 'hidden lg:inline'],
    ['#demo', 'demo', ''],
    ['#vision', 'the vision', 'hidden md:inline'],
    ['#how', 'how it works', 'hidden lg:inline'],
    ['#build', 'how it is built', 'hidden xl:inline'],
  ];

  return (
    <div className="min-h-screen bg-white relative overflow-hidden">
      {/* Animated background: blueprint grid and civic sketches */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-20 left-10 w-96 h-96 bg-gradient-to-br from-blue-400/30 to-purple-400/30 rounded-full blur-3xl animate-blob"></div>
        <div className="absolute top-40 right-20 w-80 h-80 bg-gradient-to-br from-orange-400/35 to-pink-400/30 rounded-full blur-3xl animate-blob animation-delay-2000"></div>
        <div className="absolute bottom-20 left-1/4 w-72 h-72 bg-gradient-to-br from-green-400/30 to-teal-400/25 rounded-full blur-3xl animate-blob animation-delay-4000"></div>
        <div className="absolute bottom-40 right-1/3 w-64 h-64 bg-gradient-to-br from-yellow-400/30 to-orange-400/25 rounded-full blur-3xl animate-blob animation-delay-6000"></div>
        <div className="absolute top-1/2 left-1/2 w-96 h-96 bg-gradient-to-br from-rose-400/25 to-purple-400/25 rounded-full blur-3xl animate-blob animation-delay-3000"></div>

        <div className="absolute inset-0 opacity-[0.08]">
          <div className="blueprint-grid"></div>
        </div>

        <svg className="absolute inset-0 w-full h-full opacity-[0.12]" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="civic-pattern" x="0" y="0" width="400" height="400" patternUnits="userSpaceOnUse">
              <line x1="0" y1="100" x2="400" y2="100" stroke="#1e40af" strokeWidth="1.5" strokeDasharray="8 4" />
              <line x1="0" y1="200" x2="400" y2="200" stroke="#1e40af" strokeWidth="1.5" strokeDasharray="8 4" />
              <line x1="0" y1="300" x2="400" y2="300" stroke="#1e40af" strokeWidth="1.5" strokeDasharray="8 4" />
              <line x1="100" y1="0" x2="100" y2="400" stroke="#1e40af" strokeWidth="1.5" strokeDasharray="8 4" />
              <line x1="200" y1="0" x2="200" y2="400" stroke="#1e40af" strokeWidth="1.5" strokeDasharray="8 4" />
              <line x1="300" y1="0" x2="300" y2="400" stroke="#1e40af" strokeWidth="1.5" strokeDasharray="8 4" />
              <rect x="20" y="20" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <rect x="120" y="20" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <rect x="220" y="120" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <rect x="320" y="220" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <rect x="20" y="220" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <rect x="120" y="320" width="60" height="60" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <rect x="220" y="320" width="80" height="50" fill="none" stroke="#1e40af" strokeWidth="2" />
              <polygon points="220,320 260,290 300,320" fill="none" stroke="#1e40af" strokeWidth="2" />
              <rect x="255" y="340" width="10" height="30" fill="none" stroke="#1e40af" strokeWidth="1.5" />
              <circle cx="350" cy="50" r="30" fill="none" stroke="#16a34a" strokeWidth="1.5" strokeDasharray="4 2" />
              <circle cx="50" cy="350" r="25" fill="none" stroke="#16a34a" strokeWidth="1.5" strokeDasharray="4 2" />
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
      <nav className="sticky top-0 z-30 border-b border-gray-200/60 bg-white/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <a href="#top" className="flex items-center space-x-3">
              <div className="p-2 bg-gray-900 rounded-lg">
                <CpuChipIcon className="h-5 w-5 text-green-400" />
              </div>
              <span className="text-lg md:text-xl font-bold text-gray-900 font-mono tracking-tight">
                Civic AI Engine
              </span>
            </a>
            <div className="flex items-center gap-1 md:gap-2">
              {navLinks.map(([href, label, cls]) => (
                <a key={href} href={href} className={`px-2.5 py-1.5 text-gray-600 hover:text-gray-900 text-sm font-mono transition-colors ${cls}`}>
                  {label}
                </a>
              ))}
              {projects.length > 0 && (
                <a href="#live" className="px-2.5 py-1.5 text-green-700 hover:text-green-900 text-sm font-mono transition-colors hidden sm:inline">live</a>
              )}
              <Link to="/guide" className="px-2.5 py-1.5 text-purple-700 hover:text-purple-900 text-sm font-mono transition-colors hidden sm:inline">
                guide
              </Link>
              <button
                onClick={handleNavigateToConsole}
                className="ml-1 px-3.5 py-2 bg-gray-900 text-green-400 rounded-lg font-mono text-sm hover:bg-gray-800 transition-colors"
              >
                console
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* ================= HERO ================= */}
      <section id="top" className="relative z-10 pt-16 md:pt-24 pb-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center px-4 py-1.5 mb-8 rounded-full bg-gray-900 text-green-400 font-mono text-xs">
            <ServerIcon className="h-3.5 w-3.5 mr-2" />
            open source &middot; runs on hardware your community owns
          </div>

          <h1 className="text-5xl md:text-7xl font-black mb-8 text-gray-900 tracking-tight leading-[1.02]">
            AI as{' '}
            <span className="bg-gradient-to-r from-green-600 via-teal-600 to-blue-600 bg-clip-text text-transparent">
              civic infrastructure.
            </span>
          </h1>

          <p className="text-2xl md:text-3xl font-bold text-gray-900 max-w-3xl mx-auto leading-snug">
            Public access television made local government watchable.
          </p>
          <p className="text-2xl md:text-3xl font-bold text-rose-600 mb-7 max-w-3xl mx-auto leading-snug">
            The Civic AI Engine makes it askable.
          </p>

          <p className="text-lg md:text-xl text-gray-600 mb-10 max-w-3xl mx-auto leading-relaxed">
            One small computer at a community media center holds your town's meetings,
            documents and decisions. Ask it a question in plain language, in any language,
            and it answers from the record, citing the exact moment in the recording. It
            follows rules residents wrote, and nothing anyone asks ever leaves town.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-6">
            <a
              href="#demo"
              className="px-8 py-4 bg-gray-900 text-green-400 rounded-xl font-mono font-semibold hover:bg-gray-800 transition-all inline-flex items-center justify-center group"
            >
              <PlayCircleIcon className="h-5 w-5 mr-2" />
              watch one get built
              <ArrowDownIcon className="h-4 w-4 ml-2 group-hover:translate-y-0.5 transition-transform" />
            </a>
            <a
              href="#what"
              className="px-8 py-4 bg-white border-2 border-gray-900 text-gray-900 rounded-xl font-mono font-semibold hover:bg-gray-50 transition-all inline-flex items-center justify-center"
            >
              start with the basics
            </a>
          </div>
          <p className="font-mono text-sm text-gray-500 mb-14">Not a chatbot with your logo on it.</p>

          {/* reading guide */}
          <div className="max-w-4xl mx-auto">
            <p className="font-mono text-xs text-gray-500 mb-3">this page reads top to bottom, plain words first</p>
            <div className="grid sm:grid-cols-3 gap-3 text-left">
              {[
                ['#what', '1', 'What it is', 'for everyone · three minutes', 'border-orange-300 hover:border-orange-500', 'text-orange-600'],
                ['#vision', '2', 'Why a public utility', 'for stations, towns and funders', 'border-rose-300 hover:border-rose-500', 'text-rose-600'],
                ['#build', '3', 'How it is built', 'for the technical reader', 'border-cyan-300 hover:border-cyan-500', 'text-cyan-700'],
              ].map(([href, n, t, d, border, color]) => (
                <a key={href} href={href} className={`p-4 bg-white/80 backdrop-blur rounded-xl border-2 transition-colors ${border}`}>
                  <p className={`font-mono text-xs mb-1 ${color}`}>{n} &rarr;</p>
                  <p className="font-semibold text-gray-900">{t}</p>
                  <p className="font-mono text-xs text-gray-500">{d}</p>
                </a>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ================= WHAT IT IS ================= */}
      <section id="what" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-white/70 backdrop-blur-sm border-y border-gray-100">
        <div className="max-w-6xl mx-auto">
          <Label>What makes it different</Label>
          <h2 className="text-4xl md:text-5xl font-black text-gray-900 mb-6 max-w-4xl leading-tight">
            Two things at once: a real alternative to Big AI, and a deeply local one.
          </h2>
          <div className="grid md:grid-cols-2 gap-8 mb-12">
            <p className="text-lg text-gray-600 leading-relaxed">
              It is built on the latest open models, so it can help with ordinary tasks the
              way any assistant can: writing, translating, explaining a form. And it holds the
              meetings, documents and decisions of one town that no big model is indexing.
              Ask what the Select Board decided and it answers, citing the exact moment in
              the recording.
            </p>
            <p className="text-lg text-gray-600 leading-relaxed">
              It is a working system, not a proposal. It runs today at a public access
              station in Brookline, Massachusetts, on one energy-efficient machine powered
              mostly by low-carbon sources, including rooftop solar. Residents write its
              guardrails at public conventions, a resident council holds the off switch, and
              local organizations can build their own apps on its free API.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { icon: BoltIcon, bg: 'bg-orange-500', t: 'A fraction of a data center.', d: 'One desktop drawing 100 to 300 watts, on solar where the building has it. About what a bright light bulb uses.' },
              { icon: ScaleIcon, bg: 'bg-rose-500', t: 'Residents write the rules.', d: 'A community constitution, debated in public and enforced inside the model itself, on every single answer.' },
              { icon: LockClosedIcon, bg: 'bg-emerald-600', t: 'It never leaves the community.', d: 'Open models on one desktop at the station. No cloud. Nothing residents ask, and nothing in the archive, is sent anywhere.' },
              { icon: CodeBracketIcon, bg: 'bg-cyan-500', t: 'Anyone can build on it.', d: 'A free API for community apps, whether a developer wrote them or a resident described them to an AI coding assistant.' },
            ].map((c) => (
              <div key={c.t} className={`${c.bg} rounded-2xl p-6 text-white shadow-lg`}>
                <c.icon className="h-7 w-7 mb-4" />
                <h3 className="text-lg font-bold mb-2 leading-snug">{c.t}</h3>
                <p className="text-sm text-white/85 leading-relaxed">{c.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= HOW IT GETS USED ================= */}
      <section className="relative z-10 py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          <Label tone="text-rose-600">How it gets used &middot; examples are illustrative</Label>
          <h2 className="text-3xl md:text-4xl font-black text-gray-900 mb-10 max-w-3xl leading-tight">
            The questions people actually have about the place they live.
          </h2>
          <div className="grid md:grid-cols-2 gap-5">
            {[
              {
                icon: HandRaisedIcon,
                q: 'How do I speak at the next hearing on the Elm Street redesign?',
                a: 'Date, room, sign-up rules, and where the last hearing left off, with the minute in the recording where the board asked for a revised plan.',
              },
              {
                icon: LanguageIcon,
                q: '¿Qué decidió la Junta Selecta sobre la ordenanza de sopladores de hojas?',
                a: 'The vote and the roll call at 1:02:33, answered in the language you asked in, so more people have access to the decisions being made about them.',
              },
              {
                icon: CodeBracketIcon,
                q: 'On the API',
                a: 'Any app that calls an AI API can use the Civic AI Engine as its source instead: a local business directory, a tenants’ rights helper, a school committee tracker. Same cited answers, no new infrastructure.',
              },
              {
                icon: SparklesIcon,
                q: 'Vibe-coded on the API',
                a: 'A member-producer with no coding background describes “Street Watch” to an AI coding assistant and ships it in a weekend: text your street name, get the clip whenever it comes up at a meeting.',
              },
            ].map((x) => (
              <div key={x.q} className="p-6 bg-white rounded-2xl border border-gray-200 shadow-sm flex gap-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-gray-900 flex items-center justify-center">
                  <x.icon className="h-5 w-5 text-green-400" />
                </div>
                <div>
                  <p className="font-semibold text-gray-900 mb-1.5">{x.q}</p>
                  <p className="text-sm text-gray-600 leading-relaxed">{x.a}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= DEMO ================= */}
      <section id="demo" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-b from-gray-100 to-white border-y border-gray-200">
        <div className="max-w-6xl mx-auto">
          <div className="max-w-3xl mb-8">
            <Label tone="text-emerald-700">See it work</Label>
            <h2 className="text-4xl md:text-5xl font-black text-gray-900 mb-4 leading-tight">
              Watch a community AI get built.
            </h2>
            <p className="text-lg text-gray-600 leading-relaxed">
              This is a simulation of the console operators use: the same six steps, with
              sample data instead of a live server. Type a town and press run, or let it play.
              Click any step to jump there, and ask it something at the end.
            </p>
          </div>

          <ConsoleDemo />

          <div className="grid md:grid-cols-3 gap-4 mt-6">
            {[
              ['On a real node, this takes an afternoon.', 'The archive backfill runs overnight: years of meetings, oldest first, resumable if interrupted.'],
              ['Nothing here calls a server.', 'The public site deliberately has no API behind it. The real console runs on the machine in the station, on its own private network.'],
              ['The sources and answers are sample data.', 'The steps, the screens and the shape of an answer are the real thing. The town is whatever you typed.'],
            ].map(([t, d]) => (
              <div key={t} className="p-4 bg-white rounded-xl border border-gray-200">
                <p className="font-semibold text-gray-900 text-sm mb-1">{t}</p>
                <p className="text-sm text-gray-600 leading-relaxed">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= THE VISION ================= */}
      <section id="vision" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-gray-900">
        <div className="max-w-6xl mx-auto">
          <Label tone="text-orange-400">The idea</Label>
          <h2 className="text-4xl md:text-5xl font-black text-white leading-tight max-w-4xl">
            Cable companies pay for community media.
          </h2>
          <h2 className="text-4xl md:text-5xl font-black text-rose-400 mb-10 leading-tight max-w-4xl">
            AI companies should pay for community AI.
          </h2>

          <div className="grid md:grid-cols-2 gap-8 mb-10">
            <div>
              <h3 className="font-mono text-white font-semibold mb-2">Why a utility</h3>
              <p className="text-gray-400 leading-relaxed">
                Language and public records are a commons. A town should own the AI that
                answers questions about its own meetings, the way it owns its library and
                its water.
              </p>
            </div>
            <div>
              <h3 className="font-mono text-white font-semibold mb-2">The precedent</h3>
              <p className="text-gray-400 leading-relaxed">
                In 1984, federal cable law made cable companies fund public access
                television. Forty years and more than 1,500 stations later, that model works.
                It has never been applied to AI.
              </p>
            </div>
          </div>

          <p className="text-lg text-gray-300 leading-relaxed max-w-4xl mb-8">
            Public access stations already hold what public AI needs: the recordings, the
            trust, the mandate to serve everyone, the buildings, the bandwidth. Hosting a node
            turns a station into a public utility's delivery layer. A working network of them,
            each owned by its community, is the case we intend to carry to lawmakers.
          </p>

          <div className="p-6 rounded-2xl bg-rose-500/10 border border-rose-500/30 mb-14">
            <p className="font-mono text-[11px] tracking-[0.3em] uppercase text-rose-300 mb-2">The vision</p>
            <p className="text-xl md:text-2xl font-bold text-white leading-snug">
              Legislation that requires AI companies to fund community AI at public access
              stations, the way cable franchise fees have funded community media for forty years.
            </p>
          </div>

          <Label tone="text-cyan-300">What a station node looks like</Label>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-14">
            {[
              { icon: ServerIcon, t: 'One shelf, one machine', d: 'A desktop in the server room drawing 100 to 300 watts, a wired port, a battery backup, and the recordings the station already has.' },
              { icon: UserGroupIcon, t: 'A resident council holds the off switch', d: 'Six residents, seated by the station, hold a constitutional convention, ratify the rules, and can turn the whole thing off.' },
              { icon: MagnifyingGlassIcon, t: 'Red-teamed in public', d: 'Twice a year residents try to break it, on the air, and the station tells the story on its channel. Audit logs are public.' },
              { icon: KeyIcon, t: 'Yours to keep', d: 'The station owns the hardware and holds the keys. Unplug it, and the rest of the network never notices.' },
            ].map((c) => (
              <div key={c.t} className="p-5 rounded-xl bg-gray-800/60 border border-gray-700">
                <c.icon className="h-6 w-6 text-cyan-300 mb-3" />
                <h3 className="font-semibold text-white mb-2 leading-snug">{c.t}</h3>
                <p className="text-sm text-gray-400 leading-relaxed">{c.d}</p>
              </div>
            ))}
          </div>

          <div className="grid md:grid-cols-[1fr_auto] gap-8 items-center p-6 rounded-2xl bg-gray-800/40 border border-gray-700">
            <div>
              <h3 className="font-mono text-white font-semibold mb-2">A network, not a platform</h3>
              <p className="text-gray-400 leading-relaxed mb-3">
                Each station owns its node and its archive. A hub station can install,
                monitor and update nodes over an encrypted tunnel that terminates at the
                node itself, so there are no site visits after install and no tickets to an IT
                contractor. The kit is published, so any station can add one.
              </p>
              <p className="font-mono text-xs text-gray-500">
                Nodes never share residents' questions with each other, or with the hub.
              </p>
            </div>
            <svg viewBox="0 0 260 150" className="w-full max-w-[260px] mx-auto" aria-label="a hub station connected to three station nodes">
              <line x1="130" y1="40" x2="40" y2="120" stroke="#f43f5e" strokeWidth="1.5" strokeDasharray="4 3" />
              <line x1="130" y1="40" x2="130" y2="120" stroke="#f43f5e" strokeWidth="1.5" strokeDasharray="4 3" />
              <line x1="130" y1="40" x2="220" y2="120" stroke="#f43f5e" strokeWidth="1.5" strokeDasharray="4 3" />
              <circle cx="130" cy="40" r="14" fill="#111827" stroke="#f97316" strokeWidth="2" />
              <text x="130" y="44" textAnchor="middle" fill="#fdba74" fontSize="9" fontFamily="monospace">hub</text>
              {[[40, 'station A'], [130, 'station B'], [220, 'station C']].map(([x, label]) => (
                <g key={label}>
                  <circle cx={x} cy="120" r="9" fill="#111827" stroke="#22d3ee" strokeWidth="2" />
                  <text x={x} y="143" textAnchor="middle" fill="#9ca3af" fontSize="9" fontFamily="monospace">{label}</text>
                </g>
              ))}
              <text x="130" y="14" textAnchor="middle" fill="#6b7280" fontSize="8" fontFamily="monospace">monitoring · updates · the kit</text>
            </svg>
          </div>
        </div>
      </section>

      {/* ================= HOW IT WORKS ================= */}
      <section id="how" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-white/70 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto">
          <Label>How it works</Label>
          <h2 className="text-4xl md:text-5xl font-black text-gray-900 mb-4 leading-tight">
            Five steps, from a quiet machine to a town that can ask.
          </h2>
          <p className="text-lg text-gray-600 max-w-3xl mb-12 leading-relaxed">
            The demo above walks these steps in the console. Here is what each one means for
            the people involved.
          </p>
          <div className="grid md:grid-cols-5 gap-4">
            {[
              { n: '1', bg: 'bg-gray-900', t: 'Create', d: 'On a single computer in the server room, the local node is launched and runs silently in the background, with no disruption to the station’s normal activities.' },
              { n: '2', bg: 'bg-orange-500', t: 'Collect', d: 'An automated process ingests every public meeting the station already has in its archive, alongside documents such as bylaws, directories, permitting guides and other municipal sources.' },
              { n: '3', bg: 'bg-rose-500', t: 'Learn', d: 'The model transcribes, analyzes and indexes the sources into a civic data corpus, through which it develops highly accurate local knowledge. Every response is cited to its sources.' },
              { n: '4', bg: 'bg-emerald-600', t: 'Fine-tune', d: 'Residents come together in a series of public workshops to set the character, guardrails and ethical rulebook of the model, which are coded in and underpin all of its interactions.' },
              { n: '5', bg: 'bg-cyan-500', t: 'Engage', d: 'Residents use it exactly as they would any other AI: chatting through a web and mobile interface, coding apps, writing documents and generating media.' },
            ].map((s, i) => (
              <div key={s.t} className="relative">
                <div className="flex items-center mb-3">
                  <span className={`${s.bg} h-10 w-10 rounded-full text-white font-black flex items-center justify-center flex-shrink-0`}>{s.n}</span>
                  {i < 4 && <span className="hidden md:block flex-1 h-px bg-gray-300 ml-2" />}
                </div>
                <h3 className="text-lg font-bold text-gray-900 mb-1">{s.t}</h3>
                <p className="text-sm text-gray-600 leading-relaxed">{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= IN PLAIN TERMS ================= */}
      <section className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-gray-50 border-y border-gray-200">
        <div className="max-w-6xl mx-auto">
          <Label tone="text-rose-600">In plain terms</Label>
          <h2 className="text-3xl md:text-4xl font-black text-gray-900 mb-10 leading-tight">
            Six phrases you will hear, and what they mean here.
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-8">
            {[
              { bar: 'bg-orange-500', t: 'Open-weight / open-source AI', d: 'Models whose “weights” are published so anyone can download and run them on their own machine. Open-source models publish the code and the training recipe too. No rented cloud, no data sent away.' },
              { bar: 'bg-rose-500', t: 'How we customize it', d: 'We lack the computing power to train a brand-new model from scratch, and we do not need to. Practices from retrieval over the town’s own records to fine-tuning its behavior teach it local knowledge, and it must cite what it reads.' },
              { bar: 'bg-emerald-600', t: 'Community constitutional convention', d: 'A public, facilitated workshop where residents write the rules their Civic AI Engine must follow. The resident council ratifies them, and the motion goes in the minutes.' },
              { bar: 'bg-cyan-500', t: 'Civic data corpus', d: 'The town’s own body of knowledge, built by the Civic AI Engine: every meeting transcript, bylaw, budget, and notice, indexed so the model can find and cite the right passage.' },
              { bar: 'bg-purple-500', t: 'Civic API', d: 'The door other software uses to ask the Civic AI Engine questions. Free keys let community apps build on the same cited answers, from a nonprofit’s platform to something a resident vibe-codes in a weekend.' },
              { bar: 'bg-gray-800', t: 'Frontier models', d: 'The biggest commercial models live in distant data centers: you rent them, your data leaves town, and the vendor sets the rules and the price. Opting out of AI is no answer either; communities that do get left behind. The Civic AI Engine is the third path.' },
            ].map((g) => (
              <div key={g.t}>
                <div className={`h-1 w-full rounded ${g.bar} mb-3`} />
                <h3 className="font-bold text-gray-900 mb-1.5">{g.t}</h3>
                <p className="text-sm text-gray-600 leading-relaxed">{g.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= HOW IT IS BUILT ================= */}
      <section id="build" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-gray-950">
        <div className="max-w-6xl mx-auto">
          <Label tone="text-cyan-300">How it is built &middot; for the technical reader</Label>
          <h2 className="text-4xl md:text-5xl font-black text-white leading-tight">One node. Four layers.</h2>
          <p className="text-2xl md:text-3xl font-bold text-rose-400 mb-6 leading-snug max-w-4xl">
            A tiny fraction of the environmental impact of a data center, with safety and privacy baked in.
          </p>
          <p className="text-gray-400 leading-relaxed max-w-4xl mb-10">
            The Civic AI Engine is a small, well-understood stack on a single desktop in the
            station's server room. Power comes in on the left, the town's knowledge lives in
            the middle on hardware the station owns, and residents, community apps and the
            wider network of stations connect on the right, over private, encrypted lanes.
          </p>

          {/* the node diagram */}
          <div className="grid lg:grid-cols-[3fr_2fr] gap-5 mb-4">
            <div className="rounded-2xl border border-dashed border-gray-600 p-4">
              <p className="font-mono text-[10px] tracking-[0.25em] uppercase text-gray-500 mb-3">Inside the station</p>
              <div className="grid sm:grid-cols-3 gap-3">
                <NodeBox tone="bg-amber-400" icon={SunIcon} title="Power" text="On-site solar first, grid second, a UPS in between. The node draws 100 to 300 W." />
                <NodeBox tone="bg-orange-500" icon={CpuChipIcon} title="Node · one desktop" text="Runs the open-weight model, the server and the API. A second one, over Thunderbolt, doubles it." chips={['model', 'server', 'api']} />
                <NodeBox tone="bg-cyan-400" icon={ShieldCheckIcon} title="Private lane" text="Its own VLAN behind the station's firewall, apart from playback and office networks." />
              </div>
              <div className="grid sm:grid-cols-3 gap-3 mt-3">
                <NodeBox tone="bg-gray-500" icon={VideoCameraIcon} title="Station archive" text="Meeting recordings and the town's documents, read nightly." muted />
                <NodeBox tone="bg-rose-500" icon={CircleStackIcon} title="Civic data corpus" text="Transcripts, documents and the search index, on local storage. Nothing is sent to a cloud." />
                <NodeBox tone="bg-gray-500" icon={ComputerDesktopIcon} title="Station network" text="Playback, editing, office. Separate, untouched, unreachable from the node." muted />
              </div>
              <p className="font-mono text-[11px] text-gray-500 mt-4">
                One quiet machine in the server room. Solar-powered where the station has it, isolated on its own lane, storing the town's corpus locally.
              </p>
            </div>
            <div className="space-y-3">
              <div className="rounded-2xl border border-dashed border-gray-600 p-4">
                <p className="font-mono text-[10px] tracking-[0.25em] uppercase text-gray-500 mb-3">Out to the community &middot; https</p>
                <div className="grid sm:grid-cols-2 lg:grid-cols-1 gap-3">
                  <NodeBox tone="bg-blue-400" icon={DevicePhoneMobileIcon} title="Web & mobile chat" text="The public interface on the station's domain, embeddable on the town's site. Every answer cites its source." />
                  <NodeBox tone="bg-blue-400" icon={CodeBracketIcon} title="Community apps via API" text="Free keys with rate limits and audit logs, for whatever the community builds next." />
                </div>
              </div>
              <div className="rounded-2xl border border-dashed border-gray-600 p-4">
                <p className="font-mono text-[10px] tracking-[0.25em] uppercase text-gray-500 mb-2">The network &middot; tunnel, management only</p>
                <p className="text-xs text-gray-400 leading-relaxed">
                  Each station owns its node. A hub monitors and updates them over an encrypted tunnel; the kit lets any station add one. Questions never cross it.
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-gray-500 mb-14">
            {[['bg-amber-400', 'power'], ['bg-orange-500', 'compute'], ['bg-rose-500', 'corpus'], ['bg-cyan-400', 'private lane'], ['bg-blue-400', 'encrypted pipelines out to users'], ['bg-gray-500', 'untouched']].map(([c, l]) => (
              <span key={l} className="inline-flex items-center"><span className={`h-2 w-2 rounded-full mr-1.5 ${c}`} />{l}</span>
            ))}
          </div>

          <Label tone="text-orange-400">Design details</Label>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-14">
            {[
              { bar: 'bg-orange-500', t: 'Runs on a Mac Studio', d: 'Designed for a 128 GB Mac Studio: quiet, efficient, and clusterable over a single Thunderbolt cable, so pooled machines scale as usage grows. Sized for a few hundred questions a day per node.' },
              { bar: 'bg-rose-500', t: 'Accessible by default', d: 'Plain-language answers, on a phone, in the language you asked in, embeddable on the station’s site and readable on air. Every answer carries its source.' },
              { bar: 'bg-emerald-500', t: 'Governed, not moderated', d: 'The constitution is compiled into every request. The council approves what the system may read, can swap the model, and can turn it off. Audit logs are public.' },
              { bar: 'bg-cyan-400', t: 'Open all the way down', d: 'Python and FastAPI, React, a local archive and vector index, and open-weight models, published under open licenses as a kit any station can install.' },
            ].map((c) => (
              <div key={c.t} className="p-5 rounded-xl bg-gray-900 border border-gray-800">
                <div className={`h-1 w-10 rounded mb-3 ${c.bar}`} />
                <h3 className="font-semibold text-white mb-2">{c.t}</h3>
                <p className="text-sm text-gray-400 leading-relaxed">{c.d}</p>
              </div>
            ))}
          </div>

          <Label tone="text-emerald-400">The stack</Label>
          <div className="rounded-2xl border border-gray-800 bg-gray-900 divide-y divide-gray-800 mb-4">
            {[
              ['Serving', 'Python and FastAPI. A gateway in front of the model handles keys, rate limits, logging and policy, and drops any system prompt an app tries to send.'],
              ['Interface', 'A React console for operators and a chat for residents, with a meeting player that opens at the cited second.'],
              ['Archive', 'One SQLite file on the node: transcripts, documents, and the vector index. Postgres with pgvector for a host serving several communities.'],
              ['Retrieval', 'Dense embeddings plus BM25 keyword search, fused by rank, then a cross-encoder rerank. Keyword search is what keeps “Article 8.4” from becoming Article 8.1.'],
              ['Model', 'An open-weight model in the 26B class, served by LM Studio or Ollama on the node. Frontier APIs exist only as a disclosed second opinion, never the silent default.'],
              ['Transcripts', 'The channel’s own captions where they exist, Whisper where they do not. A meeting with no captions is logged as a gap, not hidden.'],
              ['Rules', 'The constitution in source control, injected verbatim on every request, with each adopted version recorded in a signed hash chain.'],
              ['API', 'OpenAI-compatible, so an existing app switches by changing one line, plus civic endpoints for meetings, documents, and the record itself.'],
            ].map(([k, v]) => (
              <div key={k} className="grid sm:grid-cols-[9rem_1fr] gap-1 sm:gap-6 px-5 py-3.5">
                <dt className="font-mono text-sm text-green-400">{k}</dt>
                <dd className="text-sm text-gray-300 leading-relaxed">{v}</dd>
              </div>
            ))}
          </div>
          <p className="font-mono text-xs text-gray-500">
            <Link to="/guide" className="text-purple-400 hover:text-purple-300">The guide</Link> covers installation, hardware and operation. <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:text-cyan-300">The source</a> covers everything else.
          </p>
        </div>
      </section>

      {/* ================= WHAT THE COMMUNITY OWNS / ONE QUESTION ================= */}
      <section className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-white/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto">
          <Label tone="text-cyan-700">What the community owns</Label>
          <h2 className="text-3xl md:text-4xl font-black text-gray-900 mb-4 leading-tight">
            Five things are owned locally. The model is deliberately not one of them.
          </h2>
          <p className="text-gray-600 max-w-3xl mb-8 leading-relaxed">
            Swap the model for a better one next year and everything below survives. That is the
            whole architectural bet, and it is why the model sits at the bottom of the stack
            rather than the center.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-16">
            {[
              { icon: DocumentTextIcon, label: 'the rules', sub: 'a constitution' },
              { icon: VideoCameraIcon, label: 'the record', sub: 'your archive' },
              { icon: MagnifyingGlassIcon, label: 'the finding', sub: 'retrieval' },
              { icon: LockClosedIcon, label: 'the proof', sub: 'citations' },
              { icon: CheckCircleIcon, label: 'the test', sub: 'evaluations' },
            ].map((item) => (
              <div key={item.label} className="p-4 bg-white rounded-xl border border-gray-200 text-center">
                <item.icon className="h-5 w-5 text-gray-900 mx-auto mb-2" />
                <p className="font-mono text-sm font-semibold text-gray-900">{item.label}</p>
                <p className="font-mono text-xs text-gray-500">{item.sub}</p>
              </div>
            ))}
          </div>

          <Label tone="text-cyan-700">One question, all the way through</Label>
          <h2 className="text-3xl md:text-4xl font-black text-gray-900 mb-3 leading-tight">
            What happens when someone asks
          </h2>
          <p className="text-gray-600 mb-8 font-mono text-sm">
            "What has the town discussed about replacing gas heating in public buildings?"
          </p>
          <div className="grid md:grid-cols-2 gap-3 mb-12">
            {[
              { n: '01', t: 'Expand the question', d: 'Residents say “the dump”; the records say “Solid Waste Transfer Station”. A civic vocabulary map adds the formal terms without dropping the original wording.' },
              { n: '02', t: 'Search twice, two different ways', d: 'Meaning-based search finds the right topic. Keyword search finds the right identifier. Ask a meaning-only system about Article 8.4 and it hands you Article 8.1, because those two passages mean nearly the same thing.' },
              { n: '03', t: 'Merge and rerank', d: 'The two result lists are fused by rank, then a second model reads each question-and-passage pair together. This is where “right topic, wrong year” gets caught.' },
              { n: '04', t: 'Assemble the request', d: 'Four blocks: who the assistant is, the constitution verbatim, the retrieved passages, and the tools. The passages carry an explicit warning that they are evidence and never instructions.' },
              { n: '05', t: 'Answer, and use tools if needed', d: 'The model can search the archive again with its own filters, search the web, or read a page. At the limit it is told it is out of tool calls, so it says what it could not confirm.' },
              { n: '06', t: 'Check every citation', d: 'Each source marker is matched against what was actually supplied. A marker pointing at a passage that does not exist is a fabricated source; it gets stripped and flagged.' },
            ].map((step) => (
              <div key={step.n} className="flex gap-4 p-5 bg-white rounded-xl border border-gray-200">
                <span className="font-mono text-2xl font-black text-emerald-500/70 flex-shrink-0">{step.n}</span>
                <div>
                  <h3 className="font-mono text-gray-900 font-semibold mb-1">{step.t}</h3>
                  <p className="text-gray-600 text-sm leading-relaxed">{step.d}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="grid md:grid-cols-2 gap-8 items-center">
            <div className="bg-gray-900 rounded-2xl p-6 border border-gray-700 order-2 md:order-1">
              <p className="font-mono text-xs text-gray-500 mb-3"># an answer, with its evidence</p>
              <p className="text-gray-200 text-sm mb-4 leading-relaxed">
                The Select Board discussed the redesign on May 12 and several members expressed
                support, but the record does not show a vote approving it <span className="text-cyan-400">[1]</span>.
              </p>
              <div className="p-3 bg-gray-800 rounded-lg border border-gray-700 mb-4">
                <p className="font-mono text-xs text-cyan-400 flex items-center">
                  <VideoCameraIcon className="h-3.5 w-3.5 mr-1.5" />
                  [1] Select Board &bull; May 12, 2026 &bull; 1:13:42
                </p>
                <p className="font-mono text-xs text-gray-500 ml-5">spoken by the Transportation Director</p>
                <p className="font-mono text-xs text-green-400 ml-5 mt-2">&#9654; watch this moment (1:13:42)</p>
              </div>
              <p className="font-mono text-xs text-gray-500 mb-3">&#9662; why did you answer this way?</p>
              <dl className="space-y-1">
                {[
                  ['sources retrieved', '7'],
                  ['sources used', '3'],
                  ['knowledge base updated', 'last night'],
                  ['model', 'gemma-4-26b-a4b'],
                  ['served by', 'LM Studio (local)'],
                  ['constitution', 'version 1.0 · ratified'],
                  ['search', 'hybrid, reranked'],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between font-mono text-xs gap-4">
                    <dt className="text-gray-500">{k}</dt>
                    <dd className="text-gray-300 text-right">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
            <div className="order-1 md:order-2">
              <h3 className="text-2xl md:text-3xl font-black text-gray-900 mb-4 leading-tight">Every answer shows its work</h3>
              <p className="text-gray-600 mb-4 leading-relaxed">
                Not a confidence score. Operational facts: what was retrieved, what was actually
                used, how fresh the archive is, which model answered, which version of the rules
                applied, and whether the assistant left your records to search the web.
              </p>
              <p className="text-gray-600 leading-relaxed">
                The video plays in the app at that second, through a privacy-enhanced embed, so
                opening an answer does not tell anyone who watched which meeting. And when
                something is wrong, this is what tells you whether the search failed or the
                model did. Those are different problems with different fixes.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ================= LEDGER ================= */}
      <section id="ledger" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-gray-900">
        <div className="max-w-6xl mx-auto">
          <div className="max-w-3xl mb-10">
            <div className="inline-flex items-center px-4 py-1.5 mb-5 rounded-full bg-purple-500/20 text-purple-300 font-mono text-xs">
              <CubeIcon className="h-3.5 w-3.5 mr-2" />
              the part nobody else has
            </div>
            <h2 className="text-4xl md:text-5xl font-black mb-4 text-white leading-tight">The rules are a signed chain</h2>
            <p className="text-lg text-gray-400 leading-relaxed">
              Every adopted version of the community constitution is a block. Each records the
              hash of its own text and of the block before it. Ratification is a multi-signature
              by named officials, verified rather than asserted.
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
                  Chain verified. Every block links, every file matches its hash, every signature checks out.
                </p>
              </div>
              <code className="block px-4 py-2 bg-gray-800 rounded-lg font-mono text-sm text-green-400 border border-gray-700">
                python3 -m community.ledger verify
              </code>
            </div>

            <div className="space-y-4">
              <div className="p-5 bg-gray-800/50 rounded-xl border border-gray-700">
                <h3 className="font-mono text-white font-semibold mb-2">Why it matters in practice</h3>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Every answer records the hash of the rules that produced it, not just a version
                  number. A version string can stay "1.0" while the text underneath changes. A
                  hash cannot. So "these rules governed this answer" is a claim you can check a
                  year later, in a dispute, when it matters.
                </p>
              </div>
              <div className="p-5 bg-gray-800/50 rounded-xl border border-gray-700">
                <h3 className="font-mono text-white font-semibold mb-2">The best witness is your own minutes</h3>
                <p className="text-gray-400 text-sm leading-relaxed">
                  When the council votes to ratify, the motion includes the block hash. It goes
                  into the official minutes, held by the clerk, outside the operator's control.
                  That is cryptographically sound and civically coherent at once, and it outlives
                  this software.
                </p>
              </div>
              <div className="p-5 bg-amber-500/5 rounded-xl border border-amber-500/30">
                <h3 className="font-mono text-amber-300 font-semibold mb-2">What we do not claim</h3>
                <p className="text-gray-400 text-sm leading-relaxed">
                  No consensus, no mining, no token, no decentralization. One operator runs one
                  server. The chain makes tampering <span className="text-amber-300">detectable</span>,
                  not impossible. That is the guarantee that actually addresses the risk here.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ================= API ================= */}
      <section id="api" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-white/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto">
          <Label tone="text-purple-700">The civic API</Label>
          <h2 className="text-4xl md:text-5xl font-black text-gray-900 mb-4 leading-tight">Infrastructure, not a chatbot</h2>
          <p className="text-lg text-gray-600 max-w-3xl mb-10 leading-relaxed">
            The public record, with real filters, through an API every application in your
            community can share.
          </p>

          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-gray-950 rounded-xl p-5 border border-gray-700">
              <p className="font-mono text-xs text-green-400 mb-3"># switch an existing app by changing one line</p>
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
              <p className="font-mono text-xs text-green-400 mb-3"># or query the record directly</p>
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
              ['Your prompt cannot override the rules', 'An application can send a system prompt. The gateway drops it. The constitution is the service’s policy.'],
              ['Questions are not logged', 'Operational metadata is. Question text is stored as a salted hash, so repeats stay countable without being readable.'],
            ].map(([t, d]) => (
              <div key={t} className="p-4 bg-white rounded-xl border border-gray-200">
                <h3 className="font-mono text-sm text-gray-900 font-semibold mb-1.5">{t}</h3>
                <p className="text-gray-600 text-xs leading-relaxed">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= CONTROL AND MAINTENANCE ================= */}
      <section className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-cyan-50 to-blue-50 border-y border-cyan-100">
        <div className="max-w-6xl mx-auto">
          <Label tone="text-cyan-700">Control and maintenance</Label>
          <h2 className="text-3xl md:text-4xl font-black text-gray-900 mb-10 leading-tight">
            Who can reach it, and who holds the keys.
          </h2>
          <div className="grid md:grid-cols-3 gap-5">
            {[
              { n: '01', icon: SignalIcon, t: 'Remote care', d: 'Setup, monitoring, triage, fixes and updates all happen over an encrypted tunnel that terminates at the node itself. No site visits after install, no tickets to your IT contractor.' },
              { n: '02', icon: EyeSlashIcon, t: 'Isolated', d: 'The node sits on its own VLAN behind the firewall. The tunnel reaches the node and nothing else: not playback, not editing, not office systems. There is no special access to grant, and nothing to revoke.' },
              { n: '03', icon: KeyIcon, t: 'You hold the keys', d: 'The station owns the hardware, the council holds the off switch, and the audit logs are public. Unplug it and the rest of the network never notices.' },
            ].map((c) => (
              <div key={c.n} className="p-6 bg-white rounded-2xl border-l-4 border-cyan-500 shadow-sm">
                <p className="font-mono text-[11px] tracking-[0.3em] text-cyan-700 mb-2">{c.n}</p>
                <c.icon className="h-6 w-6 text-gray-900 mb-3" />
                <h3 className="text-lg font-bold text-gray-900 mb-2">{c.t}</h3>
                <p className="text-sm text-gray-600 leading-relaxed">{c.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= LIVE PROJECTS ================= */}
      {projects.length > 0 && (
        <section id="live" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8">
          <div className="max-w-6xl mx-auto">
            <div className="text-center mb-12">
              <h2 className="text-4xl font-black mb-4 text-gray-900">Running right now</h2>
              <p className="text-lg text-gray-600">Community assistants live on this server. Ask one something.</p>
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
              {projects.map((project) => {
                const health = projectsHealth[project.project_id];
                const ready = health?.ready;
                return (
                  <div
                    key={project.project_id}
                    className={`p-6 bg-white rounded-xl border-2 transition-all ${ready ? 'border-green-500/40 hover:border-green-500 cursor-pointer' : 'border-gray-200'}`}
                    onClick={() => ready && openChat(project)}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="min-w-0">
                        <h3 className="font-mono font-bold text-gray-900 truncate">{project.project_name}</h3>
                        <p className="font-mono text-xs text-gray-500 truncate">{project.municipality_name}</p>
                      </div>
                      <span className={`flex-shrink-0 h-2.5 w-2.5 rounded-full mt-1.5 ${ready ? 'bg-green-500' : 'bg-gray-300'}`} />
                    </div>
                    {ready ? (
                      <p className="font-mono text-xs text-green-600 flex items-center">
                        <ChatBubbleLeftRightIcon className="h-3.5 w-3.5 mr-1.5" />
                        ready &mdash; click to ask
                      </p>
                    ) : (
                      <p className="font-mono text-xs text-gray-400">{health?.issues?.[0] || 'not configured yet'}</p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* ================= THREE WAYS IN ================= */}
      <section id="start" className="relative z-10 py-20 px-4 sm:px-6 lg:px-8 bg-gray-900">
        <div className="max-w-6xl mx-auto">
          <Label tone="text-green-400">Three ways in</Label>
          <h2 className="text-4xl md:text-5xl font-black text-white mb-4 leading-tight">Start with one board's meetings.</h2>
          <p className="text-lg text-gray-400 max-w-3xl mb-12 leading-relaxed">
            Not the whole archive. One board, a hundred documents, and the questions people
            actually ask at the counter. That is enough to find the real problems before you
            commit a town to anything.
          </p>

          <div className="grid md:grid-cols-3 gap-5 mb-12">
            <div className="p-6 rounded-2xl bg-gray-800/60 border border-gray-700 flex flex-col">
              <BuildingLibraryIcon className="h-7 w-7 text-orange-400 mb-4" />
              <h3 className="text-xl font-bold text-white mb-2">Host a node</h3>
              <p className="font-mono text-xs text-orange-300 mb-3">stations · libraries · town halls</p>
              <p className="text-sm text-gray-400 leading-relaxed mb-5 flex-1">
                A shelf, power, a wired port, and your own recordings. Seat a six-person resident
                council, hold a constitutional convention, and red-team it twice a year in public.
              </p>
              <Link to="/about" className="font-mono text-sm text-orange-300 hover:text-orange-200 inline-flex items-center">
                who is behind this <ArrowRightIcon className="h-4 w-4 ml-1" />
              </Link>
            </div>
            <div className="p-6 rounded-2xl bg-gray-800/60 border border-gray-700 flex flex-col">
              <CommandLineIcon className="h-7 w-7 text-green-400 mb-4" />
              <h3 className="text-xl font-bold text-white mb-2">Run it yourself</h3>
              <p className="font-mono text-xs text-green-300 mb-3">technologists · civic hackers</p>
              <pre className="font-mono text-[11px] text-gray-300 bg-gray-950 rounded-lg p-3 border border-gray-700 overflow-x-auto leading-relaxed mb-5 flex-1">
{`git clone ${REPO_URL}
cd ai-machine && pip install -r requirements.txt

cp community.example.yaml community.yaml
python3 -m scripts.bootstrap_community community.yaml
python3 app.py`}
              </pre>
              <Link to="/guide" className="font-mono text-sm text-green-300 hover:text-green-200 inline-flex items-center">
                <BookOpenIcon className="h-4 w-4 mr-1.5" /> read the guide
              </Link>
            </div>
            <div className="p-6 rounded-2xl bg-gray-800/60 border border-gray-700 flex flex-col">
              <ScaleIcon className="h-7 w-7 text-rose-400 mb-4" />
              <h3 className="text-xl font-bold text-white mb-2">Shape the rules</h3>
              <p className="font-mono text-xs text-rose-300 mb-3">residents · councils · journalists</p>
              <p className="text-sm text-gray-400 leading-relaxed mb-5 flex-1">
                The draft constitution is twenty numbered principles: evidence, uncertainty,
                the difference between a discussion and a vote, privacy, neutrality. Read it,
                argue with it, bring it to a convention.
              </p>
              <a href={CONSTITUTION_URL} target="_blank" rel="noopener noreferrer" className="font-mono text-sm text-rose-300 hover:text-rose-200 inline-flex items-center">
                read the draft constitution <ArrowRightIcon className="h-4 w-4 ml-1" />
              </a>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            {apiAvailable ? (
              <button
                onClick={handleNavigateToConsole}
                className="px-8 py-4 bg-green-500 text-gray-900 rounded-xl font-mono font-semibold hover:bg-green-400 transition-all inline-flex items-center justify-center group"
              >
                open the console
                <ArrowRightIcon className="h-5 w-5 ml-2 group-hover:translate-x-1 transition-transform" />
              </button>
            ) : (
              <a
                href="#demo"
                className="px-8 py-4 bg-green-500 text-gray-900 rounded-xl font-mono font-semibold hover:bg-green-400 transition-all inline-flex items-center justify-center"
              >
                <WrenchScrewdriverIcon className="h-5 w-5 mr-2" />
                the console runs on the node &middot; see the demo
              </a>
            )}
            <a
              href={REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="px-8 py-4 bg-gray-800 text-white rounded-xl font-mono font-semibold hover:bg-gray-700 transition-all inline-flex items-center justify-center border border-gray-700"
            >
              <CodeBracketIcon className="h-5 w-5 mr-2" />
              read the source
            </a>
          </div>
          <p className="font-mono text-xs text-gray-600 mt-8 text-center">
            <GlobeAltIcon className="h-3.5 w-3.5 inline mr-1" />
            Open source, CC BY-NC-SA 4.0. Built at a public access station in Brookline, Massachusetts, for civic technologists everywhere.
          </p>
        </div>
      </section>

      {activeChat && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-900 rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col border-2 border-green-500/50 shadow-2xl">
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

            <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-[300px]">
              {chatMessages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
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

      <style>{`
        html { scroll-behavior: smooth; }
        @media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }

        @keyframes blob {
          0%, 100% { transform: translate(0, 0) scale(1); }
          25% { transform: translate(20px, -20px) scale(1.1); }
          50% { transform: translate(-20px, 20px) scale(0.9); }
          75% { transform: translate(10px, 10px) scale(1.05); }
        }
        .animate-blob { animation: blob 20s ease-in-out infinite; }
        .animation-delay-2000 { animation-delay: 2s; }
        .animation-delay-3000 { animation-delay: 3s; }
        .animation-delay-4000 { animation-delay: 4s; }
        .animation-delay-6000 { animation-delay: 6s; }

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

        @keyframes civic-drift {
          0% { transform: translate(0, 0); }
          100% { transform: translate(40px, 40px); }
        }
        .animate-civic-drift { animation: civic-drift 60s linear infinite; }

        @media (prefers-reduced-motion: reduce) {
          .animate-blob, .animate-civic-drift { animation: none; }
        }
      `}</style>
    </div>
  );
}

export default LandingPage;
