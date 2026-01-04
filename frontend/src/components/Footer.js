import React from 'react';
import { Link } from 'react-router-dom';
import {
  CodeBracketIcon
} from '@heroicons/react/24/outline';

function Footer({ variant = 'default' }) {
  // variant can be 'default' (dark bg), 'landing' (already has dark footer), or 'light'
  const bgClass = variant === 'light' ? 'bg-gray-100 border-gray-200' : 'bg-gray-900 border-gray-800';
  const textClass = variant === 'light' ? 'text-gray-600' : 'text-gray-400';
  const headingClass = variant === 'light' ? 'text-gray-900' : 'text-white';
  const linkClass = variant === 'light' ? 'hover:text-gray-900' : 'hover:text-white';

  return (
    <footer className={`${bgClass} border-t mt-auto`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Main Footer Content */}
        <div className="grid md:grid-cols-4 gap-8 mb-8">
          {/* Brand Column */}
          <div>
            <div className="flex items-center space-x-2 mb-4">
              <span className="text-green-400 font-mono text-sm">&gt;</span>
              <h3 className={`font-bold ${headingClass} font-mono`}>neighborhood_ai</h3>
            </div>
            <p className={`${textClass} text-sm`}>
              Building AI for communities, not corporations. Privacy-respecting, energy-efficient, locally-run.
            </p>
          </div>

          {/* Resources Column */}
          <div>
            <h4 className={`font-semibold ${headingClass} mb-4 font-mono text-sm`}># resources</h4>
            <ul className={`space-y-2 text-sm ${textClass}`}>
              <li>
                <Link to="/guide" className={`${linkClass} transition-colors`}>Documentation</Link>
              </li>
              <li>
                <a
                  href="https://github.com/amateurmenace/ai-machine"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`${linkClass} transition-colors inline-flex items-center space-x-1`}
                >
                  <CodeBracketIcon className="h-3 w-3" />
                  <span>GitHub</span>
                </a>
              </li>
              <li>
                <Link to="/console" className={`${linkClass} transition-colors`}>Console</Link>
              </li>
            </ul>
          </div>

          {/* Community Column */}
          <div>
            <h4 className={`font-semibold ${headingClass} mb-4 font-mono text-sm`}># community</h4>
            <ul className={`space-y-2 text-sm ${textClass}`}>
              <li>
                <Link to="/about" className={`${linkClass} transition-colors`}>About Us</Link>
              </li>
              <li>
                <a
                  href="https://community.weirdmachine.org"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`${linkClass} transition-colors`}
                >
                  Community Forum
                </a>
              </li>
              <li>
                <a
                  href="mailto:stephen@weirdmachine.org"
                  className={`${linkClass} transition-colors`}
                >
                  Contact
                </a>
              </li>
            </ul>
          </div>

          {/* Family Column */}
          <div>
            <h4 className={`font-semibold ${headingClass} mb-4 font-mono text-sm`}># family</h4>
            <ul className={`space-y-2 text-sm ${textClass}`}>
              <li>
                <a
                  href="https://community.weirdmachine.org"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`${linkClass} transition-colors`}
                >
                  Community AI Project
                </a>
              </li>
              <li>
                <a
                  href="https://brooklineinteractive.org"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`${linkClass} transition-colors`}
                >
                  Brookline Interactive Group
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Attribution and Logos */}
        <div className={`border-t ${variant === 'light' ? 'border-gray-200' : 'border-gray-800'} pt-8`}>
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 mb-6">
            <div className="text-center md:text-left">
              <p className={`${variant === 'light' ? 'text-gray-700' : 'text-gray-300'} text-sm mb-2`}>
                A <a href="https://community.weirdmachine.org" className="text-orange-500 hover:text-orange-400" target="_blank" rel="noopener noreferrer">Community AI Project</a> from{' '}
                <a href="https://brooklineinteractive.org" className="text-blue-500 hover:text-blue-400" target="_blank" rel="noopener noreferrer">Brookline Interactive Group</a>
              </p>
              <p className={`${textClass} text-xs`}>
                Designed and developed by <a href="https://weirdmachine.org" className={`${headingClass} ${linkClass}`} target="_blank" rel="noopener noreferrer">Stephen Walter</a> + AI
              </p>
            </div>

            {/* Logos */}
            <div className="flex items-center gap-6">
              <a href="https://weirdmachine.org" target="_blank" rel="noopener noreferrer" className="block">
                <img
                  src="/weirdmachine.png"
                  alt="Weird Machine"
                  className="h-8 w-auto opacity-70 hover:opacity-100 transition-opacity"
                />
              </a>
              <a href="https://brooklineinteractive.org" target="_blank" rel="noopener noreferrer" className="block">
                <img
                  src="/big-logo.png"
                  alt="Brookline Interactive Group"
                  className="h-12 w-auto opacity-70 hover:opacity-100 transition-opacity"
                />
              </a>
            </div>
          </div>

          {/* License and Copyright */}
          <div className="flex flex-col md:flex-row items-center justify-center gap-4 pt-4 border-t border-gray-800/50">
            <a
              href="https://creativecommons.org/licenses/by-nc-sa/4.0/"
              target="_blank"
              rel="noopener noreferrer"
              className={`flex items-center gap-2 ${textClass} hover:text-gray-300 text-sm`}
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/>
              </svg>
              <span className="font-mono text-xs">CC BY-NC-SA 4.0</span>
            </a>
            <span className={`${textClass} hidden md:inline`}>|</span>
            <p className={`${textClass} text-xs font-mono`}>
              Made for communities by civic technologists
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
