const express = require("express");
const cors = require("cors");

const tideRoutes = require("./routes/tideRoutes");
const climateRoutes = require("./routes/climateRoutes");
const weatherRoutes = require("./routes/weatherRoutes");

const app = express();
app.use(cors());

// Middleware untuk membaca JSON
app.use(express.json());
app.use("/tide", tideRoutes);
app.use("/climate", climateRoutes);
app.use("/weather", weatherRoutes);


// Route pertama
app.get("/", (req, res) => {
    res.send("Server Running 🚀");
});


module.exports = app;