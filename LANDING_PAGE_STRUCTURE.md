# Landing Page Structure

The public site (https://civicaiengine.org) is the landing page, the guide and
the rules. It is built with `REACT_APP_API_URL=none`, so nothing on the landing
page may depend on an API: the demo is a scripted simulation, and the "running
right now" section only appears when the same build is served by the API on
its own machine.

The page reads top to bottom, plain words first, technical detail last. Each
section has an anchor the sticky nav and the hero's reading guide link to.

```
frontend/src/components/LandingPage.js        the page
frontend/src/components/ConsoleDemo.js        the console simulation (renderer)
frontend/src/components/consoleDemoScript.js  what the simulation shows (content)
```

## Sections, in order

| # | Anchor | Section | Audience | Source of the copy |
| --- | --- | --- | --- | --- |
| 1 | `#top` | **Hero.** "AI as civic infrastructure." Public access TV made government watchable; this makes it askable. Two CTAs (the demo, the basics) and a three-part reading guide. | everyone | Civic AI Engine brief, p. 1 |
| 2 | `#what` | **What makes it different.** Two things at once: a real alternative to Big AI and a deeply local one. Four accent cards: a fraction of a data center, residents write the rules, it never leaves the community, anyone can build on it. | everyone | brief, p. 1 |
| 3 | | **How it gets used.** Four illustrative uses: speaking at a hearing, a question answered in Spanish, apps on the API, a vibe-coded app. | everyone | brief, p. 1 |
| 4 | `#demo` | **Watch a community AI get built.** The console simulation (below). Three notes under it: an afternoon on a real node, nothing calls a server, the data is sample data. | everyone | |
| 5 | `#vision` | **The idea.** Cable companies pay for community media; AI companies should pay for community AI. Why a utility, the 1984 precedent, what stations already hold, the vision callout (legislation), what a station node looks like, a hub-and-nodes network. No partner stations are named. | stations, towns, funders | brief, p. 2 and p. 3 |
| 6 | `#how` | **How it works.** Five steps: create, collect, learn, fine-tune, engage. | everyone | brief, p. 2 |
| 7 | | **In plain terms.** Six-term glossary: open-weight AI, how we customize it, constitutional convention, civic data corpus, civic API, frontier models. | everyone | brief, p. 2 |
| 8 | `#build` | **How it is built.** "One node. Four layers." The node diagram (power, node, private lane, archive, corpus, station network; web chat and apps out; the management-only network), four design details, the stack table. | technical | brief, p. 3; SYSTEM_GUIDE.md |
| 9 | | **What the community owns** (rules, record, finding, proof, test), **what happens when someone asks** (the six-step retrieval pipeline), and **every answer shows its work** (a cited answer with its provenance panel). | technical | SYSTEM_GUIDE.md §1–2 |
| 10 | `#ledger` | **The rules are a signed chain.** The constitution ledger, what it guarantees and what it does not claim. | technical | LEDGER.md |
| 11 | `#api` | **Infrastructure, not a chatbot.** The OpenAI-compatible and civic endpoints, keys, the gateway dropping system prompts, question hashing. | technical | api/gateway.py |
| 12 | | **Control and maintenance.** Remote care, isolated, you hold the keys. | stations | brief, p. 3 |
| 13 | `#live` | **Running right now.** Live assistants with a chat modal. Only when `apiAvailable` (src/api.js). | | |
| 14 | `#start` | **Three ways in.** Host a node (stations), run it yourself (technologists, with the bootstrap commands), shape the rules (residents, linking to the draft constitution). Final CTAs adapt to whether an API is available. | everyone | HANDOFF.md |

Followed by the shared `Footer`.

## The console demo

`ConsoleDemo` replays the real setup wizard's six steps (`./init`,
`./discover`, `./constitution`, `./finetune`, `./config`, `./launch`) and a
first question (`./chat`), with the same commands, step names, terminal lines
and status badges the console uses.

How it works:

- `consoleDemoScript.js` exports `buildScript(town)`: a list of timed events,
  each a function from the demo's state to the next. The renderer keeps one
  number, how many events have been applied, and derives the screen from it.
  Play, pause, jump-to-step, restart and the 2x speed are all changes to that
  number or to the timer.
- The visitor can type any town. The name flows through project ids, source
  names, the personality prompt and the answers. Everything else is sample
  data and the console is labeled "simulation · sample data".
- It starts on its own the first time it scrolls into view. With
  `prefers-reduced-motion` the typing is instant and pauses are short, so the
  sequence is the same, only quicker.
- The chat step asks one question by script and offers three more as chips.
  Each canned answer shows a property the real system has: a deep link to a
  timestamp, an answer in the language of the question, a discussion kept
  distinct from a vote, and an honest "the record does not include this".
- To change what the demo says, edit `consoleDemoScript.js` only.

## Conventions

- Section labels are small uppercase monospace (`<Label>`), the way the printed
  brief does it. Accent colors follow the brief: orange, rose, emerald, cyan.
- Never build Tailwind class names dynamically (`text-${color}-600` is purged
  at build time). Put the full class string in the data.
- `CI=true npm run build` must pass with no warnings; Netlify treats warnings as
  errors.
- The constitution link points at the repository's `main` branch
  (`CONSTITUTION_URL` in LandingPage.js).
