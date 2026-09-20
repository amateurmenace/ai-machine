# Evaluation

Section 16 of the community-owned AI guide argues that the evaluation set may
become the community's most valuable long-term asset, because it is what makes
any change measurable. A model swap, a constitution amendment, a chunking
change, and a fine-tune are all indistinguishable acts of faith without it.

## The one rule

**Measure retrieval separately from generation.**

```
Bad answer
    ├── Correct source NOT retrieved → RAG problem
    │      (chunking, metadata, hybrid weighting, filters, reranking)
    └── Correct source WAS retrieved → generation problem
           (prompt, constitution, model, fine-tuning)
```

Fixing a prompt when the passage never arrived wastes a week. The runner reports
these two failure classes separately and never merges them into one score.

## Categories

Taken from the guide's table. Every case names one.

| Category | What it tests |
| --- | --- |
| `local_factual` | A fact the record establishes |
| `temporal` | Who or what is current, versus historical |
| `historical` | The state of things at a past date |
| `ambiguous` | Discussion versus adopted action (Principle 4) |
| `conflicting_evidence` | Two sources disagree (Principle 17) |
| `source_absence` | The archive has nothing (Principle 3, 18) |
| `community_disagreement` | Plural views, no fabricated consensus (Principles 6, 19) |
| `attribution` | Who actually said it (Principle 8) |
| `general_ai` | Ordinary capability, e.g. write a function (Principle 13) |
| `writing` | Drafting help |
| `reasoning` | Comparison and analysis |
| `multilingual` | Explaining policy in another language (Principle 12) |

## Case format

One JSON object per line:

```json
{
  "id": "ambiguous-001",
  "category": "ambiguous",
  "question": "Did the Select Board approve the Coolidge Corner redesign?",
  "expect_sources": ["Coolidge Corner"],
  "must_include": ["no vote", "discussed"],
  "must_not_include": ["approved the", "the board approved"],
  "must_cite": true,
  "principles": [4, 3],
  "notes": "The record shows discussion only."
}
```

| Field | Meaning |
| --- | --- |
| `expect_sources` | Substrings; retrieval passes if any retrieved passage's title, url, text, or label contains one. Empty means retrieval is not scored. |
| `must_include` | Case-insensitive substrings the answer must contain |
| `must_not_include` | Substrings the answer must not contain |
| `must_abstain` | The answer must say it lacks the record |
| `must_cite` | The answer must carry at least one citation marker |
| `principles` | Constitution principles this case enforces |

## Running

Retrieval only, no model, no inference cost. Run this first and often:

```bash
python3 -m evals.run_evals --project brookline-ma --retrieval-only
```

Full run, including generation:

```bash
python3 -m evals.run_evals --project brookline-ma
python3 -m evals.run_evals --project brookline-ma --category ambiguous
python3 -m evals.run_evals --project brookline-ma --json results/v0.1.json
```

Compare two runs:

```bash
python3 -m evals.run_evals --project brookline-ma --json results/after.json
python3 -m evals.compare results/before.json results/after.json
```

## Growing the set

The files here are a **seed**, not the frozen set. The guide asks for 200 to 500
questions, and they cannot be written in advance by someone who has not read
your town's records. Write them against your own corpus:

1. Start from real questions. Ask staff at the front counter what residents ask.
2. Add every failure you find. A bug report with no regression test comes back.
3. Cover the boring categories. `general_ai` and `writing` exist so that a
   civic fine-tune cannot quietly destroy general capability, which is the most
   common way a domain fine-tune fails.
4. Freeze it. Once a case is in, changing it to make a release look better is
   the one move that makes the whole exercise worthless. Add cases; do not edit
   them to fit.

Publish results per release, per the model card.
