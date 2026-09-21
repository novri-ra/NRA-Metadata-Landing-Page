// automation.js
// Orchestration logic for the NRA DreamLab automation loop.

// ---- Shared state globals (classic scripts share the global lexical env) ----
let isPausedGlobal = false;
let batchLimitGlobal = 0;
let isAutomatingGlobal = false;

// Global execution flag for the automation loop
let isRunning = false;
// Mutex guard: prevents concurrent startMainLoop() invocations (KRITIS-2)
let isLoopActive = false;
// Session Statistics Telemetry
let prompts = [];
let sessionStats = {
  startTime: null,
  successCount: 0,
  downloadCount: 0,
  totalCooldowns: 0,
  totalPrompts: 0,
};

let isWaitingForCooldown = false;
let isCooldownActive = false; // Guard
let consecutiveCooldownCount = 0; // Guard for consecutive cooldowns

// Snapshot batch lama (tombol & gambar) sebelum klik Generate, untuk deteksi render anti-stale-DOM
let renderSnapshot = null;

/**
 * Error Handling Router: updates state in storage and logs details to side panel.
 * @param {Error} err
 */
function handleAutomationError(err) {
  isRunning = false;
  isLoopActive = false;

  const e = asAutomationError(err);

  if (e.code === ERR.USER_STOPPED) {
    console.info("[NRA DreamLab] Process stopped manually.");
    chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
      sendStatusUpdate("[STOP] Automation stopped. System ready.");
    });
    return;
  }

  console.error("[NRA DreamLab] Loop broken due to:", e.message);
  if (e && e.stack) console.error("[Stack Trace]:", e.stack);

  if (e.code === ERR.MONTHLY_LIMIT_REACHED) {
    console.error(
      "[NRA DreamLab] Monthly AI limit reached. Stopping permanently.",
    );
    chrome.storage.local.set({ isAutomating: false, step: "ERROR" }, () => {
      sendStatusUpdate("[LIMIT] Monthly Limit Reached. Stopped.");
      safeSendMessage({
        action: "SHOW_NOTIFICATION",
        title: "Canva Automation Halted",
        message:
          "You've hit your plan's monthly AI limit! Automation has been permanently stopped.",
      });
    });
    return;
  }

  const errMsg = e.message || "Unknown error occurred.";
  chrome.storage.local.set({ isAutomating: false, step: "ERROR" }, () => {
    safeSendMessage({
      action: "STATUS_UPDATE",
      status: "Error: " + errMsg,
    });
  });
  safeSendMessage({ action: "RELEASE_AWAKE" });
}

async function safeCdpClick(element, context = "element") {
  try {
    await cdpClick(element);
  } catch (error) {
    if (error && error.message === ERR.USER_STOPPED) throw error;
    console.error(`[NRA DreamLab] Failed to click ${context}:`, error);
    safeSendMessage({ action: "EMERGENCY_CLEANUP" });
    throw new AutomationError("CLICK_FAILED", `Click interaction failed for ${context}`);
  }
}

async function safeCdpTypeHuman(text, context = "input") {
  try {
    await cdpTypeHuman(text);
  } catch (error) {
    if (error && error.message === ERR.USER_STOPPED) throw error;
    console.error(`[NRA DreamLab] Failed to type in ${context}:`, error);
    safeSendMessage({ action: "EMERGENCY_CLEANUP" });
    throw new AutomationError("TYPE_FAILED", `Type interaction failed for ${context}`);
  }
}

async function cdpClick(element) {
  // Proteksi tambahan: Pastikan elemen masih terhubung ke DOM
  if (!element.isConnected) {
    throw new Error("Element detached from DOM before click");
  }

  element.scrollIntoView({ behavior: "smooth", block: "center" });
  await delay(300);

  // Suntikkan event klik murni ke DOM (mengakali perlindungan React/Next.js)
  element.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, view: window }));
  element.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true, view: window }));
  element.click();
}

