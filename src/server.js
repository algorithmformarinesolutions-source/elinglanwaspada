
require("dotenv").config({
  path: require("path").join(__dirname, "..", "backend.env")
});

const app = require("./app");
const PORT = process.env.PORT || 3000;

const {
  startTideScheduler
} = require("./services/tideScheduler");

const server = app.listen(PORT, () => {
  console.log(`EWS Bedono backend running on port ${PORT}`);

  // Aktifkan pemeriksaan otomatis data pasang surut
  startTideScheduler();
});
