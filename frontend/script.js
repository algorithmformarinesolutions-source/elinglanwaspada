(() => {
  const API_BASE = window.EWS_API_BASE || "http://localhost:3000";
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  let weatherOk = false, climateOk = false, tideOk = false;
  let tideSeries = [];
  let robForecast = null;
  let currentCalendarDate = new Date();
  const format = (v, digits = 1) => Number.isFinite(Number(v)) ? Number(v).toFixed(digits) : "--";
  const directionName = (degree) => {
    if (!Number.isFinite(Number(degree))) return "--";
    const dirs = ["Utara", "Timur Laut", "Timur", "Tenggara", "Selatan", "Barat Daya", "Barat", "Barat Laut"];
    return dirs[Math.round((((Number(degree) % 360) + 360) % 360) / 45) % 8];
  };
  function updateStatus() {
    const el = document.getElementById("connectionStatus"); if (!el) return;
    const span = $("span", el), ok = weatherOk && climateOk;
    if (span) span.textContent = ok ? "Live" : "Gangguan";
    el.classList.toggle("gangguan", !ok);
  }
  function addReading(card, label, value, unit) {
    if (!card) return;
    let box = $(".live-reading", card);
    if (!box) {
      box = document.createElement("div"); box.className = "live-reading";
      box.style.cssText = "margin:10px 0 12px;padding:10px 12px;background:#fff;border:1px solid #c8e6c9;border-radius:8px;";
      const title = document.createElement("div"); title.style.cssText = "font-size:.75rem;color:#68796d;margin-bottom:4px;"; title.textContent = label;
      const reading = document.createElement("strong"); reading.className = "live-reading-value"; reading.style.cssText = "font-size:1.35rem;color:#1a251e;";
      const units = document.createElement("span"); units.className = "live-reading-unit"; units.style.cssText = "font-size:.8rem;color:#68796d;margin-left:5px;";
      box.append(title, reading, units);
      // Keep a single value per card, before any legacy chart area.
      const chart = $(".metric-chart", card); if (chart) card.insertBefore(box, chart); else card.appendChild(box);
    }
    $(".live-reading-value", box).textContent = value; $(".live-reading-unit", box).textContent = unit;
  }
  function trendText(diff, unit) {
    const d = Number(diff); if (!Number.isFinite(d) || Math.abs(d) < 0.005) return "→ Stabil dibanding data sebelumnya";
    return `${d > 0 ? "↑ Naik" : "↓ Turun"} ${Math.abs(d).toFixed(2)} ${unit} dibanding data sebelumnya`;
  }
  async function getJson(path) {
    const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`); return response.json();
  }
  function setUpdatedAt(date) {
    const el = document.getElementById("updatedAt");
    if (el) el.textContent = date.toLocaleString("id-ID", { timeZone: "Asia/Jakarta", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) + " WIB";
  }
  function svgLineChart(container, points, opts = {}) {
    if (!container) return;
    if (!points.length) { container.textContent = opts.empty || "Data belum tersedia dari backend."; container.style.cssText += ";min-height:240px;display:flex;align-items:center;justify-content:center;color:var(--text-sub)"; return; }
    const W=720,H=240,L=52,R=18,T=18,B=38, PW=W-L-R,PH=H-T-B;
    const vals=points.map(p=>p.value), min0=Math.min(...vals), max0=Math.max(...vals);
    const pad=(max0-min0)*0.12 || Math.max(Math.abs(max0)*0.05,1); const min=min0-pad,max=max0+pad;
    const x=i=>L+(points.length<2?0:i/(points.length-1))*PW, y=v=>T+(max-v)/(max-min)*PH;
    const poly=points.map((p,i)=>`${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
    const ticks=[0,1,2,3].map(i=>{const v=min+(max-min)*i/3, yy=y(v);return `<line x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}" stroke="#e4ece5"/><text x="${L-8}" y="${yy+4}" text-anchor="end" fill="#657568" font-size="11">${format(v,opts.digits??2)}</text>`}).join("");
    const first=new Date(points[0].time),last=new Date(points[points.length-1].time);
    const dateLabel=d=>Number.isNaN(d.getTime())?"":d.toLocaleString("id-ID",{timeZone:"Asia/Jakarta",day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"});
    container.innerHTML=`<div style="width:100%;"><div style="font-size:12px;color:#607064;margin:0 4px 2px;">${opts.label} · ${points.length} titik data</div><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${opts.label}" style="width:100%;height:auto;display:block"><g>${ticks}</g><polyline fill="none" stroke="${opts.stroke||'#149b62'}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" points="${poly}"/>${points.length===1?`<circle cx="${x(0)}" cy="${y(points[0].value)}" r="4" fill="${opts.stroke||'#149b62'}"/>`:''}<text x="${L}" y="${H-10}" fill="#657568" font-size="11">${dateLabel(first)}</text><text x="${W-R}" y="${H-10}" text-anchor="end" fill="#657568" font-size="11">${dateLabel(last)}</text></svg><div style="font-size:11px;color:#657568;margin:0 4px;">${opts.note||"Sumber: EWS Bedono (ThingSpeak)."}</div></div>`;
  }
  
function renderTide(range) {
  const host = document.getElementById("tideChart");
  if (!host) return;

  if (!robForecast || !Array.isArray(robForecast.days)) {
    host.textContent =
      "Data prediksi Python belum tersedia. Tunggu proses prediksi selesai.";
    return;
  }

  const now = new Date();
  const today = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate()
  );

  const end = new Date(today);
  if (range === "week") {
    end.setDate(end.getDate() + 6);
  }

  const points = [];

  for (const day of robForecast.days) {
    // Format tanggal API: DD-MM-YYYY atau YYYY-MM-DD.
    let date;
    if (/^\d{2}-\d{2}-\d{4}$/.test(day.date)) {
      date = parseLocalDate(day.date);
    } else if (/^\d{4}-\d{2}-\d{2}$/.test(day.date)) {
      const [y, m, d] = day.date.split("-").map(Number);
      date = new Date(y, m - 1, d);
    } else {
      continue;
    }

    if (!date || date < today || date > end) continue;

    for (const hour of (day.hours || [])) {
      const value = Number(hour.waterLevel);
      const match = String(hour.time || "").match(/^(\d{1,2}):(\d{2})/);

      if (!Number.isFinite(value) || !match) continue;

      const timestamp = new Date(date);
      timestamp.setHours(Number(match[1]), Number(match[2]), 0, 0);

      points.push({
        time: timestamp.toISOString(),
        value
      });
    }
  }

  points.sort((a, b) => Date.parse(a.time) - Date.parse(b.time));

  if (!points.length) {
    host.textContent =
      "Tidak ada data prediksi untuk rentang tanggal ini. Periksa tanggal pada hasil Python.";
    return;
  }

  svgLineChart(host, points, {
    label: range === "today"
      ? "Prediksi pasang surut hari ini"
      : "Prediksi pasang surut 7 hari",
    digits: 2,
    stroke: "#168bba",
    note: `Prediksi berdasarkan data pengamatan pasang surut Sayung, Demak · Ambang batas: ${robForecast.threshold} cm`
  });
}

  function parseLocalDate(key) {
    const m = String(key || "").match(/^(\d{2})-(\d{2})-(\d{4})$/);
    if (!m) return null;
    return new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
  }
  function formatDateKey(date) {
    return `${String(date.getDate()).padStart(2,"0")}-${String(date.getMonth()+1).padStart(2,"0")}-${date.getFullYear()}`;
  }
  function setRobBanner(kind, title, detail) {
    const banner = document.getElementById("robAlertBanner");
    const titleEl = document.getElementById("robAlertTitle");
    const detailEl = document.getElementById("robAlertDetail");
    if (!banner || !titleEl || !detailEl) return;
    banner.classList.remove("high", "pending");
    if (kind === "high") banner.classList.add("high");
    if (kind === "pending") banner.classList.add("pending");
    titleEl.textContent = title; detailEl.textContent = detail;
  }
  function renderRobCalendar() {
    const host = document.getElementById("calendarDays");
    const monthText = document.getElementById("currentMonthText");
    if (!host || !monthText) return;
    host.innerHTML = "";
    const year = currentCalendarDate.getFullYear(), month = currentCalendarDate.getMonth();
    monthText.textContent = currentCalendarDate.toLocaleString("id-ID", { month:"long", year:"numeric" });
    const firstDay = new Date(year, month, 1).getDay();
    const totalDays = new Date(year, month + 1, 0).getDate();
    for (let i=0;i<firstDay;i++) { const empty=document.createElement("div"); empty.className="cal-date empty"; host.appendChild(empty); }
    const dayMap = new Map((robForecast?.days || []).map(d => [d.date, d]));
    for (let day=1;day<=totalDays;day++) {
      const date = new Date(year, month, day), key = formatDateKey(date), data = dayMap.get(key);
      const cell=document.createElement("button"); cell.type="button"; cell.className="cal-date";
      cell.style.cssText += ";font:inherit;text-align:center;cursor:pointer;";
      if (!data) { cell.classList.add("risk-unavailable"); cell.title="Prediksi untuk tanggal ini tidak tersedia"; }
      else if (data.status === "TINGGI") { cell.classList.add("risk-bahaya"); cell.title=`Threshold terlampaui. Maksimum prediksi ${format(data.maxWaterLevel,1)} cm`; }
      else { cell.classList.add("risk-aman"); cell.title=`Prediksi di bawah threshold. Maksimum ${format(data.maxWaterLevel,1)} cm`; }
      cell.innerHTML = `<span>${day}</span><div class="risk-dot"></div>`;
      cell.addEventListener("click", () => {
        const label = date.toLocaleDateString("id-ID", { weekday:"long", day:"numeric", month:"long", year:"numeric" });
        if (!data) { alert(`${label}\nData prediksi belum tersedia untuk tanggal ini.`); return; }
        const peak = data.hours.filter(h => h.status === "TINGGI").slice(0,4);
        const details = peak.length ? peak.map(h => `${h.time}: ${format(h.waterLevel,1)} cm (threshold terlampaui)`).join("\n") : "Tidak ada jam yang melewati threshold pada prediksi ini.";
        alert(`${label}\nStatus: ${data.status === "TINGGI" ? "POTENSI ROB / THRESHOLD TERLAMPAUI" : "DI BAWAH THRESHOLD"}\nMaksimum prediksi: ${format(data.maxWaterLevel,1)} cm\nThreshold: ${format(robForecast.threshold,1)} cm\n\n${details}`);
      });
      host.appendChild(cell);
    }
  }
  async function loadRobForecast(force = false) {
    setRobBanner("pending", "Memuat prediksi banjir rob…", "Backend sedang memeriksa hasil pipeline Python. Proses pertama dapat memerlukan waktu.");
    const host=document.getElementById("calendarDays");
    try {
      const data = await getJson(`/tide/forecast${force ? "?refresh=1" : ""}`);

      robForecast = data;

      // Render ulang kalender.
      renderRobCalendar();

      // Render grafik secara otomatis setelah data prediksi tersedia.
      const activeRange = document.getElementById("btn7Hari")?.classList.contains("active")
        ? "week"
        : "today";

      renderTide(activeRange);
      renderRobCalendar();
      const upcoming = (data.days || []).filter(d => d.status === "TINGGI");
      if (upcoming.length) {
        const first=upcoming[0], date=parseLocalDate(first.date);
        const dateLabel=date?date.toLocaleDateString("id-ID",{day:"numeric",month:"long",year:"numeric"}):first.date;
        setRobBanner("high", `POTENSI ROB: ${upcoming.length} tanggal melewati threshold`, `Tanggal terdekat: ${dateLabel}. Puncak prediksi ${format(first.maxWaterLevel,1)} cm; threshold ${format(data.threshold,1)} cm. Dibuat: ${new Date(data.generatedAt).toLocaleString("id-ID",{timeZone:"Asia/Jakarta"})} WIB.`);
      } else {
        setRobBanner("normal", "Tidak ada tanggal yang melewati threshold pada hasil prediksi", `Threshold ${format(data.threshold,1)} cm · ${data.forecastCount} titik prediksi · dibuat ${new Date(data.generatedAt).toLocaleString("id-ID",{timeZone:"Asia/Jakarta"})} WIB.`);
      }
      
      const note = document.getElementById("calendarDataNote");
      if (note) {
        note.textContent = `Prediksi berdasarkan data pengamatan pasang surut Sayung, Demak · ${data.forecastCount} titik prediksi · Ambang batas: ${format(data.threshold, 1)} cm. Status prediksi bukan jaminan bahwa banjir tidak akan terjadi.`;
      }
      } catch (error) {
        robForecast = null;
        renderRobCalendar();

        setRobBanner(
          "pending",
          "Informasi Prediksi Rob Belum Tersedia",
          "Data prediksi pasang surut belum tersedia. Informasi potensi rob akan ditampilkan setelah data berhasil diolah dan divalidasi."
        );

        if (host) {
          host.setAttribute("aria-label", "Informasi prediksi rob belum tersedia");
        }

        const note = document.getElementById("calendarDataNote");
        if (note) {
          note.textContent = "Data prediksi belum tersedia. Status potensi rob akan ditampilkan setelah proses pengolahan data selesai.";
        }

        console.error("Gagal memuat prediksi rob:", error);
      }
      }

  window.showRobAlert = function () {
    if (!robForecast) { alert("Prediksi rob belum tersedia. Periksa status backend dan pipeline Python."); return; }
    const high=(robForecast.days||[]).filter(d=>d.status==="TINGGI");
    if(!high.length){alert(`Tidak ada tanggal yang melewati threshold ${robForecast.threshold} cm pada hasil prediksi yang tersedia. Ini bukan jaminan bebas rob.`);return;}
    alert(`Peringatan potensi rob\n${high.length} tanggal melewati threshold ${robForecast.threshold} cm.\nTanggal terdekat: ${high[0].date}\nMaksimum prediksi: ${format(high[0].maxWaterLevel,1)} cm.`);
  };
  function wireCalendarControls() {
    const prev=document.getElementById("btnPrevMonth"), next=document.getElementById("btnNextMonth");
    if(prev) prev.addEventListener("click",()=>{currentCalendarDate.setMonth(currentCalendarDate.getMonth()-1);renderRobCalendar();});
    if(next) next.addEventListener("click",()=>{currentCalendarDate.setMonth(currentCalendarDate.getMonth()+1);renderRobCalendar();});
  }

  async function loadWeather() {
    try {
      const data=await getJson("/weather"); weatherOk=true;
      const cards=$$(".metrics-grid .metric-card");
      addReading(cards[0],"Kecepatan angin terkini",format(data.windSpeed,2),"km/jam");
      addReading(cards[3],"Curah hujan terkini",format(data.rain,1),"mm");
      
const directionCard = $$(".middle-grid .section-card")[1];

if (directionCard) {
  // Ambil elemen yang sudah ada.
  const existing = $$(".live-wind-direction", directionCard);

  // Hapus tulisan duplikat yang sudah terlanjur muncul.
  let live = existing[0] || null;
  existing.slice(1).forEach(el => el.remove());

  // Buat elemen hanya jika belum tersedia.
  if (!live) {
    live = document.createElement("p");
    live.className = "live-wind-direction";
    live.style.cssText =
      "margin:8px 0;color:#1a251e;font-weight:600;";

    directionCard.insertBefore(
      live,
      $(".chart-wrap", directionCard) || null
    );
  }

  // Perbarui isi tanpa membuat elemen baru.
  live.textContent =
    `Arah angin terkini: ${directionName(data.windDirection)} (${format(data.windDirection, 0)}°)`;
}

      if(data.time){const d=new Date(data.time);if(!Number.isNaN(d.getTime()))setUpdatedAt(d);}
    } catch(e){weatherOk=false;console.error("Gagal memuat cuaca:",e);} finally{updateStatus();}
  }
  function windSpeedColor(speed) {
    const v = Number(speed);
    if (!Number.isFinite(v)) return "#9ca3af";
    if (v < 20) return "#00b4d8";
    if (v < 30) return "#10b981";
    if (v <= 38) return "#f59e0b";
    return "#ef4444";
  }
  function renderWindCompass(direction, speed, time) {
    const host = document.getElementById("windChart");
    if (!host) return;
    const deg = Number(direction);
    if (!Number.isFinite(deg)) {
      host.textContent = "Data arah angin belum tersedia dari backend.";
      return;
    }
    const angle = ((deg % 360) + 360) % 360;
    const dirs = ["U", "TL", "T", "Tg", "S", "BD", "B", "BL"];
    const names = ["Utara", "Timur Laut", "Timur", "Tenggara", "Selatan", "Barat Daya", "Barat", "Barat Laut"];
    const idx = Math.round(angle / 45) % 8;
    const color = windSpeedColor(speed);
    const cx=180, cy=112, radius=65, arrowR=55;
    const rad=angle*Math.PI/180, ax=cx+Math.sin(rad)*arrowR, ay=cy-Math.cos(rad)*arrowR;
    const labels = dirs.map((d,i)=>{
      const a=i*45*Math.PI/180, x=cx+Math.sin(a)*radius, y=cy-Math.cos(a)*radius;
      const bold = i===idx ? "font-weight:700;fill:#26352b" : "fill:#7b887d";
      return `<text x="${x}" y="${y+4}" text-anchor="middle" font-size="${i%2===0?12:10}" style="${bold}">${d}</text>`;
    }).join("");
    const dateText = time && !Number.isNaN(new Date(time).getTime()) ? new Date(time).toLocaleString("id-ID",{timeZone:"Asia/Jakarta",day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"})+" WIB" : "Waktu data tidak tersedia";
    host.innerHTML = `<div style="width:100%;max-width:380px;margin:0 auto;text-align:center;color:#26352b;">
      <svg viewBox="0 0 360 225" role="img" aria-label="Kompas arah angin ${Math.round(angle)} derajat dari ${names[idx]}" style="width:100%;height:auto;display:block;background:#fff;">
        <circle cx="180" cy="112" r="65" fill="#fff" stroke="#c5cec7" stroke-width="1.3"/>
        <line x1="115" y1="112" x2="245" y2="112" stroke="#e0e5e1"/><line x1="180" y1="47" x2="180" y2="177" stroke="#e0e5e1"/>
        ${labels}
        <line x1="180" y1="112" x2="${ax.toFixed(1)}" y2="${ay.toFixed(1)}" stroke="${color}" stroke-width="3.5" stroke-linecap="round"/>
        <polygon points="${ax.toFixed(1)},${ay.toFixed(1)} ${(ax-5*Math.sin(rad+Math.PI/2)).toFixed(1)},${(ay+5*Math.cos(rad+Math.PI/2)).toFixed(1)} ${(ax-9*Math.sin(rad)).toFixed(1)},${(ay+9*Math.cos(rad)).toFixed(1)} ${(ax-5*Math.sin(rad-Math.PI/2)).toFixed(1)},${(ay+5*Math.cos(rad-Math.PI/2)).toFixed(1)}" fill="${color}"/>
        <circle cx="180" cy="112" r="3" fill="${color}"/>
      </svg>
      <div style="font-size:12px;font-weight:600;margin-top:2px;">Kecepatan: ${Number.isFinite(Number(speed))?Number(speed).toFixed(2)+" km/jam":"--"}</div>
      <div style="font-size:10px;color:#718075;margin-top:4px;">${dateText} · Sumber: EWS Bedono</div>
    </div>`;
  }
  async function loadWindHistory() {
    const host=document.getElementById("windChart");
    try {
      const data=await getJson("/weather/history?results=800");
      const series=(data.series||[]).filter(p=>Number.isFinite(Number(p.direction)));
      const latest=series[series.length-1];
      if (!latest) throw new Error("Tidak ada data arah angin valid");
      renderWindCompass(latest.direction, latest.speed, latest.time);
    } catch(e){if(host)host.textContent="Data arah angin gagal dimuat. Periksa koneksi backend dan konfigurasi ThingSpeak.";console.error("Gagal memuat data arah angin:",e);}
  }
  async function loadClimate() {
    try {
      const data=await getJson("/climate");climateOk=true;
      const cards=$$(".metrics-grid .metric-card");
      addReading(cards[1],"Kelembapan terkini",format(data.humidity,1),"%");
      addReading(cards[2],"Suhu udara terkini",format(data.seaTemperature,1),"°C");
      if(data.time){const d=new Date(data.time);if(!Number.isNaN(d.getTime()))setUpdatedAt(d);}
    }catch(e){climateOk=false;console.error("Gagal memuat iklim:",e);}finally{updateStatus();}
  }
  async function loadTide() {
    try {
      const data=await getJson("/tide?results=8000");tideOk=true;tideSeries=data.series||[];
      const tideCard=$$(".middle-grid .section-card")[0];
      if(tideCard){let reading=$(".live-tide-reading",tideCard);if(!reading){reading=document.createElement("div");reading.className="live-tide-reading";reading.style.cssText="margin:8px 0;padding:8px 10px;background:#f4fbf5;border:1px solid #c8e6c9;border-radius:8px;font-weight:600;color:#1a251e;";tideCard.insertBefore(reading,$(".chart-wrap",tideCard)||null);}reading.textContent=`Nilai pasang surut terbaru: ${format(data.tide,3)} · ${data.time?new Date(data.time).toLocaleString("id-ID",{timeZone:"Asia/Jakarta"})+" WIB":"waktu tidak tersedia"}`;}
      renderTide(document.getElementById("btn7Hari")?.classList.contains("active")?"week":"today");
    }catch(e){tideOk=false;const host=document.getElementById("tideChart");if(host)host.textContent="Data pasut gagal dimuat dari backend. Periksa konfigurasi ThingSpeak.";console.error("Gagal memuat pasut:",e);}
  }
  function wireControls(){
    const refresh=document.getElementById("refreshButton");if(refresh)refresh.addEventListener("click",refreshAll);
    const today=document.getElementById("btnHariIni"),week=document.getElementById("btn7Hari");
    if(today&&week){today.addEventListener("click",()=>{today.classList.add("active");week.classList.remove("active");renderTide("today");});week.addEventListener("click",()=>{week.classList.add("active");today.classList.remove("active");renderTide("week");});}
  }
  async function refreshAll(){
    await Promise.all([loadWeather(),loadClimate(),loadTide(),loadWindHistory()]);
    updateStatus();
    // Timestamp indicates when the dashboard refresh completed; individual cards retain their own source timestamps where shown.
    if (weatherOk || climateOk || tideOk) setUpdatedAt(new Date());
    await loadRobForecast(false);
  }
  document.addEventListener("DOMContentLoaded",()=>{wireControls();wireCalendarControls();refreshAll();window.setInterval(refreshAll,60000);});
})();
