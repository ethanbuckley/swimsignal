"""The model scorecard, for the site's Research pages (docs/MODEL-SCORECARD-CONTRACT-v1.md): each forecast model or
candidate, what it predicts, where and when it was tested, its accuracy against a simple reference, what it misses,
how often it was wrong, its stage, and whether a result can be shown at all.

    uv run python scripts/export_model_scorecard.py export [--state DUCKDB] [--out PATH]
    uv run python scripts/export_model_scorecard.py check [PATH]

Every figure is copied from a test record in docs/, and carries the record's own words (`quote`) and file
(`source`): the check refuses a quote that is not in its record, so a figure cannot drift from its verdict. A running
test shows its window and read date, never a score from inside its window: the check refuses a result marked
`prospective` before its read date. With --state (a copy of the state release's dipcast.duckdb, opened read only)
the export counts the rows each running test has logged so far; it reads no forecast or outcome, only counts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research" / "model_scorecard.v1.json"
SCHEMA, VERSION = "swimsignal.model-scorecard", "1.0.0"
STAGES = {
    "live": "Live: the forecast the site shows.",
    "shadow": "Running test: its window is open or about to open, and nobody reads its score before the read date.",
    "scheduled": "Scheduled: the window has not opened yet.",
    "lab": "In the lab: tested, not good enough yet to run beside the forecast. Kept for development.",
    "not_started": "Not started.",
}
DATA = {
    "held_out": "scored on data the model never saw while it was built",
    "seen": "scored on data that was used to choose or build it: a direction, not evidence",
    "live": "scored on SwimSignal's own live forecasts, after the outcomes were known",
    "pre_window": "live rows from before its test window: reported, not deciding",
    "prospective": "scored inside its test window",
}
CLAIM = {
    "public_wording": "Each model or candidate SwimSignal has built or is testing to forecast sewage spills, with how "
                      "it was tested and how it did against a simple reference. A score is a past result on the "
                      "rows it names, not a promise about tomorrow, and none of it is a water test.",
    "not_claimed": ["a measure of the water at a spot", "that a candidate will pass its read",
                    "a score from inside a running test's window", "that a model is safe to rely on alone"],
}
ACCURACY = "verification.html"
ALL_NINE = "the nine English water companies"
BRIER = ("Brier score: the mean squared gap between the chance given and what happened (1 for a spill, 0 for none). "
         "Lower is better; 0 is perfect.")
ECE = ("Calibration error (ECE): how far, on average, the chances given were from how often spills happened at "
       "those chances. Lower is better.")


def r(label, measure, model, ref, ref_name, data, quote, source, *, diff=None, interval=None, note=None):
    """One result: the model's figure beside a reference's, on rows `data` describes, with its record's words."""
    return {"label": label, "measure": measure, "model": model, "reference": ref, "reference_name": ref_name,
            "difference": diff, "interval": interval, "data": data, "note": note, "quote": quote, "source": source}


def rec(title, path):
    return {"title": title, "href": path if path.startswith("http") else
            f"https://github.com/ethanbuckley/swimsignal/blob/main/{path}"}


