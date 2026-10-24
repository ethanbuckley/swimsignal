# Moving the site to Cloudflare Pages, October 2026

Item 6 of `docs/MARKETS-2026-10.md` section 6a. Written on 20 October 2026.

Marks: **[checked]** I opened the source or ran the command on 20 Oct 2026. **[inferred]** my reasoning,
not a fact. **[unverified]** a claim from a source that is not Cloudflare's own documentation.

## 1. Summary

The site can move to Cloudflare Pages with no change to how it is built. It fits Cloudflare's limits
with room to spare, and Cloudflare's terms do not bar business use. The Workers need no change, because
they check the domain, not the host.

The workflow change is in the same PR as this file. Merging it changes nothing. The site keeps deploying
to GitHub Pages until the secret `CLOUDFLARE_API_TOKEN` exists. From the first build after the secret
is added, the site deploys to Cloudflare Pages and GitHub Pages stops getting updates. Ethan then
switches the domain's DNS records (section 6).

One visible change: Cloudflare Pages redirects `/about.html` to `/about` (section 4). Links still work.
Each one costs one extra round trip until a follow-up changes the links.

## 2. Why move

GitHub's Pages limits page says Pages is "not intended for or allowed to be used as a free web-hosting
service to run your online business", e-commerce, or commercial software as a service **[checked]**
(https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits). A paid
pilot or a sponsor makes SwimSignal a business, so it must be hosted elsewhere first. Since 24 Oct 2026
the switch waits until a customer commits in writing (`docs/ORGANISER-PIVOT-2026-10.md`, "Revised 24
October 2026").

Cloudflare's Service-Specific Terms for the Developer Platform cover Pages. They say the platform "can be
used to host content", ban phishing and volumetric attacks, and set no rule against commercial or
business use **[checked]** (https://www.cloudflare.com/service-specific-terms-developer-platform/,
last updated 28 Sep 2026). Its rule on video applies to Cloudflare Stream, which SwimSignal does not use.

## 3. The site against Cloudflare Pages' limits

Measured on the artifact of site.yml run 39416990535 (20 Oct 2026, 11:43 UTC) **[checked]**:

| | The built site | Cloudflare Pages Free plan | Source |
|---|---|---|---|
| Files | 2,691 | 20,000 per site | limits page |
| Largest file | 7.9 MB (`data/verification_live.csv`); next `data/overflows.geojson` 6.3 MB | 25 MiB per file | limits page |
| Total size | 76 MB | no total limit stated | limits page |
| `_headers` rules | 3 (written by the deploy job) | 100 | limits page |
| Deploys | up to 48 a day, about 1,500 a month | 500 builds a month, for Git-connected builds | limits page, community answer |

Sources: https://developers.cloudflare.com/pages/platform/limits/ and
https://developers.cloudflare.com/pages/get-started/direct-upload/ (wrangler uploads: 20,000 files,
25 MiB each) **[checked]**.

