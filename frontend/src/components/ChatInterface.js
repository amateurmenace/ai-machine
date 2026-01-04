import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import { PaperAirplaneIcon, LinkIcon, CommandLineIcon, SparklesIcon, ArrowLeftIcon } from '@heroicons/react/24/outline';

function ChatInterface() {
  const { projectId } = useParams();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [project, setProject] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    loadProject();
  }, [projectId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const loadProject = async () => {
    try {
      const response = await axios.get(`/api/projects/${projectId}`);
      setProject(response.data);

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

      const response = await axios.post('/api/chat', {
        project_id: projectId,
        message: userMessage,
        conversation_history: conversationHistory
      });

      // Add assistant response
      setMessages([...newMessages, {
        role: 'assistant',
        content: response.data.answer,
        sources: response.data.sources || [],
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
              {message.sources && message.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-700">
                  <p className="text-xs font-mono text-gray-500 mb-2"># sources:</p>
                  <div className="space-y-1">
                    {message.sources.map((source, idx) => (
                      <a
                        key={idx}
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center text-xs text-cyan-400 hover:text-cyan-300 font-mono transition-colors"
                      >
                        <LinkIcon className="h-3 w-3 mr-1 flex-shrink-0" />
                        <span className="truncate">{source.title}</span>
                        {source.relevance_score && (
                          <span className="ml-2 text-gray-600">({(source.relevance_score * 100).toFixed(0)}%)</span>
                        )}
                      </a>
                    ))}
                  </div>
                </div>
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
    </div>
  );
}

export default ChatInterface;
