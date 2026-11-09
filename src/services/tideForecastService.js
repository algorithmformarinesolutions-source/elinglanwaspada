
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const projectRoot = path.resolve(__dirname, "..", "..");
const moduleDir = path.join(projectRoot, "Pasut_Tes_1_FULL_MONTH_FIX");
const outputDir = path.join(moduleDir, "output");

const calendarPath = path.join(outputDir, "07_tide_calendar.csv");
const forecastPath = path.join(outputDir, "05_forecast_threshold.csv");

let running = null;

function parseCsvLine(line) {
  return line.split(",").map((value) =>
    value.trim().replace(/^"|"$/g, "")
  );
}

function readCsv(filePath) {
  if (!fs.existsSync(filePath)) return [];

  const lines = fs.readFileSync(filePath, "utf8")
    .split(/\r?\n/)
    .filter(Boolean);

  if (lines.length < 2) return [];

  const headers = parseCsvLine(lines[0]);

  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);

    return Object.fromEntries(
      headers.map((header, i) => [header, values[i] ?? ""])
    );
  });
}

// Mengganti output lama hanya setelah kedua output baru valid.
// Jika proses penggantian gagal, output lama dikembalikan.
function commitOutputs(tempDir) {
  const files = [
    {
      staged: path.join(tempDir, "07_tide_calendar.csv"),
      target: calendarPath,
      backup: path.join(tempDir, "backup_calendar.csv")
    },
    {
      staged: path.join(tempDir, "05_forecast_threshold.csv"),
      target: forecastPath,
      backup: path.join(tempDir, "backup_forecast.csv")
    }
  ];

  const backedUp = [];
  const installed = [];

  try {
    // Cadangkan output lama.
    for (const file of files) {
      if (fs.existsSync(file.target)) {
        fs.renameSync(file.target, file.backup);
        backedUp.push(file);
      }
    }

    // Pasang output baru.
    for (const file of files) {
      fs.renameSync(file.staged, file.target);
      installed.push(file);
    }

  } catch (error) {
    // Hapus output baru yang sempat terpasang.
    for (const file of installed.reverse()) {
      try {
        fs.unlinkSync(file.target);
      } catch {}
    }

    // Pulihkan output lama.
    for (const file of backedUp.reverse()) {
      try {
        if (fs.existsSync(file.backup)) {
          fs.renameSync(file.backup, file.target);
        }
      } catch (restoreError) {
        console.error(
          "[TIDE] Gagal memulihkan output:",
          restoreError.message
        );
      }
    }

    throw error;
  }
}

async function executePipeline() {
  fs.mkdirSync(outputDir, { recursive: true });

  const venvPython = process.platform === "win32"
    ? path.join(moduleDir, ".venv", "Scripts", "python.exe")
    : path.join(moduleDir, ".venv", "bin", "python");

  const python = process.env.PYTHON_EXECUTABLE ||
    (fs.existsSync(venvPython)
      ? venvPython
      : (process.platform === "win32" ? "python" : "python3"));

  const env = {
    ...process.env,
    THINGSPEAK_CHANNEL_ID:
      process.env.THINGSPEAK_TIDE_CHANNEL_ID ||
      process.env.THINGSPEAK_CHANNEL_ID || "",

    THINGSPEAK_READ_API_KEY:
      process.env.THINGSPEAK_TIDE_READ_API_KEY ||
      process.env.THINGSPEAK_READ_API_KEY || "",

    TIDE_SHOW_PLOT: "0",
    HOBO_VALIDATION_ENABLED: "0"
  };

  if (!env.THINGSPEAK_CHANNEL_ID || !env.THINGSPEAK_READ_API_KEY) {
    throw new Error(
      "Konfigurasi ThingSpeak pasut belum lengkap di backend.env."
    );
  }

  if (!fs.existsSync(python)) {
    throw new Error(`Python interpreter tidak ditemukan: ${python}`);
  }

  // Setiap eksekusi mempunyai folder sementara sendiri.
  const tempDir = fs.mkdtempSync(
    path.join(outputDir, ".tide-run-")
  );

  try {
    env.TIDE_OUTPUT_FOLDER = tempDir;

    console.log("[TIDE] Menjalankan Python:", python);
    console.log("[TIDE] Temporary output:", tempDir);

    const result = await new Promise((resolve, reject) => {
      const child = spawn(
        python,
        [
          "run_pipeline.py",
          "--no-validation",
          "--no-plot",
          "--threshold",
          process.env.TIDE_THRESHOLD || "125",
          "--outdir",
          tempDir
        ],
        {
          cwd: moduleDir,
          env,
          windowsHide: true
        }
      );

      let stdout = "";
      let stderr = "";
      let timedOut = false;

      const timeout = setTimeout(() => {
        timedOut = true;
        child.kill("SIGTERM");
      }, 240000);

      child.stdout.on("data", (chunk) => {
        stdout += chunk.toString();
      });

      child.stderr.on("data", (chunk) => {
        stderr += chunk.toString();
      });

      child.on("error", (error) => {
        clearTimeout(timeout);

        reject(
          new Error(
            `Gagal menjalankan Python (${python}): ${error.message}`
          )
        );
      });

      child.on("close", (code) => {
        clearTimeout(timeout);

        if (timedOut) {
          return reject(
            new Error("Python melewati batas waktu 240 detik.")
          );
        }

        if (code !== 0) {
          return reject(
            new Error(
              (stderr || stdout ||
                `Pipeline berhenti dengan kode ${code}`).slice(-1800)
            )
          );
        }

        resolve({
          stdout,
          stderr
        });
      });
    });

    // Periksa keberadaan kedua file sebelum mengganti output lama.
    const newCalendar = path.join(
      tempDir,
      "07_tide_calendar.csv"
    );

    const newForecast = path.join(
      tempDir,
      "05_forecast_threshold.csv"
    );

    for (const file of [newCalendar, newForecast]) {
      if (!fs.existsSync(file) || fs.statSync(file).size === 0) {
        throw new Error(
          `Output Python tidak ditemukan atau kosong: ${path.basename(file)}`
        );
      }

      if (readCsv(file).length === 0) {
        throw new Error(
          `Output CSV tidak memiliki baris data: ${path.basename(file)}`
        );
      }
    }

    // Kedua file sudah valid. Sekarang ganti output lama.
    commitOutputs(tempDir);

    console.log("[TIDE] Output prediksi berhasil diperbarui.");

    return {
      finishedAt: new Date().toISOString(),
      log: (result.stdout + "\n" + result.stderr).slice(-1200)
    };

  } finally {
    // Hapus folder sementara setelah proses selesai.
    fs.rmSync(tempDir, {
      recursive: true,
      force: true
    });
  }
}

