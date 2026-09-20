# Building the archive

What actually happens when you load five hundred Brookline meetings.

This is the step everything else has been waiting for. The retrieval, the
citations, the constitution, the ledger, the provider comparison — all of it is
machinery for answering questions from a record that does not exist yet. This
document is how the record gets made.

---

## What you have and what you get

Brookline Interactive Group holds the recording of every Select Board and
School Committee meeting, plus subcommittees, on YouTube. Each one has
auto-generated captions. That is the raw material, and it is unusually good
raw material: it is the primary source, it is timestamped, and it is already
public.

What comes out the other end is one file, roughly 300MB, containing every
passage anybody said at any of those meetings, each one tagged with which board
said it, when, who was speaking, what agenda item it was under, whether a vote
was taken and how it went, and a link that opens the video at the second the
words were spoken.

That last part is the thing residents will notice. An answer that says *the
Select Board approved this 4-1 on March 12th* with a video that starts playing
at the moment the chair says it is a different kind of claim than a chatbot
paraphrasing a PDF.

---

## The shape of it

```
  YouTube channel
        │
        │  1. scan       what meetings exist, and which are new
        ▼
  list of videos, parsed into board + date + title
        │
        │  2. transcript one at a time, captions via the API
        ▼
  caption segments, a few seconds each
        │
        │  3. chunk      merged until the speaker changes or ~220 words
        ▼
  citable passages, each with a timestamp
        │
        │  4. classify   parliamentary vocabulary read at ingestion
        ▼
  passages tagged adopted / proposed / discussion, with vote and tally
        │
        │  5. embed      384-dimension vector per passage
        ▼
  archive.sqlite3   ← the whole public record, one file
        │
        │  6. snapshot   verified, hashed, optionally offsite
        ▼
  backups/archive-2026-09-20T02-00-00Z.sqlite3
```

Steps 1 through 5 are one command. Step 6 is a line in cron.

---

## Doing it

### Before you start

```bash
pip install -r requirements.txt
export YOUTUBE_API_KEY=...        # optional; yt-dlp works without one
```

The API key is worth having for a backfill this size. Without it the channel
listing goes through yt-dlp, which works but gives less reliable publish dates —
which matters less than it sounds, because the date in a meeting title is more
trustworthy than the upload date anyway. A meeting recorded on the 12th and
uploaded on the 19th is dated the 12th, and `collectors/meeting_titles.py`
prefers the title.

Make sure the project exists and lists the channel:

```bash
python3 -m scripts.bootstrap_community community.yaml
```

### 1. Look before you leap

```bash
python3 -m scripts.backfill_archive --project brookline-ma --dry-run
```

Nothing is written. What you get is the list of what would be ingested, and
this is the moment to actually read it:

```
  423 meeting(s) to ingest, 168 not classified as meetings, 0 already in the archive
    2016-01-12  Select Board               Select Board Meeting 1/12/2016
    2016-01-26  Select Board               Select Board Meeting 1/26/2016
    2016-02-09  School Committee           School Committee Meeting 2/9/2016
    ...
```

Two things to check before committing to a six hour run:

**Are the boards right?** If a subcommittee's videos are titled in a way the
parser does not recognize, they will show as `(unclassified)` or be counted in
the 168. That is fixable in `collectors/meeting_titles.py` — and it is much
cheaper to fix now than to re-ingest later.

**Are the 168 really not meetings?** A public access channel carries concerts,
school plays, and candidate forums alongside government meetings. Those should
be excluded. But if the count looks too high, the title parser is probably
missing a naming convention the station changed in 2019.

### 2. Run it

```bash
python3 -m scripts.backfill_archive --project brookline-ma --limit 600 --snapshot-every 50
```

It walks oldest to newest, writing each meeting to the archive as soon as it
has it:

```
  [1/423] ok     2016-01-12  Select Board    Select Board Meeting 1/12/2016   94 passages  ~5.1h left
  [2/423] ok     2016-01-26  Select Board    Select Board Meeting 1/26/2016  112 passages  ~5.0h left
  [3/423] NO CC  2016-02-09  School Committee  School Committee Meeting 2/9/2016
```

You can stop it. Ctrl-C finishes the meeting it is on, saves state, and exits;
running the same command again picks up where it left off. That is not a
convenience, it is the design: a six hour job that cannot be interrupted is a
job that gets run at a bad time and then abandoned.

`--snapshot-every 50` takes a verified backup every fifty meetings. On a first
build that is cheap insurance.

### 3. Check what you got

```bash
python3 -m stores.backup create --project brookline-ma
```

and read the report the backfill wrote:

```bash
cat data/brookline-ma/backfill-report.json
```