async function cdpTypeHuman(text) {
  // Kembalikan posisi halaman ke paling atas agar textarea terlihat jelas oleh pengguna
  window.scrollTo({ top: 0, behavior: "instant" });
  await delay(300);

  const textarea = await waitForElement(CANVA_SELECTORS.PROMPT_TEXTAREA);
  if (!textarea) throw new Error("Textarea not found");

  // Jika textarea ditemukan, pastikan dia masuk ke fokus visual layar kembali
  textarea.scrollIntoView({ behavior: "instant", block: "center" });
  textarea.focus();
  await delay(200);

  const storage = await chrome.storage.local.get(["typingMode"]);
  const mode = storage.typingMode || "human";

  // Debugging untuk memastikan mode apa yang terbaca
  console.log(`[NRA DreamLab] Debugging - Current Typing Mode: ${mode}`);

  if (mode === "instant") {
    console.log(`[NRA DreamLab] Executing Instant Paste...`);

    // Pancing state aktif pada elemen
    textarea.focus();

    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
    nativeInputValueSetter.call(textarea, text);

    // Tambahkan cancelable: true agar event disimulasikan lebih realistis
    textarea.dispatchEvent(new Event("input", { bubbles: true, cancelable: true }));
    textarea.dispatchEvent(new Event("change", { bubbles: true, cancelable: true }));

    // Lepas fokus agar Canva menyadari bahwa input telah selesai
    textarea.blur();
  } else {
    console.log(`[NRA DreamLab] Executing Super Fast Human Typing (20ms delay)...`);
    textarea.value = "";
    const typingDelay = 20; // Diturunkan ke 20ms agar pengetikan jauh lebih cepat
    for (const char of text) {
      textarea.value += char;
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      await delay(typingDelay);
    }
    textarea.dispatchEvent(new Event("change", { bubbles: true }));
  }
}

async function safeSelectCanvaConfiguration(typeLabel, optionText) {
  try {
    return await selectCanvaConfiguration(typeLabel, optionText);
  } catch (error) {
    console.error(
      `[NRA DreamLab] Failed to configure ${typeLabel} with ${optionText}:`,
      error,
    );
    safeSendMessage({ action: "EMERGENCY_CLEANUP" });
    throw new Error(`Configuration interaction failed for ${typeLabel}`);
  }
}

async function selectCanvaConfiguration(label, value) {
  if (!value || value === "None" || value === "" || value === "Random") return true;

  console.info(`[NRA DreamLab] Memulai proses pemilihan: Menu '${label}' -> Opsi '${value}'`);

  // LANGKAH 1: Buka Menu Dropdown (seperti tombol "Style") jika diperlukan
  const buttons = Array.from(document.querySelectorAll('button'));
  const dropdownBtn = buttons.find(btn =>
    (btn.getAttribute('aria-label') && btn.getAttribute('aria-label').toLowerCase().includes(label.toLowerCase())) ||
    (btn.textContent && btn.textContent.toLowerCase().trim() === label.toLowerCase())
  );

  if (dropdownBtn) {
    const isExpanded = dropdownBtn.getAttribute('aria-expanded') === 'true';
    if (!isExpanded) {
      console.info(`[NRA DreamLab] Membuka dropdown menu '${label}'...`);
      dropdownBtn.click();
      await new Promise(r => setTimeout(r, 1200)); // Tunggu animasi menu terbuka
    } else {
      console.info(`[NRA DreamLab] Dropdown menu '${label}' sudah terbuka.`);
    }
  } else {
    console.info(`[NRA DreamLab] Tombol menu '${label}' tidak ditemukan (mungkin opsi langsung tampil di layar).`);
  }

  // LANGKAH 2: Cari dan klik opsi (Style / Aspect Ratio)
  for (let i = 0; i < 10; i++) {
    // Ambil elemen yang berperan sebagai opsi style (role="button") atau opsi ratio (role="option")
    const optionElements = Array.from(document.querySelectorAll('[role="button"], [role="option"]'));

    const targetOption = optionElements.find(el => {
      const ariaLabel = el.getAttribute('aria-label') || "";
      const text = el.textContent || "";
      // Cocokkan persis (case-insensitive) dengan aria-label ATAU teks
      return ariaLabel.toLowerCase() === value.toLowerCase() ||
        text.toLowerCase().trim() === value.toLowerCase();
    });

    if (targetOption) {
      // Hapus kondisi pembatas !isSelected agar bot tidak melewatkan (skip) klik akibat state history lama
      targetOption.click();
      console.info(`[NRA DreamLab] ✅ Pemaksaan klik dieksekusi pada opsi '${value}' untuk menu '${label}'.`);

      await new Promise(r => setTimeout(r, 800)); // Jeda stabilitas DOM
      return true;
    }
    await new Promise(r => setTimeout(r, 1000));
  }

  console.error(`[NRA DreamLab] GAGAL: Opsi '${value}' tidak ditemukan di layar.`);
  return false;
}

/**
 * Starts the main bulk automation loop, running sequentially without page reloads.
 */
