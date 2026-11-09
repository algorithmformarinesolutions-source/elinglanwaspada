const { getTide } = require("../services/thingspeakService");
const { getTideForecast } = require("../services/tideForecastService");
const num = (v) => v === null || v === undefined || v === "" ? null : Number(v);
async function tideController(req, res) {
  try {
    const requested = Number.parseInt(req.query.results, 10) || 2;
    const result = await getTide(Math.min(8000, Math.max(2, requested)));
    const feeds = (result.feeds || [])
      .map(f => ({ time: f.created_at, value: num(f.field1) }))
      .filter(p => p.time && p.value !== null && Number.isFinite(p.value));
    if (!feeds.length) return res.status(502).json({ message: "ThingSpeak belum memiliki data pasang surut." });
    const latest = feeds[feeds.length - 1];
    res.json({ tide: latest.value, time: latest.time, unit: "sesuai field1 ThingSpeak", series: feeds, count: feeds.length, source: "ThingSpeak" });
  } catch (error) { res.status(500).json({ message: "Gagal mengambil data tide", error: error.message }); }
}
async function tideForecastController(req, res) {
  try {
    const forecast = await getTideForecast({ force: req.query.refresh === "1" });
    res.json(forecast);
  } catch (error) {
    res.status(503).json({ message: "Prediksi banjir rob belum tersedia.", detail: error.message, source: "Python pipeline" });
  }
}
module.exports = { tideController, tideForecastController };
