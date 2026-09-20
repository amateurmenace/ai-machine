import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import api, { apiBaseUrl } from '../api';
import MeetingPlayer from './MeetingPlayer';
import SecondOpinion from './SecondOpinion';
import {
  PaperAirplaneIcon, LinkIcon, SparklesIcon, ArrowLeftIcon,
  InformationCircleIcon, ExclamationTriangleIcon, DocumentTextIcon,
  VideoCameraIcon, ChevronDownIcon, ChevronRightIcon,
  GlobeAltIcon, WrenchScrewdriverIcon, PlayCircleIcon,
} from '@heroicons/react/24/outline';

// Operational facts about one answer, per section 14 of the community-owned AI
// guide: what was retrieved, what was used, how fresh the archive is, which
// model answered, and which constitution version applied. Deliberately not the
// model's reasoning -- the guide is explicit that this control shows what the
// system did, not what it was thinking.
function ProvenancePanel({ provenance }) {
  const [open, setOpen] = useState(false);
  if (!provenance) return null;

  const retrieval = provenance.retrieval || {};
  const rows = [
    ['sources retrieved', provenance.sources_retrieved],
    ['sources used', provenance.sources_used],
    ['passages in knowledge base', provenance.corpus_size],
    ['knowledge base updated', provenance.knowledge_updated || 'unknown'],
    ['model', provenance.model],
    ['served by', provenance.provider],
    ['system version', provenance.system_version],
    ['constitution', provenance.constitution_version
      ? `version ${provenance.constitution_version}${
          provenance.constitution_hash
            ? ` · ${String(provenance.constitution_hash).split(':').pop().slice(0, 8)}` : ''}${
          provenance.constitution_ratified ? ' · ratified' : ''}`
      : 'none'],
    ['search', retrieval.reranked
      ? `hybrid, reranked (${retrieval.rerank_model || 'cross-encoder'})`
      : 'hybrid, fusion order'],
    ['candidates considered', retrieval.candidates_considered],
    ['retrieval time', retrieval.elapsed_ms != null ? `${retrieval.elapsed_ms} ms` : null],
  ].filter(([, value]) => value !== null && value !== undefined && value !== '');

  const notes = [...(provenance.warnings || []), ...(retrieval.notes || [])];
  const tools = provenance.tools || {};
  const invocations = tools.invocations || [];

  return (
    <div className="mt-3 pt-3 border-t border-gray-700">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center text-xs font-mono text-gray-500 hover:text-cyan-400 transition-colors"
      >
        {open
          ? <ChevronDownIcon className="h-3 w-3 mr-1" />
          : <ChevronRightIcon className="h-3 w-3 mr-1" />}
        <InformationCircleIcon className="h-3 w-3 mr-1" />
        why did you answer this way?
      </button>

      {open && (
        <div className="mt-2 p-3 bg-gray-900/60 rounded border border-gray-700">
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
            {rows.map(([label, value]) => (
              <div key={label} className="flex justify-between text-xs font-mono gap-3">
                <dt className="text-gray-500 whitespace-nowrap">{label}</dt>
                <dd className="text-gray-300 text-right break-all">{String(value)}</dd>
              </div>
            ))}
          </dl>

          {invocations.length > 0 && (
            <div className="mt-3 pt-2 border-t border-gray-800">
              <p className="text-xs font-mono text-gray-500 mb-1">
                tools used ({tools.iterations} round{tools.iterations === 1 ? '' : 's'})
              </p>
              {invocations.map((call, idx) => (
                <p key={idx} className="text-xs font-mono text-gray-400 flex items-start">
                  {call.external
                    ? <GlobeAltIcon className="h-3 w-3 mr-1 mt-0.5 flex-shrink-0 text-amber-500/80" />
                    : <WrenchScrewdriverIcon className="h-3 w-3 mr-1 mt-0.5 flex-shrink-0 text-gray-600" />}
                  <span>
                    {call.tool}
                    {call.arguments && call.arguments.query
                      ? ` "${String(call.arguments.query).slice(0, 48)}"` : ''}
                    <span className={call.ok ? 'text-gray-600' : 'text-red-400'}>
                      {' '}— {call.summary}
                    </span>
                  </span>
                </p>
              ))}
              {tools.external_calls > 0 && (
                <p className="mt-1 text-xs font-mono text-amber-500/70">
                  This answer used sources outside the community's records.
                </p>
              )}
            </div>
          )}

          {notes.length > 0 && (
            <div className="mt-3 pt-2 border-t border-gray-800">
              {notes.map((note, idx) => (
                <p key={idx} className="text-xs font-mono text-amber-400/80 flex items-start">
                  <ExclamationTriangleIcon className="h-3 w-3 mr-1 mt-0.5 flex-shrink-0" />
                  <span>{note}</span>
                </p>
              ))}
            </div>
          )}

          <p className="mt-3 text-xs font-mono text-gray-600">
            This shows what the system did, not the model's private reasoning.
          </p>
        </div>
      )}
    </div>
  );
}

