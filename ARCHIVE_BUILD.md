# Building the archive

What actually happens when you load five hundred Brookline meetings.

This is the step everything else has been waiting for. The retrieval, the
citations, the constitution, the ledger, the provider comparison — all of it is
machinery for answering questions from a record that does not exist yet. This
document is how the record gets made.

---

## What the first real run found

Everything below this section was written before anything had been pulled from
YouTube. On 20 September 2026 it was tried for real, on the machine that will
hold the archive, and several things in this document turned out to be wrong.
They are corrected in place where a command would have done harm, and listed
here so nobody has to find them the same way.

**It is about 1,450 meetings, not 500.** The channel is
`youtube.com/@BrooklineInteractiveGroup` and holds 5,133 videos. The Select
Board and School Committee alone are about 940 meetings and 2,700 hours; with
Town Meeting, the ZBA and the subcommittees it is about 4,300 hours. Budget
roughly 165,000 passages and 800MB, not 50,000 and 300MB.

**The regular meetings are live streams, and live streams are on a different
tab.** YouTube files a broadcast under `/streams` and it never appears under
`/videos`. The keyless listing read `/videos` only, so it found the work
sessions and missed nearly every regular Select Board and School Committee
meeting, while printing a list that looked perfectly plausible. It reads both
now. `--limit` is per tab and counts videos scanned, newest first: `--limit
600` would have covered the newest eighth of one tab.

**YouTube will not give one machine a thousand transcripts in an evening.**
The first run was refused after about 25 meetings, three seconds apart:
`IpBlocked` from one caption reader, `HTTP 429` from the other. Eight full
channel listings on the same day, about 170 requests each, will not have
helped. So a backfill is fed a night at a time (`--max-meetings`, `--delay`),
the channel listing is kept for a day so that resuming and dry-running cost
YouTube nothing, and the run stops at the first refusal, because every request
made during a block lengthens it.

**A refusal used to be recorded as a hole in the record.** Every failure in the
transcript path was caught and returned as "no transcript", which the backfill
counted as a meeting without captions and marked as seen, so it was never
tried again. A block at meeting 300 would have produced several hundred
permanent, false gaps. Now "no captions" and "could not find out" are different
answers; only the first is ever recorded; and it is recorded only when two
readers agree *and* the fetches either side of it worked, because a machine
being turned away is served pages with the caption tracks simply left out.

**No API key is needed for transcripts, and none would help.** The Data API
only releases captions to the channel's owner over OAuth, at about 250 quota
units a video. A key improves the *listing*: without one there are no publish
dates at all, so a title with no date in it ("Transportation Board Meeting June
2024") stays undated.

**A citation opens where its passage starts, not at the second.** Passages are
about 220 words, which is about ninety seconds of talk. The link is good to
that.

**The captions are kept.** `data/<project>/captions/<video id>.json.gz` holds
what YouTube sent, as it sent it, about forty kilobytes a meeting. A passage is
a decision about where to cut, and changing that decision should not mean
asking YouTube for four thousand hours again. It has already paid for itself:
the vote classifier was corrected against the first night's meetings and the
archive re-labelled from these files in twenty-five seconds, offline.

**Read the dry run. It is long now on purpose.** It lists the boards it found
with how many meetings each, what it left out and why, the titles that read
like civic meetings but matched no board, and the days with two videos for one
board. The first one showed 165 School Committee subcommittee meetings filed
under no board, and candidate forums filed under the Select Board. A
community's own boards go in the source's `bodies` list in `community.yaml`.

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
python3 -m scripts.backfill_archive --project brookline-ma --dry-run --limit 6000
python3 -m scripts.backfill_archive --project brookline-ma --dry-run --limit 6000 --full
```

`--limit` has to cover the channel, and it is counted per tab. The first of
these lists the channel, which is the expensive part; the listing is then kept
for a day, so the second, and every dry run while you correct the board list,
asks YouTube for nothing. `--full` names every meeting and everything left out.

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
python3 -m scripts.backfill_archive --project brookline-ma --limit 6000 \
    --board "Select Board" --board "School Committee" --since 2000-01-01 \
    --hold-same-day --max-meetings 60 --delay 30 --snapshot-every 200
```

That is one night's worth, and the same command the next night takes the next
sixty. An earlier version of this line said `--limit 600 --snapshot-every 50`
and promised an evening; see the top of this document for what that would have
done. The flags, because each is there for a reason:

| | |
| --- | --- |
| `--board` | One pass per board, or a few. The rest are left unmarked for a later pass. Start with the boards residents ask about. |
| `--since 2000-01-01` | Leaves out, unmarked, the few meetings whose titles carry no date. |
| `--hold-same-day` | Leaves out, unmarked, any day with two videos for one board, until somebody has said which are duplicates and which are a meeting in two parts. |
| `--max-meetings 60 --delay 30` | What YouTube has so far tolerated is not known; this is a guess on the careful side. The run stops itself at the first refusal either way. |
| `--snapshot-every 200` | A snapshot is a full copy of the archive. Every 50 over a thousand meetings is twenty copies. |

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
| Pulling transcripts | **the long pole, and not for the reason guessed here.** A transcript takes a second to fetch. YouTube's patience is the constraint: about sixty meetings a night, so weeks of nights, unattended. |
| Chunking and classifying | minutes; it is regex and string work |
| Embedding | 20-60 minutes on CPU, a few minutes on the GPU already in the machine |
| Total | **a few weeks of nights**, each of which needs nobody watching it. Not an evening. |

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
