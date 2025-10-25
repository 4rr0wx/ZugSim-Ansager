const selectors = {
  splash: document.getElementById("splash"),
  routeName: document.getElementById("route-name"),
  statusMessage: document.getElementById("status-message"),
  nextStation: document.getElementById("next-station"),
  stationCount: document.getElementById("station-count"),
  stationsList: document.getElementById("stations"),
  manualPresets: document.getElementById("manual-presets"),
  playNext: document.getElementById("play-next"),
  repeatLast: document.getElementById("repeat-last"),
  reset: document.getElementById("reset"),
  fileInput: document.getElementById("file-input"),
  dropzone: document.getElementById("dropzone"),
  autoSpeak: document.getElementById("auto-speak"),
  toast: document.getElementById("toast"),
  openSettings: document.getElementById("open-settings"),
  closeSettings: document.getElementById("close-settings"),
  cancelSettings: document.getElementById("cancel-settings"),
  settingsModal: document.getElementById("settings-modal"),
  settingsForm: document.getElementById("settings-form"),
  openaiKey: document.getElementById("openai-key"),
  voiceSelect: document.getElementById("voice-select"),
  ttsModeRadios: document.querySelectorAll("input[name='tts-mode']"),
};

const state = {
  routeLoaded: false,
  nextStation: null,
  autoSpeak: true,
  lastMessage: null,
  presets: [],
  ttsMode: "browser", // "browser" | "openai"
  openaiKey: "",
  openaiVoice: "alloy",
  currentAudio: null,
};

function stopCurrentAudio() {
  if (state.currentAudio) {
    try {
      state.currentAudio.pause();
      state.currentAudio.src = "";
    } catch (_) {
      // ignore
    }
    state.currentAudio = null;
  }
}

function speakWithBrowser(message) {
  if (!("speechSynthesis" in window)) {
    showToast("Browser unterstützt keine Sprachsynthese.", "error");
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(message);
  utterance.lang = "de-DE";
  window.speechSynthesis.speak(utterance);
}

async function speakWithOpenAI(message) {
  if (!state.openaiKey) {
    throw new Error("Bitte OpenAI API Key hinterlegen.");
  }
  stopCurrentAudio();
  const response = await fetch("https://api.openai.com/v1/audio/speech", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${state.openaiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "gpt-4o-mini-tts",
      voice: state.openaiVoice,
      input: message,
      format: "mp3",
    }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail?.error?.message ?? "OpenAI Ausgabe fehlgeschlagen.");
  }
  const arrayBuffer = await response.arrayBuffer();
  const blob = new Blob([arrayBuffer], { type: "audio/mpeg" });
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  state.currentAudio = audio;
  audio.play().finally(() => {
    URL.revokeObjectURL(url);
  });
}

async function speak(message) {
  if (!state.autoSpeak) {
    return;
  }
  if (state.ttsMode === "openai" && state.openaiKey) {
    await speakWithOpenAI(message);
  } else if (state.ttsMode === "openai" && !state.openaiKey) {
    showToast("Kein OpenAI Key hinterlegt – Browser-Stimme wird verwendet.", "error");
    speakWithBrowser(message);
  } else {
    speakWithBrowser(message);
  }
}

function showToast(text, variant = "info") {
  selectors.toast.textContent = text;
  selectors.toast.dataset.variant = variant;
  selectors.toast.classList.add("show");
  setTimeout(() => selectors.toast.classList.remove("show"), 2400);
}

function setLoading(isLoading) {
  selectors.playNext.disabled = isLoading || !state.routeLoaded;
  selectors.repeatLast.disabled = isLoading || !state.lastMessage;
  selectors.reset.disabled = isLoading || !state.routeLoaded;
}

function updateStations(stations, active) {
  selectors.stationsList.replaceChildren(
    ...stations.map((station, idx) => {
      const li = document.createElement("li");
      if (station === active) {
        li.classList.add("active");
      }
      const badge = document.createElement("span");
      badge.className = "index";
      badge.textContent = String(idx + 1).padStart(2, "0");
      const name = document.createElement("span");
      name.textContent = station;
      li.append(badge, name);
      return li;
    }),
  );
}

function updateUi(data) {
  state.routeLoaded = data.routeLoaded;
  state.nextStation = data.nextStation;

  selectors.playNext.disabled = !data.routeLoaded;
  selectors.repeatLast.disabled = !state.lastMessage;
  selectors.reset.disabled = !data.routeLoaded;

  if (!data.routeLoaded) {
    selectors.routeName.textContent = "Noch keine Strecke geladen";
    selectors.stationCount.textContent = "0 Stationen";
    selectors.statusMessage.textContent = "Lade eine Strecke, um zu starten.";
    selectors.nextStation.textContent = "Nächster Halt: –";
    updateStations([], null);
    return;
  }

  selectors.routeName.textContent = `${data.routeName} • ${data.stations.length} Stationen`;
  selectors.stationCount.textContent = `${data.stations.length} Stationen`;
  selectors.nextStation.textContent = `Nächster Halt: ${data.nextStation ?? "–"}`;
  updateStations(data.stations, data.nextStation);

  if (data.finished) {
    selectors.statusMessage.textContent = "Alle Ansagen wurden abgespielt.";
  }
}

async function fetchState() {
  const response = await fetch("/api/state");
  if (!response.ok) {
    throw new Error("Status konnte nicht geladen werden.");
  }
  const data = await response.json();
  updateUi(data);
}

