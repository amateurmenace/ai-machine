# Moving this to your own machine

The work in this repository was built in a cloud development session. Nothing
about it depends on that: it is a normal Python project, everything is
committed, and a fresh clone passes the full test suite with no network access
and no API keys. This document is how to pick it up locally.

There is also a prompt at the bottom you can paste into Claude Code on the
other machine, which will do most of this for you.

---

## What is and is not in git

**In git:** all the code, all the tests, all the documentation, the
constitution and its ledger, the evaluation sets, the deployment scripts, and
example versions of every config file.

**Not in git, by design:**

| | |
| --- | --- |
| `.env` | API keys, the tunnel token. Template: `.env.example` |
| `community.yaml` | who the community is and what it ingests. Template: `community.example.yaml` |
| `tenants.yaml` | only if you run several communities. Template: `tenants.example.yaml` |
| `data/` | the archive, sync state, logs, uploads. Rebuilt by ingestion |
| `constitution/signers.json` | ships empty. Real ratifier keys go here, and **must** be added before adopting anything |

So a clone gives you a working system with an empty archive, which is exactly
what you want: the archive gets built on the machine that will hold it.

---

## Doing it by hand

```bash
git clone https://github.com/amateurmenace/ai-machine.git
cd ai-machine
git checkout claude/neighborhood-ai-update-6s4s38

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

./run_tests.sh          # ~1,000 assertions, no GPU, no network, no keys
```

If the tests pass, the transfer is complete — that suite covers retrieval,
citations, the gateway, the ledger, tenancy, the archive backends, backups and
the backfill.

Then:

```bash
cp .env.example .env                      # fill in what you have
cp community.example.yaml community.yaml  # name the community, list the sources
python3 -m scripts.bootstrap_community community.yaml
python3 app.py                            # http://localhost:8000
```

The archive is at `data/<project_id>/archive.sqlite3` and does not exist until
you ingest something. `ARCHIVE_BUILD.md` is the guide for filling it.

## A different Claude account is not a problem

The repository is under your personal GitHub account
(`amateurmenace/ai-machine`), so any machine signed in as you can clone and
push it. Claude Code on the other machine authenticates as whoever is signed in
there; it does not need access to this session or the account that ran it.

What does not transfer is this conversation's history. The prompt below carries
the parts that matter.

---

## Things worth knowing before you start

**The database is local now, on purpose.** The archive is one SQLite file next
to the machine running inference. An earlier draft of `ROADMAP.md` recommended
Cloud SQL; §2.3 explains why that was wrong and what changed. There is nothing
to provision and nothing to pay for.

**Back it up before you care about it, not after.**

```bash
python3 -m stores.backup create --project <id> --keep 14
```

**Deployment is written but has never been run.** `deploy/cloudrun.sh` has
account guards that refuse to deploy to an organization or to the wrong
account. It has not been executed because the development environment had no
access to any cloud control plane. Run it from your own machine, signed in as
your personal account, and read what it prints before confirming.

**LM Studio must not face the internet directly.** The tunnel terminates at the
gateway. This is in `TUNNEL_SETUP.md` and it matters.

---

## The prompt

Paste this into Claude Code on the other machine, in an empty directory. It is
written to be read by a session that knows nothing about this project.

