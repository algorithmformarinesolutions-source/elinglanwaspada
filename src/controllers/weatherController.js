const { getWeather } = require("../services/thingspeakService");
const num = (v) => v === null || v === undefined || v === "" ? null : Number(v);
const diff = (latest, previous, factor = 1) => latest === null || previous === null ? 0 : (latest - previous) * factor;
async function weatherController(req, res) {
  try {
    const result = await getWeather(2);
    const feeds = (result.feeds || []).filter(f => f.field1 !== null || f.field2 !== null || f.field3 !== null);
    if (!feeds.length) return res.status(502).json({ message: "ThingSpeak belum memiliki data cuaca." });
    const latest = feeds[feeds.length - 1], previous = feeds.length > 1 ? feeds[feeds.length - 2] : latest;
    const ws = num(latest.field1), pws = num(previous.field1), rain = num(latest.field3), prain = num(previous.field3);
    res.json({ windSpeed: ws === null ? null : ws * 3.6, windDirection: num(latest.field2), rain,
      windDifference: diff(ws, pws, 3.6), rainDifference: diff(rain, prain), time: latest.created_at });
  } catch (error) { res.status(500).json({ message: "Gagal mengambil data weather", error: error.message }); }
}
async function windHistoryController(req, res) {
  try {
    const requested = Number.parseInt(req.query.results, 10) || 100;
    const result = await getWeather(Math.min(8000, Math.max(2, requested)));
    const series = (result.feeds || []).map(f => ({
      time: f.created_at,
      direction: num(f.field2),
      speed: num(f.field1) === null ? null : num(f.field1) * 3.6,
    })).filter(p => p.time && p.direction !== null && Number.isFinite(p.direction));
    if (!series.length) return res.status(502).json({ message: "ThingSpeak belum memiliki riwayat arah angin." });
    res.json({ series, count: series.length, source: "ThingSpeak" });
  } catch (error) { res.status(500).json({ message: "Gagal mengambil riwayat arah angin", error: error.message }); }
}
module.exports = { weatherController, windHistoryController };