MODELS = [
    {
        "id": "production",
        "name": "The live spill forecast",
        "stage": "live",
        "predicts": "For each monitored storm overflow upstream of a spot, the chance that it spills on each of the "
                    "next five days, from rain, how wet the ground is, the time of year and the overflow's own "
                    "record. A spot's sewage spill risk adds those chances up along the river. On rivers from May to "
                    "September, a second model estimates the chance a water sample would hold more than 900 E. coli "
                    "per 100 ml.",
        "tested": "The spill model was fitted on United Utilities' overflows in 2023 and 2024 and tested on 2025: "
                  "826,725 overflow-days. The E. coli estimate was tested on 1,502 Environment Agency samples at 31 "
                  "inland bathing waters, 2024 to 2026. Since 28 September 2026 every live forecast is scored "
                  "afterwards against what the overflows did, at all nine companies.",
        "reference": "Each overflow's long-run spill rate; for the live record also \"it is spilling now or spilled "
                     "in the last two days\" and \"more than 10 mm or 5 mm of rain in two days\".",
        "results": [
            r("2025, United Utilities, same-day, reanalysis rain", "Brier", 0.0445, 0.0669, "long-run spill rate",
              "held_out", "SwimSignal (the model, with each overflow's own record)</td><td class=\"num\">0.0445",
              "src/dipcast/pages/methods.html", note="Skill 0.33. Rain as it fell, so weather-forecast error is left out."),
            r("E. coli over 900 on rivers and lakes, each year left out", "Brier", 0.092, 0.096, "rain only",
              "held_out", "<td>The E. coli estimate</td><td class=\"num\">0.092", "src/dipcast/pages/methods.html",
              note="Climatology by water type: 0.120. On lakes neither does reliably better than chance."),
            r("Live, all companies, same-day, 29 Sep to 23 Oct 2026", "Skill", 0.21, None, "long-run spill rate",
              "live", "| All companies | 0 | 0.21 (0.08 to 0.44) | −0.05 (−0.19 to 0.17)",
              "docs/INTERIM-USEFULNESS-2026-10.md", interval=[0.08, 0.44],
              note="Skill is 1 − Brier ÷ the reference's Brier: above 0 is better than the reference."),
            r("Same rows, against \"spilling now or in the last two days\"", "Skill", -0.05, None, "persistence",
              "live", "| All companies | 0 | 0.21 (0.08 to 0.44) | −0.05 (−0.19 to 0.17)",
              "docs/INTERIM-USEFULNESS-2026-10.md", interval=[-0.19, 0.17],
              note="Not shown to beat persistence on the same day."),
            r("Live, all companies, one to four days ahead, against the best simple rule", "Skill", 0.07, None,
              "rain over 10 mm in two days", "live", "| All companies | 0.07 (−0.05 to 0.12) | rain > 10 mm |",
              "docs/INTERIM-USEFULNESS-2026-10.md", interval=[-0.05, 0.12]),
        ],
        "verdict": {"quote": "No company passes the promise rule.", "source": "docs/INTERIM-USEFULNESS-2026-10.md",
                    "plain": "It beats each overflow's long-run rate and ranks spill days well, but it is not yet "
                             "shown to beat simple rules a swimmer could use. So for now it is worded as showing "
                             "what the upstream monitors say, with the forecast still being tested."},
        "misses": "The spill model learned from United Utilities only; other companies' overflows get the same model. "
                  "It does not see runoff from fields and roads, treated sewage, wildlife, or wind and mixing on a "
                  "lake, and on lakes E. coli spikes are mostly not from overflows. In Thames Water's area it was "
                  "worse than persistence on the same day. Welsh overflows are not in it.",
        "wrong": "Its chances run too high: in the live check, 29 September to 23 October 2026, same-day spills "
                 "happened 0.74 times as often as forecast (95% interval 0.65 to 0.87), and 388 of 963 high "
                 "warnings came true (40%). In the 2025 test, days forecast at 85% had a spill 79% of the time.",
        "window": None,
        "log": None,
        "show": {"shown": True, "why": "It is the forecast, worded by what it has shown. Its live score is "
                                       "published every day on the Accuracy page, including where it is wrong."},
        "records": [rec("Accuracy page", "https://swimsignal.co.uk/verification.html"),
                    rec("Method", "https://swimsignal.co.uk/methods.html"),
                    rec("Interim usefulness read", "docs/INTERIM-USEFULNESS-2026-10.md"),
                    rec("Calibration check", "docs/CALIBRATION-CHECK-2026-10.md")],
    },
    {
        "id": "regional-v1",
        "name": "Regional routing (regional-v1)",
        "stage": "shadow",
        "predicts": "The same daily spill chance per overflow. At eight companies it uses a model fitted on all nine "
                    "companies' records with a correction for each overflow (the nine-company model's arm (b)); at "
                    "United Utilities, and anywhere else, it keeps the live forecast.",
        "tested": "The nine-company model was trained on the Environment Agency's 2024 and 2025 records and tested "
                  "on 1 January to 31 August 2026: 3,270,537 overflow-days at 13,459 overflows. The routing rule "
                  "was then chosen from those same results.",
        "reference": "The live forecast, each overflow's past spill rate, and a flat rate per company.",
        "results": [
            r("Nine-company model, arm (b), all nine companies, same-day", "Brier", 0.0365, 0.0420, "live forecast",
              "held_out", "All nine | 3,270,537 | 0.060 | 0.0378 (0.010) | 0.0365 (0.009) | 0.0420 (0.024)",
              "docs/NINE-COMPANY-MODEL-V2-TEST-2026-11.md", diff=-0.00550, interval=[-0.00883, -0.00268],
              note="Interval: 95%, resampling overflows and weeks."),
            r("Same, United Utilities only", "Brier", 0.0390, 0.0377, "live forecast", "held_out",
              "United Utilities | 539,946 | 0.054 | 0.0411 (0.023) | 0.0390 (0.016) | 0.0377 (0.006)",
              "docs/NINE-COMPANY-MODEL-V2-TEST-2026-11.md", interval=[0.00007, 0.00261],
              note="3.4% worse, interval wholly above zero: the reason United Utilities keeps the live forecast."),
            r("regional-v1 rule, all nine companies, same-day", "Brier", 0.03633, 0.04204, "live forecast", "seen",
              "regional-v1 (v2 at eight, production at United Utilities) | 0.03633 (13.6% below production)",
              "docs/REGIONAL-ROUTING-2026-11.md",
              note="The rows that chose the rule, with reanalysis rain: says the rule is worth a live look, not how "
                   "it will do live."),
        ],
        "verdict": {"quote": "Neither arm passes. Both fail condition 2 at United Utilities, and only there.",
                    "source": "docs/NINE-COMPANY-MODEL-V2-TEST-2026-11.md",
                    "plain": "The nine-company model was not adopted: 11% to 23% better at eight companies, 3.4% worse "
                             "at United Utilities. The routing rule is a development idea tested live from 31 October."},
        "misses": "Chosen after seeing the results, so its seen-data gain will shrink live. United Utilities keeps "
                  "the live forecast. The test is judged on SwimSignal's own polls of the companies' live feeds: a "
                  "missing or stale status counts as unknown, never as a dry day.",
        "wrong": "On 2026 data its calibration error was 0.009 across the nine companies, against the live "
                 "forecast's 0.024 (worst company: Thames, 0.0221 against 0.0401).",
        "window": {"start": "2026-10-31", "end": "2026-11-27", "read_on": "2026-11-28",
                   "rule": "Useful if its same-day Brier at the eight companies is at least 5% below the live "
                           "forecast's, with the 95% interval below zero; a company more than 5% worse goes back to "
                           "the live forecast. Settled before the window opened.",
                   "extension": "Under 10,000 known overflow-days at the eight companies: one more 28-day window."},
        "log": {"table": "shadow_regional_v1", "where": "true"},
        "show": {"shown": False, "why": "Not until the read on 28 November 2026. If it passes, a limited rollout at "
                                        "the eight companies is proposed in its own change."},
        "records": [rec("Regional routing plan", "docs/REGIONAL-ROUTING-2026-11.md"),
                    rec("Nine-company model test", "docs/NINE-COMPANY-MODEL-V2-TEST-2026-11.md")],
    },
    {
        "id": "live-status",
        "name": "Live spill status as an input",
        "stage": "shadow",
        "predicts": "The daily spill chance per overflow, today and four days ahead, with three more inputs: "
                    "whether the overflow is spilling now, its spill hours in the last 24 hours and its spill days "
                    "in the last week.",
        "tested": "Fitted on 2024, tested on 2025 at all nine companies: 5,077,150 overflow-days with reanalysis "
                  "rain, and 1,928,619 a lead with archived forecast rain. Labels from the Environment Agency's "
                  "start and stop records.",
        "reference": "The nine-company model without the status inputs (not the live forecast), and a flat rate per "
                     "company.",
        "results": [
            r("2025, same-day, reanalysis rain", "Brier", 0.0265, 0.0362, "same model without status", "held_out",
              "| 0 | 0.0265 | 0.0362 | −0.0096 [−0.0125, −0.0070] | −27% |",
              "docs/LIVE-STATUS-FEATURE-TEST-2026-10.md", diff=-0.0096, interval=[-0.0125, -0.0070],
              note="Interval: 95%, resampling calendar weeks."),
            r("2025, four days ahead, reanalysis rain", "Brier", 0.0332, 0.0362, "same model without status",
              "held_out", "| 4 | 0.0332 | 0.0362 | −0.0030 [−0.0041, −0.0019] | −8% |",
              "docs/LIVE-STATUS-FEATURE-TEST-2026-10.md", diff=-0.0030, interval=[-0.0041, -0.0019]),
            r("2025, same-day, forecast rain", "Brier", 0.02868, 0.03784, "same model without status", "held_out",
              "| 0 | 0.02868 | 0.03784 | −0.0092 [−0.0118, −0.0067] | −24% |",
              "docs/LIVE-STATUS-FEATURE-TEST-2026-10.md", diff=-0.0092, interval=[-0.0118, -0.0067]),
            r("2025, four days ahead, forecast rain", "Brier", 0.04510, 0.04919, "same model without status",
              "held_out", "| 4 | 0.04510 | 0.04919 | −0.0041 [−0.0058, −0.0024] | −8% |",
              "docs/LIVE-STATUS-FEATURE-TEST-2026-10.md", diff=-0.0041, interval=[-0.0058, -0.0024]),
        ],
        "verdict": {"quote": "The status input helps at every lead, 0 to 4. As stated above, nothing deploys on this.",
                    "source": "docs/LIVE-STATUS-FEATURE-TEST-2026-10.md",
                    "plain": "Passed all five conditions at every lead on 2025. Not deployed: it must first work on "
                             "SwimSignal's own live polls, with a fallback when the status is missing."},
        "misses": "With every status input missing it is much worse than the model without them (0.0537 against "
                  "0.0362 same-day). About half the same-day gain comes from how the label is defined. Northumbrian "
                  "gains least. Southern reports no usable live status, so the live test says nothing about it.",
        "wrong": "Calibration error same-day 0.003, against 0.008 for the model without status.",
        "window": {"start": "2026-10-25", "end": "2026-11-21", "read_on": "2026-11-23",
                   "rule": "Lead by lead, against the live forecast: the 95% interval wholly below zero over the "
                           "nine companies, no company with 50 or more spill rows clearly worse, calibration no "
                           "worse (or at most 0.02), and spills that start from dry not clearly worse.",
                   "extension": "Too few spill rows with a known status: runs to 5 December, read on or after "
                                "7 December."},
        "log": {"table": "forecast_overflows", "where": "p_status IS NOT NULL"},
        "show": {"shown": False, "why": "Logged beside the forecast but never shown: no page, alert or score reads it "
                                        "before the read."},
        "records": [rec("Live-status test", "docs/LIVE-STATUS-FEATURE-TEST-2026-10.md"),
                    rec("Live-status shadow", "docs/LIVE-STATUS-SHADOW-TEST-2026-10.md")],
    },
    {
        "id": "lead-calibration-b",
        "name": "Lead calibration, option B",
        "stage": "shadow",
        "predicts": "The live forecast's daily spill chances, re-mapped by a new calibration for each lead, fitted on "
                    "2025 at the eight companies other than United Utilities.",
        "tested": "A 2025 replay at 3,050 overflows at the eight companies, the map fitted on odd months and scored "
                  "on even ones, then the reverse. Then a check on SwimSignal's own live forecasts, 29 September to "
                  "16 October 2026: 79,084 scored forecasts, 2,334 with a spill.",
        "reference": "The live forecast with the map in use today.",
        "results": [
            r("2025 replay, leads 0 to 4 together", "Brier", 0.03818, 0.03941, "today's map", "held_out",
              "B: production model + a map fitted on these rows, cross-fitted by month | 0.03818",
              "docs/LEAD-CALIBRATION-B-TEST-2026-10.md", note="No interval was worked out for the replay."),
            r("Live forecasts, 29 Sep to 16 Oct 2026", "Brier", 0.03099, 0.02721, "today's map", "pre_window",
              "| Brier | 0.02721 | 0.03099 |", "docs/LEAD-CALIBRATION-B-TEST-2026-10.md",
              note="Before the window: reported, not deciding."),
            r("Same rows", "ECE", 0.0320, 0.0117, "today's map", "pre_window", "| ECE | 0.0117 | 0.0320 |",
              "docs/LEAD-CALIBRATION-B-TEST-2026-10.md"),
        ],
        "verdict": {"quote": "On these rows B would fail all three conditions.",
                    "source": "docs/LEAD-CALIBRATION-B-TEST-2026-10.md",
                    "plain": "No verdict yet: the window decides. The live rows before it, and 2025's records, point "
                             "in opposite directions."},
        "misses": "Fitted on 2025's records, where the forecast ran too low; on the live rows the forecast already "
                  "runs too high at six of nine companies, and B raises it further.",
        "wrong": "On the live rows before the window its mean chance was 0.0615 against 0.0295 observed (today's "
                 "map: 0.0393).",
        "window": {"start": "2026-10-18", "end": "2026-11-14", "read_on": "2026-11-16",
                   "rule": "All three: lower Brier than today's map; no company with 50 or more spills more than 2% "
                           "worse; calibration error no worse. At least 200 spills.",
                   "extension": None},
        "log": None,
        "how": "Nothing extra is logged: at the read the map is applied to the live forecast's own published scored rows.",
        "show": {"shown": False, "why": "Nothing is deployed unless all three conditions hold at the read."},
        "records": [rec("Lead calibration B test", "docs/LEAD-CALIBRATION-B-TEST-2026-10.md")],
    },
    {
        "id": "company-calibration-a8",
        "name": "Company calibration (A8)",
        "stage": "shadow",
        "predicts": "The live forecast's daily spill chances with a frozen correction for each overflow at the eight "
                    "companies other than United Utilities, fitted on SwimSignal's own polls.",
        "tested": "Fitted on 20,783 same-day rows, target days 29 September to 23 October 2026, 1,010 overflows. "
                  "No score was worked out on the fitting rows. The corrections are frozen in a file with a "
                  "SHA-256 beginning 2662dcfa.",
        "reference": "The live forecast and a flat rate per company.",
        "results": [],
        "verdict": {"quote": "My prediction: not adopted.", "source": "docs/COMPANY-CALIBRATION-TEST-2026-11.md",
                    "plain": "Not yet run. The prediction written before the window was that it will not be adopted."},
        "misses": "Overflows that never spilled get corrections only down to 0.73 of the forecast, not lower. United "
                  "Utilities is not changed.",
        "wrong": "Background, before the window: the live forecast's Brier over the eight companies was about 9% above "
                 "a flat rate's (Thames about 57%, Southern 41%, Wessex 23%).",
        "window": {"start": "2026-10-26", "end": "2026-11-22", "read_on": "2026-11-25",
                   "rule": "Shown better than both the live forecast and the flat rate over the eight companies (95% "
                           "interval wholly below zero), and no changed company clearly worse.",
                   "extension": "Too few spills at a changed company: 14 days more, to 6 December, read on or after "
                                "9 December."},
        "log": None,
        "how": "Nothing extra is logged: at the read the frozen corrections are applied to the live forecast's own "
               "published scored rows.",
        "show": {"shown": False, "why": "Never deployed before the read, and only then if the conditions hold."},
        "records": [rec("Company calibration test", "docs/COMPANY-CALIBRATION-TEST-2026-11.md")],
    },
    {
        "id": "ensemble-rain-d4",
        "name": "Ensemble rain (D4)",
        "stage": "shadow",
        "predicts": "The spill forecast run on each of three members of the Met Office's MOGREPS-UK ensemble rain "
                    "forecast, giving a range around the headline chance two to four days ahead.",
        "tested": "Not tested on past data: Open-Meteo does not keep the ensemble's past runs, so a backtest is not "
                  "possible. The live window is the first test.",
        "reference": "The single rain forecast the headline uses now.",
        "results": [],
        "verdict": None,
        "misses": "Three members are a narrow sample of the weather. Before the window, the headline sat inside the "
                  "members' range on about 70% of rows two days ahead and 65% four days ahead.",
        "wrong": "Not yet measured.",
        "window": {"start": "2026-10-23", "end": "2026-11-19", "read_on": "2026-11-21",
                   "rule": "Whether a wider range marks a larger error, and whether the members' mean is no worse "
                           "than the single forecast, overall and at each lead and company.",
                   "extension": "Too few spill rows: runs to 3 December, read on or after 5 December."},
        "log": {"table": "forecast_overflows", "where": "p_cal_members IS NOT NULL"},
        "show": {"shown": True, "why": "The range is shown, labelled as under test; the level and the headline chance "
                                       "do not use it."},
        "records": [rec("Ensemble rain test", "docs/ENSEMBLE-RAIN-TEST-2026-11.md")],
    },
    {
        "id": "upgraded-overflows-b",
        "name": "Upgraded overflows, option B",
        "stage": "shadow",
        "predicts": "The daily spill chance with each overflow's own correction fitted only on its record after a "
                    "start date, so an overflow that was upgraded and went quiet is not judged on its old spills.",
        "tested": "Not yet scored. Two windows are fixed: the Environment Agency's records for 1 January to "
                  "31 August 2026, same-day; and SwimSignal's own live forecasts for target days 29 September to "
                  "30 November 2026, leads 0 to 4.",
        "reference": "The live forecast, and the same correction fitted on the whole record (B0).",
        "results": [],
        "verdict": None,
        "misses": "A broken monitor that reports no spills with fresh time stamps passes the dead-monitor check. The "
                  "16 Ilkley overflows are left out. The live window is autumn, when the forecast has run too high.",
        "wrong": "Not yet measured.",
        "window": {"start": "2026-09-29", "end": "2026-11-30", "read_on": "2026-12-02",
                   "rule": "Seven conditions, all needed, including a gain on the 2026 records with the interval "
                           "below zero, no loss over 1% in the live window, and no company clearly worse.",
                   "extension": None},
        "log": None,
        "how": "Nothing extra is logged: at the read the arms are rebuilt from the live forecast's logged raw chances.",
        "show": {"shown": False, "why": "Not before the read. A pass leads to a separate running test early in 2027, "
                                        "not straight to the forecast."},
        "records": [rec("Upgraded overflows test B", "docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md"),
                    rec("Recency note", "docs/UPGRADED-OVERFLOWS-TEST-B-RECENCY-NOTE-2026-10.md")],
    },
    {
        "id": "winter-recalibration",
        "name": "Winter recalibration",
        "stage": "scheduled",
        "predicts": "The live forecast's chances with a fixed correction after the lead map, by lead and possibly by "
                    "company, fitted on the live autumn rows to bring the chances down where they run too high.",
        "tested": "An earlier correction on 12 days of live rows (58,274 rows) was 4.3% better against a 5% bar. "
                  "A later check on 117,324 live rows, 29 September to 23 October, found the chances run too high "
                  "overall. The new correction is fitted on or after 10 December to target days 29 September to "
                  "6 December.",
        "reference": "The live forecast as shown.",
        "results": [
            r("Earlier correction, company intercepts, 12 days of live rows", "Brier", 0.02182, 0.02280,
              "live forecast", "live", "B, company intercepts | 0.02182 (−4.3%)",
              "docs/LIVE-RECALIBRATION-TEST-2026-10.md", note="Scored leaving one day out at a time; no interval."),
        ],
        "verdict": {"quote": "Verdict: neither passes. Nothing changes.",
                    "source": "docs/LIVE-RECALIBRATION-TEST-2026-10.md",
                    "plain": "The earlier correction missed its 5% bar. The winter test is its successor, with a "
                             "different route written down before any of its rows."},
        "misses": "Fitted on autumn, judged on winter: whether the same bias holds in summer is not tested.",
        "wrong": "In the live check, of same-day forecasts in the highest band, 388 of 963 came true (40%).",
        "window": {"start": "2026-12-14", "end": "2027-03-07", "read_on": "2027-03-09",
                   "rule": "At least 1% better with the interval above zero, or no more than 1% worse with a shown "
                           "calibration gain; no company clearly worse.",
                   "extension": "If too few spills: 16 weeks, to 4 April 2027, read on or after 6 April."},
        "log": None,
        "how": "Logs a separate corrected chance from the fit, never shown before its rollout review.",
        "show": {"shown": False, "why": "Not before the read. It stays a labelled secondary for 2027 and never "
                                        "replaces the frozen 2027 evaluation's predictions."},
        "records": [rec("Winter recalibration plan", "docs/CALIBRATION-TEST-PROPOSAL-2026-11.md"),
                    rec("Calibration check", "docs/CALIBRATION-CHECK-2026-10.md"),
                    rec("Earlier recalibration test", "docs/LIVE-RECALIBRATION-TEST-2026-10.md")],
    },
    {
        "id": "spill-duration",
        "name": "Spill duration",
        "stage": "lab",
        "predicts": "For an overflow spilling now, the chance it is still spilling 1, 3, 6, 12 and 24 hours later. "
                    "When a spill ends is not when the water clears.",
        "tested": "Trained on 2024 and scored on 2025: 1,582,953 hours of spills at the nine companies. Then a "
                  "replay of 2024-25 at the times SwimSignal actually polls, and a check of the 2024-25 table on "
                  "SwimSignal's own polls, 28 September to 31 October 2026.",
        "reference": "B1: the share of a company's spills still running after the same elapsed time.",
        "results": [
            r("2025, all horizons", "Brier", 0.1507, 0.1705, "B1, company table", "held_out",
              "0.1507 | −0.0198 | −0.0242 to −0.0148", "docs/SPILL-DURATION-TEST-2026-11.md",
              diff=-0.0198, interval=[-0.0242, -0.0148], note="11.6% better, but its chances were unreliable."),
            r("2024-25 replay at the live poll times, calibrated", "Brier", 0.1652, 0.1954, "B1, company table",
              "seen", "0.1652 | −0.0302 (−15.5%) | −0.0319 to −0.0286", "docs/SPILL-DURATION-REPLAY-2026-11.md",
              diff=-0.0302, interval=[-0.0319, -0.0286], note="Development on seen data: a direction, not a verdict."),
        ],
        "verdict": {"quote": "Verdict: the gate fails. Nothing was downloaded and nothing was scored on 2026",
                    "source": "docs/SPILL-DURATION-CALIBRATION-TEST-2026-11.md",
                    "plain": "The model failed its reliability condition on 2025, and the calibration gate that "
                             "followed also failed. The 2024-25 table is shown as a record, not a forecast."},
        "misses": "It under-forecasts at 24 hours. On the live polls the 2024-25 table's curve was too flat for "
                  "autumn 2026: too low at 1 hour, too high at 12 to 24 hours.",
        "wrong": "On 2025 its reliability failed in 24 of the 45 company-and-horizon cells. In the replay, 19.4% of "
                 "rows were spills that had already stopped.",
        "window": None,
        "milestones": [{"date": "2026-12-01", "what": "the same check of the table on November's polls"},
                       {"date": "2026-12-28", "what": "refit the table on three months of live polls, then a "
                                                      "held-out month"}],
        "log": None,
        "show": {"shown": False, "why": "No forecast of when a spill ends is shown. The 2024-25 durations are shown "
                                        "as a record of the past on the spill durations page."},
        "records": [rec("Duration test", "docs/SPILL-DURATION-TEST-2026-11.md"),
                    rec("Calibration test", "docs/SPILL-DURATION-CALIBRATION-TEST-2026-11.md"),
                    rec("Replay", "docs/SPILL-DURATION-REPLAY-2026-11.md"),
                    rec("Live check", "docs/SPILL-DURATION-LIVE-CHECK-2026-11.md")],
    },
    {
        "id": "primary-2027",
        "name": "The 2027 evaluation",
        "stage": "not_started",
        "predicts": "Not a new model: the live forecast, frozen before the season, scored once over the whole 2027 "
                    "season. Four results: spill forecasts same-day and one to four days ahead, and the E. coli "
                    "estimate on rivers same-day and ahead.",
        "tested": "Target days 1 May to 30 September 2027, at the 1,089 overflows that reach the 105 listed spots, "
                  "and about 340 river samples.",
        "reference": "Each overflow's spill rate adjusted for the month; each bathing water's own share of samples "
                     "over 900.",
        "results": [],
        "verdict": None,
        "misses": "Each result shows skill only if the lower end of its 95% interval is above 0. Candidates are "
                  "reported separately and never replace the frozen model's result.",
        "wrong": "Not started.",
        "window": None,
        "milestones": [{"date": "2027-05-01", "what": "the model is frozen and tagged before the season"},
                       {"date": "2027-10-31", "what": "the analysis runs once, on that day's snapshot"}],
        "log": None,
        "show": {"shown": False, "why": "No result until the analysis runs after the season. A trial run on autumn "
                                        "2026 rows checked the code; it is not a result."},
        "records": [rec("2027 preregistration", "docs/PREREGISTRATION-2027.md")],
    },
]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def plain(text: str) -> str:
    """A record's words as a quote is compared with them: bold and code marks dropped, white space collapsed."""
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).strip()


