# Ask SwimSignal

A question in plain words, answered from SwimSignal's own published data. "Somewhere within 40 minutes of Leeds, calm for paddleboarding, Saturday morning, kid-friendly" gets a short ranked list of spots. Under each spot are the lines SwimSignal's data has for that day, each with its source and date: official advice first, then the forecast level, water temperature, air, wind, river level, access and the practical guide. Anything the data does not have is listed as not known. Each spot links to its page, and the answer links to Plan a swim with the same day, place and distance.

This folder is the Cloudflare Worker that answers. It is **not deployed** and is **off**: `ASK_ON` is `"off"`, the secrets are not set, and the site shows nothing until the repository variable `DIPCAST_ASK_URL` is set.

## How a question is answered

1. On Plan a swim, the tile "Ask SwimSignal" (`src/dipcast/site/ask.js`) sends the question, and nothing else, to `POST /ask`. It appears only when spots.json has `"ask": {"url": ...}`, which the build adds when `DIPCAST_ASK_URL` is set (`build_site.ask_config`).
2. The Worker checks the origin, the length (300 characters), the connection's count for the day and the day's spend (below). Then it gives the question to Claude with four tools (`src/tools.js`):
   - `find_place`: a town in `data/places.json` (OS Open Names), the list Plan a swim uses.
   - `search_spots`: the spots within a straight-line distance, from `data/spots-lite.json`, with each one's level for the day and its official advice.
   - `get_spot`: one spot's lines for the day (`src/facts.js`), from `data/spots-lite.json` and the spot's `data/spot/<id>.json` for its guide.
   - `give_answer`: the answer.
   The tools read only the site's published files. The model has no web access and no other tools.
3. The model writes only four things: a short summary, how it read the question ("40 minutes read as 25 miles in a straight line"), a phrase on why each spot fits, and what the data does not know. Every fact the reader sees is written by `src/facts.js`, with the page's own level words (`levels.js`, `dayHeadline` and `dayAction`), not by the model.
4. `src/answer.js` checks `give_answer` before anyone sees it, and sends it back to the model with the problems if:
   - its words say "safe", "clean" or their kin ("safer", "pollution-free", "harmless" and so on, `NEVER`);
   - its words judge a spot "kid-friendly" or "suitable for children" (`KIDS`);
   - its words name a condition (calm, shallow, warm, clear and others, `CONDITIONS`) that no line it was shown says. A line that says the condition is not known ("cannot say whether the water will be calm") does not count. Words about one spot must find it in that spot's own lines; a sentence that names no spot must find it in the lines of every spot given;
   - its words give a number, with its unit, that the data does not give: "2 steps" is not "2 miles";
   - only what the tools gave back counts for these two. The question never does, and nor do the model's own tool inputs. A hedge or a "not known" in the model's own sentence never lets a condition through: "No wind forecast means the water is calm" says the water is calm. A condition the lines do not say may appear only in the unknown list, asked as a question ("Whether the water will be calm"), and an assumption may restate the question's numbers only before "read as" ("40 minutes read as 25 miles");
   - it names a spot it did not look up with `get_spot`;
   - its summary names a level ("low risk") for a day the forecast does not cover.
   After three refusals, or if the model never answers, refuses or runs out of turns, the reader gets the lines for the spots it looked up with a plain sentence, not the model's words.
5. The Worker also reorders the spots: one whose official advice restricts swimming goes after the others, and one at high or very high risk after those at low or moderate, whatever the model's order.

### What it says is not known

- **Wind**, always. SwimSignal has no wind forecast, so it cannot say whether water will be calm. A lake's line adds that wind decides where river water goes.
- **Travel time.** Distances are straight lines. The model turns a time into a distance (30 minutes about 20 miles, 40 minutes 25, an hour 35) and says so.
- **Suitability for children, beginners or paddleboards.** SwimSignal does not rate it. The guide's lines on getting in, paths and toilets are given instead, and the guide's rules are always shown.
- **The forecast outside its five days**, as "Forecast for Saturday 7 November: not known".
- **Water temperature for another day.** The estimate or reading is today's, and the line says so.
- **A spot with no guide yet.**