async function configureStyleAndRatio(imageStyle, aspectRatio) {
  const styleOk = await safeSelectCanvaConfiguration("Style", imageStyle);
  if (styleOk === false) {
    console.error("[NRA DreamLab] Gagal memilih Style, tidak melanjutkan ke Ratio.");
    return false;
  }
  const ratioOk = await safeSelectCanvaConfiguration("Ratio", aspectRatio);
  if (ratioOk === false) {
    console.error("[NRA DreamLab] Gagal memilih Ratio.");
    return false;
  }
  return true;
}

async function clearInputField() {
  const textarea = await waitForElement(CANVA_SELECTORS.PROMPT_TEXTAREA);
  if (!textarea || !textarea.isConnected) throw new Error("Textarea not found or stale");

  // Pastikan input bisa diklik/difokuskan sebelum dibersihkan
  await safeCdpClick(textarea, "focus textarea");
  await delay(300);

  textarea.value = "";
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
}

async function typePrompt(currentPrompt) {
  const textarea = await waitForElement(CANVA_SELECTORS.PROMPT_TEXTAREA);
  if (!textarea || !textarea.isConnected) throw new Error("Textarea not found or stale");
  await safeCdpTypeHuman(currentPrompt, "prompt input");
}

async function submitPrompt(currentIndex, totalPrompts) {
  console.info("[NRA DreamLab] Mencari tombol Generate...");
  const generateBtn = await waitForElement(CANVA_SELECTORS.SUBMIT_BUTTON, 15000);

  // Snapshot batch lama SEBELUM klik Generate (anti stale-DOM):
  // tombol download & src gambar yang sudah ada TIDAK boleh memicu deteksi render baru.
  renderSnapshot = {
    downloadButtons: new Set(document.querySelectorAll(CANVA_SELECTORS.DOWNLOAD_BUTTON)),
    imageSrcs: new Set(
      Array.from(document.querySelectorAll('img[src^="https://"], img[src^="blob:"]'))
        .map((img) => img.currentSrc || img.getAttribute("src"))
        .filter(Boolean)
    ),
  };

  // Implement DOM Tagging (Marking): Prevent bot from reading previous generated images
  getRenderContainers().forEach((c) => c.setAttribute("data-nra-processed", "true"));

  await safeCdpClick(generateBtn, "generate button");

  // Tag semua tombol download yang sudah ada SEBELUM generate.
  // Sinyal kesiapan = MUNCULNYA tombol download baru (bukan kontainer),
  // sehingga tidak bergantung pada struktur kontainer yang bisa reused/berubah.
  document.querySelectorAll(CANVA_SELECTORS.DOWNLOAD_BUTTON).forEach((b) =>
    b.setAttribute("data-nra-downloaded", "true")
  );

  // State Transition Wait: Jeda singkat agar Canva sempat memproses klik & menambah/menghapus DOM
  await delay(1500);
}

