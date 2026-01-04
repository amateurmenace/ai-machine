import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeftIcon,
  BookOpenIcon,
  CpuChipIcon,
  DocumentTextIcon,
  CloudIcon,
  WrenchScrewdriverIcon,
  QuestionMarkCircleIcon,
  LightBulbIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowTopRightOnSquareIcon,
  ComputerDesktopIcon,
  GlobeAltIcon,
  CommandLineIcon,
  ChevronRightIcon,
  PlayIcon,
  RocketLaunchIcon
} from '@heroicons/react/24/outline';
import Footer from './Footer';

function Guide() {
  const [activeSection, setActiveSection] = useState('overview');

  const sections = [
    { id: 'overview', title: 'Overview', icon: BookOpenIcon },
    { id: 'requirements', title: 'System Requirements', icon: ComputerDesktopIcon },
    { id: 'installation', title: 'Installation', icon: CommandLineIcon },
    { id: 'ollama', title: 'Setting Up Ollama', icon: CpuChipIcon },
    { id: 'starting', title: 'Starting the App', icon: PlayIcon },
    { id: 'first-project', title: 'Your First Project', icon: RocketLaunchIcon },
    { id: 'data-sources', title: 'Data Sources', icon: DocumentTextIcon },
    { id: 'cloud-providers', title: 'Cloud Providers', icon: CloudIcon },
    { id: 'deployment', title: 'Deployment', icon: GlobeAltIcon },
    { id: 'troubleshooting', title: 'Troubleshooting', icon: WrenchScrewdriverIcon },
    { id: 'faq', title: 'FAQ', icon: QuestionMarkCircleIcon },
  ];

  const Tip = ({ children }) => (
    <div className="flex items-start space-x-2 p-4 bg-cyan-500/10 rounded-lg border border-cyan-500/30 text-sm my-4">
      <LightBulbIcon className="h-5 w-5 text-cyan-400 flex-shrink-0 mt-0.5" />
      <p className="text-cyan-200">{children}</p>
    </div>
  );

  const Warning = ({ children }) => (
    <div className="flex items-start space-x-2 p-4 bg-yellow-500/10 rounded-lg border border-yellow-500/30 text-sm my-4">
      <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400 flex-shrink-0 mt-0.5" />
      <p className="text-yellow-200">{children}</p>
    </div>
  );

  const CodeBlock = ({ children, title }) => (
    <div className="my-4">
      {title && (
        <div className="bg-gray-800 px-4 py-2 rounded-t border-b border-gray-700">
          <span className="text-xs text-gray-400 font-mono">{title}</span>
        </div>
      )}
      <pre className={`bg-gray-900 p-4 ${title ? 'rounded-b' : 'rounded'} overflow-x-auto border border-gray-700`}>
        <code className="text-green-400 font-mono text-sm">{children}</code>
      </pre>
    </div>
  );

  const renderSection = () => {
    switch (activeSection) {
      case 'overview':
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white font-mono"># Overview</h2>
            <p className="text-gray-300">
              Neighborhood AI is an open-source platform for creating local AI assistants tailored to
              your community, municipality, or organization. It uses RAG (Retrieval-Augmented Generation)
              to ground AI responses in your actual data sources.
            </p>

            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h3 className="text-white font-mono mb-4">Key Features:</h3>
              <ul className="space-y-3 text-gray-300">
                <li className="flex items-start space-x-2">
                  <CheckCircleIcon className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                  <span><strong>Local AI</strong> - Run models on your own hardware with Ollama</span>
                </li>
                <li className="flex items-start space-x-2">
                  <CheckCircleIcon className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                  <span><strong>Multiple Data Sources</strong> - YouTube, websites, PDFs, RSS feeds</span>
                </li>
                <li className="flex items-start space-x-2">
                  <CheckCircleIcon className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                  <span><strong>Privacy First</strong> - Your data stays on your servers</span>
                </li>
                <li className="flex items-start space-x-2">
                  <CheckCircleIcon className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                  <span><strong>Customizable</strong> - Tailor the AI's personality and behavior</span>
                </li>
                <li className="flex items-start space-x-2">
                  <CheckCircleIcon className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                  <span><strong>Citation Support</strong> - Answers include source references</span>
                </li>
              </ul>
            </div>

            <h3 className="text-xl font-bold text-white font-mono mt-8">Why Local AI?</h3>
            <p className="text-gray-300">
              Running AI locally provides several advantages:
            </p>
            <ul className="list-disc list-inside space-y-2 text-gray-300 pl-4">
              <li><strong>Privacy</strong> - Sensitive community data never leaves your network</li>
              <li><strong>Cost</strong> - No per-request API fees after initial setup</li>
              <li><strong>Control</strong> - Full control over updates and model behavior</li>
              <li><strong>Latency</strong> - Faster responses for local users</li>
            </ul>

            <Tip>
              While local AI is recommended for privacy, you can also use cloud providers like
              OpenAI or Anthropic for better response quality when needed.
            </Tip>
          </div>
        );

      case 'requirements':
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white font-mono"># System Requirements</h2>

            <div className="grid md:grid-cols-2 gap-6">
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-4">Minimum Requirements</h3>
                <ul className="space-y-2 text-gray-300 text-sm">
                  <li>CPU: 4+ cores (Intel/AMD x64 or Apple Silicon)</li>
                  <li>RAM: 8GB (for smaller models)</li>
                  <li>Storage: 20GB free space</li>
                  <li>OS: macOS 12+, Windows 10/11, Linux</li>
                  <li>Python: 3.9+</li>
                  <li>Node.js: 16+</li>
                </ul>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-4">Recommended Requirements</h3>
                <ul className="space-y-2 text-gray-300 text-sm">
                  <li>CPU: 8+ cores</li>
                  <li>RAM: 16GB+ (32GB for larger models)</li>
                  <li>GPU: NVIDIA RTX 3060+ with 8GB VRAM (optional)</li>
                  <li>Storage: 50GB+ SSD</li>
                </ul>
              </div>
            </div>

            <h3 className="text-xl font-bold text-white font-mono mt-8">Model Size Guide</h3>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="text-left py-2 text-gray-400 font-mono">Model</th>
                    <th className="text-left py-2 text-gray-400 font-mono">RAM Needed</th>
                    <th className="text-left py-2 text-gray-400 font-mono">Quality</th>
                    <th className="text-left py-2 text-gray-400 font-mono">Speed</th>
                  </tr>
                </thead>
                <tbody className="text-gray-300">
                  <tr className="border-b border-gray-700">
                    <td className="py-2 font-mono text-cyan-400">llama3.2:3b</td>
                    <td className="py-2">4GB</td>
                    <td className="py-2">Good</td>
                    <td className="py-2">Fast</td>
                  </tr>
                  <tr className="border-b border-gray-700">
                    <td className="py-2 font-mono text-green-400">llama3.1:8b</td>
                    <td className="py-2">8GB</td>
                    <td className="py-2">Very Good</td>
                    <td className="py-2">Moderate</td>
                  </tr>
                  <tr className="border-b border-gray-700">
                    <td className="py-2 font-mono text-yellow-400">mistral:7b</td>
                    <td className="py-2">8GB</td>
                    <td className="py-2">Very Good</td>
                    <td className="py-2">Fast</td>
                  </tr>
                  <tr>
                    <td className="py-2 font-mono text-purple-400">llama3.1:70b</td>
                    <td className="py-2">48GB+</td>
                    <td className="py-2">Excellent</td>
                    <td className="py-2">Slow (GPU recommended)</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <Tip>
              Apple Silicon Macs (M1/M2/M3) are excellent for local AI - they can run 8B models
              smoothly using unified memory, even without a dedicated GPU.
            </Tip>
          </div>
        );

      case 'installation':
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white font-mono"># Installation</h2>

            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6">
              <h3 className="text-white font-mono mb-4">Prerequisites</h3>
              <ul className="space-y-2 text-gray-300">
                <li className="flex items-center space-x-2">
                  <CheckCircleIcon className="h-4 w-4 text-green-400" />
                  <span>Python 3.9 or higher</span>
                </li>
                <li className="flex items-center space-x-2">
                  <CheckCircleIcon className="h-4 w-4 text-green-400" />
                  <span>Node.js 16 or higher</span>
                </li>
                <li className="flex items-center space-x-2">
                  <CheckCircleIcon className="h-4 w-4 text-green-400" />
                  <span>Git</span>
                </li>
              </ul>
            </div>

            <h3 className="text-xl font-bold text-white font-mono">Step 1: Clone the Repository</h3>
            <CodeBlock>
{`git clone https://github.com/your-org/neighborhood-ai.git
cd neighborhood-ai`}
            </CodeBlock>

            <h3 className="text-xl font-bold text-white font-mono">Step 2: Install Backend Dependencies</h3>
            <CodeBlock title="Mac/Linux">
{`python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt`}
            </CodeBlock>
            <CodeBlock title="Windows">
{`python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt`}
            </CodeBlock>

            <h3 className="text-xl font-bold text-white font-mono">Step 3: Install Frontend Dependencies</h3>
            <CodeBlock>
{`cd frontend
npm install
cd ..`}
            </CodeBlock>

            <h3 className="text-xl font-bold text-white font-mono">Step 4: Configure Environment</h3>
            <CodeBlock>
{`cp .env.example .env
# Edit .env with your settings if needed`}
            </CodeBlock>

            <Tip>
              Most settings can be configured through the web UI - you only need to edit .env
              for advanced options like changing ports.
            </Tip>
          </div>
        );

      case 'ollama':
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white font-mono"># Setting Up Ollama</h2>
            <p className="text-gray-300">
              Ollama is a tool for running large language models locally. It handles downloading,
              caching, and serving AI models on your computer.
            </p>

            <h3 className="text-xl font-bold text-white font-mono">Step 1: Download Ollama</h3>
            <p className="text-gray-300 mb-4">Visit the official download page:</p>
            <a
              href="https://ollama.ai/download"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-4 py-2 bg-cyan-500/20 text-cyan-400 rounded border border-cyan-500/50 hover:bg-cyan-500/30 font-mono"
            >
              https://ollama.ai/download <ArrowTopRightOnSquareIcon className="h-4 w-4 ml-2" />
            </a>

            <h3 className="text-xl font-bold text-white font-mono mt-8">Step 2: Start Ollama Server</h3>
            <p className="text-gray-300 mb-2">After installation, start the Ollama server:</p>
            <CodeBlock title="Mac/Linux/Windows">
{`ollama serve`}
            </CodeBlock>
            <p className="text-gray-500 text-sm">Keep this terminal window open. Ollama runs in the background.</p>

            <h3 className="text-xl font-bold text-white font-mono mt-8">Step 3: Download a Model</h3>
            <p className="text-gray-300 mb-2">Open a new terminal and download the recommended model:</p>
            <CodeBlock>
{`ollama pull llama3.1:8b`}
            </CodeBlock>
            <p className="text-gray-500 text-sm">This downloads approximately 4.5GB. Wait for completion.</p>

            <h3 className="text-xl font-bold text-white font-mono mt-8">Step 4: Test the Model</h3>
            <p className="text-gray-300 mb-2">Verify the model works:</p>
            <CodeBlock>
{`ollama run llama3.1:8b`}
            </CodeBlock>
            <p className="text-gray-500 text-sm">Type a message to chat. Use /bye to exit.</p>

            <h3 className="text-xl font-bold text-white font-mono mt-8">Available Models</h3>
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="space-y-3">
                <div className="flex justify-between items-center py-2 border-b border-gray-700">
                  <div>
                    <span className="text-white font-mono">llama3.1:8b</span>
                    <span className="ml-2 px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">Recommended</span>
                  </div>
                  <span className="text-gray-500 text-sm">8GB RAM | Best balance</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-gray-700">
                  <span className="text-white font-mono">llama3.2:3b</span>
                  <span className="text-gray-500 text-sm">4GB RAM | Lightweight</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-gray-700">
                  <span className="text-white font-mono">mistral:7b</span>
                  <span className="text-gray-500 text-sm">8GB RAM | Fast inference</span>
                </div>
                <div className="flex justify-between items-center py-2">
                  <span className="text-white font-mono">llama3.1:70b</span>
                  <span className="text-gray-500 text-sm">48GB+ RAM | GPU recommended</span>
                </div>
              </div>
            </div>

            <Warning>
              On first run, models are loaded into memory which can take 30-60 seconds.
              Subsequent queries are much faster.
            </Warning>
          </div>
        );

      case 'starting':
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white font-mono"># Starting the Application</h2>

            <p className="text-gray-300 mb-4">
              Neighborhood AI consists of two parts: the Python backend (API server) and the
              React frontend (web interface). Both need to be running.
            </p>

            <h3 className="text-xl font-bold text-white font-mono">Terminal 1: Start the Backend</h3>
            <CodeBlock title="Mac/Linux">
{`cd neighborhood-ai
source venv/bin/activate
python app.py`}
            </CodeBlock>
            <CodeBlock title="Windows">
{`cd neighborhood-ai
venv\\Scripts\\activate
python app.py`}
            </CodeBlock>
            <p className="text-gray-500 text-sm mb-6">The API server will start on http://localhost:8000</p>

            <h3 className="text-xl font-bold text-white font-mono">Terminal 2: Start the Frontend</h3>
            <CodeBlock>
{`cd neighborhood-ai/frontend
npm start`}
            </CodeBlock>
            <p className="text-gray-500 text-sm mb-6">The web interface will open at http://localhost:3000</p>

            <h3 className="text-xl font-bold text-white font-mono">Terminal 3: Ollama (if not already running)</h3>
            <CodeBlock>
{`ollama serve`}
            </CodeBlock>

            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mt-6">
              <h3 className="text-white font-mono mb-4">Quick Start Summary</h3>
              <p className="text-gray-300 mb-4">You need 3 terminal windows running:</p>
              <ol className="space-y-2 text-gray-300">
                <li className="flex items-center space-x-2">
                  <span className="w-6 h-6 bg-green-500/20 text-green-400 rounded flex items-center justify-center text-sm">1</span>
                  <span>Ollama: <code className="bg-gray-900 px-2 rounded">ollama serve</code></span>
                </li>
                <li className="flex items-center space-x-2">
                  <span className="w-6 h-6 bg-cyan-500/20 text-cyan-400 rounded flex items-center justify-center text-sm">2</span>
                  <span>Backend: <code className="bg-gray-900 px-2 rounded">python app.py</code></span>
                </li>
                <li className="flex items-center space-x-2">
                  <span className="w-6 h-6 bg-purple-500/20 text-purple-400 rounded flex items-center justify-center text-sm">3</span>
                  <span>Frontend: <code className="bg-gray-900 px-2 rounded">npm start</code> (in /frontend)</span>
                </li>
              </ol>
            </div>

            <Tip>
              You can use a terminal multiplexer like tmux or run all services in Docker for
              easier management. See the Deployment section.
            </Tip>
          </div>
        );

      case 'first-project':
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white font-mono"># Creating Your First Project</h2>

            <p className="text-gray-300 mb-4">
              Once the application is running, you can create your first AI assistant project.
            </p>

            <div className="space-y-6">
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-3 flex items-center">
                  <span className="w-6 h-6 bg-cyan-500/20 text-cyan-400 rounded flex items-center justify-center text-sm mr-3">1</span>
                  Open the Console
                </h3>
                <p className="text-gray-300 text-sm">
                  Navigate to <code className="bg-gray-900 px-2 rounded">http://localhost:3000</code> and click
                  "Launch Console" or go directly to <code className="bg-gray-900 px-2 rounded">/console</code>.
                </p>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-3 flex items-center">
                  <span className="w-6 h-6 bg-cyan-500/20 text-cyan-400 rounded flex items-center justify-center text-sm mr-3">2</span>
                  Create New Project
                </h3>
                <p className="text-gray-300 text-sm">
                  Click "+ new" and follow the setup wizard. Enter your community name
                  (e.g., "Brookline, MA") and choose an AI provider (Ollama recommended).
                </p>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-3 flex items-center">
                  <span className="w-6 h-6 bg-cyan-500/20 text-cyan-400 rounded flex items-center justify-center text-sm mr-3">3</span>
                  Add Data Sources
                </h3>
                <p className="text-gray-300 text-sm mb-3">
                  Go to ./data and add your first data sources. Good starting points:
                </p>
                <ul className="list-disc list-inside text-gray-400 text-sm space-y-1">
                  <li>Official website (e.g., yourtown.gov)</li>
                  <li>YouTube playlist of town meetings</li>
                  <li>PDF documents (budgets, reports)</li>
                </ul>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-3 flex items-center">
                  <span className="w-6 h-6 bg-cyan-500/20 text-cyan-400 rounded flex items-center justify-center text-sm mr-3">4</span>
                  Ingest the Data
                </h3>
                <p className="text-gray-300 text-sm">
                  Click the sync button next to each source to ingest the content. This
                  processes the data and adds it to the knowledge base.
                </p>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-3 flex items-center">
                  <span className="w-6 h-6 bg-cyan-500/20 text-cyan-400 rounded flex items-center justify-center text-sm mr-3">5</span>
                  Start Chatting
                </h3>
                <p className="text-gray-300 text-sm">
                  Go to ./chat and ask questions about your community. The AI will answer
                  based on the ingested data and cite its sources.
                </p>
              </div>
            </div>

            <Tip>
              Start with 5-10 high-quality sources rather than dozens of low-quality ones.
              You can always add more later.
            </Tip>
          </div>
        );

      case 'data-sources':
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white font-mono"># Data Sources</h2>

            <p className="text-gray-300 mb-6">
              Neighborhood AI supports multiple data source types. Each type has its own
              collection method and best practices.
            </p>

            <div className="space-y-6">
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <div className="flex items-center space-x-3 mb-4">
                  <PlayIcon className="h-6 w-6 text-red-400" />
                  <h3 className="text-white font-mono">YouTube Videos & Playlists</h3>
                </div>
                <p className="text-gray-300 text-sm mb-4">
                  Transcripts are automatically extracted using YouTube's caption API. Works best
                  with videos that have auto-generated or manual captions enabled.
                </p>
                <div className="bg-gray-900 rounded p-3 text-xs text-gray-400">
                  <strong>How it works:</strong> We use the youtube_transcript_api to fetch captions
                  directly from YouTube. The text is then chunked into segments for retrieval.
                </div>
                <Warning>
                  Some videos may not have captions available. If transcript download fails,
                  the video likely has captions disabled.
                </Warning>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <div className="flex items-center space-x-3 mb-4">
                  <GlobeAltIcon className="h-6 w-6 text-blue-400" />
                  <h3 className="text-white font-mono">Websites</h3>
                </div>
                <p className="text-gray-300 text-sm mb-4">
                  Web pages are crawled and their text content is extracted. We follow links
                  on the page to collect up to 50 related pages.
                </p>
                <div className="bg-gray-900 rounded p-3 text-xs text-gray-400">
                  <strong>How it works:</strong> We use BeautifulSoup to parse HTML and extract
                  meaningful text, filtering out navigation, ads, and boilerplate.
                </div>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <div className="flex items-center space-x-3 mb-4">
                  <DocumentTextIcon className="h-6 w-6 text-green-400" />
                  <h3 className="text-white font-mono">PDF Documents</h3>
                </div>
                <p className="text-gray-300 text-sm mb-4">
                  PDF files can be uploaded directly or linked by URL. Text and metadata are
                  extracted from all pages.
                </p>
                <div className="bg-gray-900 rounded p-3 text-xs text-gray-400">
                  <strong>How it works:</strong> We use PyPDF to extract text from each page.
                  Scanned PDFs may require OCR (not currently supported).
                </div>
              </div>
            </div>

            <h3 className="text-xl font-bold text-white font-mono mt-8">Best Practices</h3>
            <ul className="space-y-3 text-gray-300">
              <li className="flex items-start space-x-2">
                <CheckCircleIcon className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                <span>Prioritize official, authoritative sources over user-generated content</span>
              </li>
              <li className="flex items-start space-x-2">
                <CheckCircleIcon className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                <span>Include a variety of content types for comprehensive coverage</span>
              </li>
              <li className="flex items-start space-x-2">
                <CheckCircleIcon className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                <span>Re-sync sources periodically to capture new content</span>
              </li>
              <li className="flex items-start space-x-2">
                <CheckCircleIcon className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                <span>Use descriptive names for sources to help with citation clarity</span>
              </li>
            </ul>
          </div>
        );

      case 'cloud-providers':
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white font-mono"># Cloud AI Providers</h2>

            <p className="text-gray-300 mb-6">
              While Ollama provides free local inference, you can also use cloud AI providers
              for higher quality responses or when local hardware is insufficient.
            </p>

            <h3 className="text-xl font-bold text-white font-mono">Why Use Cloud Providers?</h3>
            <ul className="space-y-2 text-gray-300 mb-6">
              <li>- Better response quality (especially for complex queries)</li>
              <li>- No local compute requirements</li>
              <li>- Access to latest models</li>
              <li>- Required for personality generation feature</li>
            </ul>

            <div className="grid md:grid-cols-2 gap-6">
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-4">OpenAI</h3>
                <p className="text-gray-400 text-sm mb-4">
                  GPT-4o, GPT-4, GPT-3.5 Turbo
                </p>
                <a
                  href="https://platform.openai.com/api-keys"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-cyan-400 hover:text-cyan-300 text-sm"
                >
                  Get API Key <ArrowTopRightOnSquareIcon className="h-4 w-4 ml-1" />
                </a>
                <div className="mt-4 bg-gray-900 rounded p-3 text-xs text-gray-400">
                  Cost: ~$0.01-0.03 per query depending on model
                </div>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-4">Anthropic</h3>
                <p className="text-gray-400 text-sm mb-4">
                  Claude Opus 4.5, Sonnet 4, Haiku 4
                </p>
                <a
                  href="https://console.anthropic.com/settings/keys"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-cyan-400 hover:text-cyan-300 text-sm"
                >
                  Get API Key <ArrowTopRightOnSquareIcon className="h-4 w-4 ml-1" />
                </a>
                <div className="mt-4 bg-gray-900 rounded p-3 text-xs text-gray-400">
                  Cost: ~$0.01-0.05 per query depending on model
                </div>
              </div>
            </div>

            <Warning>
              API keys are sensitive credentials. Never commit them to version control.
              Store them securely in environment variables or the app's settings.
            </Warning>

            <Tip>
              Use Ollama for development and testing, then switch to cloud providers for
              production if response quality is critical.
            </Tip>
          </div>
        );

      case 'deployment':
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white font-mono"># Deployment</h2>

            <p className="text-gray-300 mb-6">
              Deploy Neighborhood AI for public access using Docker, traditional hosting, or
              cloud platforms.
            </p>

            <h3 className="text-xl font-bold text-white font-mono">Docker Deployment (Recommended)</h3>
            <CodeBlock>
{`# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down`}
            </CodeBlock>

            <h3 className="text-xl font-bold text-white font-mono mt-8">Creating Public Access</h3>
            <p className="text-gray-300 mb-4">
              To make your AI accessible to the public, you'll need:
            </p>
            <ol className="space-y-3 text-gray-300 list-decimal list-inside">
              <li>A domain name pointing to your server</li>
              <li>HTTPS certificate (use Let's Encrypt for free)</li>
              <li>Reverse proxy (nginx recommended)</li>
            </ol>

            <CodeBlock title="Example nginx config">
{`server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }

    location /api {
        proxy_pass http://localhost:8000;
    }
}`}
            </CodeBlock>

            <h3 className="text-xl font-bold text-white font-mono mt-8">Cloud Hosting Options</h3>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <h4 className="text-white font-mono mb-2">DigitalOcean</h4>
                <p className="text-gray-400 text-xs">Starting at $12/mo with 2GB RAM droplet</p>
              </div>
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <h4 className="text-white font-mono mb-2">Linode</h4>
                <p className="text-gray-400 text-xs">Starting at $12/mo with dedicated compute</p>
              </div>
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <h4 className="text-white font-mono mb-2">AWS EC2</h4>
                <p className="text-gray-400 text-xs">t3.medium or larger recommended</p>
              </div>
            </div>

            <Tip>
              For production deployments, use cloud AI providers (OpenAI/Anthropic) instead of
              Ollama to avoid the high compute costs of local inference.
            </Tip>
          </div>
        );

      case 'troubleshooting':
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white font-mono"># Troubleshooting</h2>

            <div className="space-y-6">
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-2">"Ollama is not running"</h3>
                <p className="text-gray-400 mb-3">
                  The Ollama server is not accessible. Solutions:
                </p>
                <ol className="list-decimal list-inside text-gray-300 text-sm space-y-1">
                  <li>Open a terminal and run <code className="bg-gray-900 px-1 rounded">ollama serve</code></li>
                  <li>Keep the terminal open while using the app</li>
                  <li>Check if port 11434 is available</li>
                </ol>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-2">"Model not found"</h3>
                <p className="text-gray-400 mb-3">
                  The specified model isn't downloaded. Solutions:
                </p>
                <ol className="list-decimal list-inside text-gray-300 text-sm space-y-1">
                  <li>Run <code className="bg-gray-900 px-1 rounded">ollama pull llama3.1:8b</code></li>
                  <li>Wait for the download to complete (may take several minutes)</li>
                  <li>Verify with <code className="bg-gray-900 px-1 rounded">ollama list</code></li>
                </ol>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-2">"No transcript available"</h3>
                <p className="text-gray-400 mb-3">
                  YouTube video doesn't have captions. Solutions:
                </p>
                <ol className="list-decimal list-inside text-gray-300 text-sm space-y-1">
                  <li>Check if the video has captions enabled on YouTube</li>
                  <li>Try a different video from the same channel</li>
                  <li>Some live streams and newly uploaded videos may not have captions yet</li>
                </ol>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-2">"API key invalid"</h3>
                <p className="text-gray-400 mb-3">
                  Cloud provider API key is incorrect. Solutions:
                </p>
                <ol className="list-decimal list-inside text-gray-300 text-sm space-y-1">
                  <li>Copy the API key again, ensuring no extra spaces</li>
                  <li>Check if the key has expired or been revoked</li>
                  <li>Verify you have sufficient credits/quota</li>
                </ol>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-2">Slow responses</h3>
                <p className="text-gray-400 mb-3">
                  Model inference is taking too long. Solutions:
                </p>
                <ol className="list-decimal list-inside text-gray-300 text-sm space-y-1">
                  <li>Use a smaller model (e.g., llama3.2:3b instead of llama3.1:8b)</li>
                  <li>Ensure sufficient RAM is available</li>
                  <li>Close other memory-intensive applications</li>
                  <li>Consider using a cloud provider for faster inference</li>
                </ol>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-2">Vector store errors</h3>
                <p className="text-gray-400 mb-3">
                  Issues with the Qdrant database. Solutions:
                </p>
                <ol className="list-decimal list-inside text-gray-300 text-sm space-y-1">
                  <li>Restart the backend server</li>
                  <li>Delete ./data/[project_id]/qdrant and re-ingest sources</li>
                  <li>Check disk space (at least 1GB free recommended)</li>
                </ol>
              </div>
            </div>
          </div>
        );

      case 'faq':
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white font-mono"># Frequently Asked Questions</h2>

            <div className="space-y-6">
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-2">Why use Ollama instead of just calling OpenAI?</h3>
                <p className="text-gray-300 text-sm">
                  Ollama keeps all data local - nothing is sent to external servers. This is
                  crucial for government data, HIPAA compliance, or any sensitive information.
                  It's also free after initial setup.
                </p>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-2">Why do we use cloud AI for personality generation?</h3>
                <p className="text-gray-300 text-sm">
                  The "Generate Personality" feature creates a custom system prompt based on your
                  community. This one-time task benefits from more capable cloud models. Your actual
                  chat queries still use your chosen provider (local or cloud).
                </p>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-2">How much does this cost to run?</h3>
                <p className="text-gray-300 text-sm">
                  With Ollama: Just your electricity (~$1-2/month). With cloud providers:
                  $0.01-0.05 per query depending on model. A typical small town might spend
                  $10-50/month on cloud API if not using local inference.
                </p>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-2">Can I use this for my business instead of a municipality?</h3>
                <p className="text-gray-300 text-sm">
                  Yes, Neighborhood AI works for any organization that wants a custom AI assistant
                  grounded in their own data - businesses, nonprofits, schools, etc.
                </p>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-2">How accurate are the responses?</h3>
                <p className="text-gray-300 text-sm">
                  Responses are grounded in your provided data sources, which significantly reduces
                  hallucination compared to generic AI. However, always verify critical information -
                  this is a tool to assist, not replace, official sources.
                </p>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-white font-mono mb-2">Can multiple people use it at once?</h3>
                <p className="text-gray-300 text-sm">
                  Yes, the system supports concurrent users. With Ollama, requests are queued
                  (one at a time per model). With cloud providers, parallel requests are supported.
                  For high traffic, consider cloud deployment.
                </p>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Header */}
      <header className="bg-gray-900 border-b border-green-500/30 shadow-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <Link to="/" className="flex items-center space-x-3 group">
              <span className="text-green-400 font-mono text-lg animate-pulse">&gt;</span>
              <h1 className="text-xl md:text-2xl font-bold text-white font-mono tracking-tight">
                neighborhood<span className="text-green-400">_</span>ai
              </h1>
              <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs font-mono rounded border border-purple-500/30">
                guide
              </span>
            </Link>

            <nav className="flex items-center space-x-4">
              <Link to="/console" className="text-gray-400 hover:text-green-400 px-3 py-2 rounded font-mono text-sm transition-colors">
                console
              </Link>
              <Link to="/" className="text-gray-500 hover:text-gray-300 px-3 py-2 rounded font-mono text-sm transition-colors">
                home
              </Link>
            </nav>
          </div>
        </div>
      </header>

      <div className="flex max-w-7xl mx-auto flex-1">
        {/* Sidebar Navigation */}
        <aside className="w-64 bg-gray-900 border-r border-gray-800 p-4 sticky top-16 hidden lg:block self-start">
          <nav className="space-y-1">
            {sections.map((section) => {
              const Icon = section.icon;
              return (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-mono transition-colors ${
                    activeSection === section.id
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{section.title}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        {/* Mobile Navigation */}
        <div className="lg:hidden w-full bg-gray-900 border-b border-gray-800 p-4 overflow-x-auto">
          <div className="flex space-x-2">
            {sections.map((section) => (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={`px-3 py-1 rounded-lg text-xs font-mono whitespace-nowrap transition-colors ${
                  activeSection === section.id
                    ? 'bg-green-500/20 text-green-400'
                    : 'text-gray-400 hover:bg-gray-800'
                }`}
              >
                {section.title}
              </button>
            ))}
          </div>
        </div>

        {/* Main Content */}
        <main className="flex-1 p-6 lg:p-8 max-w-4xl">
          {renderSection()}

          {/* Navigation */}
          <div className="flex justify-between mt-12 pt-6 border-t border-gray-800">
            <button
              onClick={() => {
                const currentIndex = sections.findIndex(s => s.id === activeSection);
                if (currentIndex > 0) {
                  setActiveSection(sections[currentIndex - 1].id);
                }
              }}
              disabled={sections.findIndex(s => s.id === activeSection) === 0}
              className="flex items-center space-x-2 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed font-mono text-sm"
            >
              <ArrowLeftIcon className="h-4 w-4" />
              <span>Previous</span>
            </button>
            <button
              onClick={() => {
                const currentIndex = sections.findIndex(s => s.id === activeSection);
                if (currentIndex < sections.length - 1) {
                  setActiveSection(sections[currentIndex + 1].id);
                }
              }}
              disabled={sections.findIndex(s => s.id === activeSection) === sections.length - 1}
              className="flex items-center space-x-2 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed font-mono text-sm"
            >
              <span>Next</span>
              <ChevronRightIcon className="h-4 w-4" />
            </button>
          </div>
        </main>
      </div>

      <Footer />
    </div>
  );
}

export default Guide;