```json
{
  "meetings_ingested": 398,
  "passages_written": 47211,
  "meetings_without_transcripts": 22,
  "meetings_that_errored": 3,
  "videos_not_classified_as_meetings": 168
}
```

**The number that matters is 22.** Those are meetings with captions switched
off: real holes in the public record, and the system does not know what
happened at them. The report lists their video ids. Someone should decide
whether to caption them, transcribe them another way, or publish the gap. What
nobody should do is let "we have the archive" mean "we have 398 of 420
meetings" without saying so — a resident asking about the one meeting that
matters to them will find the hole, and finding it themselves is much worse
than being told.

The 3 errors will usually be transient. Re-running the command retries only
those.

---

## What it costs

Measured on this codebase, not estimated:

| | |
| --- | --- |
| Storage | **4.6 KB per passage.** 50,000 passages is 231MB; 70,000 is 324MB. Call it under half a gigabyte for a decade of two boards. |
| Chunks per meeting | ~90-140 for a three hour meeting at ~220 words each |
| Query, 20,000 passages | 598ms hybrid, 40ms for the keyword half alone — **without numpy** |
| Query, with numpy | roughly twenty times faster on the vector half; this is why numpy is in `requirements.txt` |

Time, which is harder to measure without actually pulling from YouTube:

| Step | For 500 meetings |
| --- | --- |
| Scanning the channel | minutes |
| Pulling transcripts | **the long pole.** One request per video, rate limited, with retries. Budget 1-3 hours. |
| Chunking and classifying | minutes; it is regex and string work |
| Embedding | 20-60 minutes on CPU, a few minutes on the GPU already in the machine |
| Total | **an evening.** Start it after dinner, read the report in the morning. |

The embedding step is the one people expect to dominate and does not. Pulling
50,000 captions politely from YouTube takes longer than turning them into
vectors.

---

## What goes wrong

Each of these is handled, and each is handled by recording it rather than by
pretending it did not happen:

| | |
| --- | --- |
| **Captions are off for a meeting** | Counted as a gap, listed in the report, marked skipped in sync state so it is not retried forever. The archive is honest about its holes. |
| **A video is not a meeting** | Skipped and counted. A concert on the town common does not belong in the civic record. |
| **A title does not parse** | Below the confidence threshold, it is skipped rather than ingested with a guessed board and date. A wrong attribution is worse than a missing one. |
| **The transcript request fails** | Logged with its exception type, the run continues, re-running retries only the failures. |
| **You stop it halfway** | State is saved per meeting. Oldest-first ordering means what you have is a contiguous run of years, not a decade with holes. |
| **The disk fills** | The write fails, that meeting is not marked ingested, and re-running after clearing space re-does exactly that meeting. |

What is **not** handled, and you should know it:

- **Auto-generated captions are wrong sometimes.** Names especially. "Ortiz"
  becomes "or teas". Retrieval is robust to this because the dense half matches
  meaning, but exact-phrase search for a misspelled name will miss. This is the
  strongest argument for the speaker-identification work in the roadmap.
- **Speaker labels come from caption metadata, which is sparse.** Many meetings
  will have passages attributed to no one. The chunker still splits on speaker
  change where it can see one.
- **A meeting re-uploaded under a new video id is ingested twice.** Sync state
  keys on video id, so the same meeting at a new URL looks new. Rare, and
  `delete_by_source` cleans it up.

---

## Keeping it current

The backfill is the once. After that, the scheduler handles it — every few
hours it scans for videos published since the cursor and ingests only those.
Typically that is two meetings a week, and it takes under a minute.

```bash
# nightly, after the scheduler has done its work
0 2 * * *  cd /srv/civic-ai && python3 -m stores.backup create --project brookline-ma --keep 14
```

`--keep 14` holds two weeks. Retention never deletes the last verified copy,
whatever that number says.

Once, after the first backup, restore it somewhere harmless and ask it a
question:

```bash
python3 -m stores.backup restore data/backups/brookline-ma/archive-*.sqlite3 \
    --destination /tmp/drill.sqlite3 --yes
COMMUNITY_DB_PATH=/tmp/drill.sqlite3 python3 -m evals.run_evals \
    --project brookline-ma --retrieval-only
```

A backup nobody has restored is a hypothesis.

---

## Then the part that is not engineering

An archive is not an answer. The next thing after this — and the highest-value
work left in the project — is writing two hundred real evaluation questions
against the real archive: questions residents actually ask, each with the
answer and the citation that proves it.

Until that exists, every claim about whether a local model is good enough here
is a guess. After it exists, it is a number, and the number can be argued with.
The eval harness has been ready since Part 1 of the roadmap. It is waiting on
the archive, and then on somebody who knows Brookline sitting down for two days
with a text editor.

That is the whole project, really. The code is the easy half.
