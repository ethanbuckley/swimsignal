-- A partner's file of water-sample results (docs/PARTNER-SAMPLES-CONTRACT-v1.md), sent from the partner page and held
-- for the operator. Never published by the Worker: no public route reads this table. The operator downloads a file
-- on /moderate, checks it with scripts/partner_samples.py and, once the permissions are confirmed in writing, moves
-- it to the private folder; Accept marks that done. The daily cron deletes every row PARTNER_KEEP_DAYS (rules.js)
-- after it arrived, contact details and file with it. Off until PARTNER_SAMPLES is "on" (wrangler.toml);
-- docs/PARTNER-PROGRAMME-2026-11.md has the reasons.
CREATE TABLE partner_submissions (
  id TEXT PRIMARY KEY,
  organisation TEXT NOT NULL,                 -- the group, club or lab, as the sender writes it
  contact_name TEXT NOT NULL,                 -- may be empty
  email TEXT NOT NULL,                        -- to reply to: the only way to reach the sender
  message TEXT NOT NULL,                      -- may be empty
  filename TEXT NOT NULL,                     -- as the sender's computer named it
  csv TEXT NOT NULL,                          -- the file, as sent (UTF-8, at most MAX_PARTNER_CSV bytes)
  sha256 TEXT NOT NULL,                       -- of the file, to match it with what is checked and kept
  partner_id TEXT NOT NULL,                   -- the file's own partner_id
  rows INTEGER NOT NULL,                      -- results in the file, the header not counted
  first_day TEXT,                             -- the earliest and latest sampled_on in the file, where real dates
  last_day TEXT,
  status TEXT NOT NULL CHECK (status IN ('pending', 'accepted')),
  created_at TEXT NOT NULL,
  decided_at TEXT,
  token_hash TEXT NOT NULL                    -- SHA-256 of the key the sender's browser keeps, to withdraw it
);
CREATE INDEX partner_submissions_by_status ON partner_submissions (status, created_at);
