# Community AI: Setup Guide

Standing up a locally governed, locally hosted AI for one community. This is
Community AI v0.1: constitution, hybrid retrieval, citations, an API, and a
chatbot. No fine-tuning, on purpose. See `COMMUNITY_AI_SCOPE.md` for why and for
what comes after.

Expect about half a day to a working system with a small corpus, and a few weeks
to something a town would put its name on. Most of that is not software.

---

## What you need

| | |
| --- | --- |
| A machine you control | 32 GB RAM to run a 26B model at 4-bit. Less is fine with a smaller model. |
| Python | 3.10 or newer |
| Node | 18 or newer, for the frontend |
| LM Studio | Or Ollama, or an API key. LM Studio is what this guide assumes. |
| Disk | ~20 GB for the model, plus the corpus |

A GPU is not required. It is the difference between an answer in seconds and an
answer in a minute.

---

## 1. Install

```bash
git clone https://github.com/amateurmenace/ai-machine.git
cd ai-machine

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && cd ..
```

The first run downloads the embedding model, about 90 MB.

---

## 2. Start the model server

Download **Gemma 4 26B-A4B** in LM Studio, then start its server. On a desktop:
Developer tab, Start Server. On a server with no display:

```bash
lms server start
lms load gemma-4-26b-a4b
```

Check it:

```bash
curl http://localhost:1234/v1/models
```

You should see the model id. Whatever id it reports is what goes in your config;
LM Studio's identifiers do not always match the name on the download page.

Or ask the app, which reports the remedy when the server is down:

```bash
python3 providers.py
```

> **Do not expose port 1234 to the internet.** LM Studio has no authentication,
> no rate limits, and no logging. The gateway in `api/` is the only thing that
> should face outward. Section 12 of the guide is unambiguous about this and it
> is the one mistake in this setup that is actually dangerous.

For a permanent install, run it under systemd. `SERVER_MANAGEMENT.md` has the
service pattern this repo already uses.

---

## 3. Write your constitution

This is the part to do before the technical setup feels finished, because
everything else references it.

```bash
ls constitution/
# constitution-v1.0.md  changelog.md  governance.md  model-card.md  data-card.md
```

`constitution-v1.0.md` ships with the twenty principles from the guide's
Appendix B. It is marked `draft` and **is not adopted**. Read it with the people
who will be accountable for this system, and edit it. `changelog.md` lists three
gaps the draft does not settle, including whether the assistant should help a
resident draft public testimony, where Principle 7 and Principle 13 genuinely
conflict.

To adopt a revision, copy rather than edit:

```bash
cp constitution/constitution-v1.0.md constitution/constitution-v1.1.md
# edit v1.1: bump the version in the frontmatter, set status: adopted
# add a changelog entry saying what changed and why
```

Adopted versions are never edited in place. `governance.md` describes the
amendment process and the issue-triage categories.

Check that it parses:

```bash
python3 -m community.constitution
# version=1.0 status=draft principles=20
```

Twenty principles should be reported. If you get zero, your headings are not in
the `## N. Title` form the parser expects.

---

## 4. Configure the community

```bash
cp community.example.yaml community.yaml
cp knowledge/sources.example.yaml knowledge/sources.yaml
```

Edit `community.yaml`: name, `project_id`, operator, contact, and the model id
LM Studio reported in step 2.

Edit `knowledge/sources.yaml`: your meeting video playlists, your town website,
your bylaws and budgets. Set `body` on meeting sources (`"Select Board"`,
`"Planning Board"`) and `department`, `document_type` and `status` on documents.
That metadata is what turns a citation from "Source 3" into "Select Board •
March 12, 2026 • 1:13:42", so it is worth the ten minutes.

Fill in `known_gaps` honestly. Principle 18 requires the assistant to be able to
say what the archive does not have, and this is where a maintainer writes it
down.

Validate without writing anything:

```bash
python3 -m scripts.bootstrap_community community.yaml --dry-run
```

It will refuse template placeholders and unsupported source types. Then create
the project:

```bash
python3 -m scripts.bootstrap_community community.yaml
```

Re-running later updates configuration and adds new sources. It never deletes a
source, drops an ingested corpus, or revokes a key.

---

## 4b. Choose a provider

Five are available. Local is the default and the point.

```yaml
model:
  provider: "lmstudio"        # lmstudio | ollama | anthropic | openai | gemini
  name: "gemma-4-26b-a4b"
  base_url: "http://localhost:1234/v1"
```

Ask a provider what it actually serves, rather than trusting the preset list:

```bash
curl "http://localhost:8000/api/providers"
curl "http://localhost:8000/api/providers/lmstudio/discover"
curl -X POST "http://localhost:8000/api/projects/brookline-ma/test-connection"
```

The last one distinguishes a stopped LM Studio from an unreachable tunnel and
names the fix. From the outside they look the same and need different remedies.

### Running the model somewhere else

LM Studio can live on a machine at your office and serve a public website. Put
the tunnel's public hostname in `base_url` and the tunnel's credential in the
project's `local_auth_header`, as one `Name: value` line:

```yaml
model:
  provider: "lmstudio"
  base_url: "https://ai-server.yourtown.org/v1"
```

```bash
curl -X PUT http://localhost:8000/api/projects/brookline-ma   -H 'Content-Type: application/json'   -d '{"local_auth_header": "CF-Access-Client-Id: ...\nCF-Access-Client-Secret: ..."}'
```

A Cloudflare tunnel needs no static IP and no inbound port. `TUNNEL_SETUP.md`
has the cloudflared side.

> **The tunnel must terminate at the gateway, not at LM Studio.** LM Studio has
> no authentication, no rate limits and no logging. Anything that can reach it
> can use your GPU and read every prompt.

### Frontier providers

Set an API key in Settings, or in the environment: `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `GEMINI_API_KEY`.

One caveat the app will tell you about: OpenAI moved tool calling to its
Responses API for the newest models, so `gpt-6-astra` answers normally but
cannot use web search here. `gpt-5.5` can.

---

## 4c. Turn on tools, if you want them

Off by default. An assistant bound to the community's own public record is a
legitimate choice.

```yaml
retrieval:
  # ...
tools:
  enabled: true
  allowed: ["search_community_records", "web_search", "fetch_url"]
  max_iterations: 4
  web_search_backend: "duckduckgo"   # searxng | brave | tavily | duckduckgo
```

Or per project:

```bash
curl -X PUT http://localhost:8000/api/projects/brookline-ma   -H 'Content-Type: application/json'   -d '{"enable_tools": true, "enabled_tools": ["search_community_records", "web_search"]}'
```

**Pick a search backend deliberately.** The keyless DuckDuckGo parser is fine
for trying this out and is genuinely fragile: it is unofficial and breaks when
the markup changes. For anything residents depend on, run a **SearXNG** instance
so no third party sees their queries, or pay for Brave or Tavily.

```yaml
web_search_backend: "searxng"
web_search_base_url: "https://search.yourtown.org"
```

Tools cannot reach private addresses. Every fetch resolves the hostname first
and refuses loopback, private, link-local and cloud-metadata addresses, after
every redirect. That guard is why this is safe to run on a cloud instance.

---

## 4d. Add the meeting archive

A whole channel, scanned repeatedly, is the shape a public-access archive
actually takes:

```yaml
sources:
  - name: "BIG Meeting Archive"
    type: youtube_channel
    url: "https://www.youtube.com/@YourStation"
```

Set `body` when a source is one board's playlist; the override beats anything
guessed from a title:

```yaml
  - name: "Select Board Meetings"
    type: youtube_playlist
    url: "https://www.youtube.com/playlist?list=..."
    body: "Select Board"
```

**Look at the plan before a backfill.** A decade of meetings is hours of work:

```bash
curl -X POST "http://localhost:8000/api/projects/brookline-ma/sources/<source-id>/preview-scan?limit=200"
```

It reports how many videos were found, which boards were recognized, what would
be skipped and why. If boards are coming back empty, add your community's own
body names rather than letting a thousand records index with no board attached.

Then ingest, and check what happened:

```bash
curl -X POST "http://localhost:8000/api/projects/brookline-ma/sources/<source-id>/ingest"
curl "http://localhost:8000/api/projects/brookline-ma/sources/<source-id>/sync-state"
```

The sync state lists meetings whose captions were disabled. Those are real gaps
in the public record: copy them into `constitution/data-card.md`, because
Principle 18 requires the assistant to be able to say what it does not have.

After the backfill, new meetings arrive on their own:

```bash
COMMUNITY_SYNC_ENABLED=true
COMMUNITY_SYNC_INTERVAL_MINUTES=360
```

A run that finds nothing new costs one listing request. Set a YouTube Data API
key (`YOUTUBE_API_KEY`) for exact publish dates and faster paging; without one
it falls back to yt-dlp, which needs no key.

---

## 5. Ingest a proof-of-concept corpus

Start small. The guide suggests roughly 100 documents and 20 meeting
transcripts, and that is the right size: enough to find real retrieval problems,
small enough to re-ingest when you change chunking.

```bash
python3 app.py            # terminal 1
cd frontend && npm start  # terminal 2
```

Add sources through the interface at `http://localhost:3000`, or ingest
everything in your config:

```bash
python3 -m scripts.bootstrap_community community.yaml --ingest
```

Video archives take hours. Run it overnight.

What ingestion produces:

- **Meeting video** becomes passages grouped by speaker and agenda item, each
  keeping the timestamp where it starts.
- **PDFs** are chunked within each page, so citations can name a page.
- **Websites** are chunked with their page title and URL.

Confirm it landed:

```bash
curl http://localhost:8000/community/brookline-ma/stats
```

---

## 6. Check retrieval before you check answers

This is the habit that saves the most time. Run the evaluation set in
retrieval-only mode. It needs no model and costs nothing:

```bash
python3 -m evals.run_evals --project brookline-ma --retrieval-only
```

```
  PASS  ground-001           local_factual              8 src     142ms
  RAG   ground-002           local_factual              8 src     138ms
```

A `RAG` verdict means the passage never reached the model. No prompt change and
no fine-tune fixes that. Fix chunking, metadata, or filters first.

Then the full run:

```bash
python3 -m evals.run_evals --project brookline-ma
```

```
  Retrieval    18/22 (82%)   <- chunking, metadata, ranking, filters
  Generation   24/29 (83%)   <- prompt, constitution, model
```

The two numbers are never averaged. They point at different people's work.

The 32 shipped cases are a seed. Write your own against your corpus, starting
with what residents actually ask at the counter. `evals/README.md` explains the
format and the one rule: once a case is in the set, add cases, never edit them
to make a release look better.

---

## 7. Talk to it

Open `http://localhost:3000`, pick your project, and ask something your corpus
should know.

You should see citations that carry a board and a date, links that land on a
timestamp or a page, and a **"why did you answer this way?"** control showing
sources retrieved, sources used, corpus freshness, model, and constitution
version. If citations are missing, check that `require_citations` is on and that
retrieval is returning anything at all.

---

## 8. Open the API

Issue a key per application, not one key for everything:

```bash
curl -X POST http://localhost:8000/api/projects/brookline-ma/api-clients \
  -H 'Content-Type: application/json' \
  -d '{"name": "Town Website Widget", "scopes": ["ask", "read"], "rate_limit_per_minute": 30}'
```

The plaintext key is returned once and stored only as a hash. If you lose it,
issue a new one and revoke the old.

Scopes: `ask` generates answers and costs inference, `search` retrieves without
generating, `read` lists meetings and documents, `admin` reads usage statistics.
Give a public-facing widget `ask` and `read`, and nothing else.

Any OpenAI client now works:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="cai_...")
response = client.chat.completions.create(
    model="community-ai",
    messages=[{"role": "user", "content": "Summarize tonight's Select Board meeting."}],
)
print(response.choices[0].message.content)
print(response.community["sources"])     # citations, as an extension
```

And the civic endpoints, for applications that want the record rather than an
answer about it:

```bash
curl -X POST http://localhost:8000/community/search \
  -H "Authorization: Bearer cai_..." \
  -d '{"query": "heat pumps", "filters": {"body": "Select Board", "date_from": "2025-01-01"}}'

curl "http://localhost:8000/community/meetings?body=Planning%20Board" \
  -H "Authorization: Bearer cai_..."
```

Two endpoints are public and need no key, because the constitution and the
system's own facts are public documents:

```bash
curl http://localhost:8000/community/brookline-ma/constitution
curl http://localhost:8000/community/brookline-ma/stats
```

Full schema at `http://localhost:8000/docs`.

---

## 9. Go to production

Put a reverse proxy in front with TLS. `DEPLOYMENT.md` and `TUNNEL_SETUP.md`
cover what this repo already uses. The shape:

```
internet -> Caddy/nginx (TLS) -> gateway :8000 -> LM Studio :1234 (localhost only)
```

Check before you open it up:

- [ ] LM Studio bound to localhost, not `0.0.0.0`
- [ ] Port 1234 not reachable from outside the machine
- [ ] `api_enabled` on, with per-application keys issued
- [ ] Rate limits set to something your hardware can actually serve
- [ ] Log retention decided, and written in your published privacy policy
- [ ] `constitution/model-card.md` and `data-card.md` filled in and published
- [ ] Constitution ratified, or clearly labeled a draft to residents

The chat UI shows "constitution not yet ratified" while the file says `draft`.
Leave that visible until it is true.

