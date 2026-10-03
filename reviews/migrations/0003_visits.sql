-- Quick notes on a visit: what a spot was like today or yesterday, as ticks from a fixed list (rules.js,
-- VISIT_KINDS), a few words and one photo. A review describes the place; a note describes a day there,
-- so each one ends: `until` is the last day any of its ticks is shown, and the daily cron deletes the
-- note, and its photo, after that. A note of only ticks is published at once (rules.js says why);
-- one with words or a photo waits for the operator, as a review does.
CREATE TABLE visits (
  id TEXT PRIMARY KEY,
  spot TEXT NOT NULL,
  seen_on TEXT NOT NULL,                              -- YYYY-MM-DD, the day of the visit (London time)
  kinds TEXT NOT NULL,                                -- JSON: the ticks, ids from VISIT_KINDS
  body TEXT NOT NULL DEFAULT '',
  photo TEXT NOT NULL DEFAULT '[]',                   -- JSON: [{"w","h","tw","th"}], at most one
  confirmed_on TEXT,                                  -- the last day another swimmer said it is still so
  confirmations INTEGER NOT NULL DEFAULT 0,
  verified TEXT NOT NULL DEFAULT '',                  -- the operator's source for confirming pollution or algae
  until TEXT NOT NULL,                                -- YYYY-MM-DD, the last day it is shown
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'published')),
  created_at TEXT NOT NULL,
  published_at TEXT,
  token_hash TEXT NOT NULL                            -- SHA-256 of the key the sender's browser keeps
);
CREATE INDEX visits_by_status ON visits (status, created_at);
CREATE INDEX visits_by_until ON visits (until);
