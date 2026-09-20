# Deploying to Google Cloud

Two deployments, for two different purposes. Do not confuse them.

---

## A test instance, in one command

```bash
./deploy/cloudrun.sh YOUR_GCP_PROJECT_ID
```

That builds the container with Cloud Build and deploys it to Cloud Run. Takes
about ten minutes the first time, mostly the React build and the embedding
model. Re-running updates the service in place.

You need `gcloud` installed and authenticated, and billing enabled on the
project. Nothing else.

When it finishes you get a URL. Check it:

```bash
curl https://your-service-xyz.run.app/healthz
```

### What you get, and what you don't

You get the console, the gateway, the retrieval stack, the constitution ledger,
and the API, all reachable on a public URL. Enough to click around, create a
project, and see the whole thing work.

**You do not get a model.** The image contains no weights on purpose. Point a
project at your own LM Studio server over a tunnel, which is the recommended
shape, or set a frontier key to try it quickly:

```bash
gcloud run services update community-ai --region us-central1 \
  --set-env-vars ANTHROPIC_API_KEY=sk-ant-...
```

**You do not get persistence.** Cloud Run's filesystem is in memory. Projects,
the ingested archive and the sync state live under `data/`, and all of it
disappears when the instance restarts, which Cloud Run does whenever it feels
like it. That is fine for a look. It is not fine for a town.

The deploy script sets `--max-instances 1` and `COMMUNITY_SYNC_ENABLED=false`
deliberately. A second instance would take a second copy of the keyword index
and run a second sync timer, and two timers means the same meeting ingested
twice.

---

## A production deployment

The test instance is a demo of the code, not an architecture. Production needs
four changes, and the first is not optional.

### 1. Move the database to Cloud SQL

This is the blocker. The embedded vector store writes to a local directory that
Cloud Run does not keep, and takes an exclusive lock that caps you at one
instance. `ROADMAP.md` has the full argument; the summary is that Cloud SQL for
PostgreSQL with pgvector replaces three things at once, the vector store, the
Python metadata filtering, and the in-memory keyword index that is the thing
actually pinning you to one machine.

```bash
gcloud sql instances create community-ai \
  --database-version=POSTGRES_16 --tier=db-custom-2-7680 \
  --region=us-central1 --storage-size=100GB --storage-auto-increase
gcloud sql databases create community --instance=community-ai
```

Then enable the extension and connect Cloud Run over the Cloud SQL connector
rather than a public IP.

Until that work is done, run this on a single Compute Engine VM with a
persistent disk instead of Cloud Run. That is a perfectly good deployment for
one community and it needs no code changes at all.

### 2. Keep inference on your own hardware

A GPU on Google Cloud is roughly $500 a month, forever, for capability you can
buy outright for about $3,500. It also gives up the property this project
exists for.

Run LM Studio at your office, expose it through a Cloudflare tunnel, and point
the project's `lmstudio_base_url` at the tunnel hostname with the tunnel's
credential in `local_auth_header`.

The tunnel must terminate at this gateway, never at LM Studio. LM Studio has no
authentication, no rate limits and no logging.

### 3. Drive sync from Cloud Scheduler

With more than one instance, the in-process scheduler duplicates work. Turn it
off and let one external trigger do it:

```bash
gcloud scheduler jobs create http community-ai-sync \
  --schedule="0 */6 * * *" \
  --uri="https://your-service.run.app/api/projects/YOUR_PROJECT/sync-all" \
  --http-method=POST --oidc-service-account-email=YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com
```

### 4. Secrets in Secret Manager

API keys and the tunnel credential do not belong in `config.json` or in
environment variables set on the command line.

```bash
echo -n "sk-ant-..." | gcloud secrets create anthropic-key --data-file=-
gcloud run services update community-ai --region us-central1 \
  --set-secrets ANTHROPIC_API_KEY=anthropic-key:latest
```

---

## Continuous deployment

`cloudbuild.yaml` builds, tests, and deploys. Point a GitHub trigger at it and
every push to your branch deploys.

It runs two checks before deploying, and one of them is unusual enough to call
out: **the constitution ledger is verified in the pipeline.** A commit that
edits an adopted constitution version fails the build. That is the right place
for the check, because a runtime warning is something people learn to ignore and
a red build is not.

---

## Costs, for one town

| | Monthly |
| --- | --- |
| Cloud Run, scales to zero, town traffic | $5-20 |
| Cloud SQL, 2 vCPU / 7.5GB / 100GB | $150-200 |
| Cloud SQL, `db-f1-micro`, for a pilot | ~$15 |
| Storage, Secret Manager, Scheduler | under $5 |
| **Production total, inference stays local** | **~$200** |
| The same with a Cloud GPU instead | **~$700** |

---

## Troubleshooting

**Cold starts are slow.** First request after a scale-to-zero loads the
embedding model. Set `--min-instances 1` if that matters, at roughly $15 a month.

**Out of memory.** The keyword index holds the corpus. Raise `--memory`, or
move to Postgres, which is the real fix.

**The archive vanished.** Expected on Cloud Run without Cloud SQL. See above.

**The model server is unreachable.** Run the connection test; it distinguishes a
stopped LM Studio from a broken tunnel:

```bash
curl -X POST https://your-service.run.app/api/projects/YOUR_PROJECT/test-connection
```

**The build fails on the ledger step.** Someone edited an adopted constitution
version in place. That is what the check is for. Adopt a new version instead:

```bash
cp constitution/constitution-v1.0.md constitution/constitution-v1.1.md
# edit v1.1, then:
python3 -m community.ledger seal 1.1 --status draft --summary "what changed"
```