// One citation. Links land on the exact page or timestamp rather than the top
// of a 300-page PDF (Principle 20, Verifiability), and a meeting citation can
// open its own player so the resident can watch the board say the thing.
function SourceCitation({ source, index }) {
  const [showPlayer, setShowPlayer] = useState(false);

  const isMeeting = source.source_type === 'meeting_transcript';
  const isWeb = source.source_type === 'web' || source.source_type === 'page';
  const Icon = isMeeting ? VideoCameraIcon : isWeb ? GlobeAltIcon : DocumentTextIcon;
  const label = source.label || source.title || 'Source';
  const number = source.number != null ? source.number : index + 1;
  const canPlay = Boolean(source.embed && source.embed.embed_url);

  return (
    <div className={`text-xs font-mono ${source.used === false ? 'opacity-50' : ''}`}>
      <div className="flex items-start">
        <span className="text-gray-600 mr-1 flex-shrink-0">[{number}]</span>
        <Icon className="h-3 w-3 mr-1 mt-0.5 flex-shrink-0 text-gray-500" />
        <a
          href={source.url || '#'}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyan-400 hover:text-cyan-300 transition-colors break-words"
        >
          {label}
          {source.url && <LinkIcon className="h-3 w-3 ml-1 inline-block opacity-60" />}
        </a>
      </div>

      {(source.attribution || source.agenda_item || source.status) && (
        <p className="ml-6 text-gray-600">
          {[source.attribution, source.agenda_item && `on ${source.agenda_item}`, source.status]
            .filter(Boolean)
            .join(' · ')}
        </p>
      )}

      {isWeb && (
        <p className="ml-6 text-amber-500/70">
          from the web, not this community's records
        </p>
      )}

      {canPlay && (
        <div className="ml-6 mt-1">
          <button
            onClick={() => setShowPlayer(!showPlayer)}
            className="flex items-center text-gray-500 hover:text-green-400 transition-colors"
          >
            <PlayCircleIcon className="h-3.5 w-3.5 mr-1" />
            {showPlayer ? 'hide video' : `watch this moment${
              source.embed.start_label ? ` (${source.embed.start_label})` : ''}`}
          </button>
          {showPlayer && (
            <MeetingPlayer
              embed={source.embed}
              label={label}
              speaker={source.speaker}
              agendaItem={source.agenda_item}
              onClose={() => setShowPlayer(false)}
              autoOpen
            />
          )}
        </div>
      )}
    </div>
  );
}

