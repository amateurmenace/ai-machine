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
the changes below, and the first is not optional. The rest are each one
environment variable, and each one falls back to the local behavior when it is
not set, so they can be done one at a time.

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

There is a second way, and it is the one to use for a value that belongs to a
project rather than to the service. Any configuration field or environment
variable may hold a reference instead of a value:

```json
{
  "api_key": "sm://projects/YOUR_PROJECT/secrets/anthropic-key/versions/latest",
  "local_auth_header": "Authorization: Bearer sm://projects/YOUR_PROJECT/secrets/tunnel/versions/latest"
}
```

The reference is resolved at the moment the provider is built and cached for
the life of the process, so the key is never written to `config.json`, never
appears in a backup of it, and never lands in a support thread. A field without
the `sm://` prefix is used exactly as written, which is what a community
keeping its key in an environment variable on its own machine wants.

The service account needs the Secret Manager Secret Accessor role, and the
short form `sm://anthropic-key` works when `GOOGLE_CLOUD_PROJECT` is set. A
reference that cannot be resolved leaves the value empty and logs the reason;
it is never passed along as if it were a key.

### 5. Uploaded PDFs in Cloud Storage

Cloud Run's filesystem is in memory, so a PDF a resident uploaded is gone at
the next restart, along with the citations pointing at it.

```bash
gcloud storage buckets create gs://YOUR_PROJECT-uploads --location=us-central1
gcloud run services update community-ai --region us-central1 \
  --set-env-vars COMMUNITY_STORAGE_BUCKET=YOUR_PROJECT-uploads
```

The service account needs Storage Object Admin on the bucket. Sources that were
ingested before the bucket existed keep their `file://` URIs and are still read
from local disk, so switching does not orphan them.

### 6. Rate limits in Memorystore

The limiter counts in one process. With four instances a community that
configured sixty requests a minute is serving two hundred and forty.

```bash
gcloud redis instances create community-ai --size=1 --region=us-central1
gcloud run services update community-ai --region us-central1 \
  --vpc-connector YOUR_CONNECTOR \
  --set-env-vars COMMUNITY_REDIS_URL=redis://10.0.0.3:6379/0
```

Needs `pip install redis` in the image and a VPC connector, since Memorystore
has no public address. Redis becoming unreachable does not fail requests: the
gateway falls back to per-process limits, says so in the logs, and picks the
shared counter back up on its own when Redis answers again.

### 7. Request logs in Cloud Logging

The JSONL log under `data/<project>/logs` is what the usage statistics read, so
it stays. This mirrors the same records somewhere they survive the instance.

```bash
gcloud run services update community-ai --region us-central1 \
  --set-env-vars COMMUNITY_CLOUD_LOGGING=true
```

The privacy rules do not change and are applied again on the way out: what is
written is operational metadata plus a salted hash of the question, and the
question text only if the project set `log_question_text`. Cloud Logging
enforces retention on the log bucket, which this service cannot set, so each
entry carries the project's `log_retention_days` and you set the bucket to
match:

```bash
gcloud logging buckets update _Default --location=global --retention-days=30
```

Needs the Logs Writer role, and `pip install google-cloud-logging` in the image.

---

## Environment variables

Every one of these is optional, and unset means the local behavior that a
community running on one machine depends on. Nothing here is required to run
this project.

| Variable | Turns on | Also needs |
| --- | --- | --- |
| `COMMUNITY_REDIS_URL` | Rate limits counted in Redis, shared by every instance | `pip install redis`, a VPC connector |
| `COMMUNITY_STORAGE_BUCKET` | Uploaded PDFs in Cloud Storage | `pip install google-cloud-storage`, Storage Object Admin |
| `COMMUNITY_STORAGE_PREFIX` | Object prefix inside that bucket (default `uploads`) | |
| `COMMUNITY_CLOUD_LOGGING` | Request records mirrored to Cloud Logging | `pip install google-cloud-logging`, Logs Writer |
| `COMMUNITY_CLOUD_LOG_NAME` | Log name (default `community-ai-requests`) | |
| `GOOGLE_CLOUD_PROJECT` | The project short `sm://` references resolve in | |
| `COMMUNITY_DATA_ROOT` | Where local uploads and logs live (default `./data`) | |
| `sm://` in a config field | That value read from Secret Manager | `pip install google-cloud-secret-manager`, Secret Accessor |

None of these client libraries are in `requirements.txt`. A community server
should not have to install four Google packages to answer a question about a
zoning bylaw, and a missing one degrades to the local backend with a line in
the log saying what to install.

## Check what is actually running

The fallbacks are what make one machine work, and they are also what makes a
misconfigured cloud deployment look exactly like a working local one. Ask:

```bash
curl https://your-service.run.app/api/admin/cloud-status
```

```json
{
  "cloud_configured": true,
  "degraded": ["storage"],
  "rate_limits": {"backend": "redis", "active": true},
  "storage": {
    "backend": "local",
    "configured": true,
    "active": false,
    "detail": "COMMUNITY_STORAGE_BUCKET names brookline-uploads, but uploads are going to local disk, which Cloud Run does not keep.",
    "remedy": "Install it with: pip install google-cloud-storage ..."
  }
}
```

`degraded` is the list to watch. Empty means every backend you configured is
the one actually serving.

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
