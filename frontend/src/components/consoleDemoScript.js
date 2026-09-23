// The console demo on the landing page is a scripted replay of the setup
// wizard, with sample data instead of a server. Everything a visitor sees is
// produced by this file: a list of timed events, each a function from the
// demo's state to the next state. ConsoleDemo.js applies the events in order
// and derives the screen from them, so jumping to a step is just applying
// every event before it at once.
//
// Edit content here. The renderer does not know what any step says.
//
// The public site is built with no API behind it (src/api.js), so nothing in
// this file may reach for one. The town is whatever the visitor typed; the
// sources, the numbers and the answers are illustrative and are labeled so.

export const SCENES = [
  { id: 'init', name: 'Location', cmd: 'init' },
  { id: 'discover', name: 'Discover', cmd: 'discover' },
  { id: 'constitution', name: 'Constitution', cmd: 'constitution' },
  { id: 'finetune', name: 'Fine Tune', cmd: 'finetune' },
  { id: 'config', name: 'Configure', cmd: 'config' },
  { id: 'launch', name: 'Launch', cmd: 'launch' },
  { id: 'chat', name: 'Ask', cmd: 'chat' },
];

export const DEFAULT_TOWN = 'Riverbend, MA';

export const VALUE_PRESETS = [
  'Transparency', 'Accuracy', 'Privacy', 'Accessibility', 'Civic neutrality', 'Community voice',
];

export const PROVIDERS = [
  { id: 'lmstudio', name: 'LM Studio', note: 'local', local: true },
  { id: 'ollama', name: 'Ollama', note: 'local', local: true },
  { id: 'anthropic', name: 'Anthropic', note: 'sends the question out', local: false },
  { id: 'openai', name: 'OpenAI', note: 'sends the question out', local: false },
];

export const SOURCE_TYPES = ['youtube_video', 'youtube_playlist', 'website', 'pdf_url'];

export function splitTown(town) {
  const trimmed = (town || '').trim() || DEFAULT_TOWN;
  const [name, ...rest] = trimmed.split(',');
  const short = name.trim() || 'Riverbend';
  const region = rest.join(',').trim();
  return { full: trimmed, short, region };
}

export function slugify(text) {
  return (
    String(text)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'community'
  );
}

export function formatNumber(n) {
  return Number(n).toLocaleString('en-US');
}

// Immutable set of a dotted path: setPath(s, 'form.municipality', 'x').
function setPath(state, path, value) {
  const keys = path.split('.');
  const next = { ...state };
  let cursor = next;
  for (let i = 0; i < keys.length - 1; i += 1) {
    cursor[keys[i]] = { ...cursor[keys[i]] };
    cursor = cursor[keys[i]];
  }
  cursor[keys[keys.length - 1]] = value;
  return next;
}

export function initialState() {
  return {
    scene: 'init',
    sceneIndex: 0,
    form: { municipality: '', projectName: '', projectId: '' },
    terminal: [],
    discovery: { phase: 'idle', sources: [] },
    constitution: { mode: '', values: [], guidelines: [], redLines: [] },
    custom: { open: false, type: '', url: '', name: '' },
    config: { provider: '', model: '', temperature: null, personality: '' },
    launch: { started: false, progress: {}, done: false },
    dashboard: false,
    chat: { input: '', messages: [], loading: false, done: false },
  };
}

// What discovery "finds". The counts are plausible for a mid-sized town and
// exist so the ingestion step has something to count down.
export function sourceCatalog(town) {
  const { short, full } = splitTown(town);
  const slug = slugify(full);
  return [
    { id: 'sb', name: `${short} Select Board meetings`, type: 'youtube_playlist', detail: 'public access channel · 312 recordings', total: 312, unit: 'recordings', words: 1904000, weight: 1 },
    { id: 'sc', name: `${short} School Committee meetings`, type: 'youtube_playlist', detail: 'public access channel · 148 recordings', total: 148, unit: 'recordings', words: 881000, weight: 0.85 },
    { id: 'web', name: 'Town website', type: 'website', detail: `${slug}.gov · departments, permits, FAQs`, total: 214, unit: 'pages', words: 96000, weight: 0.6 },
    { id: 'zoning', name: 'Zoning bylaws', type: 'pdf_url', detail: '184 pages · adopted document', total: 184, unit: 'pages', words: 71000, weight: 0.5 },
    { id: 'budget', name: 'FY2027 budget', type: 'pdf_url', detail: '96 pages · adopted document', total: 96, unit: 'pages', words: 38000, weight: 0.45 },
    { id: 'news', name: `${short} Independent`, type: 'website', detail: 'local news · secondary source', total: 1200, unit: 'articles', words: 640000, weight: 0.9 },
  ];
}

