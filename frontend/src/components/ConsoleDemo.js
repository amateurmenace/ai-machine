import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  PlayIcon,
  PauseIcon,
  ArrowPathIcon,
  ForwardIcon,
  CheckIcon,
  VideoCameraIcon,
  DocumentTextIcon,
  GlobeAltIcon,
  PaperAirplaneIcon,
  InformationCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ScaleIcon,
  UserGroupIcon,
  CogIcon,
  ChatBubbleLeftRightIcon,
  CircleStackIcon,
  ShieldCheckIcon,
  QuestionMarkCircleIcon,
  LinkIcon,
  PlayCircleIcon,
} from '@heroicons/react/24/outline';
import {
  SCENES,
  DEFAULT_TOWN,
  VALUE_PRESETS,
  PROVIDERS,
  SOURCE_TYPES,
  buildScript,
  initialState,
  cannedAnswers,
  splitTown,
  formatNumber,
} from './consoleDemoScript';

// A scripted replay of the console: the six wizard steps and a first
// question, driven by consoleDemoScript.js. The screen is derived from how
// many events have been applied, so play, pause, jump and restart are all
// just changes to one number. Nothing here calls a server.

function usePrefersReducedMotion() {
  const query = '(prefers-reduced-motion: reduce)';
  const [reduced, setReduced] = useState(() => (
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia(query).matches
      : false
  ));
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const mq = window.matchMedia(query);
    const onChange = (e) => setReduced(e.matches);
    if (mq.addEventListener) mq.addEventListener('change', onChange);
    else if (mq.addListener) mq.addListener(onChange);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', onChange);
      else if (mq.removeListener) mq.removeListener(onChange);
    };
  }, []);
  return reduced;
}

const TYPE_STYLE = {
  youtube_playlist: { icon: VideoCameraIcon, label: 'youtube playlist', cls: 'text-red-400 bg-red-500/10 border-red-500/30' },
  youtube_video: { icon: VideoCameraIcon, label: 'youtube video', cls: 'text-red-400 bg-red-500/10 border-red-500/30' },
  website: { icon: GlobeAltIcon, label: 'website', cls: 'text-green-400 bg-green-500/10 border-green-500/30' },
  pdf_url: { icon: DocumentTextIcon, label: 'pdf', cls: 'text-orange-400 bg-orange-500/10 border-orange-500/30' },
};

const LINE_STYLE = {
  info: { prefix: '[INFO]', cls: 'text-gray-400' },
  success: { prefix: '[OK]', cls: 'text-green-400' },
  error: { prefix: '[ERR]', cls: 'text-red-400' },
  warning: { prefix: '[WARN]', cls: 'text-yellow-400' },
  command: { prefix: '$', cls: 'text-cyan-400' },
};

function Cursor() {
  return <span className="inline-block w-[7px] h-[1em] bg-green-400 align-text-bottom animate-pulse ml-0.5" aria-hidden="true" />;
}

function Field({ label, value, placeholder, typing, mono }) {
  return (
    <div>
      <p className="font-mono text-[11px] text-gray-500 mb-1">{label}</p>
      <div className={`px-3 py-2 bg-gray-800 border rounded-md min-h-[38px] text-sm ${typing ? 'border-green-500/60' : 'border-gray-700'} ${mono ? 'font-mono' : ''}`}>
        {value
          ? <span className="text-white">{value}{typing && <Cursor />}</span>
          : <span className="text-gray-600">{placeholder}{typing && <Cursor />}</span>}
      </div>
    </div>
  );
}

