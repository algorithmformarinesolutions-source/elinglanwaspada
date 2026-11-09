const express = require("express");
const router = express.Router();
const { weatherController, windHistoryController } = require("../controllers/weatherController");
router.get("/", weatherController);
router.get("/history", windHistoryController);
module.exports = router;