export const CUSTOM_SOURCE = {
  id: 'rules', name: 'Select Board rules of procedure', type: 'pdf_url',
  detail: '12 pages · adopted document', total: 12, unit: 'pages', words: 4100, weight: 0.3,
};

export const PASSAGES_INDEXED = 14208;

// Questions the visitor can ask once the assistant is "live". The first one
// is asked by the script; the rest are offered as chips. Each answer shows a
// different property the real system has: a deep link to a timestamp, an
// answer in the language of the question, discussion kept distinct from a
// vote, and an honest "the record does not have this".
export function cannedAnswers(town) {
  const { short } = splitTown(town);
  const base = {
    corpus: formatNumber(PASSAGES_INDEXED),
    updated: 'last night',
    model: 'gemma-4-26b-a4b',
    provider: 'LM Studio (local)',
    constitution: 'version 1.0 · draft',
    search: 'hybrid, reranked',
  };
  return [
    {
      id: 'hearing',
      question: 'How do I speak at the next hearing on the Elm Street redesign?',
      answer: 'The next hearing is Tuesday, October 6 at 7:00 pm in the Town Hall auditorium [1]. Sign up with the clerk before the meeting starts; each speaker gets three minutes [2]. At the last hearing the board asked staff for a revised plan with protected bike lanes and did not vote, so the design is still open [3].',
      sources: [
        { n: 1, kind: 'doc', title: `${short} Select Board · agenda for October 6, 2026`, where: 'p. 1', action: 'opens the agenda at page 1' },
        { n: 2, kind: 'doc', title: 'Select Board rules of procedure', where: 'p. 4', action: 'opens the PDF at page 4' },
        { n: 3, kind: 'video', title: `${short} Select Board · September 8, 2026`, where: '1:42:15', speaker: 'spoken by the Transportation Director', action: 'plays the recording at 1:42:15' },
      ],
      provenance: { ...base, retrieved: 7, used: 3, ms: 138 },
    },
    {
      id: 'hojas',
      question: '¿Qué decidió la Junta Selecta sobre la ordenanza de sopladores de hojas?',
      answer: 'La Junta Selecta votó 4 a 1 el 8 de septiembre de 2026 a favor de la ordenanza, que entra en vigor el 1 de enero de 2027 [1]. Los sopladores de gasolina quedan prohibidos del 15 de mayo al 15 de septiembre; los eléctricos siguen permitidos todo el año [1]. La votación nominal está en la grabación [1].',
      sources: [
        { n: 1, kind: 'video', title: `${short} Select Board · 8 de septiembre de 2026`, where: '1:02:33', speaker: 'votación nominal', action: 'reproduce la grabación en 1:02:33' },
      ],
      provenance: { ...base, retrieved: 5, used: 1, ms: 121 },
    },
    {
      id: 'gas',
      question: 'What has the town discussed about replacing gas heating in public buildings?',
      answer: 'The Select Board discussed it on May 12, 2026 and several members spoke in favor, but the record does not show a vote [1]. The FY2027 budget funds a feasibility study for the library boiler [2]. Nothing in the archive shows an adopted policy yet.',
      sources: [
        { n: 1, kind: 'video', title: `${short} Select Board · May 12, 2026`, where: '1:13:42', speaker: 'spoken by the Facilities Director', action: 'plays the recording at 1:13:42' },
        { n: 2, kind: 'doc', title: 'FY2027 budget', where: 'p. 73', action: 'opens the PDF at page 73' },
      ],
      provenance: { ...base, retrieved: 8, used: 2, ms: 152 },
    },
    {
      id: 'trash',
      question: 'When is trash day on Elm Street?',
      answer: "The record I have does not include collection schedules by street, so I can't tell you the day. The Public Works page lists pickup by zone [1]. Tell me your zone and I can check what the record says about holiday delays.",
      sources: [
        { n: 1, kind: 'web', title: `${short} Public Works · trash and recycling`, where: 'web page', action: 'opens the page' },
      ],
      provenance: { ...base, retrieved: 3, used: 1, ms: 97 },
    },
  ];
}