function FakeButton({ children, active, primary }) {
  const base = 'inline-flex items-center px-3 py-1.5 rounded font-mono text-xs font-semibold transition-colors';
  const tone = primary
    ? (active ? 'bg-green-400 text-gray-900 ring-2 ring-green-300/60' : 'bg-green-500 text-gray-900')
    : (active ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-400 border border-gray-700');
  return <span className={`${base} ${tone}`}>{children}</span>;
}

function SourceRow({ source, showCheckbox, progress }) {
  const style = TYPE_STYLE[source.type] || TYPE_STYLE.website;
  const Icon = style.icon;
  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border ${source.selected === false ? 'border-gray-800 bg-gray-900/40 opacity-60' : 'border-gray-700 bg-gray-800/60'}`}>
      {showCheckbox && (
        <span className={`mt-0.5 flex-shrink-0 h-4 w-4 rounded border flex items-center justify-center ${source.selected === false ? 'border-gray-600' : 'border-green-400 bg-green-500/20'}`}>
          {source.selected !== false && <CheckIcon className="h-3 w-3 text-green-400" />}
        </span>
      )}
      <Icon className={`h-4 w-4 mt-0.5 flex-shrink-0 ${style.cls.split(' ')[0]}`} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm text-white truncate">{source.name}</p>
          <span className={`px-1.5 py-0.5 rounded border font-mono text-[10px] ${style.cls}`}>{style.label}</span>
          {source.custom && (
            <span className="px-1.5 py-0.5 rounded border font-mono text-[10px] text-purple-300 bg-purple-500/10 border-purple-500/30">custom</span>
          )}
        </div>
        <p className="font-mono text-[11px] text-gray-500 truncate">{source.detail}</p>
        {progress && (
          <div className="mt-2">
            <div className="h-1.5 bg-gray-700 rounded overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${progress.pct >= 100 ? 'bg-green-500' : 'bg-cyan-500'}`}
                style={{ width: `${progress.pct}%` }}
              />
            </div>
            <p className="font-mono text-[11px] text-gray-500 mt-1">
              {progress.pct >= 100
                ? <span className="text-green-400">completed</span>
                : <span className="text-cyan-400">running</span>}
              {' '}· {formatNumber(progress.items)}/{formatNumber(source.total)} {source.unit} · {formatNumber(progress.words)} words
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function InitScreen({ state }) {
  const { form, terminal } = state;
  return (
    <div className="space-y-4">
      <p className="font-mono text-xs text-gray-400">
        <span className="text-green-400">#</span> where is this assistant for?
      </p>
      <Field
        label="municipality or neighborhood"
        value={form.municipality}
        placeholder="e.g. Brookline, MA"
        typing={!form.projectName}
      />
      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="project name" value={form.projectName} placeholder="filled in for you" />
        <Field label="project id" value={form.projectId} placeholder="filled in for you" mono />
      </div>
      <FakeButton primary active={terminal.length > 0}>$ ./init</FakeButton>
    </div>
  );
}

function DiscoverScreen({ state }) {
  const { discovery } = state;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-xs text-gray-400">
          <span className="text-green-400">#</span> finding the public record
        </p>
        <FakeButton primary active={discovery.phase !== 'idle'}>
          {discovery.phase === 'searching' && (
            <span className="h-3 w-3 mr-2 border-2 border-gray-900/40 border-t-gray-900 rounded-full animate-spin" />
          )}
          $ ./discover --web-search
        </FakeButton>
      </div>
      {discovery.phase === 'searching' && discovery.sources.length === 0 && (
        <p className="font-mono text-xs text-gray-500">searching for meeting recordings, bylaws, budgets and town pages<Cursor /></p>
      )}
      <div className="space-y-2">
        {discovery.sources.map((src) => <SourceRow key={src.id} source={src} showCheckbox />)}
      </div>
      {discovery.sources.length > 0 && (
        <p className="font-mono text-[11px] text-gray-500">
          {discovery.sources.filter((s) => s.selected !== false).length} of {discovery.sources.length} selected · all are selected by default; untick what you do not want
        </p>
      )}
    </div>
  );
}

