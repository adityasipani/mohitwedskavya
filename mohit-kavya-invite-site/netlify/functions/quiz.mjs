// Quiz results for the Mohit & Kavya invite.
// GET  /api/quiz            -> { counts: { "0": {"Mohit":3,"Kavya":5,"Both":1}, ... } }
// POST /api/quiz {voter, q, choice, prev}  -> updated counts
// Votes live in Netlify Blobs. One vote per question per device (voter id kept in the browser);
// changing an answer moves the vote instead of adding a new one.
import { getStore } from "@netlify/blobs";

const CHOICES = new Set(["Mohit", "Kavya", "Both"]);
const QUESTIONS = 4;
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });

async function readCounts(store) {
  return (await store.get("counts", { type: "json" })) || {};
}

export default async (req) => {
  const store = getStore({ name: "quiz", consistency: "strong" });

  if (req.method === "GET") return json({ counts: await readCounts(store) });
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);

  let body;
  try { body = await req.json(); } catch { return json({ error: "Bad JSON" }, 400); }
  const { voter, q, choice } = body || {};
  const qi = Number(q);
  if (typeof voter !== "string" || !/^[a-z0-9-]{8,64}$/i.test(voter)) return json({ error: "Bad voter" }, 400);
  if (!Number.isInteger(qi) || qi < 0 || qi >= QUESTIONS) return json({ error: "Bad question" }, 400);
  if (!CHOICES.has(choice)) return json({ error: "Bad choice" }, 400);

  // What did this device vote before on this question? (server-side record, not trusted from the client)
  const voteKey = `vote/${voter}/${qi}`;
  const prev = await store.get(voteKey);
  if (prev === choice) return json({ counts: await readCounts(store) });

  // Update the tally, retrying if another guest wrote at the same moment.
  for (let attempt = 0; attempt < 5; attempt++) {
    const entry = await store.getWithMetadata("counts", { type: "json" });
    const counts = entry?.data || {};
    const row = (counts[qi] = counts[qi] || { Mohit: 0, Kavya: 0, Both: 0 });
    if (prev && CHOICES.has(prev) && row[prev] > 0) row[prev]--;
    row[choice] = (row[choice] || 0) + 1;
    const opts = entry?.etag ? { onlyIfMatch: entry.etag } : { onlyIfNew: true };
    let res;
    try { res = await store.setJSON("counts", counts, opts); }
    catch { res = await store.setJSON("counts", counts); } // older runtimes without conditional writes
    if (res?.modified !== false) {
      await store.set(voteKey, choice);
      return json({ counts });
    }
  }
  return json({ error: "Busy, please try again" }, 503);
};

export const config = { path: "/api/quiz" };
