const express = require("express");
const router = express.Router();

const { climateController } = require("../controllers/climateController");

router.get("/", climateController);

module.exports = router;