function ConstitutionScreen({ state }) {
  const { constitution } = state;
  const modes = [
    { id: 'online', name: 'online form', note: 'right here, right now' },
    { id: 'workshop', name: 'workshop', note: 'residents in a room' },
    { id: 'skip', name: 'skip', note: 'use the 20-principle draft' },
  ];
  return (
    <div className="space-y-4">
      <p className="font-mono text-xs text-gray-400">
        <span className="text-green-400">#</span> the rules this assistant must follow, written by the people it serves
      </p>
      <div className="grid grid-cols-3 gap-2">
        {modes.map((m) => (
          <div key={m.id} className={`p-2.5 rounded-lg border text-center ${constitution.mode === m.id ? 'border-green-500/60 bg-green-500/10' : 'border-gray-700 bg-gray-800/60'}`}>
            <p className={`font-mono text-xs ${constitution.mode === m.id ? 'text-green-400' : 'text-gray-300'}`}>{m.name}</p>
            <p className="font-mono text-[10px] text-gray-500 hidden sm:block">{m.note}</p>
          </div>
        ))}
      </div>
      {constitution.mode === 'online' && (
        <div className="grid md:grid-cols-3 gap-3">
          <div className="p-3 rounded-lg border border-gray-700 bg-gray-800/60">
            <p className="font-mono text-[11px] text-gray-500 mb-2">core values · pick at least 3</p>
            <div className="flex flex-wrap gap-1.5">
              {VALUE_PRESETS.map((v) => {
                const on = constitution.values.includes(v);
                return (
                  <span key={v} className={`px-2 py-0.5 rounded-full border font-mono text-[11px] ${on ? 'border-green-500/60 bg-green-500/15 text-green-300' : 'border-gray-700 text-gray-500'}`}>
                    {on && <CheckIcon className="h-3 w-3 inline mr-1" />}{v}
                  </span>
                );
              })}
            </div>
          </div>
          <div className="p-3 rounded-lg border border-gray-700 bg-gray-800/60">
            <p className="font-mono text-[11px] text-gray-500 mb-2">ethical guidelines</p>
            <ul className="space-y-1.5">
              {constitution.guidelines.map((g) => (
                <li key={g} className="text-xs text-gray-200 flex items-start">
                  <span className="text-cyan-400 mr-1.5 font-mono">+</span>{g}
                </li>
              ))}
              {constitution.guidelines.length === 0 && <li className="text-xs text-gray-600">none yet</li>}
            </ul>
          </div>
          <div className="p-3 rounded-lg border border-gray-700 bg-gray-800/60">
            <p className="font-mono text-[11px] text-gray-500 mb-2">red lines · what it never does</p>
            <ul className="space-y-1.5">
              {constitution.redLines.map((r) => (
                <li key={r} className="text-xs text-gray-200 flex items-start">
                  <span className="text-rose-400 mr-1.5 font-mono">-</span>{r}
                </li>
              ))}
              {constitution.redLines.length === 0 && <li className="text-xs text-gray-600">none yet</li>}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

function FinetuneScreen({ state }) {
  const { discovery, custom } = state;
  const selected = discovery.sources.filter((s) => s.selected !== false);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-xs text-gray-400">
          <span className="text-green-400">#</span> what it will learn from
        </p>
        <FakeButton active={custom.open}>+ add custom source</FakeButton>
      </div>
      {custom.open && (
        <div className="p-3 rounded-lg border border-green-500/40 bg-gray-800/60 space-y-3">
          <div className="flex flex-wrap gap-1.5">
            {SOURCE_TYPES.map((t) => (
              <span key={t} className={`px-2 py-0.5 rounded border font-mono text-[11px] ${custom.type === t ? 'border-green-500/60 bg-green-500/15 text-green-300' : 'border-gray-700 text-gray-500'}`}>{t}</span>
            ))}
          </div>
          <Field label="url" value={custom.url} placeholder="https://" typing={!!custom.url && !custom.name} mono />
          <Field label="name" value={custom.name} placeholder="what to call it" typing={!!custom.name} />
          <FakeButton primary>+ add</FakeButton>
        </div>
      )}
      <div className="space-y-2">
        {selected.map((src) => <SourceRow key={src.id} source={src} />)}
      </div>
    </div>
  );
}

function ConfigScreen({ state }) {
  const { config } = state;
  return (
    <div className="space-y-4">
      <p className="font-mono text-xs text-gray-400">
        <span className="text-green-400">#</span> which model answers, and how it speaks
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {PROVIDERS.map((p) => {
          const on = config.provider === p.id;
          return (
            <div key={p.id} className={`p-2.5 rounded-lg border ${on ? 'border-green-500/60 bg-green-500/10' : 'border-gray-700 bg-gray-800/60'}`}>
              <p className={`font-mono text-xs ${on ? 'text-green-400' : 'text-gray-300'}`}>{p.name}</p>
              <p className={`font-mono text-[10px] ${p.local ? 'text-green-500/80' : 'text-amber-500/80'}`}>{p.note}</p>
            </div>
          );
        })}
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="model" value={config.model} placeholder="pick a provider first" mono />
        <div>
          <p className="font-mono text-[11px] text-gray-500 mb-1">
            temperature {config.temperature !== null && <span className="text-white">{config.temperature.toFixed(1)}</span>}
          </p>
          <div className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-md min-h-[38px] flex items-center">
            <div className="relative h-1.5 w-full bg-gray-700 rounded">
              <div className="absolute inset-y-0 left-0 bg-green-500 rounded transition-all duration-500" style={{ width: `${(config.temperature ?? 0.7) * 100}%` }} />
              <div className="absolute top-1/2 -translate-y-1/2 h-3.5 w-3.5 rounded-full bg-white border-2 border-green-500 transition-all duration-500" style={{ left: `calc(${(config.temperature ?? 0.7) * 100}% - 7px)` }} />
            </div>
          </div>
          <p className="font-mono text-[10px] text-gray-600 mt-1">0.0 sticks to the record · 1.0 gets creative</p>
        </div>
      </div>
      <div>
        <div className="flex items-center justify-between mb-1">
          <p className="font-mono text-[11px] text-gray-500">personality · system prompt</p>
          <FakeButton active={!!config.personality}>generate</FakeButton>
        </div>
        <div className={`px-3 py-2 bg-gray-800 border rounded-md min-h-[76px] text-sm leading-relaxed ${config.personality ? 'border-green-500/40 text-gray-100' : 'border-gray-700 text-gray-600'}`}>
          {config.personality || 'write your own, or generate one from the location and the constitution'}
          {config.personality && !state.terminal.some((l) => l.text.startsWith('personality generated')) && <Cursor />}
        </div>
      </div>
    </div>
  );
}

function LaunchScreen({ state, town }) {
  const { launch, discovery, config, constitution, dashboard } = state;
  const { short } = splitTown(town);
  const selected = discovery.sources.filter((s) => s.selected !== false);
  const cards = [
    { cmd: './chat', icon: ChatBubbleLeftRightIcon, note: 'ask it something' },
    { cmd: './data', icon: CircleStackIcon, note: `${selected.length} sources · synced` },
    { cmd: './ledger', icon: ScaleIcon, note: 'constitution v1.0 · draft' },
    { cmd: './settings', icon: CogIcon, note: config.model || 'model' },
    { cmd: './admin', icon: ShieldCheckIcon, note: 'health · api keys' },
    { cmd: './help', icon: QuestionMarkCircleIcon, note: 'guides' },
  ];

  if (dashboard) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="font-mono text-xs text-gray-400"><span className="text-green-400">$</span> cd ~/projects/{state.form.projectId}</p>
          <span className="inline-flex items-center font-mono text-[11px] text-green-400">
            <span className="h-2 w-2 rounded-full bg-green-500 mr-1.5 animate-pulse" />online · local
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {cards.map((c) => (
            <div key={c.cmd} className="p-3 rounded-lg border border-gray-700 bg-gray-800/60">
              <c.icon className="h-4 w-4 text-green-400 mb-1.5" />
              <p className="font-mono text-sm text-white">{c.cmd}</p>
              <p className="font-mono text-[10px] text-gray-500 truncate">{c.note}</p>
            </div>
          ))}
        </div>
        <p className="font-mono text-[11px] text-gray-500">{short} AI is running on this machine. Next: <span className="text-cyan-400">./chat</span></p>
      </div>
    );
  }

  if (!launch.started) {
    const rows = [
      ['location', town],
      ['sources', `${selected.length} configured`],
      ['constitution', `${constitution.values.length} values · ${constitution.guidelines.length} guidelines · ${constitution.redLines.length} red lines`],
      ['model', `${config.model} · LM Studio (local)`],
      ['temperature', config.temperature !== null ? config.temperature.toFixed(1) : ''],
    ];
    return (
      <div className="space-y-4">
        <p className="font-mono text-xs text-gray-400"><span className="text-green-400">#</span> review, then launch</p>
        <dl className="rounded-lg border border-gray-700 bg-gray-800/60 divide-y divide-gray-700">
          {rows.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-4 px-3 py-2 font-mono text-xs">
              <dt className="text-gray-500">{k}</dt>
              <dd className="text-gray-200 text-right">{v}</dd>
            </div>
          ))}
        </dl>
        <FakeButton primary active={state.terminal.length > 0}>$ ./launch --deploy</FakeButton>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="font-mono text-xs text-gray-400">
        <span className="text-green-400">#</span> ingesting · transcribing, chunking, embedding, indexing
      </p>
      <div className="space-y-2">
        {selected.map((src) => (
          <SourceRow key={src.id} source={src} progress={launch.progress[src.id] || { pct: 0, items: 0, words: 0 }} />
        ))}
      </div>
      {launch.done && (
        <div className="p-3 rounded-lg border border-green-500/40 bg-green-500/10 font-mono text-xs text-green-300 flex items-center">
          <CheckIcon className="h-4 w-4 mr-2" /> live on the node · nothing left the building
        </div>
      )}
    </div>
  );
}

