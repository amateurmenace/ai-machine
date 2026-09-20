# Roadmap

Where this goes next, and the two decisions worth making deliberately: how to
deploy on Google Cloud, and whether the current database is the right one.

`SYSTEM_GUIDE.md` explains how the system works today.

---

## The thesis

A community member should be able to use this with an open-weights model and not
feel they got the cheap version. That is the whole project, and it is a claim
that can be true or false rather than a slogan.

Three things separate a local model from a frontier one in practice. Two are now
closed.

| Gap | Status |
| --- | --- |
| No access to current information | **Closed.** Tools give the local model web search, page fetching, and a second pass at the archive. |
| No access to local knowledge | **Closed, and inverted.** On questions about this community, a local model with a good archive beats a frontier model without one. Retrieval is worth more than parameters here. |
| Raw reasoning on hard questions | **Open.** A 26B model reasons less well than a frontier model on a genuinely hard question. |

The third gap is real and should not be hand-waved. What follows is how to
shrink it, and how to know whether it is shrinking.

---

## Part 1 — Making the local model genuinely good enough

### 1.1 Measure the gap instead of arguing about it

**Built.** `python3 -m evals.compare_providers`. Four things this section assumed
turned out to be wrong, and they are worth recording rather than quietly fixing:

- **The general-capability row could not be produced.** Only one of seven cases
  in that category declared a scorable check, so the headline comparison this
  section is built around would have printed a dash for its most important row.
  The cases have since been rewritten to check the regression that is actually
  scorable: a civic fine-tune teaching the model to refuse work outside the
  town. Substrings cannot judge whether a grant proposal is good; they can
  detect "I can only answer questions about this community", which is the
  failure mode that matters. A scope-refusing model now fails all nine.
- **Retrieval is only provider-independent when the model-backed query rewrite
  is off**, because that rewrite puts a model in front of retrieval. The
  comparison forces it off, which is correct but was not obvious.
- **The five-point parity margin is finer than the seed set can resolve.**
  Categories hold one to eleven cases, so a single case moves a category by
  nine to a hundred points. The margin means something only once the set
  reaches the 200 to 500 questions the guide asks for. Published today, the
  table is noise.
- **One API key per project cannot fund a comparison.** Comparing three
  providers needs three credentials, so every non-project column reads its key
  from the environment.

### 1.1b The original plan, for reference

The evaluation harness already runs a frozen question set and scores retrieval
separately from generation. Add a mode that runs the same set against several
providers and publishes the comparison:

```bash
python3 -m evals.compare_providers --project brookline-ma \
    --providers lmstudio:gemma-4-26b-a4b anthropic:claude-opus-5 gemini:gemini-3.1-pro
```

The output a town actually needs looks like this:

```
                          local     Claude    Gemini
local factual              92%       94%       93%
attribution                88%       91%       90%
ambiguous (vote vs talk)   71%       89%       85%    <- the real gap
source absence             95%       93%       94%
general capability         74%       96%       94%
```

Two things fall out of that table that no amount of discussion produces. First,
the gap is not uniform: on source-grounded civic questions a local model is
usually at parity, because the answer is in the retrieved passage either way.
Second, it names the categories where the local model actually needs help, which
is where the next section's effort should go.

Publish this per release. "We use an open model and here is exactly what it
costs us" is a far stronger civic position than either "open models are just as
good" or "we need the expensive one".

**Effort: 2-3 days.** Mostly a runner that swaps providers and a table renderer.

### 1.2 Put the effort where the table says

The categories that lag are predictable, and each has a fix that is not "get a
bigger model":

- **Discussion versus adopted action** (`ambiguous`) is the classic civic
  failure and the most damaging. **Built**, in `knowledge/status.py`. A meeting
  announces its own state in a small conventional vocabulary, so this is read at
  ingestion rather than inferred at answer time, and every retrieved passage now
  carries a line naming what it is. Found a bug doing it: the meeting record
  type defaulted to "discussion", which silently prevented the classifier from
  ever detecting a vote. Six new evaluation cases.