async function waitForRenderCompletion(currentIndex, totalPrompts) {
  console.info("[NRA DreamLab] Menunggu inisiasi node kontainer baru...");

  // Tunggu kontainer render baru muncul (max 60 detik) sebelum mulai pemantauan rendering
  console.info("[NRA DreamLab] Menunggu kontainer render baru muncul di DOM...");
  const sectionWaitStart = Date.now();
  const sectionWaitMax = 60000;
  while (Date.now() - sectionWaitStart < sectionWaitMax) {
    if (!isRunning && !isWaitingForCooldown) throw new AutomationError(ERR.USER_STOPPED);
    if (getRenderContainers(true).length > 0) {
      console.info("[NRA DreamLab] Kontainer render baru terdeteksi di DOM.");
      break;
    }
    await delay(1000);
  }

  const countRes = await chrome.storage.local.get(["downloadCount"]);
  const targetDownloadCount = parseInt(countRes.downloadCount, 10) || 4;
  const requiredDownloads = targetDownloadCount;

  console.info("[NRA DreamLab] Memulai pemantauan adaptif fase rendering (Anti-Stale DOM + Anti-Skeleton)...");
  const maxWaitTimeMs = 240000;
  const checkIntervalMs = 1000;
  const startTime = Date.now();
  let detectedFinalizing = false;
  let lastStatusSecond = -1;

  while (Date.now() - startTime < maxWaitTimeMs) {

    if (!isRunning && !isWaitingForCooldown) throw new AutomationError(ERR.USER_STOPPED);

    // Status [RENDER] Rendering images... tetap muncul setiap detik selama Canva masih memproses
    const elapsedSecs = Math.floor((Date.now() - startTime) / 1000);
    if (elapsedSecs !== lastStatusSecond) {
      lastStatusSecond = elapsedSecs;
      sendStatusUpdate(`[${currentIndex + 1}/${totalPrompts}] [RENDER] Rendering images... ${formatTime(elapsedSecs)} elapsed`);
    }

    const pageText = document.body.textContent || "";

    const isSketching = /sketching/i.test(pageText);
    const isFinalizing = /finalizing/i.test(pageText);
    const isProcessingText = isSketching || isFinalizing || /refining|generating|memproses|membuat/i.test(pageText) ||
      document.querySelector('[role="progressbar"]') !== null;

    // Tandai jika bot berhasil mendeteksi fase Finalizing dari Canva
    if (isFinalizing) {
      if (!detectedFinalizing) {
        console.info("[NRA DreamLab] 🎯 Fase 'Finalizing your image...' terdeteksi di layar.");
        detectedFinalizing = true;
      }
    }

    // --- ANTI STALE-DOM: hanya elemen BARU (di luar snapshot) yang boleh dihitung ---
    // Tombol download baru: belum ditag 'data-nra-downloaded', tampil, dan node-nya bukan milik batch lama.
    const newButtons = Array.from(
      document.querySelectorAll(CANVA_SELECTORS.DOWNLOAD_BUTTON)
    ).filter((b) =>
      isVisible(b) &&
      !b.hasAttribute("data-nra-downloaded") &&
      !renderSnapshot.downloadButtons.has(b)
    );
    const buttonsReady = newButtons.length >= requiredDownloads;

    // Gambar baru: src berbeda dari snapshot batch lama
    const newImages = Array.from(document.querySelectorAll('img[src^="https://"], img[src^="blob:"]'))
      .filter((img) => !renderSnapshot.imageSrcs.has(img.currentSrc || img.getAttribute("src")));
    // ANTI SKELETON: jangan resolve selama gambar baru belum termuat sempurna.
    const imageLoaded = newImages.some((img) => img.complete && img.naturalWidth > 0);

    // Fallback: batch berbasis <canvas> tidak bisa diverifikasi muatannya -> dianggap siap begitu ada canvas
    const canvasPresent = document.querySelectorAll("canvas").length > 0;
    const mediaReady = imageLoaded || canvasPresent;

    // Render selesai = batch tombol BARU lengkap + media baru termuat + tidak ada indikator pemrosesan aktif.
    // Skeleton/placeholder (belum load) TIDAK boleh me-resolve deteksi.
    const renderDone = buttonsReady && mediaReady && !isProcessingText;

    if (renderDone) {
      // JIKA SEBELUMNYA TERDETEKSI FINALIZING, BERIKAN JEDA AMAN SINKRONISASI ANIMASI 5 DETIK
      if (detectedFinalizing) {
        console.info("[NRA DreamLab] ✨ Teks Finalizing hilang. Menahan download selama 5 detik agar animasi render selesai sempurna...");
        await delay(5000);
      }

      // Ambil ekstra safety delay dari storage jika dikonfigurasi oleh pengguna
      const res = await chrome.storage.local.get(["safetyDelay"]);
      const extraDelay = (parseInt(res.safetyDelay, 10) || 0) * 1000;
      if (extraDelay > 0) {
        console.info(`[NRA DreamLab] Menerapkan Extra Safety Delay sebesar ${extraDelay}ms...`);
        await delay(extraDelay);
      }

      console.info("[NRA DreamLab] ✅ Batch baru terdeteksi siap dan tajam! Menuju proses download...");
      return targetDownloadCount;
    }

    console.log("[NRA DreamLab] Menunggu proses rendering gambar Canva tuntas...");
    await delay(checkIntervalMs);
  }

  throw new Error("Timeout: Proses pembuatan tajam gambar Canva melampaui batas waktu aman.");
}

