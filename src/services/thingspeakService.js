const axios = require("axios");

const BASE_URL = "https://api.thingspeak.com/channels";
async function getChannelFeeds(channelId, apiKey, results = 2) {
  if (!channelId || !apiKey) throw new Error("Konfigurasi ThingSpeak belum lengkap. Periksa backend.env.");
  const safeResults = Math.min(8000, Math.max(1, Number.parseInt(results, 10) || 2));
  const response = await axios.get(`${BASE_URL}/${channelId}/feeds.json`, {
    params: { api_key: apiKey, results: safeResults },
    timeout: 15000,
  });
  return response.data;
}
const getTide = (results = 2) => getChannelFeeds(process.env.THINGSPEAK_TIDE_CHANNEL_ID, process.env.THINGSPEAK_TIDE_READ_API_KEY, results);
const getClimate = (results = 2) => getChannelFeeds(process.env.THINGSPEAK_CLIMATE_CHANNEL_ID, process.env.THINGSPEAK_CLIMATE_READ_API_KEY, results);
const getWeather = (results = 2) => getChannelFeeds(process.env.THINGSPEAK_WEATHER_CHANNEL_ID, process.env.THINGSPEAK_WEATHER_READ_API_KEY, results);
module.exports = { getTide, getClimate, getWeather };
