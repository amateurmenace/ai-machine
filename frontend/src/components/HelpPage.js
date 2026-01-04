import React from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeftIcon,
  QuestionMarkCircleIcon,
  ServerIcon,
  CpuChipIcon,
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  CogIcon,
  CircleStackIcon,
  KeyIcon,
  CommandLineIcon,
  ExclamationTriangleIcon,
  LightBulbIcon,
  ArrowTopRightOnSquareIcon
} from '@heroicons/react/24/outline';

function HelpPage() {
  const { projectId } = useParams();

  const Section = ({ title, icon: Icon, iconColor, children }) => (
    <div className="bg-gray-900 rounded-lg border border-gray-700 p-6 mb-6">
      <div className="flex items-center space-x-2 mb-4">
        <Icon className={`h-5 w-5 ${iconColor}`} />
        <h2 className="text-lg font-bold text-white font-mono">{title}</h2>
      </div>
      {children}
    </div>
  );

  const Tip = ({ children }) => (
    <div className="flex items-start space-x-2 p-3 bg-cyan-500/10 rounded border border-cyan-500/30 text-sm">
      <LightBulbIcon className="h-5 w-5 text-cyan-400 flex-shrink-0 mt-0.5" />
      <p className="text-cyan-200">{children}</p>
    </div>
  );

  const Warning = ({ children }) => (
    <div className="flex items-start space-x-2 p-3 bg-yellow-500/10 rounded border border-yellow-500/30 text-sm">
      <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400 flex-shrink-0 mt-0.5" />
      <p className="text-yellow-200">{children}</p>
    </div>
  );

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
      <div className="flex items-center space-x-3 mb-8">
        <div className="p-2 bg-cyan-500/20 rounded-lg border border-cyan-500/30">
          <QuestionMarkCircleIcon className="h-6 w-6 text-cyan-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white font-mono">help_guide</h1>
          <p className="text-gray-500 text-sm font-mono">Everything you need to know</p>
        </div>
      </div>

      {/* Getting Started */}
      <Section title="# getting_started" icon={CommandLineIcon} iconColor="text-green-400">
        <div className="space-y-4 text-sm text-gray-300">
          <p>
            Neighborhood AI creates local AI assistants that can answer questions about your community,
            municipality, or organization using your own data sources.
          </p>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-white font-mono mb-2">Quick Start Steps:</h3>
            <ol className="list-decimal list-inside space-y-2 text-gray-400">
              <li><span className="text-white">Create a project</span> - Name your AI and set the location</li>
              <li><span className="text-white">Add data sources</span> - YouTube, websites, PDFs, etc.</li>
              <li><span className="text-white">Ingest the data</span> - Process sources into searchable knowledge</li>
              <li><span className="text-white">Start chatting</span> - Test your AI with questions</li>
            </ol>
          </div>

          <Tip>
            The more relevant data you add, the better your AI will answer questions.
            Start with 5-10 high-quality sources and expand from there.
          </Tip>
        </div>
      </Section>

      {/* Setting Up Ollama */}
      <Section title="# ollama_setup" icon={CpuChipIcon} iconColor="text-purple-400">
        <div className="space-y-4 text-sm text-gray-300">
          <p>
            Ollama lets you run AI models locally on your computer. This means your data stays private
            and you don't need to pay for API access.
          </p>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-white font-mono mb-3">Step 1: Install Ollama</h3>
            <p className="text-gray-400 mb-2">Download from the official website:</p>
            <a
              href="https://ollama.ai/download"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center text-cyan-400 hover:text-cyan-300 font-mono"
            >
              https://ollama.ai/download <ArrowTopRightOnSquareIcon className="h-4 w-4 ml-1" />
            </a>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-white font-mono mb-3">Step 2: Start Ollama Server</h3>
            <p className="text-gray-400 mb-2">Open Terminal (Mac) or Command Prompt (Windows) and run:</p>
            <pre className="bg-gray-900 p-3 rounded overflow-x-auto">
              <code className="text-green-400">ollama serve</code>
            </pre>
            <p className="text-gray-500 text-xs mt-2">Keep this terminal open while using Neighborhood AI.</p>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-white font-mono mb-3">Step 3: Download a Model</h3>
            <p className="text-gray-400 mb-2">In a new terminal window, pull the recommended model:</p>
            <pre className="bg-gray-900 p-3 rounded overflow-x-auto">
              <code className="text-green-400">ollama pull llama3.1:8b</code>
            </pre>
            <p className="text-gray-500 text-xs mt-2">This downloads ~4.5GB. Wait for it to complete.</p>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-white font-mono mb-3">Step 4: Run the Model</h3>
            <p className="text-gray-400 mb-2">If the model is already downloaded, start it with:</p>
            <pre className="bg-gray-900 p-3 rounded overflow-x-auto">
              <code className="text-green-400">ollama run llama3.1:8b</code>
            </pre>
            <p className="text-gray-500 text-xs mt-2">This loads the model into memory. You can then use the /bye command to exit.</p>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-white font-mono mb-3">Available Models</h3>
            <div className="space-y-2">
              <div className="flex justify-between items-center py-2 border-b border-gray-700">
                <span className="text-white font-mono">llama3.1:8b</span>
                <span className="text-gray-500 text-xs">Recommended - 8GB RAM</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-gray-700">
                <span className="text-white font-mono">llama3.2:3b</span>
                <span className="text-gray-500 text-xs">Lightweight - 4GB RAM</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-gray-700">
                <span className="text-white font-mono">mistral:7b</span>
                <span className="text-gray-500 text-xs">Fast - 8GB RAM</span>
              </div>
              <div className="flex justify-between items-center py-2">
                <span className="text-white font-mono">llama3.1:70b</span>
                <span className="text-gray-500 text-xs">Best quality - GPU required</span>
              </div>
            </div>
          </div>

          <Warning>
            Make sure Ollama is running before using chat. If you see "Ollama is not running" errors,
            start it with <code className="bg-gray-800 px-1 rounded">ollama serve</code>.
          </Warning>
        </div>
      </Section>

      {/* Using API Keys */}
      <Section title="# cloud_providers" icon={KeyIcon} iconColor="text-yellow-400">
        <div className="space-y-4 text-sm text-gray-300">
          <p>
            Instead of running models locally, you can use cloud AI providers.
            This requires an API key and incurs costs per request.
          </p>

          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <h3 className="text-white font-mono mb-2">OpenAI</h3>
              <p className="text-gray-400 text-xs mb-2">GPT-4o, GPT-4, GPT-3.5</p>
              <a
                href="https://platform.openai.com/api-keys"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center text-cyan-400 hover:text-cyan-300 text-xs font-mono"
              >
                Get API Key <ArrowTopRightOnSquareIcon className="h-3 w-3 ml-1" />
              </a>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <h3 className="text-white font-mono mb-2">Anthropic</h3>
              <p className="text-gray-400 text-xs mb-2">Claude Opus 4.5, Sonnet, Haiku</p>
              <a
                href="https://console.anthropic.com/settings/keys"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center text-cyan-400 hover:text-cyan-300 text-xs font-mono"
              >
                Get API Key <ArrowTopRightOnSquareIcon className="h-3 w-3 ml-1" />
              </a>
            </div>
          </div>

          <Tip>
            Cloud providers offer better quality responses but cost money per request.
            Start with Ollama for testing, then consider cloud for production.
          </Tip>
        </div>
      </Section>

      {/* Data Sources */}
      <Section title="# data_sources" icon={DocumentTextIcon} iconColor="text-green-400">
        <div className="space-y-4 text-sm text-gray-300">
          <p>
            Your AI learns from the data sources you provide. The more relevant content you add,
            the better it can answer questions.
          </p>

          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <h3 className="text-white font-mono mb-2">YouTube</h3>
              <p className="text-gray-400 text-xs">
                Add playlists or individual videos. Transcripts are automatically extracted.
                Great for town halls, meetings, or educational content.
              </p>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <h3 className="text-white font-mono mb-2">Websites</h3>
              <p className="text-gray-400 text-xs">
                Add any web page URL. The page content is extracted and indexed.
                Useful for official pages, FAQs, and documentation.
              </p>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <h3 className="text-white font-mono mb-2">PDFs</h3>
              <p className="text-gray-400 text-xs">
                Upload PDF documents or provide URLs to PDF files.
                Perfect for reports, guides, and official documents.
              </p>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <h3 className="text-white font-mono mb-2">RSS Feeds</h3>
              <p className="text-gray-400 text-xs">
                Add RSS feed URLs for automatically updated content.
                Great for news and announcements.
              </p>
            </div>
          </div>

          <Warning>
            Data ingestion takes time. Large YouTube playlists may take several minutes.
            Check the Admin Console to monitor progress.
          </Warning>
        </div>
      </Section>

      {/* How RAG Works */}
      <Section title="# how_it_works" icon={CircleStackIcon} iconColor="text-cyan-400">
        <div className="space-y-4 text-sm text-gray-300">
          <p>
            Neighborhood AI uses RAG (Retrieval-Augmented Generation) to answer questions
            based on your data.
          </p>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-white font-mono mb-3">The RAG Process:</h3>
            <ol className="list-decimal list-inside space-y-3 text-gray-400">
              <li>
                <span className="text-white">Ingestion</span> - Your data sources are processed,
                split into chunks, and converted to embeddings (numerical representations).
              </li>
              <li>
                <span className="text-white">Storage</span> - Embeddings are stored in a vector
                database (Qdrant) for fast similarity search.
              </li>
              <li>
                <span className="text-white">Retrieval</span> - When you ask a question, we find
                the most relevant chunks from your data.
              </li>
              <li>
                <span className="text-white">Generation</span> - The AI uses the retrieved context
                to generate an accurate, grounded answer.
              </li>
            </ol>
          </div>

          <Tip>
            This approach ensures your AI only answers based on your actual data,
            reducing hallucinations and providing accurate, citable responses.
          </Tip>
        </div>
      </Section>

      {/* Troubleshooting */}
      <Section title="# troubleshooting" icon={ExclamationTriangleIcon} iconColor="text-red-400">
        <div className="space-y-4 text-sm text-gray-300">
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-white font-mono mb-2">"Ollama is not running"</h3>
            <p className="text-gray-400 mb-2">
              Make sure Ollama is started. Open a terminal and run:
            </p>
            <pre className="bg-gray-900 p-2 rounded">
              <code className="text-green-400">ollama serve</code>
            </pre>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-white font-mono mb-2">"Model not found"</h3>
            <p className="text-gray-400 mb-2">
              Download the model first. For example:
            </p>
            <pre className="bg-gray-900 p-2 rounded">
              <code className="text-green-400">ollama pull llama3.1:8b</code>
            </pre>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-white font-mono mb-2">"API key invalid"</h3>
            <p className="text-gray-400">
              Check that your API key is correctly entered in Settings.
              Make sure there are no extra spaces and the key hasn't expired.
            </p>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-white font-mono mb-2">"No relevant information found"</h3>
            <p className="text-gray-400">
              Your knowledge base may be empty or the question doesn't match any content.
              Add more data sources or try rephrasing your question.
            </p>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-white font-mono mb-2">Slow responses</h3>
            <p className="text-gray-400">
              Large models require significant RAM/GPU. Try a smaller model like
              <code className="bg-gray-900 px-1 rounded mx-1">llama3.2:3b</code>
              or use a cloud provider.
            </p>
          </div>
        </div>
      </Section>

      {/* Full Guide Link */}
      <div className="bg-gradient-to-r from-purple-500/10 to-cyan-500/10 rounded-lg border border-purple-500/30 p-6 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-mono text-white mb-2">Need more help?</h3>
            <p className="text-gray-400 text-sm">
              Check out our comprehensive guide with installation instructions, troubleshooting, and FAQs.
            </p>
          </div>
          <Link
            to="/guide"
            className="flex-shrink-0 ml-4 px-6 py-3 bg-purple-500 text-white rounded-lg font-mono font-semibold hover:bg-purple-400 transition-colors flex items-center space-x-2"
          >
            <ArrowTopRightOnSquareIcon className="h-5 w-5" />
            <span>Open Full Guide</span>
          </Link>
        </div>
      </div>

      {/* Quick Links */}
      <div className="grid md:grid-cols-3 gap-4">
        <Link
          to={`/console/projects/${projectId}/chat`}
          className="bg-gray-900 p-4 rounded-lg border border-gray-700 hover:border-cyan-500/50 transition-all group"
        >
          <ChatBubbleLeftRightIcon className="h-8 w-8 text-cyan-400 mb-2 group-hover:scale-110 transition-transform" />
          <h3 className="text-white font-mono text-sm">./chat</h3>
          <p className="text-gray-500 text-xs">Test your AI</p>
        </Link>

        <Link
          to={`/console/projects/${projectId}/admin`}
          className="bg-gray-900 p-4 rounded-lg border border-gray-700 hover:border-purple-500/50 transition-all group"
        >
          <ServerIcon className="h-8 w-8 text-purple-400 mb-2 group-hover:scale-110 transition-transform" />
          <h3 className="text-white font-mono text-sm">./admin</h3>
          <p className="text-gray-500 text-xs">Monitor health</p>
        </Link>

        <Link
          to={`/console/projects/${projectId}/settings`}
          className="bg-gray-900 p-4 rounded-lg border border-gray-700 hover:border-green-500/50 transition-all group"
        >
          <CogIcon className="h-8 w-8 text-green-400 mb-2 group-hover:scale-110 transition-transform" />
          <h3 className="text-white font-mono text-sm">./settings</h3>
          <p className="text-gray-500 text-xs">Configure AI</p>
        </Link>
      </div>
    </div>
  );
}

export default HelpPage;
