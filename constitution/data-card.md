# Data Card — Community AI Knowledge Base

Fill this in per deployment and publish it alongside the model card.

## Sources

- Municipal documents
- Public meeting transcripts
- Minutes and agendas
- Bylaws and policies
- Budgets and plans
- Authorized websites and open data

The authoritative, machine-readable inventory is `knowledge/sources.yaml`. This
card is the human-readable summary of it.

| Field | Value |
| --- | --- |
| Coverage | _YYYY–YYYY_ |
| Boards and departments covered | _list_ |
| Last ingestion | _YYYY-MM-DD_ |
| Document count | _n_ |
| Chunk count | _n_ |

## Known gaps

_List what is not in the corpus. This section is the most important part of the
card, because Principle 18 (Data Freshness) requires the assistant to be able to
say what it does not have._

Examples of gaps worth stating explicitly: meetings before the archive start
date, executive session minutes, records held by a body that does not publish
video, departments whose documents are only available on request.

## Transcription and OCR limitations

_State which sources are machine-transcribed, which are OCRed from scans, and
what that means for reliability. Speaker attribution in automatic transcripts is
frequently wrong; if speaker labels are inferred rather than published, say so
here, because Principle 8 (Attribution) depends on it._

## Personal information

Public meeting records contain names of officials, staff, consultants, and
residents who chose to speak in public. The system indexes them because they are
part of the public record. Principle 9 (Privacy) governs how they are used:
minimum necessary, and no aggregation of scattered details into a profile.

Removal requests and the process for handling them are described in
`constitution/governance.md`.

## Licensing

_State the license or authorization under which each source class is indexed,
and whether the indexed text may be redistributed or only queried._
