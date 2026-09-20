# Governance

How the community AI is governed, and how this constitution is changed.

## Principle

Residents debate understandable rules. Maintainers translate rules into
implementation and tests. Nobody should have to argue about LoRA alpha to
object to how the assistant describes a Town Meeting vote.

## What the community owns

| Layer | Artifact | Where |
| --- | --- | --- |
| Rules | The constitution | `constitution/constitution-v*.md` |
| Knowledge | Source inventory | `knowledge/sources.yaml` |
| Retrieval | Chunking, metadata, ranking | `rag/` |
| Behavior | Training data, adapters | `training/` |
| Definition of good | Frozen evaluation set | `evals/` |
| Access | Gateway and API | `api/` |
| Operations | Deployment, logs, privacy policy | `deployment/` |

The foundation model is deliberately not on that list. It should be
replaceable. If a better open model appears, the community keeps its
constitution, archive, evaluation set, API, and applications.

## Amending the constitution

1. **Propose.** Open an issue describing the behavior you want changed, with at
   least one real transcript of the assistant getting it wrong.
2. **Classify.** A maintainer labels the likely cause: retrieval metadata bug,
   constitution change, new training example, prompt change, or a missing
   evaluation regression test. Most complaints are not constitution changes.
3. **Draft.** If it is a constitution change, open a pull request that adds or
   edits a numbered principle and adds at least one evaluation case that fails
   before the change and passes after it.
4. **Review.** Public comment period. The proposal, the failing transcript, and
   the evaluation case are all public.
5. **Adopt.** On acceptance, bump the version, write a changelog entry, and
   copy the file to a new `constitution-v<major>.<minor>.md`. Never edit an
   adopted version in place.
6. **Release.** Publish the evaluation results for the new version alongside the
   previous one so residents can see what changed and what it cost.

Version numbering: increase the minor version for clarifications and added
principles, the major version when a principle is removed or reversed.

## Issue triage categories

Every behavior report gets exactly one of these labels. The label determines who
does the work.

- `rag-metadata` — the record was indexed with the wrong board, date, page, or
  speaker. Fix ingestion, then backfill.
- `retrieval` — the right passage exists but never reached the model. Fix
  chunking, hybrid weighting, filters, or reranking.
- `constitution` — the written rules do not actually forbid the behavior.
  Amend the constitution.
- `prompt` — the rules forbid it but the assembled request does not convey them.
  Fix the gateway.
- `training-example` — the rules are clear and conveyed, and the model still
  fails. Add critique-and-revision examples.
- `eval-regression` — we fixed this once and it came back. Add a frozen test.

## What stays private

Publishing the repository does not mean publishing everything. These stay
restricted, and the reason is recorded:

- Raw request logs containing resident questions.
- API keys and operator credentials.
- Any source the community is licensed to index but not to redistribute.

Aggregate statistics from logs are public. Question text is not.

## Releases

Each release publishes: the constitution version, the corpus snapshot date, the
model and adapter versions, the evaluation results, and a human-readable note
explaining why behavior changed. Residents should be able to read why
Community AI 1.5 answers differently from 1.6 without reading a diff.
