# Model Card — Community AI

Fill this in per deployment and publish it. Values below are the template
defaults from `community.example.yaml`.

| Field | Value |
| --- | --- |
| System name | Community AI |
| System version | 0.1 |
| Foundation model | Gemma 4 26B-A4B |
| Quantization | 4-bit for inference |
| Inference | LM Studio, local |
| Cloud AI required for core inference | No |
| Operator | _community organization or municipality_ |
| Location | _locally operated server_ |
| Constitution version | 1.0 |
| Community adapter | none (fine-tuning not enabled at v0.1) |
| Embedding model | all-MiniLM-L6-v2 (BGE-M3 optional) |
| Retrieval | hybrid dense + keyword, reciprocal rank fusion, optional cross-encoder rerank |
| Last evaluation | _YYYY-MM-DD_ |

## Intended use

Answering questions about the public record of one community, and serving as a
general-purpose assistant for residents. Not a substitute for official municipal
guidance, legal advice, or a permitting decision.

## Out of scope

Binding interpretations of bylaw or regulation. Individualized legal, medical,
or financial advice. Any use that implies municipal endorsement of an answer.

## Known limitations

- The archive covers only ingested sources. Absence of a record in the corpus is
  not evidence that the event did not happen.
- Automatic transcription and OCR introduce errors, especially for names,
  addresses, and dollar figures.
- Retrieval quality on exact identifiers (article numbers, docket numbers) is
  better than on vague topical questions, but neither is perfect.
- The assistant can state the public record accurately and still be wrong about
  what the public record means.

## Evaluation

Results are published per release from the frozen evaluation set in `evals/`,
reported separately for retrieval and generation. See `evals/README.md`.
