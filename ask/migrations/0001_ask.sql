-- Questions a day from one connection, for the limit. The key is a keyed hash of the IP address and the
-- day, never the address; the daily cron deletes days before yesterday.
CREATE TABLE hits (
  key TEXT NOT NULL,
  day TEXT NOT NULL,
  n INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (key, day)
);

-- Each day's questions and spend (UTC days), for the daily cap. Millionths of a US dollar. No question,
-- answer or connection is kept here, only the totals.
CREATE TABLE spend (
  day TEXT PRIMARY KEY,
  questions INTEGER NOT NULL DEFAULT 0,
  reserved_micro INTEGER NOT NULL DEFAULT 0,
  spent_micro INTEGER NOT NULL DEFAULT 0
);