- **Conflicting evidence** improves when the retriever deliberately fetches
  *both* sides rather than the top-k most similar passages, which tend to agree
  with each other. A diversity pass over the reranked candidates. **Built**, in
  `rag/diversity.py`, off by default. Two corrections to this section's
  assumptions: the diversity pass and the existing adaptive context window are
  in conflict rather than independent, since that window stops adding passages
  right where a dissenting one sits, so diversity replaces it rather than
  following it. And the category it is meant to improve holds two cases, so the
  harness in 1.1 cannot yet measure whether it worked.
- **General capability** lags because a small model is a small model. Do not fix
  this with a civic fine-tune; that is how you make it worse. Fix it by routing
  (below).

### 1.3 Let the resident choose, visibly

Not automatic routing by difficulty. Automatic routing sends residents' questions
to a frontier provider without them knowing, which is exactly the property the
project exists to avoid.

Instead: answer locally by default, and when the local model is uncertain, offer
a second opinion as a button.

```
Answered locally by Gemma 4 26B.
[ Ask a frontier model too ]  — this sends your question to Anthropic
```

The disclosure is the feature. A resident asking about a zoning bylaw gets a
local answer; a resident asking for help drafting a grant proposal can decide
for themselves whether that is worth sending out.

**Effort: 3-4 days** including the UI and a per-question provider override in
the gateway.

### 1.4 Precompute the questions everyone asks

A town's questions have a long head. "When is trash day", "how do I get a
parking permit", "what happened at the last Select Board meeting" are asked
constantly. Run them against the local model nightly, when the GPU is idle, and
cache the answers with their citations. Invalidate when the archive changes.

Latency stops being the local model's weakness for the questions that matter
most, and the marginal cost of a resident asking a common question drops to a
database read.

**Effort: 3-4 days.** The request log already counts question hashes, which is
where the head of the distribution comes from without storing anyone's question.

### 1.5 Use frontier models offline, not in the request path

This is the ethically coherent use of a frontier model in this project: one
time, on your own data, to make the local model better. Not once per resident.

The training scaffolding already exists (`training/`). A frontier model generates
candidate critique-and-revision examples from the constitution, humans review a
representative sample, and a QLoRA adapter trains on the result. Nothing about a
resident's question ever leaves.

**Do not do this yet.** The gate is written in `training/README.md`: a frozen
evaluation set of at least 200 cases and a passing retrieval-only run. Training
before retrieval is solved teaches a model to be confidently wrong from bad
evidence. **Effort when the gate is met: 2-3 weeks plus GPU time.**

### 1.6 Hardware, plainly

What a community actually needs to run this:

| Setup | Cost | Serves |
| --- | --- | --- |
| Mac Studio M4 Max, 64GB | ~$3,500 once | Gemma 4 26B at reading speed, a few concurrent users |
| Used RTX 3090 (24GB) in a desktop | ~$1,500 once | Same class, faster, more fiddly |
| Two 3090s or an RTX 6000 | ~$3,000-7,000 | 70B-class models, more concurrency |
| Cloud GPU (L4 on GCP) | ~$500/month, forever | Comparable, and defeats the purpose |

The one-time purchase beats the subscription within a year and keeps the
property that matters. A machine in a closet at a public-access station, reached
through a tunnel, is a completely reasonable production deployment and is
directly supported today.

---

## Part 2 — Google Cloud

### 2.1 What breaks if you lift this onto Cloud Run tomorrow

Be clear about this before choosing anything. The current design is a
**single-machine** design, and three parts of it assume that:

1. **The vector database is an embedded file store.** Qdrant in local mode
   writes to a directory. Cloud Run's filesystem is in-memory and disappears on
   every cold start. Deploying as-is means silently losing the archive.
2. **It takes an exclusive file lock.** Two instances against one directory is a
   crash, so the service cannot scale past one container. Cloud Run autoscales
   by default.
3. **The keyword index and the scheduler live in process memory.** Every
   instance rebuilds the BM25 index from the whole corpus on first use, and
   every instance runs its own sync timer. Three instances means three copies of
   the index and the same meeting ingested three times.

