// Quiz results for the Mohit & Kavya invite — Vercel version (same API as netlify/functions/quiz.mjs).
// GET  /api/quiz                  -> { counts: { "0": {"Mohit":3,"Kavya":5,"Both":1}, ... } }
// POST /api/quiz {voter, q, choice} -> updated counts
// Votes are kept in a free Upstash Redis database connected through Vercel (Storage tab).
// One vote per question per device; changing an answer moves the vote instead of adding a new one.

const CHOICES = new Set(["Mohit", "Kavya", "Both"]);
const QUESTIONS = 4;
const URL_ = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
const TOKEN = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;

async function redis(cmds) {
  const r = await fetch(`${URL_}/pipeline`, {
    method: "POST",
    headers: { Authorization: `Bearer ${TOKEN}`, "content-type": "application/json" },
    body: JSON.stringify(cmds),
  });
  if (!r.ok) throw new Error("redis " + r.status);
  return (await r.json()).map((x) => x.result);
}

async function readCounts() {
  const rows = await redis([...Array(QUESTIONS).keys()].map((i) => ["HGETALL", `quiz:c:${i}`]));
  const counts = {};
  rows.forEach((arr, i) => {
    if (!arr || !arr.length) return;
    const row = { Mohit: 0, Kavya: 0, Both: 0 };
    for (let k = 0; k < arr.length; k += 2) row[arr[k]] = Math.max(0, Number(arr[k + 1]) || 0);
    counts[i] = row;
  });
  return counts;
}

export default async function handler(req, res) {
  res.setHeader("cache-control", "no-store");
  if (!URL_ || !TOKEN) return res.status(500).json({ error: "Database not connected" });
  try {
    if (req.method === "GET") return res.status(200).json({ counts: await readCounts() });
    if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });

    let body = req.body;
    if (typeof body === "string") { try { body = JSON.parse(body); } catch { body = null; } }
    const { voter, q, choice } = body || {};
    const qi = Number(q);
    if (typeof voter !== "string" || !/^[a-z0-9-]{8,64}$/i.test(voter)) return res.status(400).json({ error: "Bad voter" });
    if (!Number.isInteger(qi) || qi < 0 || qi >= QUESTIONS) return res.status(400).json({ error: "Bad question" });
    if (!CHOICES.has(choice)) return res.status(400).json({ error: "Bad choice" });

    const field = `${voter}:${qi}`;
    const [prev] = await redis([["HGET", "quiz:votes", field]]);
    if (prev !== choice) {
      const cmds = [["HSET", "quiz:votes", field, choice], ["HINCRBY", `quiz:c:${qi}`, choice, 1]];
      if (prev && CHOICES.has(prev)) cmds.push(["HINCRBY", `quiz:c:${qi}`, prev, -1]);
      await redis(cmds);
    }
    return res.status(200).json({ counts: await readCounts() });
  } catch (e) {
    return res.status(503).json({ error: "Busy, please try again" });
  }
}