**The 500-builds limit.** Cloudflare's limits page ties it to Git pushes: "Each time you push new code to
your Git repository, Pages will build and deploy your site." It does not say whether `wrangler pages
deploy` uploads count. A Cloudflare Community MVP (Erisa, not staff) answered in April 2023 that they do
not: "using wrangler pages publish does not count towards the build limit. At the moment you can do an
unlimited amount of those." **[checked that the answer says this; unverified as policy]**
(https://community.cloudflare.com/t/builds-vs-deployments/494717). The workflow uses wrangler, so this
applies. If Cloudflare ever counts uploads, the free plan would run out about 10 days into a month. The
fix would be to deploy hourly or pay for Pro (5,000 a month). Check the count once in the first week
(section 7, step 5).

The click-anywhere files are well inside the limits: `data/anypoint/` is 28 MB in all, and its largest
file is 0.98 MB.

## 4. What assumes GitHub Pages, and what changes

| Place | What it assumes | On Cloudflare Pages |
|---|---|---|
| `.github/workflows/site.yml`, `deploy` job | `actions/deploy-pages` | Skipped once the secret is set. The new `deploy-cloudflare` job runs instead. |
| GitHub's Settings → Pages, custom domain `swimsignal.co.uk` | No CNAME file: the domain is set in the settings **[checked: `gh api repos/ethanbuckley/swimsignal/pages` gives `cname: swimsignal.co.uk`]** | Unaffected. The site has no CNAME file to remove. |
| `404.html` at the root (`scripts/build_site.py`, `not_found_page`) | GitHub serves it for any missing address, at any depth | Same. Pages looks for the nearest `404.html` up the tree, ending at `/404.html` **[checked, serving-pages doc]**. Its links are already absolute. |
| `.nojekyll` | Stops GitHub running Jekyll | Ignored. It is still uploaded, as an empty file. |
| Base paths | Pages use a relative `<base>`, so they work at any address | Unaffected. |
| `site_url()` in `build_site.py` | Falls back to the github.io address when `DIPCAST_SITE_URL` is unset | Unaffected while that variable stays set. The live canonical link is `https://swimsignal.co.uk/` **[checked]**, so it is set. |
| `push/wrangler.toml`, `reviews/wrangler.toml` | `SITE_URL = "https://swimsignal.co.uk/"`, `ALLOWED_ORIGIN = "https://swimsignal.co.uk"` | Unaffected: same domain. The pages.dev address is refused by both Workers, which is right. |
| `push/src/dispatch.js` | Reads `SITE_URL/data/spots-lite.json` to see when the last build ran, then asks GitHub to run site.yml | Unaffected. It reads the same address, and site.yml still runs on GitHub. |
| Response headers | GitHub sends `Access-Control-Allow-Origin: *` and `Cache-Control: max-age=600` **[checked with curl]** | The deploy job writes a `_headers` file that keeps `Access-Control-Allow-Origin: *`. Pages sends `Cache-Control: public, max-age=0, must-revalidate` with an ETag **[checked, serving-pages doc]**. Browsers then check for a new copy on every load and get a 304 if nothing changed. Data will be fresher, not staler. |
| `.html` addresses | GitHub serves both `/verification` and `/verification.html` with 200 **[checked with curl]** | Pages redirects `/contact.html` to `/contact` **[checked, serving-pages doc]**. The doc gives neither the status code nor whether the query string is kept. Check both before the DNS switch (section 6, step E). |
| `sw.js` | Stores `feedback.html` when it installs | Offline only: the stored copy will be a redirected response. Chrome refuses a redirected response for a page navigation, so an offline visit to the feedback page may show an error instead of the stored page **[inferred]**. Online use is unaffected. Follow-up in section 9. |
| Search engines | The sitemap lists `/about.html` and the other prose pages | They will follow the redirect. Changing the sitemap and links to extensionless addresses avoids it. GitHub serves those too, so the change is safe before the move. Follow-up in section 9. |
| The pages.dev address | none | The `_headers` file sends `X-Robots-Tag: noindex` on `swimsignal.pages.dev` and its preview addresses, so search engines do not index a second copy. This is Cloudflare's own example **[checked, headers doc]**. |