None of this is a flaw in the current design. It is the correct design for one
server, which is what a town needs. It is simply not a Cloud Run design.

### 2.2 The recommended architecture: static front, local everything else

**Keep the console on Netlify, where it already is. Keep the API, the archive
and the model on your hardware. Cloud Run is for later, and section 2.2b says
exactly when.**

```
             residents on the web
                      │
                      ▼
      ┌───────────────────────────────┐
      │  Netlify                      │   the console: static React
      │  (free tier, already running) │   neighborhood-ai.netlify.app
      └───────────┬───────────────────┘
                  │
                  │
                  ▼
           Cloudflare tunnel
                  │
                  ▼
    ┌─────────────────────────────────┐
    │  one machine at BIG             │
    │                                 │
    │  FastAPI — gateway, RAG, API    │
    │  LM Studio — Gemma on your GPU  │
    │  archive.sqlite3 — the record   │
    └─────────────────────────────────┘
                  │
                  ▼
        nightly snapshot, optionally
        to a bucket that costs cents
```

Why this shape and not the obvious alternatives:

- **The console belongs in the cloud, and already is.** It is static files.
  Netlify serves them from a CDN for nothing, they are up at 2am whatever the
  office is doing, and a page that loads and says the assistant is temporarily
  offline is a far better outage than a dead link. `deploy/netlify.sh`
  publishes it, with the same account and site guards the Cloud Run script has.
- **The API does not belong in the cloud, for the same reason the database
  does not.** This is the bullet that used to argue the opposite, and the
  argument it made — up at 2am, survives a power cut, absorbs a traffic spike —
  does not survive contact with where the model is. If inference runs on the
  machine at the office, an API in Google's data centre is up and unable to
  answer anything the moment that machine is down. It converts an outage into
  a differently-shaped outage. The traffic spike argument fails the same way:
  autoscaling the web tier does not help when every request queues behind one
  GPU. So the API sits next to the model and the archive, and the tunnel puts
  it on the public internet without exposing the machine.
- **Inference belongs on your hardware.** A GPU on GCP is about $500/month
  forever for capability you can buy outright for $3,500. More importantly,
  moving inference to Google's servers gives up the property the project is
  about. The tunnel support built for exactly this already works.
- **The archive belongs next to the model.** This reverses what an earlier
  draft of this document recommended, and the reason is in the diagram above.
  Once inference is on your hardware behind a tunnel, the service is already
  down when that machine is down. A managed database in the cloud cannot make
  it up again; it can only add $150-200 a month and a network hop to every
  retrieval. The availability was already spent on the tunnel. What the
  archive actually needs is backups, and backups are a scheduled copy of a
  file, not a database server.

If the office network is genuinely too unreliable to serve inference, the
fallback is a frontier provider with the switch clearly disclosed to residents,
not a cloud GPU. That is cheaper and more honest than pretending a GCP L4 is
"local".

### 2.2b When Cloud Run becomes the right answer

`deploy/cloudrun.sh` is written, guarded, and tested as far as it can be
without a cloud account. It is not deleted, because the case for it is real.
It is just not this month's case. One condition decides it:

> **Move the API to Cloud Run when the default answer path no longer depends
> on the machine at the office.**

Which means one of:

- **The default provider becomes a frontier model.** Then there is no tunnel
  in the request path, nothing local to be down, and an always-up API tier is
  worth paying for. That is a policy change more than a technical one, and it
  gets disclosed to residents rather than slipped in.
- **You host a second and third community.** The machine at one office is then
  a single point of failure for towns that do not share that office, and the
  argument in section 3.1 for Postgres is the same argument for a cloud API
  tier. They arrive together.
- **Inference moves to a cloud GPU.** $500 a month, and it gives up the thing
  the project is about. Listed for completeness, not recommended.

