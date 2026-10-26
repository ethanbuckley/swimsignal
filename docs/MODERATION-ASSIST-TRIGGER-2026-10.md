# When to add help with moderation: a trigger, not a build

Written 26 October 2026. Nothing is built. Reviews, notes on a visit and illness reports stay as they are: rules in the
Worker first, and nothing published without Ethan (`reviews/README.md`).

## The answer

Do not add a model to moderation now. The queue is empty. Revisit only when the volume in the trigger below is reached.
When it is, tighten the Worker's own rules first. An outside model comes last, and only after a privacy review.

## Volume today

- Read on 26 October 2026, 18:36 UTC, from the public list the site build reads
  (`https://swimsignal-reviews.swimsignal-push.workers.dev/published`): **0 published reviews and 0 notes showing.**
- The number waiting was not read. It needs the admin password, and this note does not use it. `/moderate` shows it.

## What already protects the queue

From `reviews/README.md` and `reviews/src/rules.js`:
- Every review, and every note with words or a photo, waits for Ethan to press Publish. A note of ticks alone is
  published at once, because its words are the site's own.
- Per-connection limits per day (10 reviews, 10 notes, 20 reports, 4 illness reports), 300 photos a day, 300 waiting.
- Text is set as text, never markup, on `/moderate`; photos lose camera metadata on the phone and again in the Worker.
- Suspected pollution or algae reads "Not verified" until Ethan names an official source.
- Illness reports are never shown one by one, and are reviewed as batches.

## The trigger

Proposed defaults, for Ethan to change. Any one starts a review of this note:
1. **Waiting items:** more than 50 waiting on `/moderate` at a weekly look, three weeks running.
2. **Time:** moderation takes Ethan more than 30 minutes a week, four weeks running.
3. **A cap is hit:** the 300-waiting cap or the 300-photos-a-day cap is reached once.
4. **Reports:** more than 10 reviews reported by readers in a week.

How it would be counted: by eye on `/moderate` at the weekly look, written in `swimsignal-private/measure/`. No new
endpoint or logging is built for this.

## What happens then, in order

1. **More rules in the Worker.** For example: links, phone numbers and email addresses held for a closer look;
   near-duplicate text from one spot within a day; a short word list. These run inside the Worker. Nothing leaves it.
2. **A model that runs on Ethan's own machine,** to sort the queue before he reads it. Reviews and photos still never
   leave his control. Ethan still presses Publish.
3. **An outside model service,** only after all of these: a short DPIA (data protection impact assessment) that
   covers it; the privacy notice changed to say so before any review is sent; a data processing agreement with the
   provider; and Ethan's decision. Photos can show people, including children, so they are the last thing to send, if
   ever.

## What never changes

- No model publishes or deletes anything by itself.
- Nothing from moderation touches a forecast or a spot's level.
- Illness reports are never sent to any model.
- Real reviews and photos are not sent to any outside model for testing either. Tests use made-up text.
