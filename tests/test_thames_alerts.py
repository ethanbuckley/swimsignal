"""Thames Water's alert stream joined into discharges (ingest/thames_alerts.py)."""

import pandas as pd

from dipcast.ingest.thames_alerts import alerts_to_events


def _alerts(rows):
    df = pd.DataFrame(rows, columns=["permitNumber", "locationName", "alertType", "datetime"])
    df["x"], df["y"] = 530000, 180000
    df["time"] = pd.to_datetime(df["datetime"]).dt.tz_localize("UTC")
    return df


def test_each_start_takes_the_next_stop_at_its_location():
    ev = alerts_to_events(_alerts([
        ("CSAB.0531", "Northumberland Street CSO", "Start", "2024-01-02T10:00:00"),
        ("CSAB.0531", "Northumberland Street CSO", "Stop", "2024-01-02T10:30:00"),
        ("CSAB.0531", "Northumberland Street CSO", "Start", "2024-01-02T10:30:00"),   # restarts the minute it stops
        ("CSAB.0531", "Northumberland Street CSO", "Stop", "2024-01-02T11:00:00"),
        ("TEMP.0615", "Castle Drive", "Start", "2024-01-03T08:00:00"),
        ("TEMP.0615", "Castle Drive", "Offline start", "2024-01-03T09:00:00"),
        ("TEMP.0615", "Castle Drive", "Stop", "2024-01-03T09:00:00"),
        ("TEMP.0615", "Other outlet", "Start", "2024-01-04T08:00:00"),                # still running
    ]))
    assert ev["duration_h"].round(2).tolist()[:3] == [0.5, 0.5, 1.0]
    assert ev["event_end"].isna().tolist() == [False, False, False, True]
    assert ev["location"].nunique() == 3                 # one permit, two outlets