def count_logs(models: list[dict], db: Path) -> None:
    """Fill each logged model's `log` with the rows logged so far and the first and last issue time: counts only,
    from a read-only copy of the state database. No forecast or outcome is read."""
    import duckdb
    con = duckdb.connect(str(db), read_only=True)
    for m in models:
        if not (lg := m.get("log")):
            continue
        n, first, last = con.execute(
            f"SELECT count(*), strftime(min(issued_at) AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%MZ'), "
            f"strftime(max(issued_at) AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%MZ') FROM {lg['table']} WHERE {lg['where']}"
        ).fetchone()
        lg.update(rows=int(n), first=first, last=last)


def build(state: Path | None, as_of: date) -> dict:
    models = json.loads(json.dumps(MODELS))
    if state:
        count_logs(models, state)
    return {
        "schema": SCHEMA, "version": VERSION, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "as_of": as_of.isoformat(),
        "claim": CLAIM, "stages": STAGES, "data_kinds": DATA, "measures": {"Brier": BRIER, "ECE": ECE},
        "counted_from": ("a read-only copy of the state release's dipcast.duckdb" if state else None),
        "models": models,
        "sources": {"register": "docs/RESEARCH-RECOVERY-2026-10.md",
                    "code_sha256": {"scripts/export_model_scorecard.py": sha256(Path(__file__))}},
    }


