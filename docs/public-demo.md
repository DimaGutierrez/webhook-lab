# Public interactive demo

**URL:** https://diegogutierrez.pages.dev/webhook-lab/

The public demo runs entirely in the visitor's browser. Cloudflare Pages serves the HTML, CSS and JavaScript; no service runs on the author's computer. It has no server API, database binding, billing integration, analytics or external delivery targets.

## What you can try

- Add fictional sample events and inspect payloads and diagnostic headers.
- Simulate failed (503), accepted (200) and timed-out replay attempts.
- Compare attempt history while keeping the original payload and stable event key.
- Search the loaded page, paginate, download a sample body and reset the demo.

All results and timings are simulated. A simulated 200 does not demonstrate exactly-once processing. Data exists only in memory in the current browser tab. Reloading restores the samples; tabs do not share events. Limits are 100 events and 50 attempts per event.

For actual HTTP capture, SQLite persistence and delivery to configured services, install the Python/FastAPI backend using the README. The browser demo is not a hosted version of that backend.

## Source and checks

`demo/index.html`, `demo/style.css`, `demo/app.js` and `demo/engine.mjs` are the four deployment files. They use relative asset URLs, so they can be hosted in a subdirectory. Tests: `node --test demo/engine.test.mjs` (Node 22+).

Copy only the four deployment files into `webhook-lab/` in the existing portfolio build. Preserve every existing portfolio asset and configuration file when creating a Pages deployment. Do not upload only the demo directory as the complete portfolio deployment.

The route is deliberately absent from the portfolio menu and sitemap and has a `noindex` directive. Anyone with the link can open it; being unlisted is not access control. The deployed route has a Content Security Policy with `connect-src 'none'` and does not make API requests. No Pages Functions or Workers were added.