Adding wind would need a wind variable in the build's weather call (`build_site.attach_weather`), which is a separate change and costs Open-Meteo budget.

## Model and cost

The model is `claude-haiku-5-5` (`ASK_MODEL`), at `ASK_EFFORT = "medium"`. The task suits a small model: the tools do the searching, the code writes the facts, and the checks refuse a bad answer. Any model in `PRICES` (`src/index.js`) can be set instead; the Worker refuses a model it cannot price, because it could not count the cap.

**Estimated cost per question.** These are estimates, not measurements: no question has been sent to the API.

- What was measured: a typical question takes 4 calls. The requests the Worker builds for the eval set total about 34,000 to 41,000 characters of input over those calls, about 10,000 to 12,000 tokens at 3.5 characters a token.
- What was assumed: about 1,000 output tokens a call (thinking, tool calls and the answer), so about 4,000 a question. A refused answer adds a call.
- Prices: Anthropic's list as given in the claude-api reference (cached 6 October 2026). Check https://www.anthropic.com/pricing before deploying.

| Model | Input / output per million tokens | One question (12k in, 4k out) | 300 questions a day |
| --- | --- | --- | --- |
| Claude Haiku 5.5 (default) | $0.10 / $0.50 | about $0.003 | about $1 |
| Claude Sonnet 5.5 | $2 / $10 | about $0.06 | about $19 |
| Claude Opus 5.5 | $4 / $20 | about $0.13 | about $38 |

The first live run will give the real figure: `npm run eval -- --live` asks the 26 eval questions and prints the cost from the usage the API reports (about $0.08 on Haiku by the estimate above).

### The limits in the Worker

- **Daily spend cap**, `ASK_DAILY_CAP_USD` (default $1), per UTC day. Before calling the API a question reserves the most it could cost (8 calls of 40,000 input and 4,000 output tokens: $0.048 on Haiku, $0.96 on Sonnet), in one D1 statement, so two questions at once cannot both pass a cap only one fits under. When it ends, the reservation is swapped for the cost from the usage the API reported. A question that fails mid-way is charged its whole reservation. With Sonnet, raise the cap or only one question fits at a time.
- **Questions a day**, `ASK_QUESTIONS_PER_DAY` (default 300), in all.
- **Questions a day from one connection**, `ASK_PER_CONNECTION` (default 10). An IPv6 connection counts by its /64, as the reviews Worker counts.
- **One question**: 300 characters, at most 8 calls to the model, 4,000 tokens a call.

These limits are this Worker's own. Set a monthly spend limit on the Claude Console workspace too (step 1 below): it holds even if this code has a bug.

## Privacy

The Worker keeps no question and no answer, and logs neither: its log line has the number of calls, the cost and the number of spots. D1 holds two tables (`migrations/0001_ask.sql`): `hits`, a keyed hash (HMAC with `ASK_HASH_KEY`) of the connection and the day with that day's count, deleted by the daily cron the day after; and `spend`, each day's number of questions and cost. The question goes to Anthropic, which runs the model; Anthropic keeps API inputs for a limited time under its commercial terms. Check the retention period that applies to the account before switching on, and say it in the notice if you want it stated.

The privacy notice's section is `ASK_PRIVACY` in `scripts/build_site.py`. The build adds it, before "The server version", only when `DIPCAST_ASK_URL` is set, and puts "(Ask SwimSignal)" after the notice's date. Its text:

> On Plan a swim you can ask a question in your own words. When you press Ask, your question is sent to SwimSignal's Ask service, which runs on Cloudflare Workers, and from there to Anthropic, whose AI model, Claude, reads SwimSignal's published data to answer it. Nothing else is sent: not your location, your saved spots or your plan. Do not put your name or other personal details in a question. SwimSignal does not keep your question or its answer. To limit how many questions one connection can ask in a day, the service keeps a count under a keyed hash of your IP address and the day, never the address itself, and deletes it the day after. It also keeps each day's total number of questions and what they cost, with nothing that links them to anyone. Anthropic processes the question for SwimSignal and keeps it for a limited time under its own terms; Anthropic's privacy policy applies to that. Cloudflare sees your IP address when you press Ask, as any web server would; Cloudflare's privacy policy applies to that. Either may handle the question outside the UK under its own safeguards. The basis is SwimSignal's legitimate interest in answering the question you chose to ask. The answer is written by an AI model from SwimSignal's data and can be wrong: check a spot's page and the signs at the water.

