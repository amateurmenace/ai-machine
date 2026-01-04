import React from 'react';
import { Link } from 'react-router-dom';
import {
  HeartIcon,
  BoltIcon,
  UserGroupIcon,
  GlobeAltIcon,
  LightBulbIcon,
  CodeBracketIcon,
  ArrowTopRightOnSquareIcon
} from '@heroicons/react/24/outline';
import Footer from './Footer';

function AboutUs() {
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
              <span className="px-2 py-0.5 bg-orange-500/20 text-orange-400 text-xs font-mono rounded border border-orange-500/30">
                about
              </span>
            </Link>

            <nav className="flex items-center space-x-4">
              <Link to="/guide" className="text-purple-400 hover:text-purple-300 px-3 py-2 rounded font-mono text-sm transition-colors border border-purple-500/30 hover:bg-purple-500/10">
                guide
              </Link>
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

      {/* Hero Section */}
      <div className="bg-gradient-to-br from-orange-500/10 via-rose-500/10 to-purple-500/10 py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-6">
            About <span className="text-orange-400">Neighborhood AI</span>
          </h1>
          <p className="text-xl text-gray-300 max-w-3xl mx-auto">
            Building privacy-respecting, energy-efficient AI assistants for communities.
            A project from the Community AI initiative.
          </p>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 py-16">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">

          {/* Mission Section */}
          <section className="mb-16">
            <h2 className="text-2xl font-bold text-white font-mono mb-6 flex items-center space-x-2">
              <span className="text-green-400">#</span>
              <span>our_mission</span>
            </h2>
            <div className="bg-gray-900 rounded-lg border border-gray-700 p-8">
              <p className="text-gray-300 text-lg leading-relaxed mb-6">
                We believe communities deserve AI tools that respect their privacy, run efficiently
                on local hardware, and are truly owned by the people who use them.
              </p>
              <p className="text-gray-300 text-lg leading-relaxed mb-6">
                Neighborhood AI is an open-source platform for building locally-run AI assistants
                that can answer questions about your town, city, or organization using your own data
                sources - without sending anything to external servers.
              </p>
              <p className="text-gray-300 text-lg leading-relaxed">
                Our goal is to democratize AI by making it accessible to civic organizations,
                local governments, community media centers, libraries, and neighborhood groups
                who want to serve their communities with AI that's <span className="text-green-400">private</span>,
                <span className="text-yellow-400"> efficient</span>, and <span className="text-orange-400">free to operate</span>.
              </p>
            </div>
          </section>

          {/* Values Section */}
          <section className="mb-16">
            <h2 className="text-2xl font-bold text-white font-mono mb-6 flex items-center space-x-2">
              <span className="text-green-400">#</span>
              <span>our_values</span>
            </h2>
            <div className="grid md:grid-cols-2 gap-6">
              <div className="bg-gray-900 rounded-lg border border-gray-700 p-6">
                <HeartIcon className="h-8 w-8 text-rose-400 mb-4" />
                <h3 className="text-lg font-bold text-white mb-2">Community-First</h3>
                <p className="text-gray-400 text-sm">
                  Built for people, not profit. Open source and free to run. We prioritize
                  community needs over commercial interests.
                </p>
              </div>
              <div className="bg-gray-900 rounded-lg border border-gray-700 p-6">
                <BoltIcon className="h-8 w-8 text-yellow-400 mb-4" />
                <h3 className="text-lg font-bold text-white mb-2">Energy Efficient</h3>
                <p className="text-gray-400 text-sm">
                  1000x less energy than cloud models. Run on a Mac Mini using 2 watts per
                  query instead of 100 watts for frontier models.
                </p>
              </div>
              <div className="bg-gray-900 rounded-lg border border-gray-700 p-6">
                <UserGroupIcon className="h-8 w-8 text-green-400 mb-4" />
                <h3 className="text-lg font-bold text-white mb-2">Civic-Minded</h3>
                <p className="text-gray-400 text-sm">
                  Encourages participation in local governance. Cites sources so users can
                  verify information. Designed to support, not replace, human connection.
                </p>
              </div>
              <div className="bg-gray-900 rounded-lg border border-gray-700 p-6">
                <GlobeAltIcon className="h-8 w-8 text-blue-400 mb-4" />
                <h3 className="text-lg font-bold text-white mb-2">Local & Private</h3>
                <p className="text-gray-400 text-sm">
                  Your data stays on your hardware. No surveillance, no data mining.
                  Complete privacy by design.
                </p>
              </div>
            </div>
          </section>

          {/* BIG Section */}
          <section className="mb-16">
            <h2 className="text-2xl font-bold text-white font-mono mb-6 flex items-center space-x-2">
              <span className="text-green-400">#</span>
              <span>brookline_interactive_group</span>
            </h2>
            <div className="bg-gradient-to-br from-blue-500/10 to-purple-500/10 rounded-lg border border-blue-500/30 p-8">
              <div className="flex flex-col md:flex-row items-center gap-8">
                <div className="flex-shrink-0">
                  <img
                    src="/big-logo.png"
                    alt="Brookline Interactive Group"
                    className="h-24 w-auto"
                  />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white mb-3">40+ Years of Community Media</h3>
                  <p className="text-gray-300 mb-4">
                    Neighborhood AI is a project of <strong className="text-blue-400">Brookline Interactive Group (BIG)</strong>,
                    a community media organization that has been serving Brookline, Massachusetts since 1983.
                  </p>
                  <p className="text-gray-300 mb-4">
                    BIG operates three cable access channels, provides media production training, and
                    has been at the forefront of using technology to serve community information needs
                    for over four decades.
                  </p>
                  <a
                    href="https://brooklineinteractive.org"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center space-x-2 text-blue-400 hover:text-blue-300 font-mono text-sm"
                  >
                    <span>brooklineinteractive.org</span>
                    <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                  </a>
                </div>
              </div>
            </div>
          </section>

          {/* Community AI Project */}
          <section className="mb-16">
            <h2 className="text-2xl font-bold text-white font-mono mb-6 flex items-center space-x-2">
              <span className="text-green-400">#</span>
              <span>community_ai_project</span>
            </h2>
            <div className="bg-gradient-to-br from-orange-500/10 to-rose-500/10 rounded-lg border border-orange-500/30 p-8">
              <div className="flex flex-col md:flex-row items-center gap-8">
                <div className="flex-shrink-0">
                  <LightBulbIcon className="h-20 w-20 text-orange-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white mb-3">Exploring AI for Communities</h3>
                  <p className="text-gray-300 mb-4">
                    The <strong className="text-orange-400">Community AI Project</strong> is an initiative
                    exploring how artificial intelligence can be used to serve community information needs
                    in ethical, sustainable ways.
                  </p>
                  <p className="text-gray-300 mb-4">
                    We're developing tools, documentation, and best practices for community organizations
                    who want to harness AI while maintaining privacy, reducing energy consumption, and
                    staying true to civic values.
                  </p>
                  <a
                    href="https://community.weirdmachine.org"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center space-x-2 text-orange-400 hover:text-orange-300 font-mono text-sm"
                  >
                    <span>community.weirdmachine.org</span>
                    <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                  </a>
                </div>
              </div>
            </div>
          </section>

          {/* Team Section */}
          <section className="mb-16">
            <h2 className="text-2xl font-bold text-white font-mono mb-6 flex items-center space-x-2">
              <span className="text-green-400">#</span>
              <span>team</span>
            </h2>
            <div className="bg-gray-900 rounded-lg border border-gray-700 p-8">
              <div className="flex flex-col md:flex-row items-center gap-8">
                <div className="flex-shrink-0">
                  <img
                    src="/weirdmachine.png"
                    alt="Weird Machine"
                    className="h-16 w-auto"
                  />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white mb-2">Stephen Walter</h3>
                  <p className="text-gray-400 mb-4">Designer & Developer</p>
                  <p className="text-gray-300 mb-4">
                    Neighborhood AI is designed and developed by Stephen Walter in collaboration
                    with AI assistants. Stephen is a technologist focused on building tools that
                    serve community needs.
                  </p>
                  <div className="flex items-center gap-4">
                    <a
                      href="https://weirdmachine.org"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center space-x-2 text-gray-400 hover:text-white font-mono text-sm"
                    >
                      <span>weirdmachine.org</span>
                      <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                    </a>
                    <a
                      href="mailto:stephen@weirdmachine.org"
                      className="inline-flex items-center space-x-2 text-gray-400 hover:text-white font-mono text-sm"
                    >
                      <span>stephen@weirdmachine.org</span>
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Open Source Section */}
          <section className="mb-16">
            <h2 className="text-2xl font-bold text-white font-mono mb-6 flex items-center space-x-2">
              <span className="text-green-400">#</span>
              <span>open_source</span>
            </h2>
            <div className="bg-gray-900 rounded-lg border border-gray-700 p-8">
              <div className="flex items-start space-x-4">
                <CodeBracketIcon className="h-8 w-8 text-purple-400 flex-shrink-0" />
                <div>
                  <h3 className="text-lg font-bold text-white mb-3">Creative Commons BY-NC-SA 4.0</h3>
                  <p className="text-gray-300 mb-4">
                    Neighborhood AI is open source software released under the
                    <a
                      href="https://creativecommons.org/licenses/by-nc-sa/4.0/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-purple-400 hover:text-purple-300 mx-1"
                    >
                      Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License
                    </a>.
                  </p>
                  <p className="text-gray-300 mb-4">
                    You're free to use, adapt, and share this work for non-commercial purposes,
                    as long as you give appropriate credit and distribute any derivatives under the same license.
                  </p>
                  <p className="text-gray-300 mb-4">
                    We welcome contributions from the community. Whether it's bug fixes,
                    new features, documentation improvements, or just ideas - we'd love to hear from you.
                  </p>
                  <a
                    href="https://github.com/amateurmenace/ai-machine"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center space-x-2 bg-purple-500/20 text-purple-400 px-4 py-2 rounded-lg border border-purple-500/30 hover:bg-purple-500/30 transition-colors font-mono text-sm"
                  >
                    <CodeBracketIcon className="h-4 w-4" />
                    <span>View on GitHub</span>
                    <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                  </a>
                </div>
              </div>
            </div>
          </section>

          {/* CTA */}
          <section className="text-center">
            <div className="bg-gradient-to-r from-green-500/20 to-emerald-500/20 rounded-lg border border-green-500/30 p-8">
              <h2 className="text-2xl font-bold text-white mb-4">Ready to Build Your Community AI?</h2>
              <p className="text-gray-300 mb-6">
                Get started in minutes with our step-by-step guide and open source tools.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link
                  to="/console"
                  className="inline-flex items-center justify-center space-x-2 bg-green-500 text-gray-900 px-6 py-3 rounded-lg font-mono font-semibold hover:bg-green-400 transition-colors"
                >
                  <span>Open Console</span>
                </Link>
                <Link
                  to="/guide"
                  className="inline-flex items-center justify-center space-x-2 bg-gray-700 text-white px-6 py-3 rounded-lg font-mono font-semibold hover:bg-gray-600 transition-colors"
                >
                  <span>Read the Guide</span>
                </Link>
              </div>
            </div>
          </section>

        </div>
      </main>

      <Footer />
    </div>
  );
}

export default AboutUs;