async function handleDownload(countSetting = "4", currentPrompt = "", currentIndex, totalPrompts) {
  sendStatusUpdate(`[${currentIndex + 1}/${totalPrompts}] [DL] Locating download buttons...`);
  console.info(`[NRA DreamLab] Memulai isolasi kontainer untuk prompt aktif: "${currentPrompt}"`);

  // 1. Ambil kontainer render (div[role="group"][data-testid] atau section fallback)
  const allContainers = getRenderContainers();
  const newContainers = allContainers.filter(c => !c.hasAttribute('data-nra-processed'));
  // ponytail: prefer unprocessed containers; fall back to all if none found
  const sections = newContainers.length > 0 ? newContainers : allContainers;
  let targetContainer = null;

  if (currentPrompt) {
    const cleanActivePrompt = currentPrompt.trim().toLowerCase();
    // Gunakan 25 karakter pertama untuk mengatasi pemotongan string '...' oleh Canva
    const promptSnippet = cleanActivePrompt.substring(0, 25).trim();

    // 2. Lakukan perulangan untuk mencari kontainer yang membungkus teks prompt aktif
    for (const container of sections) {
      // Multi-fallback: cek span[data-testid], button span, p, lalu textContent keseluruhan
      const titleElements = container.querySelectorAll('span[data-testid], button span, p');
      let matchesPrompt = false;

      for (const el of titleElements) {
        const elText = (el.textContent || el.innerText || "").trim().toLowerCase();
        if (elText.includes(promptSnippet)) {
          matchesPrompt = true;
          break;
        }
      }

      // Fallback: bandingkan langsung textContent kontainer
      if (!matchesPrompt) {
        const fullText = (container.textContent || "").toLowerCase();
        if (fullText.includes(promptSnippet)) {
          matchesPrompt = true;
        }
      }

      if (matchesPrompt) {
        targetContainer = container;
        console.info("[NRA DreamLab] ✅ Sukses mengunci kontainer berdasarkan kecocokan teks prompt!");
        break;
      }
    }
  }

  // Fallback 1: Jika pencocokan teks gagal, ambil kontainer terbaru (indeks 0 = paling atas di DOM)
  if (!targetContainer && sections.length > 0) {
    console.warn("[NRA DreamLab] Pencocokan teks prompt tidak mendeteksi kontainer. Fallback mengambil kontainer teratas/terbaru...");
    targetContainer = sections[0];
  }

  // Fallback 2: Jika tidak ada section sama sekali
  if (!targetContainer) {
    targetContainer = document.body;
    console.warn("[NRA DreamLab] Fallback ultimate ke document body.");
  }

  let targetCount = parseInt(countSetting, 10) || 4;
  let allDownloadButtons = [];
  try {
    // 3. Cari tombol download secara eksklusif HANYA di dalam targetContainer yang telah dikunci
    const MAX_DOWNLOAD_RETRIES = 15;

    for (let attempt = 0; attempt < MAX_DOWNLOAD_RETRIES; attempt++) {
      const buttons = Array.from(targetContainer.querySelectorAll(CANVA_SELECTORS.DOWNLOAD_BUTTON))
        .filter(btn => isVisible(btn)); // Pastikan elemennya benar-benar tampil di layar

      allDownloadButtons = buttons;
      if (buttons.length >= targetCount) {
        break;
      } else {
        console.info(`[NRA DreamLab] Baru ditemukan ${buttons.length}/${targetCount} tombol download, menunggu...`);
      }
      console.info(`[NRA DreamLab] Tombol download belum siap, mencoba lagi dalam 2 detik... (Attempt ${attempt + 1}/${MAX_DOWNLOAD_RETRIES})`);
      await delay(2000);
    }

    if (allDownloadButtons.length === 0) {
      throw new Error("Tombol download tidak ditemukan setelah batas waktu penungguan.");
    }
  } catch (error) {
    throw new Error("Gagal mengisolasi tombol unduh: " + error.message);
  }


  let buttonsToClick = allDownloadButtons.slice(0, targetCount);
  console.log(`[NRA DreamLab] Mengunduh ${buttonsToClick.length} gambar eksklusif dari kontainer prompt aktif.`);

  const prefix = `[${currentIndex + 1}/${totalPrompts}]`;
  for (let i = 0; i < buttonsToClick.length; i++) {
    const btn = buttonsToClick[i];
    sendStatusUpdate(`${prefix} [DL ${i + 1}/${buttonsToClick.length}] Saving asset...`);

    // Validasi ulang: Pastikan elemen masih terhubung ke DOM sebelum berinteraksi
    if (btn && btn.isConnected) {
      try {
        // Paksa scroll visual agar tombol berada di tengah layar (mencegah terhalang layout)
        btn.scrollIntoView({ behavior: "instant", block: "center" });
        await delay(500);

        await safeCdpClick(btn, `download button ${i + 1} dari kontainer prompt aktif`);
        await delay(1000); // Jeda agresif namun aman

        sessionStats.downloadCount++;
        chrome.storage.local.set({ sessionStats: sanitizeStats(sessionStats) });
        safeSendMessage({
          action: "UPDATE_STATS",
          stats: sanitizeStats(sessionStats)
        });
      } catch (clickError) {
        console.warn(`[NRA DreamLab] Percobaan klik tombol ${i + 1} meleset, mencoba fallback klik native...`);
        btn.click();
        await delay(3000);
      }
    } else {
      console.warn(`[NRA DreamLab] Tombol download ${i + 1} terlepas dari DOM sebelum diklik. Melewati...`);
    }
  }

  sendStatusUpdate(`${prefix} [DONE] Batch downloaded (${buttonsToClick.length}/${targetCount} assets saved).`);
}

