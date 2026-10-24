# Running a pilot's sessions by hand

How Ethan runs a paid pilot's briefings with `scripts/briefing.py`, once a customer has committed in writing
(the order was revised on 24 October 2026; see `docs/ORGANISER-PIVOT-2026-10.md`). Written 20 October
2026, from the organiser plan (`docs/ORGANISER-PIVOT-2026-10.md`, sections 7 and 8, PR #272) and an
outside review's ideas 4 and 5 of the same day.

The script does the repeatable part: it fetches the live forecast once, keeps a fixed copy of what was
issued, prints the email, and says what changed later. Everything else is by hand on purpose. The
review's advice was to learn which steps matter before building accounts or admin screens.

## What a briefing is

One planned session (an organisation, a date and start time, a main spot, a backup spot, who receives
the briefing and who decides) is one TOML file. Each time Ethan issues a briefing for it, the script:

1. Reads `spots.json`, `spots-lite.json`, `verification.json` and `alerts.json` from swimsignal.co.uk
   once. The three build files must come from one build. If a deploy is half done, it waits 20 s and
   reads them all again. After three tries it stops and issues nothing.
2. Keeps only the session's two spots, and keeps `verification.json` whole.
3. Has headless Chrome draw the live decision record (`record.html`) for each spot on the session's day,
   and the sites view (`sites.html`) for both, on the session's day too. The pages' data requests are
   answered from the kept files, so the PDFs show exactly the kept build even if a new build goes live
   meanwhile.
4. Checks each page and PDF, and stops on any of these problems:
   - The page or the PDF's text does not show the build's issue time.
   - The page shows an issue id that is not this build's (PR #275 adds the id to the page).
   - The page asked for data the archive does not keep.
   - The record's level differs from `alerts.json`'s.
   - The sites view does not give each spot's level on the session's day, or gives one that differs from
     `alerts.json`'s. Without the day its rows said "today" and "tomorrow", counted from the issue, which
     is wrong on the session's day (found 20 October 2026). The manifest's `day_shown` says it passed.
5. Writes one folder holding the PDFs, the pages as drawn, the page code as served, the kept data, a
   copy of the session file, the email text and `manifest.json`. The manifest lists the issue id, the
   issue time, the forecast's version and commit, the source URLs and their hashes, what was missing at
   each spot, the checks, and every file's sha256.

The folder is never changed afterwards. Decisions and change checks go in files beside it.

**The issue id** is PR #275's: the build's commit, then the forecast's issue time in UTC to the minute,
for example `2dba49e-20261020T1700Z`. Until #275 is live, `spots.json` has no `commit`, so the script
takes the commit from the model version (`code=0.1.0+2dba49e`), as #275's page code does. Two briefings
from one build share an id. The id names the forecast, not the email.

**Every briefing opens with the forecast's limits**: it is one input to the customer's own risk
assessment, a forecast and not a water test, and it never says the water is safe or clean. It names the
hazards it does not cover. It says missing data is unknown, never low. The next paragraph says the
customer makes the decision and SwimSignal does not. That paragraph is there because of Watson v British
Boxing Board of Control: a body that takes control of safety arrangements can owe the participants a
duty (plan, section 8). For the same reason the email never gives the site's advice ("Avoid swimming
here tomorrow"), only the level and its reason.

## Where the files live

Session files name real people, so nothing about a customer goes in this repository. The default is
`~/Documents/GitHub/swimsignal-private/briefings/`. Set `SWIMSIGNAL_BRIEFINGS`, or pass `--root`, to use
another folder. The script refuses any folder inside the public repository.

```
swimsignal-private/briefings/
  sessions/<organisation>/2026-11-07-0930.toml     you write these
  issued/<organisation>/2026-11-07T0930/
    2dba49e-20261106T1800Z/                         one issued briefing, never edited
      swimsignal-record-main-<issue id>.pdf         the attachments
      swimsignal-record-backup-<issue id>.pdf
      swimsignal-sites-<issue id>.pdf
      briefing.txt                                  the email as printed
      manifest.json
      session.toml                                  the session file as it was
      data/                                         the kept data the pages were given
      page/                                         the live page code that drew them
      record-main.drawn.html, ...                   each page as drawn
    decisions.jsonl                                 from `decide`
    checks.jsonl                                    from `changes`
```

## Before the first session

1. Check that Chrome is installed at `/Applications/Google Chrome.app`. If it is somewhere else, set
   `SWIMSIGNAL_CHROME` to its path.
2. Optional: `brew install poppler`. It gives the script `pdftotext`, which lets it check the PDFs'
   own text. Without it, the script checks the drawn page only and the manifest says so.
3. Do a dry run with the made-up example:

   ```
   mkdir -p ~/Documents/GitHub/swimsignal-private/briefings/sessions/example
   cp tests/fixtures/briefings/session.toml ~/Documents/GitHub/swimsignal-private/briefings/sessions/example/
   ```

   Change `date` in the copy to tomorrow, then run:

   ```
   uv run python scripts/briefing.py issue ~/Documents/GitHub/swimsignal-private/briefings/sessions/example/session.toml
   ```

   It worked if it prints an email that starts `Subject: SwimSignal briefing for Example Outdoor Centre`,
   then `Kept in ...`, `Send to:` and `Attach:`, and the three PDFs open. Delete
   `briefings/issued/example-outdoor-centre/` afterwards.

## Setting up a customer

1. Get from the customer: each session's date and start time, the main spot and the backup spot, who
   should receive the briefing, and who makes the decision.
2. Find each spot's id. It is the part after `/spot/` in the spot page's address:
   `swimsignal.co.uk/spot/bw-uke4100-08901/` has the id `bw-uke4100-08901`.
3. Write one file per session in `sessions/<organisation>/`, copying the example's fields:

   ```toml
   organisation = "Their name, as on the agreement"
   date = 2026-11-07          # a TOML date: no quotes
   time = "09:30"             # UK time, in quotes
   main = "bw-uke4100-08901"
   backup = "wharfe-burnsall" # optional
   decision_maker = "Name, role"
   notes = ""

   [[recipients]]
   name = "Name"
   email = "name@their-domain"
   ```

You know it worked when `issue` accepts the file. A bad file is refused, with every problem listed at once.

**Most likely mistake:** quoting the date (`date = "2026-11-07"`). TOML then reads it as text, not as
a date, and the script refuses it. Dates take no quotes; the time does.

A session repeated weekly is one file per date. Copy the file and change the date. Changing a session's
date or time later starts a new folder, since the folder is named by them.

## Each session, step by step

The forecast covers the day it is issued and the four after it. Rebuilds arrive several times a day.
`issue` refuses a session more than four days ahead, and says the date its day first appears.

**The evening before** (about 18:00 to 20:00):

1. `uv run python scripts/briefing.py issue <session file>`
2. Send the printed email from your own address: the subject line, the body, and the three PDFs from
   the `Attach:` line, to the people on the `Send to:` line.

You know it worked when the command prints `Kept in <folder>` and exits 0. The email is also saved as
`briefing.txt` in that folder.

**The morning of** (about two hours before the start):

1. `uv run python scripts/briefing.py changes <session file>`
2. Exit code 0 and `No change for ...`: nothing moved for the session's day. Send nothing, or a one-line
   note if the customer asked for one.
3. Exit code 1: the printed text lists what changed, spot by spot. It covers a level up or down, a new
   reason, overflows discharging upstream, a feed gone missing or back, a new EA sample, algae check or
   rating, and flood alerts. Then run `issue` again for a new fixed copy, and send that email. Its body
   repeats the changes under "Changes since the briefing of ...".

**Most likely mistake:** running `issue` in the morning when no build has run since the evening. It
refuses ("This session already has a briefing from this build"), because the copy would be the same
forecast again. It is not an error to fix. Use `changes` to see whether anything moved.

The other refusals are on purpose too:
- **A stale forecast** (over 8 hours old, the pages' own "Stale" line). Find out why the build stopped.
  `--stale-ok` issues it anyway, and the email must then say it is stale.
- **A spot id not in the forecast.** The spot was renamed or removed. Ask the customer which spot to use.

## Recording the decision

When the customer says what they decided:

```
uv run python scripts/briefing.py decide <session file> --decision go --by "Name" --note "Their reasons, as they gave them"
```

- `--decision` is `go`, `change` (a changed plan, such as the backup spot) or `cancel`.
- The decision is tied to the latest briefing issued for the session. If they decided on an earlier one,
  add `--issue <issue id>`; they can read the id off the briefing. `--at 2026-11-07T08:15` records when
  they decided, if not now.
- It is appended to `decisions.jsonl`, and the briefing's folder is not touched.

You know it worked when it prints `Recorded: go by Name, on briefing <issue id>`. It also says if a later
briefing had been issued. That matters, because the customer may have decided on an old forecast.

**Most likely mistake:** writing your own summary in `--note`. Write the customer's reasons in their
words. The decision and the reasons are theirs, and the record should show that.

## Finding a past briefing

```
uv run python scripts/briefing.py find --org "Their name" --date 2026-11-07
uv run python scripts/briefing.py find --issue 2dba49e-20261106T1800Z
```

Each match shows the session, the issue id and time, the level at each spot that day, the decisions
made on it, its folder, and `files: as issued`, or the files that changed since. Send the PDFs from that
folder. They are the copies the customer received. If a file shows as changed, say so to the customer
before using it.

## The pilot log

The plan asks for a log per pilot (section 7). Export the issued briefings once a week:

```
uv run python scripts/briefing.py find --org "Their name" --csv > ~/Documents/GitHub/swimsignal-private/briefings/logs/<organisation>.csv
```

That gives one row per briefing: session, issue id and time, the level at each spot, the decision and
who made it, whether the files are as issued, and the folder. It has no email addresses. Add these
columns by hand, from the customer's replies and your own notes:

| Column | What to write | Where it comes from |
|---|---|---|
| used_in_decision | yes, no or not known | ask in the first week, then from their replies |
| minutes_saved | their estimate against how they did it before | ask once a month, not per session |
| what_was_missing | what they wanted and did not get | their replies; the manifest's `missing` list says what the forecast lacked |
| delivery_failure | late, bounced, wrong spot or day, a PDF that would not open | your sent mail and their replies |
| support_minutes | your time on this briefing beyond running the commands | your own note |
| changes_sent | how many change notes went out | `checks.jsonl` (one line per `changes` run) |

The end-of-pilot review (plan, section 7) reads this log: how many briefings were used in a decision,
what was missing most often, how many failed to arrive, and the support time per session.

## What is manual, and what waits

**By hand during the pilots:**
- Writing the session files.
- Running `issue` and `changes` at the right times.
- Sending the email from your own address.
- Getting the decision from the customer and recording it.
- Filling in the log.

**Done by the script:** reading the live data once, keeping the fixed copy, drawing and checking the
PDFs, the manifest, finding what changed, and finding a briefing again.

**Built only after two pilots ask for it** (plan, section 6):
- Issuing on a timer (launchd or a scheduled job).
- Sending from a mail service, with bounces handled. That needs a processor agreement, and the privacy
  notice must name the service.
- A page where customers find their own briefings. That needs sign-in, so accounts.
- Text or WhatsApp delivery.
- Repeating sessions without one file per date.

The push Worker's date alerts are already planned separately (plan, section 2).

## Limits to know

- The PDFs are drawn by the live page code at the moment of issue, and `page/` keeps that code. A later
  change to the site's wording does not change an issued briefing.
- Until PR #275 is merged and live, the record has no issue id and no "prepared for" line. It ignores
  `&org=`. It also prints "This page shows the latest forecast, and changes when the forecast does",
  which reads oddly on a fixed copy. #275 hides that sentence on paper.
- The record PDF says "Ages are counted from when this page was opened". That time is the moment of issue.
- `verification.json` comes from the build's scoring run, and has its own time in the manifest.
- The EA's short-notice advice against bathing is never in the forecast (the build cannot read it). At a
  designated bathing water, every briefing lists it as missing and links the EA's page.
- Recipients are personal data. Before the first briefing, the ICO fee and the privacy notice must cover
  customer contacts and briefing recipients (plan, section 5, item 9). Delete a customer's folders at the
  end of the period the agreement names.
