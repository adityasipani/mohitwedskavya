// Shared guest-quiz results for every invitation made by The Royal Patrika House.
// GET  /api/quiz?site=<slug>                        -> { counts: { "0": {"groom":3,"bride":5,"Both":1}, ... } }
// POST /api/quiz?site=<slug>  {voter, q, choice}    -> updated counts
// Stored in the Cloudflare KV namespace bound as QUIZ. One vote per question per device;
// changing an answer moves the vote instead of adding a new one.

const CHOICES = ["groom", "bride", "Both"];
const MAX_Q = 8;
const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "content-type",
};
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", "cache-control": "no-store", ...CORS } });

async function readCounts(kv, site) {
  const rows = await Promise.all([...Array(MAX_Q).keys()].map((i) => kv.get(`c:${site}:${i}`, "json")));
  const counts = {};
  rows.forEach((r, i) => { if (r) counts[i] = r; });
  return counts;
}

export async function onRequest({ request, env }) {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  const kv = env.QUIZ;
  if (!kv) return json({ error: "Quiz storage not connected" }, 500);
  const site = new URL(request.url).searchParams.get("site") || "";
  if (!/^[a-z0-9-]{3,60}$/.test(site)) return json({ error: "Bad site" }, 400);

  if (request.method === "GET") return json({ counts: await readCounts(kv, site) });
  if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);

  let body;
  try { body = await request.json(); } catch { return json({ error: "Bad JSON" }, 400); }
  const { voter, q, choice } = body || {};
  const qi = Number(q);
  if (typeof voter !== "string" || !/^[a-z0-9-]{8,64}$/i.test(voter)) return json({ error: "Bad voter" }, 400);
  if (!Number.isInteger(qi) || qi < 0 || qi >= MAX_Q) return json({ error: "Bad question" }, 400);
  if (!CHOICES.includes(choice)) return json({ error: "Bad choice" }, 400);

  const voteKey = `v:${site}:${voter}:${qi}`;
  const prev = await kv.get(voteKey);
  if (prev !== choice) {
    const key = `c:${site}:${qi}`;
    const row = (await kv.get(key, "json")) || { groom: 0, bride: 0, Both: 0 };
    if (prev && row[prev] > 0) row[prev]--;
    row[choice] = (row[choice] || 0) + 1;
    await kv.put(key, JSON.stringify(row));
    await kv.put(voteKey, choice, { expirationTtl: 60 * 60 * 24 * 400 });
  }
  return json({ counts: await readCounts(kv, site) });
}