function SourceCitation({ source }) {
  const isVideo = source.kind === 'video';
  const Icon = isVideo ? VideoCameraIcon : source.kind === 'web' ? GlobeAltIcon : DocumentTextIcon;
  return (
    <div className="font-mono text-[11px]">
      <p className="text-cyan-400 flex items-start">
        <Icon className="h-3.5 w-3.5 mr-1.5 mt-px flex-shrink-0" />
        <span>[{source.n}] {source.title} &bull; {source.where}</span>
      </p>
      {source.speaker && <p className="text-gray-500 ml-5">{source.speaker}</p>}
      <p className="text-green-400 ml-5 mt-0.5 flex items-center">
        {isVideo ? <PlayCircleIcon className="h-3.5 w-3.5 mr-1" /> : <LinkIcon className="h-3 w-3 mr-1" />}
        {source.action}
      </p>
    </div>
  );
}

function Provenance({ provenance, open, onToggle }) {
  const rows = [
    ['sources retrieved', provenance.retrieved],
    ['sources used', provenance.used],
    ['passages in knowledge base', provenance.corpus],
    ['knowledge base updated', provenance.updated],
    ['model', provenance.model],
    ['served by', provenance.provider],
    ['constitution', provenance.constitution],
    ['search', provenance.search],
    ['retrieval time', `${provenance.ms} ms`],
  ];
  return (
    <div className="mt-3 pt-3 border-t border-gray-700">
      <button
        type="button"
        onClick={onToggle}
        className="flex items-center text-[11px] font-mono text-gray-500 hover:text-cyan-400 transition-colors"
      >
        {open ? <ChevronDownIcon className="h-3 w-3 mr-1" /> : <ChevronRightIcon className="h-3 w-3 mr-1" />}
        <InformationCircleIcon className="h-3 w-3 mr-1" />
        why did you answer this way?
      </button>
      {open && (
        <dl className="mt-2 p-2.5 bg-gray-900/70 rounded border border-gray-700 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
          {rows.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3 font-mono text-[11px]">
              <dt className="text-gray-500 whitespace-nowrap">{k}</dt>
              <dd className="text-gray-300 text-right">{v}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

function ChatScreen({ state, town, extra, extraLoading, answers, onAsk, provOpen, onToggleProv, chatRef }) {
  const { chat } = state;
  const { short } = splitTown(town);
  const messages = [...chat.messages, ...extra];
  const asked = new Set(messages.filter((m) => m.role === 'user').map((m) => m.id));
  const remaining = answers.filter((a) => !asked.has(a.id));
  const loading = chat.loading || extraLoading;

  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <p className="font-mono text-xs text-gray-400"><span className="text-green-400">$</span> ./chat</p>
        <span className="font-mono text-[11px] text-gray-500">{short} AI · gemma-4-26b-a4b · local</span>
      </div>
      <div ref={chatRef} className="h-[19rem] sm:h-[22rem] overflow-y-auto pr-1 space-y-3 scrollbar-dark">
        {messages.length === 0 && !loading && (
          <div className="h-full flex items-center justify-center">
            <p className="font-mono text-xs text-gray-600 text-center">
              Hi, I'm {short} AI. Ask me about {town}, or anything else.
            </p>
          </div>
        )}
        {messages.map((m, i) => {
          const key = `${m.id}-${m.role}-${i}`;
          const open = provOpen[key] !== undefined ? provOpen[key] : !!m.provenanceOpen;
          return (
            <div key={key} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[92%] sm:max-w-[85%] rounded-lg px-3.5 py-2.5 ${m.role === 'user' ? 'bg-green-500/20 border border-green-500/30 text-green-100' : 'bg-gray-800 border border-gray-700 text-gray-200'}`}>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{m.content}</p>
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-700 space-y-2">
                    {m.sources.map((s) => <SourceCitation key={s.n} source={s} />)}
                  </div>
                )}
                {m.provenance && (
                  <Provenance provenance={m.provenance} open={open} onToggle={() => onToggleProv(key, !open)} />
                )}
              </div>
            </div>
          );
        })}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-3">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="mt-3 flex gap-2">
        <div className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm min-h-[40px] text-white">
          {chat.input ? <>{chat.input}<Cursor /></> : <span className="text-gray-600">Ask a question...</span>}
        </div>
        <span className={`px-3 py-2 rounded-lg ${chat.input ? 'bg-green-500 text-gray-900' : 'bg-gray-700 text-gray-500'}`}>
          <PaperAirplaneIcon className="h-5 w-5" />
        </span>
      </div>

      {chat.done && remaining.length > 0 && (
        <div className="mt-3">
          <p className="font-mono text-[11px] text-gray-500 mb-1.5">try another · sample answers</p>
          <div className="flex flex-wrap gap-1.5">
            {remaining.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => onAsk(a)}
                disabled={loading}
                className="text-left px-2.5 py-1.5 rounded-lg border border-gray-700 bg-gray-800/60 hover:border-green-500/60 hover:bg-green-500/10 text-xs text-gray-200 transition-colors disabled:opacity-50"
              >
                {a.question}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ConsoleDemo() {
  const [town, setTown] = useState(DEFAULT_TOWN);
  const [draftTown, setDraftTown] = useState(DEFAULT_TOWN);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [started, setStarted] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [extra, setExtra] = useState([]);
  const [extraLoading, setExtraLoading] = useState(false);
  const [provOpen, setProvOpen] = useState({});
  const reduced = usePrefersReducedMotion();
  const rootRef = useRef(null);
  const terminalRef = useRef(null);
  const chatRef = useRef(null);
  const askTimer = useRef(null);

  const events = useMemo(() => buildScript(town), [town]);
  const answers = useMemo(() => cannedAnswers(town), [town]);
  const state = useMemo(
    () => events.slice(0, idx).reduce((s, e) => e.fn(s), initialState()),
    [events, idx],
  );
  const finished = idx >= events.length;
  const scene = SCENES[state.sceneIndex];
  const lastMessage = state.chat.messages[state.chat.messages.length - 1];
  const lastProvenanceOpen = lastMessage ? !!lastMessage.provenanceOpen : false;

  // The scheduler: wait the next event's delay, then apply it. Reduced motion
  // collapses the typing and shortens the pauses rather than removing the
  // sequence, so the story is the same, only quicker.
  useEffect(() => {
    if (!playing) return undefined;
    if (idx >= events.length) {
      setPlaying(false);
      return undefined;
    }
    const ev = events[idx];
    let delay = ev.delay / speed;
    if (reduced) delay = ev.typing ? 0 : Math.min(delay, 200);
    const t = setTimeout(() => setIdx((i) => i + 1), delay);
    return () => clearTimeout(t);
  }, [playing, idx, events, speed, reduced]);

  // Start on its own the first time it scrolls into view.
  useEffect(() => {
    if (started || typeof IntersectionObserver === 'undefined') return undefined;
    const el = rootRef.current;
    if (!el) return undefined;
    const obs = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        setStarted(true);
        setPlaying(true);
        obs.disconnect();
      }
    }, { threshold: 0.3 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [started]);

  useEffect(() => {
    const el = terminalRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [state.terminal.length]);

  useEffect(() => {
    const el = chatRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [state.chat.messages.length, state.chat.loading, lastProvenanceOpen, extra.length, extraLoading, provOpen]);

  useEffect(() => () => { if (askTimer.current) clearTimeout(askTimer.current); }, []);

  const resetFollowUps = useCallback(() => {
    if (askTimer.current) clearTimeout(askTimer.current);
    setExtra([]);
    setExtraLoading(false);
    setProvOpen({});
  }, []);

  const restart = () => {
    resetFollowUps();
    setIdx(0);
    setStarted(true);
    setPlaying(true);
  };

  const jumpTo = (sceneId) => {
    const i = events.findIndex((e) => e.scene === sceneId);
    if (i < 0) return;
    resetFollowUps();
    setIdx(i + 1);
    setStarted(true);
    setPlaying(true);
  };

  const skipAhead = () => {
    const next = SCENES[Math.min(state.sceneIndex + 1, SCENES.length - 1)];
    if (next && next.id !== scene.id) jumpTo(next.id);
    else setIdx(events.length);
  };

  const applyTown = (e) => {
    if (e) e.preventDefault();
    const next = draftTown.trim() || DEFAULT_TOWN;
    setDraftTown(next);
    resetFollowUps();
    setTown(next);
    setIdx(0);
    setStarted(true);
    setPlaying(true);
  };

  const ask = (a) => {
    if (extraLoading) return;
    setExtra((x) => [...x, { role: 'user', id: a.id, content: a.question }]);
    setExtraLoading(true);
    askTimer.current = setTimeout(() => {
      setExtra((x) => [...x, {
        role: 'assistant', id: a.id, content: a.answer,
        sources: a.sources, provenance: a.provenance, provenanceOpen: true,
      }]);
      setExtraLoading(false);
    }, reduced ? 200 : 1300);
  };

  const toggleProv = (key, open) => setProvOpen((p) => ({ ...p, [key]: open }));

  const screen = (() => {
    switch (state.scene) {
      case 'discover': return <DiscoverScreen state={state} />;
      case 'constitution': return <ConstitutionScreen state={state} />;
      case 'finetune': return <FinetuneScreen state={state} />;
      case 'config': return <ConfigScreen state={state} />;
      case 'launch': return <LaunchScreen state={state} town={town} />;
      case 'chat':
        return (
          <ChatScreen
            state={state}
            town={town}
            extra={extra}
            extraLoading={extraLoading}
            answers={answers}
            onAsk={ask}
            provOpen={provOpen}
            onToggleProv={toggleProv}
            chatRef={chatRef}
          />
        );
      default: return <InitScreen state={state} />;
    }
  })();

  const controlBtn = 'inline-flex items-center justify-center h-7 px-2 rounded font-mono text-[11px] text-gray-300 bg-gray-800 border border-gray-700 hover:border-green-500/60 hover:text-white transition-colors';

  return (
    <div ref={rootRef} className="bg-gray-950 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden text-left">
      {/* title bar */}
      <div className="flex flex-wrap items-center gap-3 px-4 py-2.5 bg-gray-900 border-b border-gray-800">
        <div className="flex space-x-2">
          <div className="w-3 h-3 rounded-full bg-red-500" />
          <div className="w-3 h-3 rounded-full bg-yellow-500" />
          <div className="w-3 h-3 rounded-full bg-green-500" />
        </div>
        <span className="font-mono text-xs text-gray-500">civic-ai-engine — console</span>
        <span className="px-1.5 py-0.5 rounded border border-amber-500/40 bg-amber-500/10 font-mono text-[10px] text-amber-300">simulation · sample data</span>
        <div className="ml-auto flex items-center gap-1.5">
          <button type="button" onClick={() => { setStarted(true); setPlaying((p) => !p); }} className={controlBtn} aria-label={playing ? 'pause' : 'play'}>
            {playing ? <PauseIcon className="h-3.5 w-3.5" /> : <PlayIcon className="h-3.5 w-3.5" />}
            <span className="ml-1 hidden sm:inline">{playing ? 'pause' : finished ? 'done' : 'play'}</span>
          </button>
          <button type="button" onClick={skipAhead} className={controlBtn} aria-label="skip to next step" disabled={finished}>
            <ForwardIcon className="h-3.5 w-3.5" /><span className="ml-1 hidden sm:inline">next</span>
          </button>
          <button type="button" onClick={() => setSpeed((s) => (s === 1 ? 2 : 1))} className={controlBtn} aria-label="toggle speed">
            {speed}x
          </button>
          <button type="button" onClick={restart} className={controlBtn} aria-label="restart">
            <ArrowPathIcon className="h-3.5 w-3.5" /><span className="ml-1 hidden sm:inline">restart</span>
          </button>
        </div>
      </div>

      {/* town bar */}
      <form onSubmit={applyTown} className="flex flex-wrap items-center gap-2 px-4 py-2.5 border-b border-gray-800 bg-gray-900/60">
        <label htmlFor="demo-town" className="font-mono text-[11px] text-gray-500">simulating a community AI for</label>
        <input
          id="demo-town"
          value={draftTown}
          onChange={(e) => setDraftTown(e.target.value)}
          className="flex-1 min-w-[10rem] px-2.5 py-1 bg-gray-800 border border-gray-700 rounded font-mono text-xs text-white focus:outline-none focus:ring-1 focus:ring-green-500"
          placeholder={DEFAULT_TOWN}
          maxLength={48}
        />
        <button type="submit" className="px-2.5 py-1 rounded bg-green-500 text-gray-900 font-mono text-[11px] font-semibold hover:bg-green-400 transition-colors">
          run
        </button>
      </form>

      {/* step rail */}
      <div className="flex gap-1.5 px-4 py-2.5 overflow-x-auto scrollbar-none border-b border-gray-800 bg-gray-900/40" role="tablist" aria-label="setup steps">
        {SCENES.map((s, i) => {
          const done = i < state.sceneIndex || (finished && i <= state.sceneIndex);
          const active = i === state.sceneIndex && !finished;
          return (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => jumpTo(s.id)}
              className={`flex-shrink-0 inline-flex items-center px-2.5 py-1 rounded-full border font-mono text-[11px] transition-colors ${
                active
                  ? 'border-green-500 bg-green-500/15 text-green-300'
                  : done
                    ? 'border-gray-700 bg-gray-800 text-gray-400 hover:text-white'
                    : 'border-gray-800 text-gray-600 hover:text-gray-300'
              }`}
            >
              {done && !active ? <CheckIcon className="h-3 w-3 mr-1 text-green-500" /> : <span className="mr-1 opacity-70">{i + 1}</span>}
              ./{s.cmd}
            </button>
          );
        })}
      </div>

      {/* screen */}
      <div className="p-4 sm:p-5 min-h-[22rem]">
        {screen}
      </div>

      {/* terminal */}
      {state.scene !== 'chat' && (
        <div ref={terminalRef} className="px-4 py-3 bg-black/60 border-t border-gray-800 h-28 overflow-y-auto scrollbar-dark font-mono text-xs space-y-1">
          {state.terminal.length === 0 && (
            <p className="text-gray-700">
              <span className="text-green-700">$</span> waiting<Cursor />
            </p>
          )}
          {state.terminal.map((line, i) => {
            const st = LINE_STYLE[line.type] || LINE_STYLE.info;
            return (
              <p key={`${i}-${line.text}`} className={st.cls}>
                <span className="opacity-70">{st.prefix}</span> {line.text}
              </p>
            );
          })}
        </div>
      )}

      {/* footer note */}
      <div className="px-4 py-2 bg-gray-900 border-t border-gray-800 flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] text-gray-600">
          <UserGroupIcon className="h-3 w-3 inline mr-1" />
          the real console runs on the node, on hardware the community owns
        </p>
        <p className="font-mono text-[10px] text-gray-600">step {Math.min(state.sceneIndex + 1, SCENES.length)} of {SCENES.length} · {scene.name.toLowerCase()}</p>
      </div>
    </div>
  );
}
