import React, { useState } from 'react';
import api from '../api';
import {
  CloudArrowUpIcon, ExclamationTriangleIcon, ServerIcon, ArrowPathIcon,
} from '@heroicons/react/24/outline';

/**
 * Offer a frontier model as a second opinion, and say where the question goes.
 *
 * Deliberately not automatic routing. Sending the hard questions to a frontier
 * provider behind the resident's back would make this a proxy with extra steps,
 * which is the property the project exists to avoid. So it is a button, and the
 * button names the company that receives the question.
 *
 * The second opinion reads the same retrieved passages and is bound by the same
 * constitution. Where the two answers differ, the difference is the model, not
 * the evidence, and the comparison says so rather than declaring a winner.
 */
function SecondOpinion({ projectId, question, localAnswer, options = [] }) {
  const [opinion, setOpinion] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(false);

  const usable = options.filter((o) => o.configured);
  if (!question || usable.length === 0) return null;

  const request = async (provider) => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.post(`/api/projects/${projectId}/second-opinion`, {
        question,
        provider,
      });
      if (response.data.error) {
        setError(response.data.error);
      } else {
        setOpinion(response.data);
      }
    } catch (e) {
      setError('The second opinion could not be requested.');
    } finally {
      setLoading(false);
    }
  };

  const localProvider = localAnswer?.provenance?.provider;
  const isLocal = localProvider === 'lmstudio' || localProvider === 'ollama';

  return (
    <div className="mt-3 pt-3 border-t border-gray-700">
      {!open && !opinion && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-mono text-gray-500 flex items-center">
            <ServerIcon className="h-3 w-3 mr-1.5" />
            {isLocal
              ? `answered locally by ${localAnswer?.provenance?.model || 'your model'}`
              : `answered by ${localProvider || 'the configured model'}`}
          </span>
          <button
            onClick={() => setOpen(true)}
            className="text-xs font-mono text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            ask a frontier model too
          </button>
        </div>
      )}

      {open && !opinion && (
        <div className="p-3 bg-gray-900/60 rounded border border-gray-700">
          <p className="text-xs font-mono text-amber-400/90 flex items-start mb-2">
            <ExclamationTriangleIcon className="h-3.5 w-3.5 mr-1.5 mt-0.5 flex-shrink-0" />
            This sends your question, and the community records retrieved for it,
            outside your community.
          </p>
          <div className="flex flex-wrap gap-2">
            {usable.map((option) => (
              <button
                key={option.provider}
                onClick={() => request(option.provider)}
                disabled={loading}
                className="px-3 py-1.5 text-xs font-mono bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-200 rounded border border-gray-600 transition-colors"
              >
                {loading
                  ? <ArrowPathIcon className="h-3 w-3 animate-spin inline" />
                  : <CloudArrowUpIcon className="h-3 w-3 inline mr-1.5" />}
                send to {option.recipient}
                <span className="text-gray-500 ml-1">({option.model})</span>
              </button>
            ))}
            <button
              onClick={() => setOpen(false)}
              className="px-3 py-1.5 text-xs font-mono text-gray-500 hover:text-gray-300 transition-colors"
            >
              no thanks
            </button>
          </div>
        </div>
      )}

      {error && (
        <p className="text-xs font-mono text-red-400 mt-2">{error}</p>
      )}

      {opinion && (
        <div className="mt-2 p-3 bg-gray-900/60 rounded border border-amber-500/30">
          <p className="text-xs font-mono text-amber-400/90 mb-2">
            second opinion from {opinion.recipient} ({opinion.model})
          </p>
          <div className="whitespace-pre-wrap font-mono text-sm text-gray-200 mb-3">
            {opinion.answer}
          </div>

          {opinion.comparison && (
            <div className="pt-2 border-t border-gray-800">
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                {[
                  ['local sources used', opinion.comparison.local?.sources_used],
                  ['their sources used', opinion.comparison.second_opinion?.sources_used],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between text-xs font-mono gap-3">
                    <dt className="text-gray-500">{k}</dt>
                    <dd className="text-gray-300">{v ?? '-'}</dd>
                  </div>
                ))}
              </dl>
              {opinion.comparison.cited_the_same_sources ? (
                <p className="text-xs font-mono text-green-400/80 mt-2">
                  Both answers cited the same records.
                </p>
              ) : (
                <p className="text-xs font-mono text-amber-400/80 mt-2">
                  The two answers cited different records. Worth reading both.
                </p>
              )}
              <p className="text-xs font-mono text-gray-600 mt-2">
                {opinion.comparison.note}
              </p>
            </div>
          )}

          <p className="text-xs font-mono text-gray-600 mt-2 pt-2 border-t border-gray-800">
            {opinion.disclosure}
          </p>
        </div>
      )}
    </div>
  );
}

export default SecondOpinion;