One practical note for whenever that day comes: Cloud Run's filesystem is
in-memory, and the archive is now a local SQLite file, so a naive deployment
gets a service whose archive disappears on restart. The script says so when it
finishes. Making it real means either Cloud SQL, which section 2.3 argues
against, or baking a read-only copy of the archive into the container image
and rebuilding on ingest — which is a genuinely good design, cheap, and the
first thing to build if the condition above is ever met.

### 2.3 The database: keep it local, and make it one file

**Short answer: the archive stays on the machine running inference, in SQLite.
Postgres is the answer to a different question, and that question is Part 3.**

An earlier version of this section argued the opposite, and it is worth saying
why it was wrong rather than quietly editing it. The argument for Cloud SQL was
that Postgres replaces three things at once: the vector index, the in-memory
BM25 index rebuilt at every process start, and the metadata filtering done in
Python. All three of those were real problems. None of them required a server.

SQLite's FTS5 is an on-disk keyword index with BM25 built in, maintained by the
database through triggers rather than rebuilt by the application. Typed columns
and indexes do the filtering. The embeddings sit in the same file. That is the
same three wins, in a file you can copy.

What the cloud database was supposed to buy was availability, and it does not
buy it here. The tunnel already decided that: when the office loses power, the
model is gone, and an archive in Google's data centre has nothing to answer
from. Paying $150-200 a month for a database that is only reachable when the
free one would also have been reachable is paying for a property you do not get.

So the three backends, and the question each one answers:

| Backend | When it is right | What it costs |
| --- | --- | --- |
| **SQLite** (`stores/sqlite_store.py`) | One community, one machine. The default. | Nothing. One file. |
| **Qdrant** (`vector_store.py`) | Deployments that already have an index and should not be converted out from under them. | Nothing, and it is never forced off. |
| **pgvector** (`stores/pgvector_store.py`) | Many communities on shared infrastructure, or one archive large enough that a single machine is genuinely the constraint. | A managed database, and it is worth it at that point. |

`stores/select_backend()` picks between them and says why, so an operator can
ask which archive a deployment is using without starting the app:

```
$ python3 -c "from stores import select_backend; c = select_backend('brookline-ma'); print(c.backend, c.location, '--', c.reason)"
sqlite ./data/brookline-ma/archive.sqlite3 -- default: one file on this machine
```

Two rules keep the default honest. A configured database that will not open is
an error, never a quiet fallback to an empty archive: a service whose claim is
that answers come from the public record cannot serve from a different record
without saying so. And a deployment that already has a Qdrant index keeps it,
because "better default" is not licence to silently read from an empty file on
somebody's next restart. Moving is a decision, made with `stores/migrate.py`.

**When to revisit this.** The brute-force vector scan is fine into the low
hundreds of thousands of passages, which is more than a decade of one town's
meetings. Past that, install `sqlite-vec` (the store loads it automatically if
it is there) before considering Postgres. Move to Postgres when you are hosting
several communities, not when this one gets big.

### 2.3b Backups, which is what a local database actually needs

`stores/backup.py`. The whole point of one file is that protecting it is
mechanical:

```bash
python3 -m stores.backup create --project brookline-ma --keep 14
python3 -m stores.backup list   --project brookline-ma
python3 -m stores.backup verify data/backups/brookline-ma/archive-2026-09-20T02-00-00Z.sqlite3
```

Run the first one from cron at 2am. Three things in it are not obvious and are
worth knowing:

- **The snapshot is taken through SQLite's backup API, not `cp`.** A copy taken
  mid-write is torn, and an archive that restores to a corrupt file is worse
  than no backup at all. The snapshot is also taken out of WAL mode on the way
  out, so the backup really is one file rather than three.
- **Every snapshot is verified by opening it**, running an integrity check and
  counting the passages, and the count goes in the manifest beside it with a
  SHA-256. A backup nobody has opened is not a backup. A snapshot that verifies
  but is empty is recorded as not trustworthy, because an empty archive restores
  to a system that answers nothing.
- **Retention will not delete the last good copy**, whatever `--keep` says, and
  prunes nothing at all if no snapshot verifies. A retention policy that mows
  down the good copies is data loss on a schedule.

