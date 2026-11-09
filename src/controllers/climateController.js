const { getClimate } = require("../services/thingspeakService");
const num = (v) => v === null || v === undefined || v === "" ? null : Number(v);
const diff = (a,b) => a === null || b === null ? 0 : a-b;
async function climateController(req, res) {
  try {
    const result = await getClimate();
    const feeds = (result.feeds || []).filter(f => f.field1 !== null || f.field2 !== null);
    if (!feeds.length) return res.status(502).json({ message: "ThingSpeak belum memiliki data iklim." });
    const latest = feeds[feeds.length - 1], previous = feeds.length > 1 ? feeds[feeds.length - 2] : latest;
    const temp=num(latest.field1), ptemp=num(previous.field1), humidity=num(latest.field2), phumidity=num(previous.field2);
    res.json({ seaTemperature: temp, humidity, seaTemperatureDifference: diff(temp,ptemp), humidityDifference: diff(humidity,phumidity), time: latest.created_at });
  } catch (error) { res.status(500).json({ message: "Gagal mengambil data climate", error: error.message }); }
}
module.exports = { climateController };
