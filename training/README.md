# Training

**Nothing here runs at v0.1, and that is deliberate.**

The guide's recommended first milestone is constitution + RAG + citations + API
+ chatbot, *without* fine-tuning, because that exposes the real retrieval and
governance problems before anyone spends a week on adapters. Section 19 puts
training at steps 14 through 17 of a twenty-step roadmap, after the frozen
evaluation set exists.

This directory holds the scaffolding so that work has somewhere to go, and a
clear statement of the gate it has to pass.

## The gate

Train an adapter only when all of these are true:

1. The frozen evaluation set has at least 200 cases and is genuinely frozen.
2. A retrieval-only run passes. If retrieval is the bottleneck, training teaches
   the model to be confidently wrong from bad evidence.
3. Constitution-in-the-prompt has been tried and its remaining failures are
   understood and written down. Most "the model won't follow the rules" turns
   out to be "the rules never reached the model" or "the rules do not actually
   say that".
4. You can state what the adapter should change, in terms of named evaluation
   cases that currently fail.

Then, per section 19: keep the fine-tune **only if it measurably improves the
desired behavior without damaging general capability**. That is what
`evals/compare.py` is for, and why `general-capability.jsonl` exists. A civic
adapter that gains four civic cases and loses three general ones has made the
system worse.

## Building the dataset

Section 9 asks for critique-and-revision examples: a question, an incorrect
answer, a critique tied to specific constitution principles, and a corrected
answer. That structure teaches civic epistemology, not facts.

```bash
python3 -m training.build_dataset --out training/datasets/constitution-v1.jsonl
python3 -m training.build_dataset --stats
```

The builder reads `training/seed_examples.jsonl` and emits supervised examples
in chat format, with the constitution rendered into the system message exactly
as the serving pipeline renders it. Training on a different prompt layout than
you serve is a reliable way to lose the gains at inference time.

The seed file is small and hand-written. Section 11 describes scaling it:
generate scenarios, have the model critique its own answers against the written
constitution, revise, and have humans review a representative subset before
training. The important property is that the written principles and the
evaluation process stay the source of governance, rather than the dataset
becoming an opaque artifact nobody can audit.

## QLoRA

Section 10: do not try to fine-tune the quantized GGUF that LM Studio serves.
Training starts from the original checkpoint, applies QLoRA, produces a small
adapter, and then exports, merges and quantizes for inference.

```
original checkpoint -> Axolotl -> QLoRA -> adapter -> merge -> quantize -> LM Studio
```

`axolotl/` holds a starting configuration. Treat published configurations as
starting points; hardware requirements depend on sequence length, batch
configuration and optimizer, and the guide says plainly that they are not
guarantees for a particular server.

Keeping behavior in a small adapter rather than a full model copy is what makes
several variants practical:

```
gemma-4-26b + community-general-v1.lora
            + community-government-v1.lora
            + community-journalism-v1.lora
```

## What is not here

No weights, no datasets, no adapters. `datasets/` and `adapters/` are ignored by
git. Training data derived from a community's records inherits that community's
licensing and privacy commitments, and publishing it is a governance decision,
not a default.