function renderPresets() {
  const container = selectors.manualPresets;
  if (!state.presets.length) {
    container.replaceChildren();
    const placeholder = document.createElement("p");
    placeholder.className = "preset-placeholder";
    placeholder.textContent = "Keine Sonderansagen verfügbar.";
    container.append(placeholder);
    return;
  }

  const cards = state.presets.map((preset) => {
    const card = document.createElement("article");
    card.className = "preset-card";

    const title = document.createElement("h3");
    title.textContent = preset.title;

    const description = document.createElement("p");
    description.textContent = preset.description;

    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Abspielen";
    button.addEventListener("click", () => triggerPreset(preset.id));

    card.append(title, description, button);
    return card;
  });

  container.replaceChildren(...cards);
}

async function fetchPresets() {
  const response = await fetch("/api/presets");
  if (!response.ok) {
    throw new Error("Standardansagen konnten nicht geladen werden.");
  }
  const data = await response.json();
  state.presets = data.presets ?? [];
  renderPresets();
}

async function handleUpload(file) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/api/route", {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    const detail = await response.json();
    throw new Error(detail?.detail ?? "Upload fehlgeschlagen.");
  }
  const data = await response.json();
  state.lastMessage = null;
  selectors.statusMessage.textContent = "Strecke geladen. Ansage bereit.";
  updateUi(data);
}

async function triggerNext() {
  setLoading(true);
  try {
    const response = await fetch("/api/next", { method: "POST" });
    if (!response.ok) {
      const detail = await response.json();
      throw new Error(detail?.detail ?? "Ansage nicht möglich.");
    }
    const payload = await response.json();
    const message = payload.message;
    state.lastMessage = message;
    selectors.statusMessage.textContent = message;
    selectors.repeatLast.disabled = false;
    updateUi(payload.state);
    try {
      await speak(message);
    } catch (error) {
      showToast(error.message, "error");
    }
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setLoading(false);
  }
}

async function triggerPreset(presetId) {
  try {
    const response = await fetch("/api/preset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ presetId }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail?.detail ?? "Sonderansage konnte nicht abgespielt werden.");
    }
    const payload = await response.json();
    const message = payload.message;
    state.lastMessage = message;
    selectors.statusMessage.textContent = message;
    selectors.repeatLast.disabled = false;
    try {
      await speak(message);
    } catch (error) {
      showToast(error.message, "error");
    }
    showToast(payload?.preset?.title ?? "Sonderansage abgespielt", "success");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function repeatLast() {
  if (!state.lastMessage) return;
  try {
    await speak(state.lastMessage);
    showToast("Ansage wiederholt");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function resetRoute() {
  setLoading(true);
  try {
    const response = await fetch("/api/reset", { method: "POST" });
    if (!response.ok) {
      throw new Error("Zurücksetzen fehlgeschlagen.");
    }
    const data = await response.json();
    state.lastMessage = null;
    selectors.statusMessage.textContent = "Strecke zurückgesetzt.";
    updateUi(data);
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setLoading(false);
  }
}

selectors.playNext.addEventListener("click", triggerNext);
selectors.repeatLast.addEventListener("click", repeatLast);
selectors.reset.addEventListener("click", resetRoute);

selectors.autoSpeak.addEventListener("change", (event) => {
  state.autoSpeak = event.target.checked;
  if (!state.autoSpeak) {
    window.speechSynthesis.cancel();
    stopCurrentAudio();
  }
});

selectors.fileInput.addEventListener("change", async (event) => {
  if (!event.target.files?.length) return;
  try {
    await handleUpload(event.target.files[0]);
    showToast("Strecke geladen", "success");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    event.target.value = "";
  }
});

selectors.dropzone.addEventListener("click", () => selectors.fileInput.click());

selectors.dropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  selectors.dropzone.classList.add("dragover");
});

selectors.dropzone.addEventListener("dragleave", () => {
  selectors.dropzone.classList.remove("dragover");
});

selectors.dropzone.addEventListener("drop", async (event) => {
  event.preventDefault();
  selectors.dropzone.classList.remove("dragover");
  const file = event.dataTransfer?.files?.[0];
  if (!file) return;
  try {
    await handleUpload(file);
    showToast("Strecke geladen", "success");
  } catch (error) {
    showToast(error.message, "error");
  }
});

function openSettingsModal() {
  selectors.settingsModal.classList.remove("hidden");
  selectors.openaiKey.value = state.openaiKey;
  selectors.voiceSelect.value = state.openaiVoice;
  selectors.ttsModeRadios.forEach((radio) => {
    radio.checked = radio.value === state.ttsMode;
  });
}

function closeSettingsModal() {
  selectors.settingsModal.classList.add("hidden");
  selectors.settingsForm.reset();
  selectors.openaiKey.value = state.openaiKey;
  selectors.voiceSelect.value = state.openaiVoice;
  selectors.ttsModeRadios.forEach((radio) => {
    radio.checked = radio.value === state.ttsMode;
  });
}

selectors.openSettings.addEventListener("click", openSettingsModal);
selectors.closeSettings.addEventListener("click", closeSettingsModal);
selectors.cancelSettings.addEventListener("click", closeSettingsModal);

selectors.settingsForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const formData = new FormData(selectors.settingsForm);
  const mode = formData.get("tts-mode") === "openai" ? "openai" : "browser";
  const key = selectors.openaiKey.value.trim();
  const voice = selectors.voiceSelect.value;
  state.ttsMode = mode;
  state.openaiVoice = voice;
  state.openaiKey = key;
  showToast("Einstellungen aktualisiert", "success");
  closeSettingsModal();
});

async function init() {
  const results = await Promise.allSettled([fetchState(), fetchPresets()]);
  results.forEach((result) => {
    if (result.status === "rejected") {
      showToast(result.reason?.message ?? "Initialisierung fehlgeschlagen", "error");
    }
  });
  selectors.splash.classList.add("hidden");
}

document.addEventListener("DOMContentLoaded", init);

window.addEventListener("beforeunload", () => {
  state.openaiKey = "";
  stopCurrentAudio();
});
