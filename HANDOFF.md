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

Paste this into Claude Code on the other machine, in an empty directory:

```
I'm picking up a project I've been building called the Civic AI Engine. It's
at https://github.com/amateurmenace/ai-machine on the branch
claude/neighborhood-ai-update-6s4s38 — clone it, check out that branch, set up
a virtualenv, install requirements.txt, and run ./run_tests.sh. All of it
should pass without a network, a GPU, or any API keys.

Then read HANDOFF.md, SYSTEM_GUIDE.md and ROADMAP.md and tell me where things
stand and what you'd do first.

Background so you don't have to infer it:

It's a community-owned AI for civic records. A town's public record is ingested
into a local archive; questions are answered only from that archive, with
citations, under a published constitution whose amendments are recorded in a
signed hash chain. I work at Brookline Interactive Group, which has the YouTube
recording of every Brookline Select Board and School Committee meeting plus
subcommittees, and that channel is the corpus.

Decisions already made, which I don't want relitigated unless something is
actually wrong:

- The archive is a local SQLite file next to the inference machine, not a cloud
  database. ROADMAP.md §2.3 has the reasoning. Postgres is for hosting several
  communities later.
- Inference runs locally in LM Studio, reachable over a Cloudflare tunnel.
  Frontier models are available as an explicit, disclosed second opinion, not
  as the default path.
- The console is a static React app on Netlify; the API, the archive and the
  model all live on my machine behind a Cloudflare tunnel. deploy/netlify.sh
  publishes the console. Cloud Run is written (deploy/cloudrun.sh) but is
  deliberately not the current deployment — ROADMAP.md §2.2b says what would
  change that.
- Any cloud deployment goes to my personal account (swalter4669), never the
  Hope Group organization. Both deploy scripts enforce this.
- These hostnames are real and must not be renamed: neighborhood-ai.netlify.app,
  neighborhood.weirdmachine.org, neighborhoodai.org, create.neighborhoodai.org.

What's next, in the order ROADMAP.md argues for:

1. Build the real archive — roughly 500 Brookline meetings. ARCHIVE_BUILD.md is
   the guide; scripts/backfill_archive.py is the tool. Start with --dry-run and
   check that the board names and dates parse correctly before committing to a
   long run.
2. Write ~200 real evaluation questions against that archive.
3. Republish the console with deploy/netlify.sh once the archive is real.
4. Set up nightly backups and do one restore drill.

Start with step 1, and show me the dry run before ingesting anything.
```