---

## Operations

### Usage statistics

```bash
curl "http://localhost:8000/community/usage?days=30" -H "Authorization: Bearer cai_admin_..."
```

Aggregates only: request counts, latency, how often answers carried sources,
unique question counts. No question text, per `governance.md`.

### Logging and privacy

Operational metadata is logged by default; question text is not. Questions are
stored as a salted hash so repeats stay countable without being readable.

To log question text, set `privacy.log_question_text: true`. Emails and phone
numbers are redacted before writing, but that is a reduction, not a guarantee.
Say so in your privacy policy before you turn it on.

```yaml
privacy:
  log_requests: true
  log_question_text: false
  log_retention_days: 30
```

Logs are JSON Lines under `data/<project_id>/logs/`, pruned on the usage
endpoint.

### Re-ingestion

Re-ingesting a source updates its passages in place: chunk ids are derived from
the URL, page, timestamp and text, so nothing duplicates. The keyword index
rebuilds automatically after ingestion.

### Switching embedding models

The guide recommends BGE-M3. It produces 1024-dimensional vectors against
MiniLM's 384, and a Qdrant collection's vector size is fixed, so this is a
re-index and not a config change.

```bash
export COMMUNITY_EMBEDDING_MODEL="BAAI/bge-m3"
```

Starting fresh, set it before the first ingestion. With an existing corpus, the
app refuses to start with a dimension mismatch and names the remedy. To migrate:
stop the app, delete `data/<project_id>/qdrant/`, set the variable, re-ingest.
Budget the full ingestion time again.

### Pinning a constitution version

While a new version is under review, pin a project to the current one:

```bash
curl -X PUT http://localhost:8000/api/projects/brookline-ma/constitution \
  -H 'Content-Type: application/json' -d '{"version": "1.0"}'
```

---

## Troubleshooting

**"The model server is not reachable."** LM Studio is not running or not
serving. Run `python3 providers.py` for the specific remedy. If it reports the
server is up but the model is not loaded, it will list what is loaded; use one
of those ids.

**Answers have no citations.** Check `/community/<project>/stats` for
`total_passages`. If it is zero, ingestion did not land. If it is nonzero, run a
retrieval-only evaluation to see whether passages are being found at all.

**Answers cite the wrong article or year.** A retrieval problem. Confirm with
`--retrieval-only`. Usually chunking too coarse, or a source ingested without
`body` and `date` metadata so filters cannot help.

**"Reranker inactive" in the transparency panel.** The cross-encoder could not
load, usually no model cached and no network. Retrieval still works on fusion
order. Pre-download it on a machine that has network access, or ignore it.

**Keyword search misses new records.** The index rebuilds after ingestion and on
a ten-minute timer. If you wrote to Qdrant outside the app, restart it.

**Rate limits behave oddly with multiple workers.** The limiter is per-process,
so `uvicorn --workers 4` gives four times the intended limit. Run one worker, or
move the limiter to Redis.

**A dimension mismatch error on startup.** You changed the embedding model
against an existing collection. See "Switching embedding models".

---

## Running the tests

```bash
./run_tests.sh
```

Or one suite at a time:

```bash
python3 -m tests.test_rag          # retrieval, citations, pipeline
python3 -m tests.test_gateway      # auth, scopes, rate limits, HTTP behavior
python3 -m tests.test_app_wiring   # routes, imports, OpenAPI schema
python3 -m tests.test_end_to_end   # the real agent path, stubs only at the edges
python3 -m tests.test_tools        # URL guard, tool loop, failure paths
python3 -m tests.test_archive      # meeting titles, channel sync, video embeds
```

None need a GPU, a vector database, or a model, so they run in CI.

---

## Where things are

```
constitution/     the rules, versioned, with governance and cards
community/        loads and renders the constitution
knowledge/        record schemas and the source inventory
rag/              bm25, hybrid retrieval, reranking, citations, pipeline
tools/            web search, fetch, archive search, the tool loop
collectors/       youtube, websites, pdfs, channel sync, title parsing
api/              gateway, auth, privacy-aware logging
evals/            the frozen set and its runner
training/         phase 3 scaffolding, nothing runs at v0.1
scripts/          bootstrap a community from YAML
tests/            254 assertions, no GPU or network required
```

`SYSTEM_GUIDE.md` explains how it all works. `ROADMAP.md` covers where it goes
next, including the Google Cloud move and the database decision.
`COMMUNITY_AI_SCOPE.md` says what is built, what is partial, and what is left.
