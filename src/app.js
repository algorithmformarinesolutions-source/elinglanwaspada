
const express = require("express");
const cors = require("cors");
const path = require("path");

const tideRoutes = require("./routes/tideRoutes");
const climateRoutes = require("./routes/climateRoutes");
const weatherRoutes = require("./routes/weatherRoutes");

const app = express();

// Middleware
app.use(cors());
app.use(express.json());

// Lokasi folder frontend
const frontendPath = path.join(__dirname, "../frontend");

// Menampilkan file frontend dan aset gambar
app.use(express.static(frontendPath));

// Halaman utama dashboard
app.get("/", (req, res) => {
    res.sendFile(path.join(frontendPath, "html.html"));
});

// API Routes
app.use("/tide", tideRoutes);
app.use("/climate", climateRoutes);
app.use("/weather", weatherRoutes);

module.exports = app;