// ponytail: removed sendStatusUpdate (moved to utils.js)

async function handleCooldown(cooldownMs, isStartup = false, promptPrefix = "") {
  if (isCooldownActive) return true;
  isCooldownActive = true;
  isWaitingForCooldown = true;
  console.log(`[DEBUG] Entering handleCooldown for ${cooldownMs}ms`);
  if (!isStartup) sessionStats.totalCooldowns++;
  cooldownMs += 5000;
  console.warn(`[NRA DreamLab] ${isStartup ? "Startup paused. Pre-existing cooldown" : "Cooldown"} detected: ${cooldownMs}ms. Waiting...`);
  tagGhostCooldowns();
  const targetEndTime = Date.now() + cooldownMs;
  while (Date.now() < targetEndTime) {
    if (!isAutomatingGlobal) {
      if (isStartup) {
        console.log("[NRA DreamLab] Automation aborted by user during startup cooldown.");
        isWaitingForCooldown = false;
        isCooldownActive = false;
        return false;
      }
      isWaitingForCooldown = false;
      isCooldownActive = false;
      throw new AutomationError(ERR.USER_STOPPED);
    }
    const remainingSecs = Math.ceil((targetEndTime - Date.now()) / 1000);
    safeSendMessage({
      action: "STATUS_UPDATE",
      status: `${promptPrefix}[COOLDOWN] ${isStartup ? "Startup Paused (Limit Active)" : "Cooldown"}: waiting ${remainingSecs}s before next prompt...`
    });
    await delay(1000);
  }
  tagGhostCooldowns();

  consecutiveCooldownCount++;
  if (consecutiveCooldownCount >= 3) {
    console.error("[NRA DreamLab] Limit akun tercapai secara beruntun. Menghentikan bot.");
    safeSendMessage({ action: "STATUS_UPDATE", status: "Error: Account limit reached. Automation paused." });
    chrome.storage.local.set({ isAutomating: false, step: "IDLE", isPaused: true });
    isWaitingForCooldown = false;
    isCooldownActive = false;
    consecutiveCooldownCount = 0;
    throw new AutomationError(ERR.MAX_COOLDOWN_REACHED);
  }
  console.log(
    `[NRA DreamLab] ${isStartup ? "Startup cooldown cleared. Proceeding to main generation loop..." : "Cooldown cleared. Resuming..."}`,
  );
  safeSendMessage({
    action: "STATUS_UPDATE",
    status: `Resuming ${isStartup ? "automation" : "after cooldown"}...`,
  });
  isWaitingForCooldown = false;
  isCooldownActive = false;
  return true;
}

/**
 * Starts the main bulk automation loop, running sequentially without page reloads.
 */
