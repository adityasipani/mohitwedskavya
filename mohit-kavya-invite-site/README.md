# Mohit & Kavya: wedding invitation

A single-page animated wedding invite: envelope opening, scratch-to-reveal dates, event chapters with video, a gallery, a dress-code guide, a guest quiz with live results, RSVP contacts and a countdown.

## Files
- `index.html`: the whole invite (markup, styles and script). Text such as names, dates, events, contacts and gallery photos lives in the `INVITE` object near the top of the main script.
- `*.webp` / `*.mp4` / `music.mp3`: artwork, scene videos and background music.
- `netlify/functions/quiz.mjs`: the quiz results API (`/api/quiz`), which stores vote counts in Netlify Blobs.
- `netlify.toml`: Netlify settings and caching headers.

## Deploy on Netlify (once)
1. Netlify → **Add new site → Import an existing project → GitHub** → pick this repo.
2. Build command: leave empty. Publish directory: `.` (already set in `netlify.toml`).
3. Deploy. Netlify installs `@netlify/blobs` and bundles the function automatically.
4. Optional: **Domain management → Add a domain** for a custom domain, then update `og:image` in `index.html` to the full URL (for example `https://mohitweddskavya.in/og.jpg`) so WhatsApp link previews show the image.

## Updating
Edit files, then commit and push to `main`. Netlify redeploys in about a minute and the link stays the same.
To roll back: Netlify → **Deploys** → choose an earlier deploy → **Publish deploy**.

## Quiz results
- `GET /api/quiz` returns the counts; `POST /api/quiz {voter, q, choice}` records a vote.
- One vote per question per device; changing an answer moves the vote.
- To reset the tally, open Netlify → **Blobs** → store `quiz` and delete its entries.
- The results only work on the deployed site, not when opening `index.html` from disk.
