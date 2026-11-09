const express = require("express");
const router = express.Router();

const { tideController, tideForecastController } = require("../controllers/tideController");

router.get("/", tideController);
router.get("/forecast", tideForecastController);

module.exports = router;