Restoring moves the current archive aside rather than overwriting it, and
refuses a snapshot whose hash no longer matches its manifest unless you pass
`--force` and mean it.

Offsite is one flag: `--bucket your-bucket` writes a second copy to Cloud
Storage. At town scale the archive is a few gigabytes, which is about a dollar
a month in nearline storage, and a failed upload never touches the local
snapshot. This is the only part of the database story the cloud is genuinely
better at, and it is the cheap part.

There is no confidentiality to protect here — it is the public record, and
publishing it is the point — so nothing is encrypted. What it needs is
integrity, which is why every snapshot carries a hash and the constitution
hash in force when it was taken. Same chain of custody `community/ledger.py`
keeps for the rules, applied to the facts.

### 2.4 The rest of the Cloud Run work

| Piece | What changes | Effort |
| --- | --- | --- |
| Scheduler | Replace in-process APScheduler with **Cloud Scheduler** hitting `/api/projects/{id}/sync-all`. One trigger, no duplicate ingestion. | 1 day |
| Long ingestion | A decade backfill outlives a Cloud Run request. Move it to a **Cloud Run job**, or a small always-on worker. | 2-3 days |
| Rate limits | The limiter is per-process, so four instances give four times the intended limit. Move to **Memorystore** (Redis). | 1 day |
| Uploaded PDFs | Currently on local disk. Move to **Cloud Storage**. | 1 day |
| Request logs | JSONL on disk today. **Cloud Logging** with a retention policy matching what the privacy policy promises, mirrored from the local file rather than replacing it. Built; see `cloud/logging_sink.py`. | done |
| Secrets | API keys and the tunnel credential into **Secret Manager**, out of `config.json`. | 1 day |
| Embeddings | Loading a sentence-transformer per instance is slow on cold start. Either bake it into the image or move embedding to a small dedicated service. | 2 days |

### 2.5 What it costs

A rough monthly picture for one town, with inference and the archive both
staying on your hardware:

| | |
| --- | --- |
| Cloud Run (scales to zero, town-scale traffic) | $5-20 |
| Cloud Storage for offsite backups, a few GB nearline | ~$1 |
| Secret Manager, Cloud Scheduler | under $5 |
| Memorystore, smallest tier, only if you run multiple instances | ~$35 |
| The database | **$0** |
| **Total, pilot** | **~$10/month** |
| **Total, production** | **~$25/month** |
| Same with Cloud SQL for the archive, as an earlier draft recommended | **+$150-200/month** |
| Same with a GCP L4 GPU instead of local inference | **+$500/month** |

The last two rows are the argument for this architecture, in two numbers. A
town can run this for the price of a couple of coffees a month, and the two
line items that would change that are the two that give up the thing the
project is about.

One-time hardware, for reference: a machine that runs Gemma 3 27B at usable
speed is $3,500-5,000 and lasts years. The GPU row above is $6,000 a year,
forever, for less control.

---

## Part 3 — Beyond one town

### 3.1 Multi-community hosting

The platform is already community-agnostic: a new deployment is a
`community.yaml`, a constitution, and a source list. Tenancy is now built
(`tenancy.py`, `TENANCY.md`): every community gets its own constitution, its own
archive, its own evaluation set and its own keys, and the isolation check raises
rather than returning false, so a bug that crosses communities stops the request
instead of answering from the wrong town's record.

**This is where Postgres comes back.** With SQLite, twelve communities is twelve
files on one machine, which works and is genuinely fine up to the point where
you want them on separate machines, or want one of them to survive the others.
`project_id` is already on every row and `COMMUNITY_DB_URL` already switches the
backend per project, so moving the first town is a DSN and a
`python3 -m stores.migrate` run. Do it when hosting forces it, not before.

The interesting part is not technical. It is that **each community keeps its own
constitution, its own corpus, its own evaluation set, and its own release
history**, while sharing infrastructure. Brookline and Cambridge can disagree
about what the assistant should do and both be right.

### 3.2 Shared adapters, separate records