export function buildScript(town) {
  const { full, short, region } = splitTown(town);
  const slug = slugify(full);
  const catalog = sourceCatalog(full);
  const events = [];

  const at = (delay, fn, extra) => { events.push({ delay, fn, ...(extra || {}) }); };
  const scene = (id) => {
    const index = SCENES.findIndex((s) => s.id === id);
    at(500, (s) => ({ ...s, scene: id, sceneIndex: index, terminal: [] }), { scene: id });
  };
  const log = (type, text, delay = 550) => at(delay, (s) => ({ ...s, terminal: [...s.terminal, { type, text }] }));
  const set = (path, value, delay = 350) => at(delay, (s) => setPath(s, path, value));
  const typeInto = (path, text, perChar = 45, first = 400) => {
    for (let i = 1; i <= text.length; i += 1) {
      const slice = text.slice(0, i);
      at(i === 1 ? first : perChar, (s) => setPath(s, path, slice), { typing: true });
    }
  };
  const pause = (ms) => at(ms, (s) => s);

  // 1 · Location
  scene('init');
  typeInto('form.municipality', full, 55, 700);
  set('form.projectName', `${short} AI`, 500);
  set('form.projectId', slug, 250);
  log('command', `./init --location "${full}"`, 800);
  log('info', `writing data/${slug}/config.json`);
  log('success', `project ${slug} created`);
  log('info', 'constitution draft v1.0 loaded · 20 principles');
  pause(900);

  // 2 · Discover
  scene('discover');
  set('discovery.phase', 'searching', 200);
  log('command', './discover --web-search', 300);
  [
    `"${short}${region ? ` ${region}` : ''} select board meeting video"`,
    `"${short} school committee meeting recording"`,
    `"${short} town bylaws pdf"`,
    `"${short} annual budget fy2027"`,
  ].forEach((q) => log('info', `searching ${q}`, 650));
  log('success', `${catalog.length} sources found`, 700);
  set('discovery.phase', 'found', 200);
  catalog.forEach((src) => at(420, (s) => ({
    ...s,
    discovery: { ...s.discovery, sources: [...s.discovery.sources, { ...src, selected: true }] },
  })));
  at(1000, (s) => ({
    ...s,
    discovery: {
      ...s.discovery,
      sources: s.discovery.sources.map((x) => (x.id === 'news' ? { ...x, selected: false } : x)),
    },
  }));
  log('info', 'deselected: local news · a secondary source, easy to add later', 200);
  log('success', `${catalog.length - 1} sources selected`, 500);
  pause(900);

  // 3 · Constitution
  scene('constitution');
  log('command', './constitution', 300);
  set('constitution.mode', 'online', 700);
  log('info', 'online form · a workshop kit exists for in-person conventions', 300);
  ['Transparency', 'Accuracy', 'Privacy', 'Accessibility', 'Civic neutrality'].forEach((v) => at(480, (s) => ({
    ...s, constitution: { ...s.constitution, values: [...s.constitution.values, v] },
  })));
  [
    'Always cite the meeting and the timestamp',
    'Say plainly when the record is silent',
    'Keep a discussion distinct from a vote',
  ].forEach((g) => at(750, (s) => ({
    ...s, constitution: { ...s.constitution, guidelines: [...s.constitution.guidelines, g] },
  })));
  [
    'Never tell anyone how to vote',
    'Never give legal or medical advice',
    'Never assemble a profile of a resident',
  ].forEach((r) => at(750, (s) => ({
    ...s, constitution: { ...s.constitution, redLines: [...s.constitution.redLines, r] },
  })));
  log('success', 'constitution draft saved', 500);
  log('info', 'injected into every answer · residents amend it at a convention, the Council ratifies');
  pause(1200);

  // 4 · Fine tune
  scene('finetune');
  log('command', `./finetune --sources ${catalog.length - 1}`, 300);
  at(900, (s) => ({ ...s, custom: { ...s.custom, open: true } }));
  set('custom.type', 'pdf_url', 500);
  typeInto('custom.url', `https://${slug}.gov/select-board/rules-of-procedure.pdf`, 16, 400);
  typeInto('custom.name', CUSTOM_SOURCE.name, 28, 300);
  at(600, (s) => ({
    ...s,
    custom: { open: false, type: '', url: '', name: '' },
    discovery: {
      ...s.discovery,
      sources: [...s.discovery.sources, { ...CUSTOM_SOURCE, selected: true, custom: true }],
    },
  }));
  log('success', `added: ${CUSTOM_SOURCE.name}`, 200);
  log('info', 'limit per source: 120 MB or 10M words', 500);
  log('success', `${catalog.length} sources configured`, 400);
  pause(900);

  // 5 · Configure
  scene('config');
  log('command', './config', 300);
  set('config.provider', 'lmstudio', 700);
  log('info', 'inference: local · nothing leaves the building', 200);
  set('config.model', 'gemma-4-26b-a4b', 600);
  set('config.temperature', 0.3, 600);
  log('info', 'temperature 0.3 · this system cites records, so it stays close to them', 200);
  log('command', './config --generate-personality', 700);
  typeInto(
    'config.personality',
    `You are ${short} AI, a public-information service for ${full}. Answer from the town's own record, cite the meeting or the page, and say plainly when the record is silent.`,
    14,
    300,
  );
  log('success', 'personality generated · edit it any time', 400);
  pause(1100);

  // 6 · Launch
  scene('launch');
  log('command', './launch --deploy', 300);
  pause(1400);
  set('launch.started', true, 300);
  const selected = [...catalog.filter((c) => c.id !== 'news'), CUSTOM_SOURCE];
  const TICKS = 8;
  for (let t = 1; t <= TICKS; t += 1) {
    at(t === 1 ? 500 : 700, (s) => {
      const progress = {};
      selected.forEach((src) => {
        const pct = Math.min(100, Math.round((100 * t) / (TICKS * src.weight)));
        progress[src.id] = {
          pct,
          items: Math.round((src.total * pct) / 100),
          words: Math.round((src.words * pct) / 100),
        };
      });
      return { ...s, launch: { ...s.launch, progress } };
    });
  }
  log('success', `${selected.length}/${selected.length} sources ingested · ${formatNumber(PASSAGES_INDEXED)} passages indexed`, 400);
  log('info', 'hybrid index built · meaning plus keywords, reranked', 450);
  log('success', `${short} AI is live at http://127.0.0.1:8400`, 500);
  set('launch.done', true, 300);
  set('dashboard', true, 1000);
  pause(2600);

  // 7 · Ask
  scene('chat');
  const first = cannedAnswers(full)[0];
  typeInto('chat.input', first.question, 32, 900);
  at(500, (s) => ({
    ...s,
    chat: {
      ...s.chat, input: '', loading: true,
      messages: [...s.chat.messages, { role: 'user', id: first.id, content: first.question }],
    },
  }));
  at(1700, (s) => ({
    ...s,
    chat: {
      ...s.chat, loading: false,
      messages: [...s.chat.messages, {
        role: 'assistant', id: first.id, content: first.answer,
        sources: first.sources, provenance: first.provenance, provenanceOpen: false,
      }],
    },
  }));
  at(1400, (s) => ({
    ...s,
    chat: {
      ...s.chat,
      messages: s.chat.messages.map((m, i, arr) => (i === arr.length - 1 ? { ...m, provenanceOpen: true } : m)),
    },
  }));
  at(700, (s) => ({ ...s, chat: { ...s.chat, done: true } }));

  return events;
}
