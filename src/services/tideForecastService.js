
const fs = require("fs");
const path = require("path");

// Root proyek: hbuilds/last-source
const projectRoot = path.resolve(__dirname, "..", "..");

// Folder tide-data berada sejajar dengan hbuilds dan public_html.
const dataDir = process.env.TIDE_DATA_DIR
  ? path.resolve(process.env.TIDE_DATA_DIR)
  : path.resolve(projectRoot, "..", "..", "tide-data");

const calendarPath = path.join(
  dataDir,
  "07_tide_calendar.csv"
);

const forecastPath = path.join(
  dataDir,
  "05_forecast_threshold.csv"
);

// Parser CSV yang mendukung tanda kutip dan koma di dalam kolom.
function parseCSV(content) {
  const rows = [];
  let row = [];
  let value = "";
  let insideQuotes = false;

  for (let i = 0; i < content.length; i++) {
    const char = content[i];
    const next = content[i + 1];

    if (char === '"') {
      if (insideQuotes && next === '"') {
        value += '"';
        i++;
      } else {
        insideQuotes = !insideQuotes;
      }
    } else if (char === "," && !insideQuotes) {
      row.push(value.trim());
      value = "";
    } else if (
      (char === "\n" || char === "\r") &&
      !insideQuotes
    ) {
      if (char === "\r" && next === "\n") i++;

      row.push(value.trim());

      if (row.some((item) => item !== "")) {
        rows.push(row);
      }

      row = [];
      value = "";
    } else {
      value += char;
    }
  }

  if (value !== "" || row.length > 0) {
    row.push(value.trim());

    if (row.some((item) => item !== "")) {
      rows.push(row);
    }
  }

  if (!rows.length) return [];

  const headers = rows[0].map((header, index) =>
    index === 0
      ? header.replace(/^\uFEFF/, "").trim()
      : header.trim()
  );

  return rows.slice(1).map((values) => {
    return Object.fromEntries(
      headers.map((header, index) => [
        header,
        values[index] ?? ""
      ])
    );
  });
}

function readCSV(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(
      `File tidak ditemukan: ${filePath}`
    );
  }

  const content = fs.readFileSync(filePath, "utf8");

  if (!content.trim()) {
    throw new Error(
      `File CSV kosong: ${path.basename(filePath)}`
    );
  }

  const rows = parseCSV(content);

  if (!rows.length) {
    throw new Error(
      `CSV tidak memiliki baris data: ${path.basename(filePath)}`
    );
  }

  return rows;
}

function toNumber(value) {
  if (
    value === null ||
    value === undefined ||
    String(value).trim() === ""
  ) {
    return null;
  }

  const number = Number(value);

  return Number.isFinite(number) ? number : null;
}

// Mengelompokkan kalender pasut berdasarkan tanggal.
function summarizeCalendar(rows) {
  const byDate = new Map();

  for (const row of rows) {
    const date = row.date;

    if (!date) continue;

    const level = toNumber(row.water_level);
    const status = String(row.status || "")
      .trim()
      .toUpperCase();

    const item = byDate.get(date) || {
      date,
      points: 0,
      maxWaterLevel: null,
      highCount: 0,
      status: "NORMAL",
      hours: []
    };

    item.points += 1;

    if (level !== null) {
      item.maxWaterLevel =
        item.maxWaterLevel === null
          ? level
          : Math.max(item.maxWaterLevel, level);
    }

    if (
      status === "TINGGI" ||
      status === "POTENSI_ROB"
    ) {
      item.highCount += 1;
      item.status = "TINGGI";
    }

    item.hours.push({
      time: row.time || null,
      waterLevel: level,
      status: status || "DATA KOSONG"
    });

    byDate.set(date, item);
  }

  return [...byDate.values()].map((day) => ({
    ...day,
    hours: day.hours.sort((a, b) =>
      String(a.time || "").localeCompare(
        String(b.time || "")
      )
    )
  }));
}

async function getTideForecast() {
  // Pastikan kedua CSV tersedia.
  const calendarRows = readCSV(calendarPath);
  const forecastRows = readCSV(forecastPath);

  // Validasi kolom utama.
  const requiredCalendar = [
    "date",
    "time",
    "water_level",
    "status"
  ];

  const requiredForecast = [
    "time",
    "water_level_predicted",
    "status"
  ];

  for (const column of requiredCalendar) {
    if (!(column in calendarRows[0])) {
      throw new Error(
        `Kolom ${column} tidak ditemukan di 07_tide_calendar.csv`
      );
    }
  }

  for (const column of requiredForecast) {
    if (!(column in forecastRows[0])) {
      throw new Error(
        `Kolom ${column} tidak ditemukan di 05_forecast_threshold.csv`
      );
    }
  }

  const threshold = Number(
    process.env.TIDE_THRESHOLD || 125
  );

  const days = summarizeCalendar(calendarRows);

  const highDays = days.filter(
    (day) => day.status === "TINGGI"
  );

  const nextHighTide = forecastRows
    .map((row) => ({
      time: row.time,
      value: toNumber(row.water_level_predicted),
      status: String(row.status || "")
        .trim()
        .toUpperCase()
    }))
    .filter(
      (row) =>
        row.status === "TINGGI" &&
        row.value !== null
    )
    .slice(0, 10);

  const generatedAt = Math.max(
    fs.statSync(calendarPath).mtimeMs,
    fs.statSync(forecastPath).mtimeMs
  );

  return {
    source: "GitHub Actions tidal forecast pipeline",

    generatedAt: new Date(
      generatedAt
    ).toISOString(),

    threshold,
    unit: "cm",

    days,

    forecastCount: forecastRows.length,

    summary: {
      totalDays: days.length,
      highDays: highDays.length,
      normalDays: days.length - highDays.length,
      nextHighTide
    }
  };
}

module.exports = {
  getTideForecast
};