## Tests and the eval set

From this folder, with no npm install needed (the tests never load the Anthropic SDK):

```
node --test test/*.test.js
```
```
npm run eval
```

You will know they passed when the first ends `ℹ fail 0` and the second ends `26 of 26 passed (scripted model)`.

- `evals/questions.json`: 26 questions, each with what a grounded answer must show (`expect`) and a scripted model run (`mock`). Ten scripts give a bad answer first (says "safe", invents a spot, a condition, a number, or a level for a day outside the forecast; takes a condition or a number from the question; gives a number in another unit; borrows one spot's condition for another; infers a condition from a missing forecast) and check the Worker turns it back; two never answer; one ends in a refusal.
- `evals/check.js`: the checks, the same for mocked and live runs. Every answer is also checked for: no "safe", "clean" or judgement for children in the model's words; official advice as each spot's first line; wind said to be not known; a source on every line; links to the spot's page and Plan a swim; a restricted spot never first.
- `test/fixtures/`: twelve spots, their guides and nineteen places, cut from the live site's files of 31 October 2026 (issued 18:13 UTC).

`npm run eval -- --live` runs the same questions against the real API with `ANTHROPIC_API_KEY` from your environment, on the same fixtures. It needs `npm install` first and costs money. `--model claude-sonnet-5-5` tries another model; `--only id,id` runs some questions; `--show` prints each answer. On a live run the scripted-run checks (`mock_expect`) are skipped and the rest apply.

## Deploying (Ethan's decision; nothing here has been done)

Decide first:

- **Whether to pay for it.** It needs a Claude API account with a payment method. At the defaults the most it can spend is $1 a day, about $30 a month; the estimate for 300 questions a day on Haiku is about $1.
- **The cap**, `ASK_DAILY_CAP_USD`, and **the model**, `ASK_MODEL`. Haiku is the default; run the live eval on Haiku and on Sonnet and compare before choosing a larger one.
- **Anthropic's retention** for the account, for the privacy notice (above).

Then, in order:

1. In the Claude Console (console.anthropic.com), make a workspace for SwimSignal, set its monthly spend limit, and create an API key in it. You will know it worked when the key is listed under the workspace.
2. From this folder: `npm install`, then `ANTHROPIC_API_KEY=<the key> npm run eval -- --live`. You will know it worked when it ends "26 of 26 passed" with a cost. If questions fail, read them with `--show` before going on.
3. `npx wrangler d1 create swimsignal-ask --jurisdiction=eu`, and paste the `database_id` it prints into `wrangler.toml`.
4. `npx wrangler d1 migrations apply swimsignal-ask --remote`.
5. `npx wrangler secret put ANTHROPIC_API_KEY` (the key from step 1) and `npx wrangler secret put ASK_HASH_KEY` (any long random string, for example from `openssl rand -hex 32`).
6. Set `ASK_ON = "on"` in `wrangler.toml`, then `npx wrangler deploy`. You will know it worked when this answers with an answer, not an error:
   ```
   curl -s -X POST https://swimsignal-ask.<your-subdomain>.workers.dev/ask -H 'Origin: https://swimsignal.co.uk' -H 'Content-Type: application/json' -d '{"question":"Swimming near Ilkley tomorrow?"}'
   ```
7. Set the repository variable `DIPCAST_ASK_URL` to the Worker's address, ending in `/`. The next site build shows the tile on Plan a swim and adds the privacy section.

The likely mistake is step 6 before step 4: every question then answers 500 ("no such table: hits"), because `wrangler deploy` does not apply migrations. Another is setting `DIPCAST_ASK_URL` before the Worker answers: the tile then shows and every question fails.

To switch it off: set `ASK_ON = "off"` and deploy (questions answer "not switched on"), and unset `DIPCAST_ASK_URL` (the tile goes at the next build).
