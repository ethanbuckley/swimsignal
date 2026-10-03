// The limits a review is held to, in a module of their own: the Workers runtime treats every named
// export of the main module (index.js) as an entry point, and refuses to start when one is a number,
// an object or an array rather than a function ("Incorrect type for map entry").

export const MAX_PHOTOS = 3, MAX_TEXT = 1500, MAX_NAME = 40;
// Requests a day from one connection. The page sends one request a review, so a swimmer never meets
// these; a script that floods the queue does.
export const LIMITS = { review: 10, report: 20, remove: 30, status: 60, visit: 10, confirm: 30, illness: 4 };
// For everyone together. KV takes 1,000 writes a day on the free plan, two a photo, and holds 1 GB:
// at most 300 photos a day and 300 reviews waiting for the operator. Published photos accumulate;
// the operator must monitor storage and move to R2 before the store fills.
export const PHOTOS_PER_DAY = 300, MAX_PENDING = 300;
// A budget below KV's 1 GB limit, with an earlier warning. Includes space reserved by uploads
// and deletions waiting to be retried, so a failing KV operation never makes the store look empty.
export const PHOTO_STORAGE_LIMIT = 800_000_000, PHOTO_STORAGE_WARN = 640_000_000;
// Published reviews the moderation page lists, newest first; older ones by id (README).
export const PUBLISHED_LISTED = 500;
export const REASONS = ['not-about-spot', 'rude', 'person', 'spam', 'other'];

// ---- quick notes on a visit (migrations/0003_visits.sql) ----
// The ticks a note can carry. `days`: how long after the visit it is shown (1 = that day and the next).
// `confirm`: another swimmer can say it is still so, which starts its days again from that day; the
// rest simply end. `tone` orders a spot's notes: suspected pollution or algae first, then hazards, then
// the rest, and good news last, so that a good visit never sits above, or reads as cancelling, a
// warning. The page's copy of this list (src/dipcast/site/visits.js) has the words; a test keeps the
// two the same.
export const VISIT_KINDS = {
  pollution: { days: 3, tone: 'observation' },
  algae: { days: 7, tone: 'observation' },
  steps: { days: 30, tone: 'warning', confirm: true },
  access: { days: 14, tone: 'warning', confirm: true },
  rough: { days: 2, tone: 'warning' },
  sign: { days: 30, tone: 'warning', confirm: true },
  'parking-closed': { days: 14, tone: 'info', confirm: true },
  'parking-full': { days: 1, tone: 'info' },
  busy: { days: 1, tone: 'info' },
  quiet: { days: 1, tone: 'info' },
  clear: { days: 1, tone: 'good' },
  good: { days: 1, tone: 'good' },
};
export const MAX_VISIT_TEXT = 280, MAX_VERIFIED = 120, MAX_PENDING_VISITS = 300;
// A note of ticks alone is published as it arrives: its words are the site's own, from the list above,
// and it names no one, so there is nothing for the operator to read first, and a note about today is
// worth little two days later. Words or a photo still wait for the operator. False makes every note wait.
export const PUBLISH_TICKS_AT_ONCE = true;
export const VISIT_REASONS = ['not-now', 'not-about-spot', 'rude', 'person', 'spam', 'other'];

// ---- reports of illness after a swim (migrations/0004_illness.sql) ----
// Health information, so: the fewest fields that can test a forecast, counts the only thing published,
// and off until ILLNESS_REPORTS is "on" in wrangler.toml. README.md, "Illness reports", has the reasons.
// The kinds of symptom, as ticks. The page's copy (src/dipcast/site/illness.js) has the words; a test
// keeps the two the same.
export const ILLNESS_SYMPTOMS = ['gut', 'ear', 'eye', 'skin', 'other'];
// A swim at most this many days before the report: most illness from water starts within days, and an
// older swim is remembered less well.
export const ILLNESS_DAYS_BACK = 14;
// The smallest count published, for a spot and a window. Five, the k of the NHS's standard for
// publishing health data, which the ICO's anonymisation guidance cites: a count of one or two could
// name someone to anyone who knows who swam there. README.md says more.
export const ILLNESS_MIN = 5;
// A report is deleted this many days after it arrived (about 13 months): long enough to compare a whole
// summer with the forecasts after it ends, and no longer.
export const ILLNESS_KEEP_DAYS = 400;
// Reports in one day, for one spot and for everyone together: more than any real outbreak at an inland
// spot would send, few enough that a script cannot bury the counts in one day.
export const ILLNESS_SPOT_DAY = 25, ILLNESS_PER_DAY = 300;