The Workers static-assets product was checked as an alternative, because it can switch off the `.html`
redirect (`html_handling = "none"`). It is not used: with `none`, `/` and `/spot/<id>/` stop serving
their `index.html` **[checked]**
(https://developers.cloudflare.com/workers/static-assets/routing/advanced/html-handling/).

## 5. The workflow change

Three changes to `.github/workflows/site.yml`:

1. The `build` job's first step reads only whether the secret `CLOUDFLARE_API_TOKEN` is set
   (`secrets.CLOUDFLARE_API_TOKEN != ''`), never its value. It sets the job output `host` to
   `cloudflare` or `github`.
2. The `deploy` job (GitHub Pages) runs only when `host` is `github`.
3. A new `deploy-cloudflare` job runs only when `host` is `cloudflare`. It has no repository checkout
   and no GitHub token (`permissions: {}`). It downloads the same `github-pages` artifact the build
   uploads, unpacks it, writes `_headers`, and runs
   `npx wrangler@4.146.0 pages deploy site --project-name=swimsignal --branch=main`. The token is only
   in this job, which runs no code from the repository.

It needs, besides the secret, the repository variable `CLOUDFLARE_ACCOUNT_ID`. If the secret is set and
the variable is not, the job stops with an error naming the variable. The variable
`CLOUDFLARE_PAGES_PROJECT` is optional: unset means `swimsignal`.

**Tested on a runner** **[checked]**: throwaway workflow on a throwaway branch (run 39419994822,
branch deleted afterwards). Its steps were copied from the new site.yml. Results:
- the host step gives `github` when the secret is unset, and `cloudflare` when one is set (tested with
  `GITHUB_TOKEN`, which is always set);
- the job with `permissions: {}` downloads and unpacks an `upload-pages-artifact@v3` artifact, keeping
  `.nojekyll`, `404.html` and subfolders;
- `_headers` comes out as intended;
- wrangler 4.146.0 installs on Node 22 and stops at the missing token, before any upload.

Not tested: a real upload, which needs Ethan's token. The first real run is section 6, step D.

## 6. What Ethan does

Do steps A to F in one sitting, at a quiet time (for example a weekday evening). From step D until
step F, swimsignal.co.uk still points at GitHub Pages, which stops getting new builds. The forecast
there goes stale until the DNS switch. The site's own "Stale" banner shows after 8 hours.

**A. Create the Pages project** (Terminal, in `push/` where wrangler is already logged in):

```bash
npx wrangler@4.146.0 pages project create swimsignal --production-branch=main
```

You will know it worked when it prints the address `https://swimsignal.pages.dev/`. If it prints a
different address, such as `swimsignal-abc.pages.dev`, the name was taken. Then set the repository
variable `CLOUDFLARE_PAGES_PROJECT` to the project name it shows, and use that address in step E.

Likely mistake: leaving out `--production-branch=main`. Wrangler then asks for one, and a different
answer makes every deploy a preview, so the custom domain never updates. The workflow always deploys
with `--branch=main`.

**B. Create the API token.** dash.cloudflare.com → My Profile → API Tokens → Create Token → Create Custom
Token. Name it `swimsignal site deploy`. Under Permissions, choose Account, Cloudflare Pages, Edit. That
is the only permission Cloudflare's CI guide lists
(https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/).
Under Account Resources, include only your account. Create it, and copy the token: it is shown once.

**C. Find the account ID:**

```bash
npx wrangler@4.146.0 whoami
```

It prints a table with an Account ID (32 hex characters).

**D. Give GitHub the two values.** Set the variable first, then the secret:

```bash
gh variable set CLOUDFLARE_ACCOUNT_ID -R ethanbuckley/swimsignal --body PASTE_THE_ACCOUNT_ID
```

```bash
gh secret set CLOUDFLARE_API_TOKEN -R ethanbuckley/swimsignal
```

The second command asks for the value: paste the token and press Return. Then start a build, or wait up
to 30 minutes for the next one:

```bash
gh workflow run site.yml -R ethanbuckley/swimsignal
```

You will know it worked when the run's graph shows `deploy-cloudflare` green and `deploy` skipped. The
last lines of the "Deploy to Cloudflare Pages" step say the deployment is complete and give a pages.dev
address.

Likely mistake: setting the secret before the variable. A build that starts in between fails at
`deploy-cloudflare`, and the site gets no update from that run.

**E. Check the pages.dev copy before touching DNS.** Each command should print what is shown after it:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://swimsignal.pages.dev/
```
`200`

```bash
curl -s https://swimsignal.pages.dev/data/spots-lite.json | head -c 120
```
starts `{"generated_at":"` with this build's time

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://swimsignal.pages.dev/nope/deeper
```
`404` (and the page in a browser is SwimSignal's "Page not found")

```bash
curl -sI "https://swimsignal.pages.dev/embed.html?spot=thames-henley" | grep -iE "^(HTTP|location)"
```
a 3xx status, and a `location` that ends `/embed?spot=thames-henley`. **If the `?spot=` part is missing,
stop.** Every embed on other sites would then lose its spot. Tell Claude: the fix is to rename the links,
not to move.

```bash
curl -sI https://swimsignal.pages.dev/ | grep -iE "^(x-robots-tag|access-control-allow-origin)"
```
`x-robots-tag: noindex` and `access-control-allow-origin: *`

**F. Switch the domain.** dash.cloudflare.com → swimsignal.co.uk → DNS → Records.

1. Write down the 4 A records and 4 AAAA records named `swimsignal.co.uk` (185.199.108–111.153 and
   2606:50c0:8000–8003::153; checked with `dig` on 20 Oct 2026), and the CNAME `www` →
   `ethanbuckley.github.io`. These are the rollback.
2. Delete the 4 A and 4 AAAA records for `swimsignal.co.uk`. Leave MX, TXT and the `send` records alone:
   they are email.
3. Workers & Pages → swimsignal → Custom domains → Set up a custom domain → `swimsignal.co.uk` →
   Continue → Activate domain. Cloudflare adds the CNAME itself, because the zone is on the same
   account (custom-domains doc).
4. For `www`: edit the `www` record so it is an A record to `192.0.2.1`, Proxied. Then add a Bulk
   Redirect from `www.swimsignal.co.uk` to `https://swimsignal.co.uk`, status 301, with "Preserve query
   string" and "Preserve path suffix" ticked. This is Cloudflare's www guide
   (https://developers.cloudflare.com/pages/how-to/www-redirect/). GitHub does the same redirect today.

You will know it worked when the custom domain shows "Active" (usually minutes **[inferred]**), and
`curl -sI https://swimsignal.co.uk/` shows `server: cloudflare` and no `x-github-request-id`.

Likely mistake: adding the custom domain before deleting the A and AAAA records. A CNAME cannot sit
beside A records with the same name, so activation fails or waits **[inferred]**. Delete first. The gap
is the few minutes until the domain is active.

Second likely mistake: turning on proxy features that were off while the records were DNS-only. Bot
Fight Mode and a high Security Level now apply to every visitor. They can challenge feed readers,
calendar apps and the push Worker's fetch of `spots-lite.json`. Leave Security → Bots as it is now, and
check section 7, step 4.

## 7. How to verify after the switch

1. `curl -sI https://swimsignal.co.uk/` gives `HTTP/2 200` and `server: cloudflare`.
2. `curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" https://www.swimsignal.co.uk/spot/thames-henley/`
   gives `301 https://swimsignal.co.uk/spot/thames-henley/`.
3. Open the site on the iPhone. The home page, a spot page and the map load. Turn on alerts for a spot:
   the button works, because the push Worker still sees the origin `https://swimsignal.co.uk`.
4. Within an hour: in the push Worker's logs (dash → Workers & Pages → swimsignal-push → Logs), the
   dispatch line says `the last build started N min ago`, not `spots-lite.json: HTTP …`.
5. After a week: Workers & Pages → swimsignal → Deployments lists about 48 production deployments a
   day. If the dashboard shows a build count against a 500 limit, tell Claude (section 3).
6. GitHub → Settings → Pages may say the DNS check failed. That is expected, because the domain no
   longer points at GitHub.

## 8. Rollback

Takes about 10 minutes. Keep GitHub Pages switched on for two weeks after the move so this stays
possible.

1. Delete the secret, so builds deploy to GitHub Pages again:
   ```bash
   gh secret delete CLOUDFLARE_API_TOKEN -R ethanbuckley/swimsignal
   ```
2. Start a build, so GitHub Pages has today's site:
   ```bash
   gh workflow run site.yml -R ethanbuckley/swimsignal
   ```
   Wait for the `deploy` job to go green.
3. Cloudflare DNS: delete the `swimsignal.co.uk` CNAME that Pages added. Re-add the 4 A and 4 AAAA
   records from step F.1, set to DNS only. Change `www` back to a CNAME to `ethanbuckley.github.io`,
   DNS only, and delete the Bulk Redirect.
4. Workers & Pages → swimsignal → Custom domains → ⋯ → Remove domain.
5. GitHub → Settings → Pages: if the custom domain shows an error, remove `swimsignal.co.uk`, save, add
   it again, save, and tick Enforce HTTPS once the certificate is issued.

You will know it worked when `curl -sI https://swimsignal.co.uk/` shows `server: GitHub.com`.

After two stable weeks, unpublish the GitHub Pages copy (Settings → Pages → Unpublish site), so no
GitHub-hosted copy remains when pilots are paid. After that, rollback also needs Pages switched back on
(Settings → Pages → Source: GitHub Actions) before step 2.

## 9. Follow-ups

- **Extensionless links.** Write internal links and sitemap entries as `/about`, not `/about.html`.
  GitHub Pages already serves both, so this can merge before the move. It saves a redirect per click
  and gives search engines one address per page.
- **Service worker.** Store `feedback` rather than `feedback.html`, or rebuild a redirected response
  before storing it (`new Response(res.body, res)`). Then the offline copy works on both hosts.
- **Words.** The README's build description, and the "Hosting" bullet under "Before taking money or
  running ads", should say Cloudflare Pages once the move is done (item 7 of section 6a covers the
  site's own words).
- **After the move:** delete the `CLOUDFLARE_PAGES_PROJECT` fallback if unused, and pin a newer wrangler
  when the pinned one is a year old.

## 10. Sources opened on 20 Oct 2026

- GitHub Pages limits: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
- Cloudflare Pages limits: https://developers.cloudflare.com/pages/platform/limits/
- Direct Upload: https://developers.cloudflare.com/pages/get-started/direct-upload/
- Direct Upload with CI: https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/
- Serving pages (redirects, 404, caching): https://developers.cloudflare.com/pages/configuration/serving-pages/
- Headers: https://developers.cloudflare.com/pages/configuration/headers/
- Custom domains: https://developers.cloudflare.com/pages/configuration/custom-domains/
- www redirect: https://developers.cloudflare.com/pages/how-to/www-redirect/
- Workers static assets, HTML handling: https://developers.cloudflare.com/workers/static-assets/routing/advanced/html-handling/
- Cloudflare Service-Specific Terms, Developer Platform: https://www.cloudflare.com/service-specific-terms-developer-platform/
- Community answer on wrangler deploys and the build limit: https://community.cloudflare.com/t/builds-vs-deployments/494717