function ChatInterface() {
  const { projectId } = useParams();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [project, setProject] = useState(null);
  const [systemInfo, setSystemInfo] = useState(null);
  const [opinionOptions, setOpinionOptions] = useState([]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    loadProject();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const loadProject = async () => {
    try {
      const response = await api.get(`/api/projects/${projectId}`);
      setProject(response.data);

      // Public system facts, so the footer can show which constitution version
      // is in force without waiting for the first answer.
      try {
        const stats = await api.get(`/community/${projectId}/stats`);
        setSystemInfo(stats.data);
      } catch (statsError) {
        // The gateway may not be reachable; the chat still works without it.
        setSystemInfo(null);
      }

      // Which frontier models a resident could choose to ask. Absent or empty
      // means the control simply does not appear.
      try {
        const opinions = await api.get(`/api/projects/${projectId}/second-opinion/options`);
        setOpinionOptions(opinions.data.options || []);
      } catch (optionsError) {
        setOpinionOptions([]);
      }

      // Add welcome message
      setMessages([{
        role: 'assistant',
        content: `Hi! I'm ${response.data.project_name}. I can help you with information about ${response.data.municipality_name}. What would you like to know?`,
        sources: []
      }]);
    } catch (error) {
      console.error('Error loading project:', error);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');

    // Add user message
    const newMessages = [...messages, { role: 'user', content: userMessage, sources: [] }];
    setMessages(newMessages);
    setLoading(true);

    try {
      // Prepare conversation history (last 5 messages)
      const conversationHistory = newMessages.slice(-6, -1).map(msg => ({
        role: msg.role,
        content: msg.content
      }));

      const response = await api.post('/api/chat', {
        project_id: projectId,
        message: userMessage,
        conversation_history: conversationHistory
      });

      // Add assistant response
      setMessages([...newMessages, {
        role: 'assistant',
        question: userMessage,
        content: response.data.answer,
        sources: response.data.sources || [],
        provenance: response.data.provenance || null,
        thinking: response.data.thinking || null
      }]);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages([...newMessages, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        sources: [],
        isError: true
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const suggestedQuestions = [
    "When is trash day?",
    "How do I get a parking permit?",
    "What happened at the last town meeting?",
    "Tell me about local events this week"
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-12rem)]">
      {/* Back Button */}
      <Link
        to={`/console/projects/${projectId}`}
        className="inline-flex items-center text-gray-400 hover:text-green-400 font-mono text-sm mb-4 group"
      >
        <ArrowLeftIcon className="h-4 w-4 mr-2 group-hover:-translate-x-1 transition-transform" />
        <span className="text-green-400">$</span> cd ../dashboard
      </Link>

      {/* Header */}
      <div className="bg-gray-900 border border-gray-700 rounded-t-lg overflow-hidden">
        <div className="flex items-center space-x-2 px-4 py-3 bg-gray-800 border-b border-gray-700">
          <div className="flex space-x-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
          </div>
          <span className="text-gray-400 text-sm font-mono ml-4">
            {project?.project_name || 'chat'} - {project?.municipality_name}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto bg-gray-950 p-4 space-y-4 border-x border-gray-700">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-3xl rounded-lg px-4 py-3 ${
                message.role === 'user'
                  ? 'bg-green-500/20 border border-green-500/30 text-green-100'
                  : message.isError
                    ? 'bg-red-500/10 border border-red-500/30 text-red-300'
                    : 'bg-gray-800 border border-gray-700 text-gray-200'
              }`}
            >
              {/* Role indicator */}
              <div className={`text-xs font-mono mb-2 ${
                message.role === 'user' ? 'text-green-500' : 'text-cyan-500'
              }`}>
                {message.role === 'user' ? '$ you' : '> assistant'}
              </div>

              {/* Thinking (if available) */}
              {message.thinking && (
                <div className="mb-3 p-3 bg-gray-900/50 rounded border border-gray-700">
                  <div className="text-xs font-mono text-purple-400 mb-1">
                    <SparklesIcon className="h-3 w-3 inline mr-1" />
                    thinking...
                  </div>
                  <p className="text-xs text-gray-500 font-mono">{message.thinking}</p>
                </div>
              )}

              <div className="whitespace-pre-wrap font-mono text-sm">{message.content}</div>

              {/* Sources */}
              {message.sources && message.sources.length > 0 && (() => {
                const cited = message.sources.filter((s) => s.used !== false);
                const uncited = message.sources.filter((s) => s.used === false);
                return (
                  <div className="mt-3 pt-3 border-t border-gray-700">
                    <p className="text-xs font-mono text-gray-500 mb-2">
                      # sources{cited.length > 0 ? ` cited (${cited.length})` : ''}:
                    </p>
                    <div className="space-y-2">
                      {(cited.length > 0 ? cited : message.sources).map((source, idx) => (
                        <SourceCitation key={source.id || idx} source={source} index={idx} />
                      ))}
                    </div>
                    {cited.length > 0 && uncited.length > 0 && (
                      <details className="mt-2">
                        <summary className="text-xs font-mono text-gray-600 cursor-pointer hover:text-gray-400">
                          {uncited.length} more retrieved but not cited
                        </summary>
                        <div className="mt-2 space-y-2">
                          {uncited.map((source, idx) => (
                            <SourceCitation key={source.id || idx} source={source} index={idx} />
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                );
              })()}

              {/* "Why did you answer this way?" (guide section 14) */}
              {message.role === 'assistant' && message.provenance && (
                <ProvenancePanel provenance={message.provenance} />
              )}

              {/* A frontier model, if the resident chooses and is told where
                  the question goes. Never automatic. */}
              {message.role === 'assistant' && message.question && !message.isError && (
                <SecondOpinion
                  projectId={projectId}
                  question={message.question}
                  localAnswer={message}
                  options={opinionOptions}
                />
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-3">
              <div className="text-xs font-mono text-cyan-500 mb-2">> assistant</div>
              <div className="flex items-center space-x-2 text-gray-400 font-mono text-sm">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
                <span>processing query...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Questions (shown when no user messages) */}
      {messages.length <= 1 && (
        <div className="bg-gray-900 border-x border-gray-700 p-4">
          <p className="text-xs font-mono text-gray-500 mb-3"># try asking:</p>
          <div className="flex flex-wrap gap-2">
            {suggestedQuestions.map((question, idx) => (
              <button
                key={idx}
                onClick={() => setInput(question)}
                className="text-sm font-mono bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white px-3 py-2 rounded border border-gray-700 hover:border-gray-600 transition-all"
              >
                {question}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="bg-gray-900 border border-gray-700 rounded-b-lg p-4">
        <div className="flex space-x-3">
          <div className="flex-1 relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-green-400 font-mono text-sm">$</span>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="ask a question..."
              rows={1}
              className="w-full pl-8 pr-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono text-sm placeholder-gray-500 focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none"
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="px-6 py-3 bg-green-500 text-gray-900 rounded-lg font-mono font-semibold hover:bg-green-400 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed flex items-center transition-colors"
          >
            <PaperAirplaneIcon className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Public artifacts (guide section 14). The constitution and the system
          facts are public documents, so they are linked from every page. */}
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-mono text-gray-600">
        <a
          href={`${apiBaseUrl}/community/${projectId}/constitution`}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-cyan-400 transition-colors"
        >
          community constitution
          {systemInfo?.constitution_version ? ` v${systemInfo.constitution_version}` : ''}
        </a>
        <span className="text-gray-700">•</span>
        <Link
          to={`/console/projects/${projectId}/ledger`}
          className="hover:text-cyan-400 transition-colors"
        >
          amendment ledger
        </Link>
        <span className="text-gray-700">•</span>
        <a
          href={`${apiBaseUrl}/community/${projectId}/stats`}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-cyan-400 transition-colors"
        >
          system facts
        </a>
        <span className="text-gray-700">•</span>
        <Link
          to={`/console/projects/${projectId}/data`}
          className="hover:text-cyan-400 transition-colors"
        >
          sources
        </Link>
        <span className="text-gray-700">•</span>
        <a
          href={`${apiBaseUrl}/docs`}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-cyan-400 transition-colors"
        >
          api
        </a>
        {systemInfo?.knowledge_updated && (
          <>
            <span className="text-gray-700">•</span>
            <span>knowledge base updated {systemInfo.knowledge_updated}</span>
          </>
        )}
        {systemInfo?.constitution_status === 'draft' && (
          <span className="text-amber-500/70">
            (constitution not yet ratified)
          </span>
        )}
        {systemInfo?.constitution_ledger_ok === false && (
          <span className="text-red-400">
            (ledger does not verify — these may not be the adopted rules)
          </span>
        )}
      </div>
    </div>
  );
}

export default ChatInterface;
