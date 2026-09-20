import React, { useState } from 'react';
import {
  PlayIcon, XMarkIcon, ArrowTopRightOnSquareIcon, ShieldCheckIcon,
} from '@heroicons/react/24/outline';

/**
 * Plays the moment of a meeting a citation points to, inside the app.
 *
 * A link out to YouTube costs the resident their place in the answer. Playing
 * it here means they can watch the board actually say the thing and then keep
 * reading, which is the difference between a claim and a verifiable claim.
 *
 * The iframe is not mounted until the resident clicks. Until then this is a
 * thumbnail, so opening an answer with six meeting citations does not load six
 * players or contact Google six times. The embed uses youtube-nocookie.com, so
 * nothing is tracked even after playback starts.
 */
function MeetingPlayer({ embed, label, speaker, agendaItem, onClose, autoOpen = false }) {
  const [playing, setPlaying] = useState(autoOpen);

  if (!embed || !embed.embed_url) return null;

  return (
    <div className="mt-2 bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
      <div className="flex items-start justify-between px-3 py-2 bg-gray-800 border-b border-gray-700 gap-3">
        <div className="min-w-0">
          <p className="text-xs font-mono text-cyan-400 truncate">{label}</p>
          {(speaker || agendaItem) && (
            <p className="text-xs font-mono text-gray-500 truncate">
              {[speaker, agendaItem].filter(Boolean).join(' · ')}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <a
            href={embed.watch_url}
            target="_blank"
            rel="noopener noreferrer"
            title="Open on YouTube"
            className="text-gray-500 hover:text-cyan-400 transition-colors"
          >
            <ArrowTopRightOnSquareIcon className="h-4 w-4" />
          </a>
          {onClose && (
            <button
              onClick={onClose}
              title="Close player"
              className="text-gray-500 hover:text-red-400 transition-colors"
            >
              <XMarkIcon className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {playing ? (
        <div className="relative w-full" style={{ paddingTop: '56.25%' }}>
          <iframe
            title={label || 'Meeting video'}
            src={`${embed.embed_url}&autoplay=1`}
            className="absolute inset-0 w-full h-full"
            allow="accelerometer; encrypted-media; picture-in-picture; fullscreen"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
          />
        </div>
      ) : (
        <button
          onClick={() => setPlaying(true)}
          className="relative w-full group"
          style={{ paddingTop: '56.25%' }}
          aria-label={`Play meeting at ${embed.start_label || 'the cited moment'}`}
        >
          {embed.thumbnail_url && (
            <img
              src={embed.thumbnail_url}
              alt=""
              loading="lazy"
              className="absolute inset-0 w-full h-full object-cover opacity-55 group-hover:opacity-75 transition-opacity"
            />
          )}
          <span className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="flex items-center justify-center h-14 w-14 rounded-full bg-green-500/90 group-hover:bg-green-400 transition-colors">
              <PlayIcon className="h-7 w-7 text-gray-900 ml-0.5" />
            </span>
            {embed.start_label && (
              <span className="mt-2 text-xs font-mono text-white bg-gray-900/80 px-2 py-1 rounded">
                starts at {embed.start_label}
              </span>
            )}
          </span>
        </button>
      )}

      <div className="flex items-center px-3 py-1.5 bg-gray-950 border-t border-gray-800">
        <ShieldCheckIcon className="h-3 w-3 text-gray-600 mr-1.5 flex-shrink-0" />
        <p className="text-xs font-mono text-gray-600 truncate">
          {embed.privacy_note || 'privacy-enhanced embed'}
        </p>
      </div>
    </div>
  );
}

export default MeetingPlayer;
