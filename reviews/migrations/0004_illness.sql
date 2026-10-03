-- "I got ill after swimming here": a swimmer's report of illness after a swim at a spot. It is
-- information about health (UK GDPR Article 9), so a row holds as little as it can: no name, contact,
-- words, photo, time of day or address, and nothing that links it to a connection (the rate limits
-- count in `hits`, apart). Only counts of reports are ever published, from ILLNESS_MIN (rules.js). The
-- daily cron deletes a report ILLNESS_KEEP_DAYS after it arrived. Off until ILLNESS_REPORTS is "on"
-- (wrangler.toml); README.md, "Illness reports", has the reasons.
CREATE TABLE illness (
  id TEXT PRIMARY KEY,
  spot TEXT NOT NULL,
  swam_on TEXT NOT NULL,                              -- YYYY-MM-DD, the day of the swim: within 14 days of sending
  symptoms TEXT NOT NULL,                             -- JSON: ids from ILLNESS_SYMPTOMS (rules.js), at least one
  onset INTEGER NOT NULL CHECK (onset BETWEEN 0 AND 3),   -- days from the swim to the first symptom; 3 is "3 or more"
  doctor INTEGER CHECK (doctor IN (0, 1)),            -- saw a doctor or called 111; NULL when not answered
  received_on TEXT NOT NULL,                          -- YYYY-MM-DD (London), the day it arrived; never the time
  token_hash TEXT NOT NULL                            -- SHA-256 of the key the sender's browser keeps, to delete it
);
CREATE INDEX illness_by_received ON illness (received_on, spot);