Several towns share the civic reasoning problem and share none of the facts. A
QLoRA adapter trained on constitution-following behavior transfers; a corpus does
not. A shared adapter library with per-community retrieval is the natural shape,
and it is how a small community gets the benefit of a large one's training work.

### 3.3 The API as civic infrastructure

The gateway already exposes the public record with real filters. The point of
that is applications nobody on this project writes: a "what happened at last
night's meeting" newsletter, a bylaw search on the town website, a student
project, a journalist's tooling. Every one of them using the same retrieval
layer, the same citations, and the same constitution.

That is the thing that makes this infrastructure rather than a chatbot.

---

## What is done, and what is next

Everything in Part 1 and most of Part 2 exists now. The honest summary:

| | |
| --- | --- |
| Provider comparison in the evals | **done** — `second_opinion.py`, and retrieval runs once and is shared, so the comparison is of models rather than of luck |
| Record status on ingestion | **done** — `knowledge/status.py`. Discussion is never reported as a decision |
| Constitution ledger | **done** — `community/ledger.py`, `LEDGER.md`. Hash chain, N-of-M signatures, tamper detection |
| Multi-community tenancy | **done** — `tenancy.py`, `TENANCY.md` |
| Precomputed common answers | **done** — `precompute.py` |
| The local archive and its backups | **done** — `stores/sqlite_store.py`, `stores/backup.py` |
| Cloud Run deployment | **ready, not run** — `deploy/cloudrun.sh`, with account guards |
| **The actual archive** | **not done, and it is the only thing standing between this and being useful** |

### The next four things, in order

1. **Build the Brookline archive.** Five hundred meetings, backfilled and
   verified. See `ARCHIVE_BUILD.md` for what the process actually looks like,
   what it costs in time and disk, and what to check afterwards. This is mostly
   not engineering, and nothing after it is trustworthy without it. A week of
   wall-clock, a day or two of attention.

2. **Write 200 evaluation questions against the real archive.** Not synthetic
   ones. Real questions residents ask, with the answer and the citation that
   proves it. Until this exists, every claim in this document about local models
   being good enough is a guess. The eval harness has been waiting for it since
   Part 1. Two to three days, and it is the highest-value two days in the
   project.

3. **Republish the console against the real archive.** `deploy/netlify.sh`,
   which builds the frontend against the tunnel URL, checks the two agree, and
   publishes a draft before it will touch production. The API stays where it
   is. An hour. Cloud Run is not step 3 and is not step 9; section 2.2b says
   what would make it step anything.

4. **Set up the nightly backup and one restore drill.** The cron line is in
   §2.3b. Then actually restore a snapshot into a scratch directory and ask it
   a question. A backup nobody has restored is a hypothesis.

### After that, in rough order of value

- **The question log as a product.** `precompute.py` already mines the request
  log for repeated questions. Publishing "what residents asked this month",
  with the answers and citations, is a civic artifact nobody else can make.
- **Speaker identification.** Transcripts give you turns; matching them to
  named board members turns "someone said" into "Member Ortiz said" across the
  whole archive, and makes a decade of votes searchable by who cast them.
- **The re-sync gap for uploaded PDFs.** `ingest_source_background` has no
  `PDF_UPLOAD` branch, so re-syncing an uploaded document indexes nothing. Small
  bug, real one.
- **Training**, only once the gate in `training/README.md` is met — which is to
  say, only once step 2 above says fine-tuning would beat better retrieval.
  Retrieval has beaten parameters at every decision point in this project so
  far, and it will probably beat them here too.
- **A second community.** Cambridge, or any town with a YouTube channel and a
  clerk who posts agendas. The tenancy is built; running it is how you find out
  whether the architecture survives contact with a second set of conventions.

### What not to do next

Do not migrate to Postgres. Do not add a managed database. Do not move
inference to a cloud GPU. Each of those is a real option at a scale this project
is not at, and taking any of them now costs money and control in exchange for
capability that would sit unused. The system is not slow, and the archive is not
big. The archive is *empty*, and that is step 1.