```
I'm picking up a project I've been building called the Civic AI Engine.

  https://github.com/amateurmenace/ai-machine
  branch: claude/neighborhood-ai-update-6s4s38

Clone it, check out that branch, make a virtualenv, install requirements.txt,
and run ./run_tests.sh. Roughly a thousand assertions across thirteen suites;
all of it passes with no network, no GPU and no API keys. If it does, the
transfer worked.

Then read HANDOFF.md, SYSTEM_GUIDE.md and ROADMAP.md. Everything below is a
summary a previous session wrote — treat it as a starting point and check it
against the code rather than trusting it.

WHAT IT IS

A community-owned AI for civic records. A town's public record is ingested into
a local archive; questions are answered only from that archive, with citations,
under a published constitution whose amendments are recorded in a signed hash
chain. I work at Brookline Interactive Group, which holds the YouTube recording
of every Brookline Select Board and School Committee meeting plus many
subcommittees. That channel is the corpus.

HOW IT IS DEPLOYED

  residents → civicaiengine.org, create.neighborhoodai.org,
              neighborhood-ai.netlify.app (Netlify: the public site, built
              with REACT_APP_API_URL=none, so it knows there is no API)

  this machine → FastAPI on 127.0.0.1:8400 (.env) + archive.sqlite3
                 + LM Studio on the GPU. No tunnel.

The public site is the landing page, the guide and the rules; its console
says the assistant is not open to the public. The same build, served by the
API here, is the working console: http://127.0.0.1:8400. A tunnel would put
residents' questions in front of the model; it is a decision for later, and
the handoff section below says what it needs.

DECISIONS ALREADY MADE — don't relitigate these unless something is actually
wrong, in which case say so plainly:

- The archive is one local SQLite file next to the inference machine, not a
  cloud database. ROADMAP.md §2.3 has the reasoning; §2.3b covers backups.
  Postgres is for hosting several communities later, not for making this one
  bigger.
- Inference runs locally in LM Studio. Frontier models exist as an explicit,
  disclosed second opinion, never as the silent default.
- The API stays on this machine too. Cloud Run is written (deploy/cloudrun.sh)
  and deliberately unused; ROADMAP.md §2.2b gives the one condition that would
  change that.
- LM Studio must never face the internet directly. The tunnel terminates at
  the gateway.
- Any cloud deployment goes to my personal account (swalter4669), never the
  Hope Group organization. Both deploy scripts enforce this and will refuse.
- These hostnames are real, in use, and must not be renamed or "cleaned up":
  neighborhood-ai.netlify.app, neighborhood.weirdmachine.org,
  neighborhoodai.org, create.neighborhoodai.org.
- constitution/signers.json ships empty on purpose. Nothing gets adopted into
  the ledger until real ratifier keys are in it.

WHAT TO DO, in the order ROADMAP.md argues for

1. Build the real archive — roughly 1,450 Brookline meetings, which YouTube
   releases about sixty a night; the top of ARCHIVE_BUILD.md says why. It is
   the guide, scripts/backfill_archive.py is the tool. ALWAYS --dry-run first
   and show me the output: if a subcommittee's titles don't parse, that is much
   cheaper to fix before a six-hour run than after. Set YOUTUBE_API_KEY if I
   have one; yt-dlp works without it. The script is resumable, so interrupting
   it is safe.
   When it finishes, read data/<project>/backfill-report.json and tell me the
   meetings_without_transcripts count — those are real holes in the public
   record and I need to know about them, not have them rounded away.

2. Write ~200 real evaluation questions against that archive. Questions
   residents actually ask, each with the answer and the citation that proves
   it. Until this exists every claim about local models being good enough here
   is a guess. This is the highest-value work left and it is mostly not coding.

3. Republish the console: ./deploy/netlify.sh --no-api (the public site, as
   deployed on 2026-09-22), or --api-url <tunnel-url> the day there is a
   tunnel. The CLI is installed and signed in here, and frontend/ is linked to
   the neighborhood-ai site. It publishes a draft unless --prod is typed
   deliberately. civicaiengine.org is on that site as an alias, waiting on DNS
   at Squarespace: A @ 75.2.60.5, CNAME www neighborhood-ai.netlify.app.

4. Nightly backup plus one restore drill:
     python3 -m stores.backup create --project <id> --keep 14
   Then actually restore a snapshot somewhere harmless and ask it a question.

THE API IS NOT ON THE INTERNET, AND STAYS OFF IT UNTIL I SAY SO

It binds to loopback (HOST in .env) and there is no tunnel. Two things were
fixed before it could ever be exposed. app.py's CORS list now includes
create.neighborhoodai.org, which serves the console alongside
neighborhood-ai.netlify.app. And everything under /api that changes anything
is refused from any other machine unless the request carries
COMMUNITY_ADMIN_TOKEN (api/admin_guard.py); before that, one anonymous DELETE
removed the archive. "Any other machine" includes another website open in
this machine's browser, and a DNS-rebinding page: both are checked (Origin and
Host). Residents' questions never need the token. The console enters it on its
admin page and keeps it in that browser. Do not run a tunnel to this API
without asking me. Before one exists, /api/chat and /api/.../second-opinion
need the rate limits the gateway already has: the second spends the project's
frontier-model credit on whoever asks.

HOUSE RULES

Work on the branch above. Run ./run_tests.sh before pushing. Don't open a pull
request unless I ask. Don't commit the archive or anything under data/ — it's
gitignored and it's hundreds of megabytes.

Start with step 1, and show me the dry run before ingesting anything.
```