async function startMainLoop() {
  console.log("[NRA DreamLab] Starting main automation loop...");
  sendStatusUpdate("[START] Starting automation...");

  // Initialize Session Statistics
  sessionStats = {
    successCount: 0,
    downloadCount: 0,
    totalCooldowns: 0,
    startTime: Date.now(),
  };
  const storedStats = await chrome.storage.local.get(["sessionStats"]);
  if (storedStats.sessionStats) {
    sessionStats = storedStats.sessionStats;
  } else {
    await chrome.storage.local.set({ sessionStats });
  }

  // Check for last processed prompt index
  const lastIndexResult = await chrome.storage.local.get([
    "lastProcessedPromptIndex",
  ]);
  let startIndex = 0;
  if (lastIndexResult.lastProcessedPromptIndex !== undefined) {
    startIndex = lastIndexResult.lastProcessedPromptIndex;
    console.log(`[NRA DreamLab] Resuming from prompt index: ${startIndex}`);
  }

  // Natively await storage here. Any pre-flight crash falls to the outer catch block.
  try {
    const result = await chrome.storage.local.get([
      "prompts",
      "aspectRatio",
      "imageStyle",
      "downloadCount",
    ]);

    if (!window.location.href.includes("canva.com/dream-lab")) {
      throw new AutomationError(ERR.URL_MISMATCH);
    }

    const prompts = (result.prompts || []).map((p) => sanitizeInput(p));
    sessionStats.totalPrompts = prompts.length;
    sessionStats.startTime = Date.now();
    const aspectRatio = result.aspectRatio;
    const imageStyle = result.imageStyle;
    const limitRes = await chrome.storage.local.get(["batchLimit"]);
    batchLimitGlobal = parseInt(limitRes.batchLimit, 10) || 0;
    const downloadCountSetting = result.downloadCount || "4";

    if (prompts.length === 0) {
      throw new Error("No prompts found in storage.");
    }

    // Mark status as active automation
    await chrome.storage.local.set({ isAutomating: true });

    // Request Keep Awake to prevent system sleep during automation
    await safeSendMessage({ action: "KEEP_AWAKE" });

    try {
      // 🌟 INITIAL STARTUP GATEKEEPER 🌟
      const canProceed = await checkAndHandleStartupCooldown();
      if (!canProceed) return;

      let isConfigured = false;

      // 🌟 MAIN GENERATION LOOP 🌟
      let pauseNoticeSent = false;
      while (prompts.length > 0 && isRunning) {
        const storageSnapshot = await chrome.storage.local.get([
          "isPaused",
          "batchLimit",
          "isAutomating",
        ]);

        if (storageSnapshot.isAutomating === false) {
          throw new AutomationError(ERR.USER_STOPPED);
        }

        if (storageSnapshot.isPaused === true) {
          console.log("[NRA DreamLab] Automation paused by user.");
          if (!pauseNoticeSent) {
            pauseNoticeSent = true;
            sendStatusUpdate("[PAUSE] Automation paused. Click RESUME to continue.");
          }
          await delay(1000);
          continue;
        }
        pauseNoticeSent = false;

        // 1. Hitung indeks aktif secara akurat sebelum array prompts dikurangi/di-shift
        const currentIndex = startIndex + (sessionStats.totalPrompts - prompts.length);


        // MEMORY LEAK PREVENTION: Reload page natively every 50 processed prompts
        if (sessionStats.successCount > 0 && sessionStats.successCount % 50 === 0) {
          console.info("[NRA DreamLab] 🧹 Preventative memory dump: Reloading tab after 50 prompts to clear Canva DOM bloat.");
          await chrome.storage.local.set({
            isRecovering: true,
            lastProcessedPromptIndex: currentIndex
          });
          window.location.reload();
          return;
        }

        // 2. Baru ambil prompt aktif dari antrean
        const currentPrompt = prompts.shift();

        // 2. PRE-FLIGHT GATEKEEPER: Cek dan tahan bot jika ada cooldown aktif SEBELUM mulai mengetik
        let startupCooldown = getScreenCooldownMs();
        let justFinishedCooldown = false;
        if (startupCooldown > 0) {
          console.warn(`[NRA DreamLab] Batasan limit aktif terdeteksi sebelum mulai mengetik! Menahan loop selama ${startupCooldown}ms`);
          await handleCooldown(startupCooldown, false, `[${currentIndex + 1}/${sessionStats.totalPrompts}] `);

          console.info("[NRA DreamLab] 🛡️ Cooldown selesai. Mengaktifkan Post-Cooldown Recovery Delay selama 5 detik untuk stabilitas sesi...");
          await delay(5000);
          justFinishedCooldown = true;
        }

        // 3. Update prompt aktif ke storage untuk penamaan file background.js
        await chrome.storage.local.set({ downloadingPrompt: currentPrompt });

        // 4. Konfigurasi, Injeksi (Mengetik dengan kecepatan baru), dan Submit
        await prepareAndSubmitPrompt(
          currentPrompt,
          isConfigured,
          imageStyle,
          aspectRatio,
          currentIndex,
          sessionStats.totalPrompts
        );
        isConfigured = true;

        // 5. Download / Retry Loop
        let downloadSuccess = false;
        let retryCount = 0;
        const maxRetries = 3;

        while (!downloadSuccess && retryCount < maxRetries) {
          try {
            await handleDownload(downloadCountSetting, currentPrompt, currentIndex, sessionStats.totalPrompts);
            downloadSuccess = true;
            consecutiveCooldownCount = 0; // Reset guard setelah sukses
          } catch (error) {
            console.error(`[NRA DreamLab] Download attempt ${retryCount + 1} failed:`, error.message);
            retryCount++;
            if (retryCount < maxRetries) {
              console.warn("[NRA DreamLab] Memulai prosedur recovery, mereload halaman...");

              // Simpan state recovery SEBELUM me-reload halaman
              await chrome.storage.local.set({
                isRecovering: true,
                lastProcessedPromptIndex: currentIndex - 1
              });

              window.location.reload();

              // Hentikan eksekusi: instance script ini akan musnah saat page reload
              return;
            }
          }
        }

        // 6. POST-FLIGHT CHECK: Cek kembali cooldown jika limit baru lahir pasca-submit
        if (!justFinishedCooldown) {
          let postCooldownMs = getScreenCooldownMs();
          if (postCooldownMs > 0) {
            console.warn(`[NRA DreamLab] Limit akun terdeteksi pasca-submit! Waktu tunggu: ${postCooldownMs}ms`);
            await handleCooldown(postCooldownMs, false, `[${currentIndex + 1}/${sessionStats.totalPrompts}] `);

            console.info("[NRA DreamLab] 🛡️ Cooldown selesai. Mengaktifkan Post-Cooldown Recovery Delay selama 5 detik untuk stabilitas sesi...");
            await delay(5000);
          }
        } else {
          console.info("[NRA DreamLab] 🛡️ POST-FLIGHT cooldown check dilewati karena sesi ini baru saja bangkit dari cooldown (Stale DOM prevention).");
        }

        justFinishedCooldown = false;

        // 7. Update status ke storage & panel
        if (!downloadSuccess) {
          safeSendMessage({
            action: "PROMPT_FAILED",
            failedPrompt: currentPrompt
          });
        }

        sessionStats.successCount++;
        await chrome.storage.local.set({
          prompts: prompts,
          sessionStats: sanitizeStats(sessionStats),
          lastProcessedPromptIndex: currentIndex,
        });

        safeSendMessage({
          action: "UPDATE_TEXTAREA",
          remainingPrompts: prompts
        });

        if (batchLimitGlobal > 0 && sessionStats.downloadCount >= batchLimitGlobal) {
          isRunning = false;
          chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
            sendStatusUpdate("[STOP] Batch limit reached. Automation stopped.");
          });
          break;
        }

        await delay(2000);
      }

      // Final cleanup
      if (isRunning) {
        console.log("[NRA DreamLab] All prompts processed successfully.");
        chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
          sendStatusUpdate(`[DONE] All ${sessionStats.totalPrompts} prompts processed successfully!`);
        });
        safeSendMessage({ action: "RELEASE_AWAKE" });
      }
    } catch (err) {
      handleAutomationError(err);
    }
  } catch (err) {
    handleAutomationError(err);
  }
}

