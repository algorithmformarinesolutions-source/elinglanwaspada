
require("dotenv").config({
  path: require("path").join(__dirname, "..", "backend.env")
});

const app = require("./app");

const PORT = process.env.PORT || 3000;

const server = app.listen(PORT, () => {
  console.log(
    `EWS Bedono backend running on port ${PORT}`
  );

  console.log(
    "[TIDE] Prediksi pasut menggunakan CSV GitHub Actions."
  );
});

module.exports = server;
