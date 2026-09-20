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

### 2.2 The recommended architecture: cloud front, local brain

**Keep inference on your own hardware. Move everything else to Google Cloud.**

```
             residents on the web
                      │
                      ▼
      ┌───────────────────────────────┐
      │  Cloud Run                    │   the app: gateway, RAG, API
      │  (scales to zero, autoscales) │
      └───────────┬───────────────────┘
                  │
      ┌───────────┴───────────┐
      │                       │
      ▼                       ▼
  Cloud SQL              Cloudflare tunnel
  PostgreSQL + pgvector          │
  the archive                    ▼
                          LM Studio at BIG
                          Gemma on your GPU
```

Why this shape and not the obvious alternatives:

- **The web tier belongs in the cloud.** It needs to be up at 2am, survive a
  power cut at the office, and handle a traffic spike when a meeting makes the
  news. Cloud Run does that for roughly the cost of a sandwich per month at town
  traffic, and scales to zero between questions.
- **Inference belongs on your hardware.** A GPU on GCP is about $500/month
  forever for capability you can buy outright for $3,500. More importantly,
  moving inference to Google's servers gives up the property the project is
  about. The tunnel support built for exactly this already works.
- **The archive belongs in a managed database.** A town's public record should
  be backed up by someone whose job that is, with point-in-time recovery, not
  living on a disk in a closet with the model.

If the office network is genuinely too unreliable to serve inference, the
fallback is a frontier provider with the switch clearly disclosed to residents,
not a cloud GPU. That is cheaper and more honest than pretending a GCP L4 is
"local".

### 2.3 The database: change it, and change it to PostgreSQL

**Short answer: no, Qdrant embedded is not the right choice for Google Cloud.
Move to Cloud SQL for PostgreSQL with the pgvector extension.**

This also happens to be what the community-owned AI guide recommends, and its
reasoning is the right reasoning: one database holds structured metadata,
conventional filters, full-text search, and embeddings together.

The specific argument for this codebase is stronger than the general one.
Postgres does not replace one component here. It replaces **three**:

| Today | With Postgres |
| --- | --- |
| Qdrant for vectors | `vector` column with an HNSW index |
| Python metadata filtering over the whole corpus | `WHERE body = 'Select Board' AND meeting_date >= '2019-01-01'` |
| An in-memory BM25 index rebuilt per process | `tsvector` + `ts_rank_cd`, maintained by the database |

That third row is the one that matters. The in-memory keyword index is the piece
that pins the app to one instance, costs a cold-start rebuild, and caps the
corpus at 200,000 chunks. Postgres full-text search is an index on disk,
incrementally maintained, shared by every instance, and it handles phrase
queries and the exact-identifier matching that made hybrid search necessary in
the first place.

One query does the whole hybrid retrieval:

```sql
WITH dense AS (
  SELECT id, RANK() OVER (ORDER BY embedding <=> %(q_vec)s) AS rank
  FROM chunks WHERE project_id = %(project)s AND (%(body)s IS NULL OR body = %(body)s)
  ORDER BY embedding <=> %(q_vec)s LIMIT 40
),
sparse AS (
  SELECT id, RANK() OVER (ORDER BY ts_rank_cd(tsv, websearch_to_tsquery(%(q)s)) DESC) AS rank
  FROM chunks WHERE project_id = %(project)s AND tsv @@ websearch_to_tsquery(%(q)s) LIMIT 40
)
SELECT id, SUM(1.0 / (60 + rank)) AS score
FROM (SELECT * FROM dense UNION ALL SELECT * FROM sparse) fused
GROUP BY id ORDER BY score DESC LIMIT 24;
```

That is the same reciprocal-rank fusion the Python code does now, executed where
the data lives.

**Why not the alternatives:**

- **AlloyDB** is faster and roughly two to three times the cost. Worth it above a
  few million vectors. A town has tens of thousands. Revisit if you host many
  communities.
- **Vertex AI Vector Search** is a managed ANN index with a minimum spend in the
  hundreds per month for an always-on endpoint, and it keeps vectors in a
  different system from your metadata. That re-creates the two-store problem
  Postgres solves.
- **Qdrant Cloud or self-hosted Qdrant server** is a fine vector database with
  better pure-vector performance. But you still need a relational database for
  projects, API keys, sync state and logs, so this means running two. Not worth
  it at this scale.
- **Firestore** has no vector search worth the name for this, and the wrong shape
  for the relational filters civic questions need.

**The migration is contained.** `HybridRetriever` depends on exactly two methods
of the store, `search` and `iter_all_payloads`. A `PgVectorStore` implementing
that interface, plus a re-index, is the whole job. Everything above it, the
citations, the pipeline, the gateway, the evals, is unchanged.

**Effort: 1-2 weeks**, including an ingestion backfill and a schema with proper
indexes on the civic metadata columns.

### 2.4 The rest of the Cloud Run work

| Piece | What changes | Effort |
| --- | --- | --- |
| Scheduler | Replace in-process APScheduler with **Cloud Scheduler** hitting `/api/projects/{id}/sync-all`. One trigger, no duplicate ingestion. | 1 day |
| Long ingestion | A decade backfill outlives a Cloud Run request. Move it to a **Cloud Run job**, or a small always-on worker. | 2-3 days |
| Rate limits | The limiter is per-process, so four instances give four times the intended limit. Move to **Memorystore** (Redis). | 1 day |
| Uploaded PDFs | Currently on local disk. Move to **Cloud Storage**. | 1 day |
| Request logs | JSONL on disk today. Either a Postgres table or **Cloud Logging** with a retention policy matching what the privacy policy promises. | 1-2 days |
| Secrets | API keys and the tunnel credential into **Secret Manager**, out of `config.json`. | 1 day |
| Embeddings | Loading a sentence-transformer per instance is slow on cold start. Either bake it into the image or move embedding to a small dedicated service. | 2 days |

### 2.5 What it costs

A rough monthly picture for one town, with inference staying local:

| | |
| --- | --- |
| Cloud Run (scales to zero, town-scale traffic) | $5-20 |
| Cloud SQL, 2 vCPU / 7.5GB / 100GB SSD | $150-200 |
| Cloud SQL, `db-f1-micro` for a pilot | ~$15 |
| Cloud Storage, Secret Manager, Scheduler | under $5 |
| Memorystore, smallest tier, only if multi-instance | ~$35 |
| **Total, pilot** | **~$30/month** |
| **Total, production** | **~$200/month** |
| Same with a GCP L4 GPU instead of local inference | **+$500/month** |

That last row is the argument for the hybrid architecture, in one number.

---

## Part 3 — Beyond one town

### 3.1 Multi-community hosting

The platform is already community-agnostic: a new deployment is a
`community.yaml`, a constitution, and a source list. What is missing is tenancy.
Postgres gives it for free, with `project_id` on every row and row-level
security.

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

## Suggested order

1. **Provider comparison in the evals.** 2-3 days, and it tells you what
   everything else is worth.
2. **Record status on ingestion.** 2-3 days, fixes the worst civic failure mode.
3. **Backfill the real archive and write 200 evaluation questions.** The long
   pole, mostly not engineering, and nothing after it is trustworthy without it.
4. **Postgres migration.** 1-2 weeks, and it unblocks Google Cloud entirely.
5. **Cloud Run deployment** with local inference over the tunnel. 1 week.
6. **Second opinion button and precomputed common questions.** 1 week, and it is
   what residents will actually notice.
7. **Training**, only once the gate in `training/README.md` is met.

Steps 1 through 3 are worth doing before any cloud work. A faster deployment of
an unmeasured system is not progress.