// ==========================================
// Helpher Functions Extracted from startMainLoop
// ==========================================
async function checkAndHandleStartupCooldown() {
  let startupCooldown = getScreenCooldownMs();
  if (startupCooldown > 0) {
    const proceeded = await handleCooldown(startupCooldown, true);
    return proceeded;
  }
  return true;
}

async function prepareAndSubmitPrompt(
  currentPrompt,
  isConfigured,
  imageStyle,
  aspectRatio,
  currentIndex,
  totalPrompts
) {
  if (!isConfigured) {
    await configureStyleAndRatio(imageStyle, aspectRatio);
  }

  // Urutan status LINEAR & SINKRON (strict order, each awaited):
  // [CLEAN] -> [TYPE] -> [SUBMIT] -> [RENDER] (persist) -> [RENDER] N images ready
  const prefix = `[${currentIndex + 1}/${totalPrompts}]`;

  sendStatusUpdate(`${prefix} [CLEAN] Clearing input field...`);
  await clearInputField();

  sendStatusUpdate(`${prefix} [TYPE] Typing prompt...`);
  await typePrompt(currentPrompt);

  sendStatusUpdate(`${prefix} [SUBMIT] Generating images...`);
  await submitPrompt(currentIndex, totalPrompts);

  sendStatusUpdate(`${prefix} [RENDER] Rendering images...`);
  const targetDownloadCount = await waitForRenderCompletion(currentIndex, totalPrompts);

  sendStatusUpdate(`${prefix} [RENDER] ${targetDownloadCount} images ready`);
  return targetDownloadCount;
}