def check(doc: dict, root: Path = ROOT) -> list[str]:
    err = []
    if doc.get("schema") != SCHEMA or str(doc.get("version", "")).split(".")[0] != "1":
        err.append("schema or major version")
    for k in ("as_of", "claim", "stages", "data_kinds", "models", "sources"):
        if k not in doc:
            err.append(f"missing {k}")
    as_of = date.fromisoformat(doc.get("as_of", "1970-01-01"))
    ids = [m.get("id") for m in doc.get("models", [])]
    if len(set(ids)) != len(ids):
        err.append("a model id twice")
    texts: dict[str, str] = {}

    def quoted(q: str, src: str, where: str) -> None:
        p = root / src
        if not p.is_file():
            err.append(f"{where}: {src} is not a record in the repository")
            return
        if plain(q) not in texts.setdefault(src, plain(p.read_text())):
            err.append(f"{where}: quote not found in {src}: {q!r}")

    for m in doc.get("models", []):
        i = m.get("id")
        if m.get("stage") not in STAGES:
            err.append(f"{i}: stage {m.get('stage')!r}")
        w = m.get("window")
        if m.get("stage") in ("shadow", "scheduled") and not (w and w.get("read_on")):
            err.append(f"{i}: a running or scheduled test needs its window and read date")
        if w:
            if not date.fromisoformat(w["start"]) <= date.fromisoformat(w["end"]) < date.fromisoformat(w["read_on"]):
                err.append(f"{i}: window dates out of order")
        for x in m.get("results", []):
            where = f"{i}: {x['label']}"
            if x["data"] not in DATA:
                err.append(f"{where}: data {x['data']!r}")
            if x["data"] == "prospective" and (not w or as_of < date.fromisoformat(w["read_on"])):
                err.append(f"{where}: a score from inside the window before its read date")
            if (iv := x.get("interval")) and not iv[0] <= iv[1]:
                err.append(f"{where}: interval out of order")
            quoted(x["quote"], x["source"], where)
        if v := m.get("verdict"):
            quoted(v["quote"], v["source"], f"{i}: verdict")
        if not isinstance(m.get("show", {}).get("shown"), bool) or not m["show"].get("why"):
            err.append(f"{i}: whether a result is shown, and why")
        if m.get("stage") == "not_started" and m.get("results"):
            err.append(f"{i}: not started, so no results")
    if "production" not in ids or "primary-2027" not in ids:
        err.append("the live forecast and the 2027 evaluation must both be listed")
    return err


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["export", "check"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--state", type=Path, help="a copy of the state release's dipcast.duckdb, opened read only")
    ap.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(UTC).date())
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    if a.step == "export":
        doc = build(a.state, a.as_of)
        if problems := check(doc):
            raise SystemExit("\n".join(problems))
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
        print(f"wrote {a.out}: {len(doc['models'])} models")
    else:
        p = Path(a.path) if a.path else OUT
        problems = check(json.loads(p.read_text()))
        print("\n".join(problems) or f"{p}: holds the contract")
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