function runPipeline() {
  if (running) return running;

  running = executePipeline().finally(() => {
    running = null;
  });

  return running;
}

function summarizeCalendar(rows) {
  const byDate = new Map();

  for (const row of rows) {
    const date = row.date;
    if (!date) continue;

    const level = Number(row.water_level);
    const status = String(row.status || "").toUpperCase();

    const item = byDate.get(date) || {
      date,
      points: 0,
      maxWaterLevel: null,
      highCount: 0,
      status: "NORMAL",
      hours: []
    };

    item.points += 1;

    if (Number.isFinite(level)) {
      item.maxWaterLevel =
        item.maxWaterLevel === null
          ? level
          : Math.max(item.maxWaterLevel, level);
    }

    if (status === "TINGGI" || status === "POTENSI_ROB") {
      item.highCount += 1;
      item.status = "TINGGI";
    }

    item.hours.push({
      time: row.time,
      waterLevel: Number.isFinite(level) ? level : null,
      status: status || "DATA KOSONG"
    });

    byDate.set(date, item);
  }

  return [...byDate.values()].map((day) => ({
    ...day,
    hours: day.hours.sort((a, b) =>
      String(a.time).localeCompare(String(b.time))
    )
  }));
}

async function getTideForecast({ force = false } = {}) {
  let runInfo = null;

  // Python hanya dijalankan jika diminta secara eksplisit.
  // Scheduler akan menggunakan force: true.
  if (force) {
    runInfo = await runPipeline();
  }

  const calendarRows = readCsv(calendarPath);
  const forecastRows = readCsv(forecastPath);

  if (!calendarRows.length || !forecastRows.length) {
    throw new Error(
      "Belum ada hasil prediksi pasut yang valid."
    );
  }

  const threshold = Number(process.env.TIDE_THRESHOLD || 125);
  const days = summarizeCalendar(calendarRows);
  const highDays = days.filter((d) => d.status === "TINGGI");

  return {
    source: "Python tidal forecast pipeline + ThingSpeak",

    generatedAt:
      runInfo?.finishedAt ||
      fs.statSync(calendarPath).mtime.toISOString(),

    threshold,
    unit: "cm",
    days,
    forecastCount: forecastRows.length,

    summary: {
      totalDays: days.length,
      highDays: highDays.length,
      normalDays: days.length - highDays.length,

      nextHighTide: forecastRows
        .map((r) => ({
          time: r.time,
          value: Number(r.water_level_predicted),
          status: String(r.status || "").toUpperCase()
        }))
        .filter((r) =>
          r.status === "TINGGI" && Number.isFinite(r.value)
        )
        .slice(0, 10)
    }
  };
}

module.exports = {
  getTideForecast
};
