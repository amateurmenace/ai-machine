import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api, { apiBaseUrl } from '../api';
import {
  ShieldCheckIcon, ExclamationTriangleIcon, LinkIcon, ArrowLeftIcon,
  CheckBadgeIcon, KeyIcon, ClockIcon, CubeIcon,
} from '@heroicons/react/24/outline';

/**
 * The constitution ledger: a chain of signed blocks, one per adopted version.
 *
 * The vocabulary is borrowed from cryptocurrency where it is literally true.
 * Each version is a block; blocks link by hash; the first is genesis;
 * ratification is an N-of-M multi-signature. What is deliberately NOT claimed
 * anywhere on this page: consensus, decentralization, mining, or immutability.
 * The chain makes tampering visible. Saying more than that would be the kind of
 * overclaim that costs trust once someone reads the code.
 */

function Hash({ value, short, label }) {
  const [copied, setCopied] = useState(false);
  if (!value) return null;
  const display = short || String(value).split(':').pop().slice(0, 8);

  const copy = () => {
    try {
      navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (e) {
      /* clipboard unavailable; the full hash is in the title attribute */
    }
  };

  return (
    <button
      onClick={copy}
      title={`${label ? label + ': ' : ''}${value}`}
      className="font-mono text-xs px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700 text-cyan-400 hover:border-cyan-600 transition-colors"
    >
      {copied ? 'copied' : display}
    </button>
  );
}

function Block({ block, isHead }) {
  const [open, setOpen] = useState(isHead);
  const verified = block.verification || {};
  const healthy = verified.content_hash_matches !== false
    && verified.links_to_previous !== false
    && verified.links_to_genesis !== false;

  return (
    <div className="relative pl-8">
      {/* chain line */}
      <div className="absolute left-3 top-0 bottom-0 w-px bg-gray-700" />
      <div className={`absolute left-1 top-5 h-4 w-4 rounded-full border-2 ${
        healthy ? 'bg-gray-900 border-green-500' : 'bg-gray-900 border-red-500'
      }`} />

      <div className={`mb-4 rounded-lg border overflow-hidden ${
        healthy ? 'border-gray-700 bg-gray-900' : 'border-red-500/50 bg-red-950/20'
      }`}>
        <button
          onClick={() => setOpen(!open)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-800/50 transition-colors text-left gap-3"
        >
          <div className="flex items-center gap-3 min-w-0">
            <CubeIcon className="h-4 w-4 text-gray-500 flex-shrink-0" />
            <div className="min-w-0">
              <p className="font-mono text-sm text-white">
                block {block.index} · v{block.version}
                {block.genesis && (
                  <span className="ml-2 text-xs text-purple-400">genesis</span>
                )}
                {isHead && (
                  <span className="ml-2 text-xs text-green-400">head · in force</span>
                )}
              </p>
              {block.summary && (
                <p className="font-mono text-xs text-gray-500 truncate">{block.summary}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {block.ratified ? (
              <span className="flex items-center text-xs font-mono text-green-400">
                <CheckBadgeIcon className="h-4 w-4 mr-1" />
                ratified {block.signatures_valid}/{block.threshold}
              </span>
            ) : (
              <span className="text-xs font-mono text-amber-500">{block.status}</span>
            )}
            <Hash value={block.content_hash} short={block.content_hash_short} label="content" />
          </div>
        </button>

        {open && (
          <div className="px-4 pb-4 pt-1 border-t border-gray-800 space-y-3">
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1">
              {[
                ['adopted', block.adopted || 'not adopted'],
                ['status', block.status],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between text-xs font-mono gap-3">
                  <dt className="text-gray-500">{k}</dt>
                  <dd className="text-gray-300">{v}</dd>
                </div>
              ))}
              <div className="flex justify-between items-center text-xs font-mono gap-3">
                <dt className="text-gray-500">content hash</dt>
                <dd><Hash value={block.content_hash} short={block.content_hash_short} /></dd>
              </div>
              <div className="flex justify-between items-center text-xs font-mono gap-3">
                <dt className="text-gray-500">block hash</dt>
                <dd><Hash value={block.block_hash} short={block.block_hash_short} /></dd>
              </div>
              <div className="flex justify-between items-center text-xs font-mono gap-3">
                <dt className="text-gray-500">previous block</dt>
                <dd>
                  {block.genesis
                    ? <span className="text-purple-400">genesis · none</span>
                    : <Hash value={block.prev_hash} short={block.prev_hash_short} />}
                </dd>
              </div>
            </dl>

            {block.signatures && block.signatures.length > 0 && (
              <div className="pt-2 border-t border-gray-800">
                <p className="text-xs font-mono text-gray-500 mb-1">
                  ratification signatures ({block.signatures_valid} valid of{' '}
                  {block.threshold} required)
                </p>
                {block.signatures.map((sig, i) => (
                  <p key={i} className="text-xs font-mono flex items-center">
                    <KeyIcon className={`h-3 w-3 mr-1.5 flex-shrink-0 ${
                      sig.verified ? 'text-green-500' : 'text-red-500'
                    }`} />
                    <span className="text-gray-300">{sig.signer}</span>
                    {sig.role && <span className="text-gray-600 ml-1">· {sig.role}</span>}
                    {sig.signed_at && <span className="text-gray-600 ml-1">· {sig.signed_at}</span>}
                    {!sig.verified && (
                      <span className="text-red-400 ml-2">signature does not verify</span>
                    )}
                  </p>
                ))}
              </div>
            )}

            {block.anchors && block.anchors.length > 0 && (
              <div className="pt-2 border-t border-gray-800">
                <p className="text-xs font-mono text-gray-500 mb-1">
                  external witnesses to when this block existed
                </p>
                {block.anchors.map((anchor, i) => (
                  <p key={i} className="text-xs font-mono flex items-start text-gray-300">
                    <ClockIcon className="h-3 w-3 mr-1.5 mt-0.5 flex-shrink-0 text-cyan-500" />
                    <span>
                      <span className="text-cyan-400">{anchor.kind}</span>
                      {' · '}{anchor.reference}
                      {anchor.note && (
                        <span className="block text-gray-600">{anchor.note}</span>
                      )}
                    </span>
                  </p>
                ))}
              </div>
            )}

            {!healthy && (
              <p className="text-xs font-mono text-red-400 flex items-start pt-2 border-t border-gray-800">
                <ExclamationTriangleIcon className="h-3.5 w-3.5 mr-1.5 mt-0.5 flex-shrink-0" />
                This block does not verify. The text on disk is not the text that
                was sealed, or the chain link is broken.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ConstitutionLedger() {
  const { projectId } = useParams();
  const [ledger, setLedger] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await api.get(`/community/${projectId}/constitution/ledger`);
        if (!cancelled) setLedger(response.data);
      } catch (e) {
        if (!cancelled) setError('Could not load the ledger.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [projectId]);

  if (loading) {
    return <p className="font-mono text-sm text-gray-500 p-4">loading ledger...</p>;
  }
  if (error || !ledger) {
    return <p className="font-mono text-sm text-red-400 p-4">{error || 'No ledger.'}</p>;
  }

  const blocks = [...(ledger.blocks || [])].reverse();
  const explanation = ledger.explanation || {};

  return (
    <div className="max-w-4xl">
      <Link
        to={`/console/projects/${projectId}`}
        className="inline-flex items-center text-gray-400 hover:text-green-400 font-mono text-sm mb-4 group"
      >
        <ArrowLeftIcon className="h-4 w-4 mr-2 group-hover:-translate-x-1 transition-transform" />
        <span className="text-green-400">$</span> cd ../dashboard
      </Link>

      <h1 className="text-2xl font-mono text-white mb-1">Constitution ledger</h1>
      <p className="font-mono text-sm text-gray-400 mb-6">
        Every version of the rules {ledger.community} adopted, chained by hash
        and signed at ratification.
      </p>

      <div className={`mb-6 p-4 rounded-lg border ${
        ledger.valid
          ? 'bg-green-500/5 border-green-500/30'
          : 'bg-red-500/5 border-red-500/30'
      }`}>
        <div className="flex items-start">
          {ledger.valid
            ? <ShieldCheckIcon className="h-5 w-5 text-green-400 mr-2 mt-0.5 flex-shrink-0" />
            : <ExclamationTriangleIcon className="h-5 w-5 text-red-400 mr-2 mt-0.5 flex-shrink-0" />}
          <div className="min-w-0">
            <p className={`font-mono text-sm ${ledger.valid ? 'text-green-300' : 'text-red-300'}`}>
              {ledger.valid
                ? `Chain verified · ${ledger.block_count} block${ledger.block_count === 1 ? '' : 's'}`
                : `Chain does NOT verify · ${ledger.problems.length} problem(s)`}
            </p>
            <p className="font-mono text-xs text-gray-500 mt-1">
              Every block links to the one before it, every file matches the hash
              recorded for it, and every signature checks against its signer's key.
            </p>
            {!ledger.valid && ledger.problems.map((p, i) => (
              <p key={i} className="font-mono text-xs text-red-400 mt-1">· {p}</p>
            ))}
          </div>
        </div>
      </div>

      <div className="mb-6">
        {blocks.map((block, i) => (
          <Block key={block.index} block={block} isHead={i === 0} />
        ))}
      </div>

      {ledger.signers && ledger.signers.length > 0 && (
        <div className="mb-6 p-4 bg-gray-900 border border-gray-700 rounded-lg">
          <p className="font-mono text-sm text-gray-300 mb-2">Ratifiers</p>
          {ledger.signers.map((signer) => (
            <p key={signer.name} className="font-mono text-xs text-gray-400">
              <KeyIcon className="h-3 w-3 inline mr-1.5 text-gray-600" />
              {signer.name}
              {signer.role && <span className="text-gray-600"> · {signer.role}</span>}
              {signer.key_id && (
                <span className="text-gray-700 ml-2">{signer.key_id.slice(0, 26)}...</span>
              )}
            </p>
          ))}
        </div>
      )}

      <div className="p-4 bg-gray-900 border border-gray-700 rounded-lg space-y-3">
        <div>
          <p className="font-mono text-xs text-gray-500 mb-1">what this is</p>
          <p className="font-mono text-xs text-gray-400">{explanation.what_this_is}</p>
        </div>
        <div>
          <p className="font-mono text-xs text-gray-500 mb-1">what it guarantees</p>
          <p className="font-mono text-xs text-gray-400">{explanation.what_it_guarantees}</p>
        </div>
        <div>
          <p className="font-mono text-xs text-amber-500/80 mb-1">
            what it does not guarantee
          </p>
          <p className="font-mono text-xs text-gray-400">
            {explanation.what_it_does_not_guarantee}
          </p>
        </div>
        <div className="pt-2 border-t border-gray-800">
          <p className="font-mono text-xs text-gray-500 mb-1">check it yourself</p>
          <code className="font-mono text-xs text-green-400 block">
            python3 -m community.ledger verify
          </code>
          <a
            href={`${apiBaseUrl}/community/${projectId}/constitution/ledger`}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-xs text-cyan-400 hover:text-cyan-300 inline-flex items-center mt-2"
          >
            <LinkIcon className="h-3 w-3 mr-1" />
            raw ledger JSON
          </a>
        </div>
      </div>
    </div>
  );
}

export default ConstitutionLedger;
