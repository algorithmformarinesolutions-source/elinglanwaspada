const fs = require("fs");
const path = require("path");

const { getTide } = require("./thingspeakService");
const { getTideForecast } = require("./tideForecastService");

const INTERVAL_MS = 3 * 60 * 60 * 1000;

const projectRoot = path.resolve(__dirname, "..", "..");
const moduleDir = path.join(projectRoot, "Pasut_Tes_1_FULL_MONTH_FIX");
const outputDir = path.join(moduleDir, "output");

const statePath = path.join(outputDir, "tide_scheduler_state.json");

let schedulerStarted = false;
let checking = false;
let intervalHandle = null;

function readLastProcessed() {
  try {
    if (!fs.existsSync(statePath)) return null;

    return JSON.parse(fs.readFileSync(statePath, "utf8"));
  } catch (error) {
    console.error("[TIDE SCHEDULER] Gagal membaca state:", error.message);
    return null;
  }
}

function saveLastProcessed(fingerprint) {
  fs.mkdirSync(outputDir, { recursive: true });

  const tempPath = `${statePath}.tmp`;

  fs.writeFileSync(
    tempPath,
    JSON.stringify({
      fingerprint,
      processedAt: new Date().toISOString()
    }, null, 2)
  );

  fs.renameSync(tempPath, statePath);
}

async function checkNewTideData() {
  if (checking) {
    console.log("[TIDE SCHEDULER] Pemeriksaan sebelumnya masih berjalan.");
    return;
  }

  checking = true;

  try {
    console.log("[TIDE SCHEDULER] Memeriksa data ThingSpeak...");

    const response = await getTide(1);
    const feeds = response?.feeds || [];

    if (!feeds.length) {
      console.log("[TIDE SCHEDULER] Belum ada data pasut.");
      return;
    }

    const latest = feeds[feeds.length - 1];

    if (!latest.entry_id || !latest.created_at) {
      throw new Error("Data terbaru tidak memiliki entry_id atau created_at.");
    }

    const fingerprint = `${latest.entry_id}:${latest.created_at}`;
    const previous = readLastProcessed();

    if (previous?.fingerprint === fingerprint) {
      console.log("[TIDE SCHEDULER] Tidak ada data baru. Pipeline dilewati.");
      return;
    }

    console.log("[TIDE SCHEDULER] Data baru ditemukan:", fingerprint);

    // Jalankan prediksi Python
    await getTideForecast({ force: true });

    // Simpan status hanya setelah prediksi berhasil
    saveLastProcessed(fingerprint);

    console.log("[TIDE SCHEDULER] Prediksi berhasil diperbarui.");

  } catch (error) {
    console.error(
      "[TIDE SCHEDULER] Proses gagal:",
      error.message
    );
  } finally {
    checking = false;
  }
}

function startTideScheduler() {
  if (schedulerStarted) return;

  schedulerStarted = true;

  console.log("[TIDE SCHEDULER] Scheduler aktif.");
  console.log("[TIDE SCHEDULER] Interval pemeriksaan: 3 jam.");

  // Pemeriksaan pertama ketika backend aktif
  checkNewTideData();

  // Pemeriksaan berikutnya setiap 3 jam
  intervalHandle = setInterval(
    checkNewTideData,
    INTERVAL_MS
  );
}

function stopTideScheduler() {
  if (intervalHandle) {
    clearInterval(intervalHandle);
    intervalHandle = null;
  }

  schedulerStarted = false;
}

module.exports = {
  startTideScheduler,
  stopTideScheduler,
  checkNewTideData
};