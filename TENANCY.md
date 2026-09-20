# Many Communities, One Deployment

Running Brookline and Cambridge on the same server, without either one having
to accept the other's rules.

---

## The point

Density is not the point. Plenty of software can put ten customers on one box.

The point is that **each community keeps its own constitution, its own corpus,
its own evaluation set, its own ratifiers and its own release history**, while
sharing infrastructure. Brookline and Cambridge can disagree about whether the
assistant should help a resident draft public testimony, and both be right.

A tenancy model that collapsed them onto one set of rules would defeat the
project. So the rule here is stricter than ordinary multi-tenancy:

> **Nothing is shared by default except the code.**

A community's constitution falls back to the deployment's only until they adopt
their own, and while it does, the system says so out loud rather than letting a
resident believe they are reading their own town's rules.

---

## If you run one community

Do nothing. There is no tenants file, no configuration, no concept to learn.
Every project directory becomes its own tenant automatically and every request
belongs to it.

The rest of this document is for the case where you host several.

---

## Adding a second community

```yaml
# tenants.yaml
single_tenant: false

tenants:
  - id: brookline
    project_id: brookline-ma
    community: "Brookline, MA"
    hostnames:
      - brookline.civicai.org
      - ai.brooklinema.gov
    branding:
      display_name: "Brookline Community AI"
      primary_color: "#0f766e"
      operator: "Brookline Interactive Group"
    quota:
      requests_per_minute: 60

  - id: cambridge
    project_id: cambridge-ma
    community: "Cambridge, MA"
    hostnames: [cambridge.civicai.org]
    path_prefix: /cambridge
```

Then give each community its own governance:

```bash
python3 -m tenancy scaffold brookline
```

That copies the default constitution into `data/brookline-ma/constitution/` as
**their** copy, creates their evaluation directory, and prints what to do next.
The copy is deliberate. The moment Brookline amends it, their ledger diverges
from everyone else's, which is exactly what is supposed to happen.

---

## How a request finds its community

Four signals, in order of specificity:

| Signal | Use it for |
| --- | --- |
| An explicit tenant header | Internal tooling and tests |
| The project id | API calls that already name a project |
| The hostname | How residents actually arrive |
| A path prefix | Several communities on one domain |

Hostname is the one that matters in practice. A resident at
`brookline.civicai.org` never sees that Cambridge exists.

A wildcard entry like `*.demo.civicai.org` lets you add a community by creating
its directory, with no change to the tenants file.

If several communities are configured and none of the signals match, the request
resolves to **nothing** rather than to a default. Guessing which town a resident
meant is worse than asking.

---

## Isolation

Every filesystem path a request touches is checked against the requesting
tenant's directory, and the check **raises** rather than returning false:

```python
tenant.assert_contains(path)   # IsolationError if outside
```

Returning a boolean invites a caller to forget the check. Reading another
community's municipal archive is not a recoverable mistake, so this fails closed
and loudly. Path traversal, absolute paths elsewhere, and another tenant's
directory are all refused, and each has a test.

When you move to PostgreSQL, `project_id` is on every row and row-level security
turns this from a convention into something the database enforces. Until then,
the checks in `tenancy.py` are the guarantee.

---

## What each community owns

```
data/brookline-ma/
    config.json          their settings, model, provider
    constitution/        their rules, their ledger, their ratifiers
    evals/               their definition of "good"
    archive.sqlite3      their archive, one file, theirs alone
    sync/                their channel sync state
    logs/                their request metadata
    precomputed.json     their cached common answers
```

Everything in that tree belongs to one community. Nothing outside it is theirs.

### Their constitution

`tenant_constitution()` prefers `data/<project>/constitution/`. If they have not
adopted their own, the deployment default is used **and the result carries a
warning saying so**, which surfaces in the transparency panel. A community on
shared infrastructure running someone else's rules is a fact residents are
entitled to.

Each community's ledger is independent. Brookline can be on version 1.4 with
five ratifiers while Cambridge is still on the unratified draft.

### Their evaluation set

`tenant_eval_files()` prefers `data/<project>/evals/`. Two communities sharing
an evaluation set are not really separate deployments, since "good" would be
defined once for both. The console flags it.

---

## Fair sharing

Per-tenant quotas, so one community's traffic cannot starve another's on
hardware they are both paying for:

```yaml
quota:
  requests_per_minute: 60
  requests_per_day: 5000
  max_corpus_chunks: 200000
  max_sources: 50
  inference_enabled: true
```

Zero means unlimited. The defaults are generous, because the common case is a
handful of communities on one box rather than a marketplace.

`inference_enabled: false` is the useful one during onboarding: a community can
ingest their archive and browse it before anyone pays for generation.

---

## What this does not solve

**Shared inference capacity.** One GPU serving three towns is still one GPU.
Quotas keep it fair; they do not make it faster. Past a few communities you need
a second machine or a bigger one, and the roadmap's recommendation still holds:
each community running its own hardware is the architecture that scales, because
it scales by addition rather than by contention.

**Shared operator trust.** Every community on a deployment trusts whoever runs
it. The constitution ledger narrows what they must take on faith, since a
tampered constitution is detectable, but it does not eliminate the operator.
A community that wants to remove that trust runs its own instance, and the
platform is designed so that it can.

**Cross-community search.** Deliberately absent. "What did Cambridge decide
about this?" is a reasonable question and a different product. Answering it
would mean one assistant reading two communities' records, which is the exact
boundary this module exists to hold.

---

## Operating several communities

```bash
python3 -m tenancy                       # what this deployment serves
python3 -m tenancy scaffold <tenant>     # give one its own governance
curl /api/tenants                        # the same, over the API
curl /api/tenants/<id>/governance        # whose rules are in force, and why
```

Per community, check the things that differ:

```bash
python3 -m community.ledger verify --directory data/brookline-ma/constitution
python3 -m evals.run_evals --project brookline-ma --retrieval-only
```

A release is per community, not per deployment. Brookline adopting version 1.4
is Brookline's release, with Brookline's evaluation results, published to
Brookline's residents.

---

## Shared adapters, separate records

Several towns share the civic reasoning problem and share none of the facts.

A fine-tuned adapter that teaches constitution-following behaviour **transfers**
between communities. A corpus does not, and must not. That asymmetry is the
shape of the eventual answer: a shared adapter library with per-community
retrieval, so a small town gets the benefit of a large one's training work
without either one seeing the other's records.

The scaffolding for that is in `training/`, and the gate in its README applies
per community: a frozen evaluation set of at least 200 cases, written against
that community's own records.
