const state = {
  config: null,
  layouts: [],
  selected: 0,
  dirty: false,
  iconVersion: Date.now(),
  dragged: null,
  ignoreClick: false,
  mosaicDraft: null,
  mosaicPreviewResult: null,
  mosaicPreviewToken: 0,
  mosaicPreviewTimer: null,
  selectedLayoutId: "",
  layoutsRenderToken: 0,
  applications: [],
  applicationsStatus: "idle",
  applicationsError: "",
  applicationsRequest: null,
  applicationIconImports: new Map(),
};

const $ = (selector) => document.querySelector(selector);
const elements = {
  buttonGrid: $("#buttonGrid"),
  editorTitle: $("#editorTitle"),
  editorBody: $("#editorBody"),
  enabled: $("#buttonEnabled"),
  position: $("#buttonPosition"),
  wideDisplayModeField: $("#wideDisplayModeField"),
  wideDisplayMode: $("#wideDisplayMode"),
  metricsControls: $("#metricsControls"),
  metricsView: $("#metricsView"),
  metricsLayout: $("#metricsLayout"),
  metricsSize: $("#metricsSize"),
  metricsSizeValue: $("#metricsSizeValue"),
  metricsFontFamily: $("#metricsFontFamily"),
  metricsFontStyle: $("#metricsFontStyle"),
  metricsColors: {
    cpu: { color: $("#metricsCpuColor"), label_color: $("#metricsCpuLabelColor"), line_color: $("#metricsCpuLineColor") },
    mem: { color: $("#metricsMemColor"), label_color: $("#metricsMemLabelColor"), line_color: $("#metricsMemLineColor") },
    gpu: { color: $("#metricsGpuColor"), label_color: $("#metricsGpuLabelColor"), line_color: $("#metricsGpuLineColor") },
  },
  metricsStylePreview: $("#metricsStylePreview"),
  icon: $("#buttonIcon"),
  iconRow: $("#iconRow"),
  iconPreview: $("#iconPreview"),
  logoScale: $("#logoScale"),
  logoScaleValue: $("#logoScaleValue"),
  contentMarginField: $("#contentMarginField"),
  contentMargin: $("#contentMargin"),
  contentMarginValue: $("#contentMarginValue"),
  upload: $("#iconUpload"),
  mosaicUpload: $("#mosaicUpload"),
  mosaicEditor: $("#mosaicEditor"),
  mosaicPreview: $("#mosaicPreview"),
  mosaicPreviewStatus: $("#mosaicPreviewStatus"),
  editBackground: $("#editBackgroundButton"),
  mosaicScale: $("#mosaicScale"),
  mosaicScaleValue: $("#mosaicScaleValue"),
  mosaicDarkness: $("#mosaicDarkness"),
  mosaicIncludeWide: $("#mosaicIncludeWide"),
  mosaicDarknessValue: $("#mosaicDarknessValue"),
  applyMosaic: $("#applyMosaicButton"),
  backgroundOverview: $("#backgroundOverview"),
  uploadText: $("#uploadText"),
  iconHelp: $("#iconHelp"),
  wideActionToggle: $("#wideActionToggle"),
  wideActionEnabled: $("#wideActionEnabled"),
  label: $("#buttonLabel"),
  labelField: $("#buttonLabelField"),
  action: $("#buttonAction"),
  actionField: $("#buttonActionField"),
  actionFields: $("#actionFields"),
  brightness: $("#brightness"),
  brightnessValue: $("#brightnessValue"),
  labelAlign: $("#labelAlign"),
  labelSize: $("#labelSize"),
  showTitles: $("#showTitles"),
  obsHost: $("#obsHost"),
  obsPort: $("#obsPort"),
  obsPassword: $("#obsPassword"),
  save: $("#saveButton"),
  saveState: $("#saveState"),
  layoutName: $("#layoutName"),
  savedLayouts: $("#savedLayouts"),
  saveLayout: $("#saveLayoutButton"),
  loadLayout: $("#loadLayoutButton"),
  deleteLayout: $("#deleteLayoutButton"),
  deviceStatus: $("#deviceStatus"),
  serviceStatus: $("#serviceStatus"),
  toast: $("#toast"),
};

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Erro HTTP ${response.status}`);
  return data;
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function iconUrl(name) {
  return name ? `/api/icons/${encodeURIComponent(name)}?v=${state.iconVersion}` : "";
}

function toast(message, error = false) {
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", error);
  elements.toast.classList.add("visible");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => elements.toast.classList.remove("visible"), 3600);
}

function markDirty() {
  state.dirty = true;
  elements.saveState.textContent = "Alterações não salvas";
}

function setStatus(element, online, onlineText, offlineText) {
  element.classList.toggle("online", online);
  element.classList.toggle("offline", !online);
  element.lastChild.textContent = online ? onlineText : offlineText;
}

async function refreshStatus() {
  try {
    const status = await api("/api/status");
    setStatus(elements.deviceStatus, status.device_connected, "D200 conectado", "D200 desconectado");
    setStatus(elements.serviceStatus, status.service === "active", "Daemon ativo", "Daemon parado");
  } catch (error) {
    setStatus(elements.deviceStatus, false, "", "Status indisponível");
    setStatus(elements.serviceStatus, false, "", "Serviço indisponível");
  }
}

function contentMargin(button) {
  return Math.max(0, Math.min(48, Math.trunc(Number(button.content_margin) || 0)));
}

function setForegroundSize(image, button, wide = false, scale = 100) {
  const margin = wide && button.display_mode === "background" ? 0 : contentMargin(button);
  const width = wide ? 458 : 196;
  image.style.width = `${scale * (width - margin * 2) / width}%`;
  image.style.height = `${scale * (196 - margin * 2) / 196}%`;
}

function appendPreviewImage(container, name, className, scale = 100, button = null, wide = false) {
  if (!name) return;
  const image = document.createElement("img");
  image.className = className;
  image.src = iconUrl(name);
  image.style.setProperty("--preview-scale", `${scale}%`);
  if (button) setForegroundSize(image, button, wide, scale);
  image.alt = "";
  container.append(image);
}

function metricSvgElement(tag, attributes) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
}

function appendMeterPreview(metric, value, size) {
  const meter = document.createElement("div");
  meter.className = "metrics-meter";
  const svg = metricSvgElement("svg", { viewBox: "0 0 342 46", "aria-hidden": "true" });
  const count = Math.max(1, Math.floor((342 - 24 - Math.trunc(size * 3.2)) / 6));
  for (let segment = 0; segment < Math.round(value * count / 100); segment += 1) {
    svg.append(metricSvgElement("rect", { x: 8 + segment * 6, y: 8, width: 4, height: 30 }));
  }
  meter.append(svg);
  metric.append(meter);
}

function appendHistoryPreview(readout, colors) {
  const examples = {
    cpu: [12, 30, 55, 24, 61, 44, 32],
    mem: [40, 41, 43, 43, 46, 46, 48],
    gpu: [5, 5, 50, 22, 74, 29, 12],
  };
  const graph = document.createElement("div");
  graph.className = "metrics-history";
  const svg = metricSvgElement("svg", {
    viewBox: "0 0 434 72", preserveAspectRatio: "none", "aria-hidden": "true",
  });
  [0, 36, 72].forEach((y) => svg.append(metricSvgElement("line", {
    x1: 0, x2: 434, y1: y, y2: y, class: "metrics-grid-line",
  })));
  Object.entries(examples).forEach(([key, values]) => {
    const points = values.map((value, index) => `${index * 434 / 6},${72 - value * 0.72}`).join(" ");
    const line = metricSvgElement("polyline", { points, class: "metrics-history-line" });
    line.style.setProperty("--metrics-line-color", colors[key].line_color);
    svg.append(line);
  });
  graph.append(svg);
  const axis = document.createElement("div");
  axis.className = "metrics-history-axis";
  const start = document.createElement("span");
  start.textContent = "-60s";
  const end = document.createElement("span");
  end.textContent = "0s";
  axis.append(start, end);
  readout.append(graph, axis);
}

function renderMetricsPreview(container, button) {
  container.replaceChildren();
  if (!button.enabled) {
    appendPreviewImage(container, button.background_tile, "metrics-background");
    return;
  }
  const background = button.background_tile || button.image;
  if (String(background || "").toLowerCase().endsWith(".png")) {
    appendPreviewImage(container, background, "metrics-background");
  }
  const style = button.metrics_style;
  const readout = document.createElement("div");
  readout.className = `metrics-readout ${style.layout} view-${style.view} font-${style.font_family} font-style-${style.font_style}`;
  readout.style.setProperty("--metrics-size", style.size);
  readout.style.setProperty("--metrics-label-size", Math.max(12, Math.floor(
    style.size * (style.view === "text" && style.layout === "compact" ? 0.45 : 0.73),
  )));
  [["cpu", "CPU", 32], ["mem", "RAM", 48], ["gpu", "GPU", 12]].forEach(([key, name, value]) => {
    const metric = document.createElement("div");
    metric.className = "metric";
    metric.style.setProperty("--metrics-color", style.colors[key].color);
    metric.style.setProperty("--metrics-label-color", style.colors[key].label_color);
    metric.style.setProperty("--metrics-line-color", style.colors[key].line_color);
    const number = document.createElement("span");
    number.className = "metric-value";
    number.textContent = `${value}%`;
    const label = document.createElement("span");
    label.className = "metric-name";
    label.textContent = name;
    metric.append(number, label);
    if (style.view === "htop") appendMeterPreview(metric, value, style.size);
    if (style.view === "history") {
      const swatch = document.createElement("span");
      swatch.className = "metric-line-key";
      metric.append(swatch);
    }
    readout.append(metric);
  });
  if (style.view === "history") appendHistoryPreview(readout, style.colors);
  const foreground = document.createElement("div");
  foreground.className = "metrics-foreground";
  const margin = contentMargin(button);
  foreground.style.transform = `scale(${(196 - margin * 2) / 196})`;
  foreground.append(readout);
  container.append(foreground);
}

function renderMiniDeck(container, config) {
  container.replaceChildren();
  config.buttons.forEach((button, index) => {
    const item = document.createElement("div");
    item.className = "mini-button";
    if (index === 13) item.classList.add("wide");
    if (!button.enabled) item.classList.add("disabled");
    item.classList.toggle("has-background", Boolean(button.background_tile));
    if (!button.enabled) {
      appendPreviewImage(item, button.background_tile, "preview-background");
    } else if (index === 13 && button.display_mode === "stats") {
      renderMetricsPreview(item, button);
    } else if (button.enabled) {
      if (index !== 13 || button.display_mode !== "background") {
        appendPreviewImage(item, button.background_tile, "preview-background");
      }
      appendPreviewImage(
        item,
        button.icon_source || button.image,
        "preview-logo",
        index === 13 ? 100 : (button.icon_scale || 100),
        button,
        index === 13,
      );
    }
    container.append(item);
  });
}

function renderBackgroundOverview() {
  elements.editBackground.disabled = !state.config.background;
  elements.backgroundOverview.replaceChildren();
  state.config.buttons.slice(0, 13).forEach((button) => {
    const tile = document.createElement("div");
    tile.className = "background-tile";
    appendPreviewImage(tile, button.background_tile, "preview-background");
    elements.backgroundOverview.append(tile);
  });
  const wide = document.createElement("div");
  wide.className = "background-wide-slot";
  const wideButton = state.config.buttons[13];
  if (wideButton.background_tile || (wideButton.enabled && ["background", "stats"].includes(wideButton.display_mode))) {
    appendPreviewImage(
      wide,
      wideButton.background_tile || (wideButton.enabled ? wideButton.icon_source || wideButton.image : ""),
      "preview-background",
    );
  } else {
    wide.textContent = "Tela larga preservada";
  }
  elements.backgroundOverview.append(wide);
}

function selectSavedLayout(layoutId, updateName = true) {
  const layout = state.layouts.find((item) => item.id === layoutId);
  state.selectedLayoutId = layout ? layout.id : "";
  if (updateName) elements.layoutName.value = layout ? layout.name : "";
  elements.loadLayout.disabled = !layout;
  elements.deleteLayout.disabled = !layout;
  elements.savedLayouts.querySelectorAll(".layout-card").forEach((card) => {
    const selected = card.dataset.layoutId === state.selectedLayoutId;
    card.classList.toggle("selected", selected);
    card.setAttribute("aria-pressed", String(selected));
  });
}

function renderLayouts(selectedId = state.selectedLayoutId) {
  const token = ++state.layoutsRenderToken;
  elements.savedLayouts.replaceChildren();
  if (!state.layouts.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "Nenhum layout salvo. Salve o layout atual para vê-lo aqui.";
    elements.savedLayouts.append(empty);
  }
  state.layouts.forEach((layout) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "layout-card";
    card.dataset.layoutId = layout.id;
    card.setAttribute("aria-label", `Selecionar layout ${layout.name}`);
    card.setAttribute("aria-busy", "true");
    const title = document.createElement("strong");
    title.textContent = layout.name;
    const preview = document.createElement("div");
    preview.className = "mini-deck";
    preview.setAttribute("aria-hidden", "true");
    const status = document.createElement("span");
    status.className = "hint";
    status.textContent = "Carregando imagem…";
    card.append(preview, title, status);
    card.addEventListener("click", () => selectSavedLayout(layout.id));
    elements.savedLayouts.append(card);
    api(`/api/layouts/${encodeURIComponent(layout.id)}`).then((loaded) => {
      if (token !== state.layoutsRenderToken || !card.isConnected) return;
      renderMiniDeck(preview, loaded.config);
      status.remove();
      card.setAttribute("aria-busy", "false");
    }).catch((error) => {
      if (token !== state.layoutsRenderToken || !card.isConnected) return;
      status.textContent = `Não foi possível carregar a imagem: ${error.message}`;
      card.setAttribute("aria-busy", "false");
    });
  });
  selectSavedLayout(selectedId, false);
}

async function refreshLayouts(selectedId = "") {
  const result = await api("/api/layouts");
  state.layouts = result.layouts;
  renderLayouts(selectedId);
}

async function saveNamedLayout() {
  const name = elements.layoutName.value.trim();
  if (!name) {
    toast("Informe um nome para o layout", true);
    elements.layoutName.focus();
    return;
  }
  elements.saveLayout.disabled = true;
  elements.saveLayout.textContent = "Salvando…";
  try {
    await Promise.all(state.applicationIconImports.values());
    const saved = await api("/api/layouts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, config: state.config }),
    });
    await refreshLayouts(saved.id);
    elements.layoutName.value = saved.name;
    toast(`Layout “${saved.name}” salvo`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    elements.saveLayout.disabled = false;
    elements.saveLayout.textContent = "Salvar layout";
  }
}

async function loadNamedLayout() {
  const layoutId = state.selectedLayoutId;
  if (!layoutId) return;
  if (state.dirty && !window.confirm("Descartar alterações não salvas e carregar este layout?")) {
    return;
  }
  elements.loadLayout.disabled = true;
  try {
    const loaded = await api(`/api/layouts/${encodeURIComponent(layoutId)}`);
    state.config = loaded.config;
    resetMosaicEditor();
    state.selected = 0;
    state.dirty = true;
    state.iconVersion = Date.now();
    elements.layoutName.value = loaded.layout.name;
    elements.saveState.textContent = `Layout “${loaded.layout.name}” carregado; falta aplicar`;
    renderGlobalSettings();
    renderGrid();
    renderEditor();
    toast(`Layout “${loaded.layout.name}” carregado no editor`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    renderLayouts();
  }
}

async function deleteNamedLayout() {
  const layoutId = state.selectedLayoutId;
  const layout = state.layouts.find((item) => item.id === layoutId);
  if (!layout) return;
  if (!window.confirm(`Excluir o layout “${layout.name}”?`)) return;
  elements.deleteLayout.disabled = true;
  try {
    await api(`/api/layouts/${encodeURIComponent(layoutId)}`, { method: "DELETE" });
    elements.layoutName.value = "";
    await refreshLayouts();
    toast(`Layout “${layout.name}” excluído`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    renderLayouts();
  }
}

function renderGlobalSettings() {
  const config = state.config;
  elements.brightness.value = config.brightness;
  elements.brightnessValue.textContent = `${config.brightness}%`;
  elements.labelAlign.value = config.label_style.Align;
  elements.labelSize.value = config.label_style.Size;
  elements.showTitles.checked = config.label_style.ShowTitle;
  elements.obsHost.value = config.obs.host;
  elements.obsPort.value = config.obs.port;
  elements.obsPassword.value = config.obs.password || "";
}

function swapButtons(from, to) {
  if (from === to || from < 0 || to < 0 || from === 13 || to === 13) return;
  [state.config.buttons[from], state.config.buttons[to]] = [
    state.config.buttons[to],
    state.config.buttons[from],
  ];
  state.config.buttons.forEach((button, index) => { button.index = index; });
  state.selected = to;
  markDirty();
  renderGrid();
  renderEditor();
}

function renderGrid() {
  elements.buttonGrid.replaceChildren();
  state.config.buttons.forEach((button, index) => {
    button.content_margin ??= 0;
    const card = document.createElement("button");
    card.type = "button";
    card.className = "deck-button";
    card.classList.toggle("wide-display", index === 13);
    card.draggable = index !== 13;
    card.classList.toggle("selected", index === state.selected);
    card.classList.toggle("disabled", !button.enabled);
    card.classList.toggle("has-background", Boolean(button.background_tile));
    card.setAttribute("aria-label", `Editar ou mover botão ${index + 1}`);

    const iconSource = button.icon_source || button.image;
    const statsDisplay = index === 13 && button.display_mode === "stats";
    if (!button.enabled && button.background_tile) {
      appendPreviewImage(card, button.background_tile, "background-layer");
    } else if (button.enabled && statsDisplay) {
      renderMetricsPreview(card, button);
    } else if (button.enabled && iconSource) {
      if ((index !== 13 || button.display_mode !== "background") && button.background_tile) {
        const background = document.createElement("img");
        background.className = "background-layer";
        background.src = iconUrl(button.background_tile);
        background.alt = "";
        card.append(background);
      }
      const image = document.createElement("img");
      image.className = "logo-layer";
      image.src = iconUrl(iconSource);
      setForegroundSize(image, button, index === 13, index === 13 ? 100 : (button.icon_scale || 100));
      image.alt = "";
      card.append(image);
    } else if (button.background_tile) {
      appendPreviewImage(card, button.background_tile, "background-layer");
    } else {
      const fallback = document.createElement("span");
      fallback.className = "fallback";
      fallback.textContent = "+";
      card.append(fallback);
    }

    const number = document.createElement("span");
    number.className = "button-number";
    number.textContent = index + 1;
    if (!button.enabled || !statsDisplay || button.metrics_style.view === "text") card.append(number);

    if (button.enabled && state.config.label_style.ShowTitle && button.label) {
      const label = document.createElement("span");
      label.className = "button-label";
      label.textContent = button.label;
      card.append(label);
    }

    card.addEventListener("click", () => {
      if (state.ignoreClick) return;
      state.selected = index;
      renderGrid();
      renderEditor();
    });
    card.addEventListener("dragstart", (event) => {
      if (index === 13) {
        event.preventDefault();
        return;
      }
      state.dragged = index;
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", String(index));
      card.classList.add("dragging");
    });
    card.addEventListener("dragover", (event) => {
      if (index === 13) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      if (state.dragged !== index) card.classList.add("drag-target");
    });
    card.addEventListener("dragleave", () => card.classList.remove("drag-target"));
    card.addEventListener("drop", (event) => {
      event.preventDefault();
      card.classList.remove("drag-target");
      const source = Number(event.dataTransfer.getData("text/plain"));
      if (Number.isInteger(source)) swapButtons(source, index);
    });
    card.addEventListener("dragend", () => {
      state.dragged = null;
      state.ignoreClick = true;
      document.querySelectorAll(".deck-button").forEach((item) => {
        item.classList.remove("dragging", "drag-target");
      });
      window.setTimeout(() => { state.ignoreClick = false; }, 0);
    });
    elements.buttonGrid.append(card);
  });
  renderBackgroundOverview();
}

function refreshIconOptions(selectedName) {
  elements.icon.replaceChildren();
  const wide = state.selected === 13;
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = wide ? "Selecione um GIF" : "Selecione um ícone";
  elements.icon.append(empty);
  state.config.icons
    .filter((name) => wide ? name.toLowerCase().endsWith(".gif") : name.toLowerCase().endsWith(".png"))
    .forEach((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      elements.icon.append(option);
    });
  elements.icon.value = selectedName || "";
}

function renderIconPreview(name, scale = 100, backgroundName = "") {
  elements.iconPreview.replaceChildren();
  const button = state.config.buttons[state.selected];
  const wide = state.selected === 13;
  elements.iconPreview.classList.toggle("disabled", !button.enabled);
  elements.iconPreview.classList.toggle("has-background", Boolean(backgroundName));
  if (backgroundName && (!button.enabled || !wide || button.display_mode !== "background")) {
    const background = document.createElement("img");
    background.className = "background-layer";
    background.src = iconUrl(backgroundName);
    background.alt = "";
    elements.iconPreview.append(background);
  }
  if (!button.enabled || !name) {
    if (!backgroundName) {
      const text = document.createElement("span");
      text.textContent = "Sem ícone";
      elements.iconPreview.append(text);
    }
    return;
  }
  const image = document.createElement("img");
  image.className = "logo-layer";
  image.src = iconUrl(name);
  image.style.setProperty("--logo-scale", `${scale}%`);
  setForegroundSize(image, button, wide, scale);
  image.alt = "Prévia do ícone";
  elements.iconPreview.append(image);
}

function field(label, value, onInput, options = {}) {
  const wrapper = document.createElement("label");
  wrapper.className = "field";
  const title = document.createElement("span");
  title.textContent = label;
  const input = document.createElement("input");
  input.type = options.type || "text";
  if (options.id) input.id = options.id;
  input.value = value || "";
  input.placeholder = options.placeholder || "";
  input.autocomplete = "off";
  input.addEventListener("input", () => {
    onInput(input.value);
    if (options.dirty !== false) markDirty();
  });
  wrapper.append(title, input);
  return wrapper;
}

function obsActionField(button) {
  const wrapper = document.createElement("label");
  wrapper.className = "field";
  const title = document.createElement("span");
  title.textContent = "Operação do OBS";
  const select = document.createElement("select");
  const actions = [
    ["toggle_scene", "Alternar entre cenas"],
    ["set_scene", "Ativar uma cena"],
    ["toggle_source", "Mostrar/ocultar fonte"],
    ["toggle_recording", "Iniciar/parar gravação"],
    ["toggle_streaming", "Iniciar/parar transmissão"],
  ];
  actions.forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    select.append(option);
  });
  select.value = button.params.action || "toggle_recording";
  select.addEventListener("change", () => {
    button.params = defaultParams("obs", select.value);
    markDirty();
    renderActionFields(button);
  });
  wrapper.append(title, select);
  return wrapper;
}

function defaultParams(action, obsAction = "toggle_recording") {
  if (action === "app") return { name: "" };
  if (action === "key") return { keys: "" };
  if (action === "obs") {
    if (obsAction === "toggle_scene") return { action: obsAction, scene1: "", scene2: "" };
    if (obsAction === "set_scene") return { action: obsAction, scene: "" };
    if (obsAction === "toggle_source") return { action: obsAction, scene: "", source: "" };
    return { action: obsAction };
  }
  return { cmd: "" };
}

function loadApplications() {
  if (!state.applicationsRequest) {
    state.applicationsStatus = "loading";
    state.applicationsRequest = api("/api/applications")
      .then((data) => {
        state.applications = data.applications;
        state.applicationsStatus = "ready";
      })
      .catch((error) => {
        state.applicationsError = error.message;
        state.applicationsStatus = "error";
      });
  }
  return state.applicationsRequest;
}

function importSelectedApplicationIcon(button, application) {
  if (state.config.buttons.indexOf(button) === 13) return;
  const params = button.params;
  const previousSource = button.icon_source;
  const previousImage = button.image;
  const isCurrent = () => state.config.buttons.includes(button)
    && button.action === "app" && button.params === params
    && params.name === application.desktop_file
    && button.icon_source === previousSource && button.image === previousImage
    && state.applicationIconImports.get(button) === request;
  const request = (async () => {
    try {
      const result = await api("/api/applications/icon", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: application.id }),
      });
      if (!isCurrent()) return;
      if (!result.filename) {
        toast("Aplicativo sem ícone disponível; ícone atual mantido");
        return;
      }
      if (!state.config.icons.includes(result.filename)) {
        state.config.icons.push(result.filename);
        state.config.icons.sort();
      }
      button.icon_source = result.filename;
      button.image = result.filename;
      state.iconVersion = Date.now();
      markDirty();
      renderGrid();
      if (state.config.buttons[state.selected] === button) renderEditor();
    } catch (error) {
      if (isCurrent()) toast(`Não foi possível obter o ícone: ${error.message}`, true);
    } finally {
      if (state.applicationIconImports.get(button) === request) {
        state.applicationIconImports.delete(button);
      }
    }
  })();
  state.applicationIconImports.set(button, request);
}

function applicationFields(button) {
  const wrapper = document.createElement("div");
  wrapper.className = "application-picker";
  const params = button.params;
  let manualMode = null;
  const searchField = field("Pesquisar aplicativos", "", updateOptions, {
    id: "applicationSearch",
    type: "search",
    placeholder: "Digite o nome do aplicativo",
    dirty: false,
  });
  const search = searchField.querySelector("input");
  const selectField = document.createElement("label");
  selectField.className = "field";
  const title = document.createElement("span");
  title.textContent = "Aplicativo instalado";
  const select = document.createElement("select");
  select.id = "applicationSelect";
  selectField.append(title, select);
  const status = document.createElement("p");
  status.id = "applicationStatus";
  status.className = "hint application-status";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  search.setAttribute("aria-describedby", status.id);
  select.setAttribute("aria-describedby", status.id);
  const manualField = field("Executável", params.name, (value) => {
    manualMode = true;
    params.name = value;
  }, { id: "applicationExecutable", placeholder: "firefox" });
  const manualInput = manualField.querySelector("input");
  wrapper.append(searchField, selectField, status, manualField);

  function isCurrent() {
    return wrapper.isConnected
      && state.config.buttons[state.selected] === button
      && button.action === "app"
      && button.params === params;
  }

  function updateOptions() {
    const applications = state.applications;
    const current = applications.find((app) => app.desktop_file === params.name);
    const query = search.value.trim().toLocaleLowerCase();
    const filtered = applications.filter((app) => app.name.toLocaleLowerCase().includes(query));
    const useManual = manualMode ?? (
      (Boolean(params.name) && !current)
      || state.applicationsStatus === "error"
      || (state.applicationsStatus === "ready" && !applications.length)
    );
    const currentVisible = current && filtered.some((app) => app.desktop_file === current.desktop_file);
    const placeholder = document.createElement("option");
    placeholder.value = "__choose__";
    placeholder.disabled = true;
    placeholder.textContent = current && !currentVisible
      ? `${current.name} (fora da pesquisa)`
      : "Selecione um aplicativo";
    const manualOption = document.createElement("option");
    manualOption.value = "";
    manualOption.textContent = "Informar executável manualmente";
    select.replaceChildren(placeholder, manualOption);
    filtered.forEach((app) => {
      const option = document.createElement("option");
      option.value = app.desktop_file;
      option.textContent = app.name;
      select.append(option);
    });
    select.value = useManual ? "" : (currentVisible ? current.desktop_file : "__choose__");
    manualField.hidden = !useManual;
    if (manualInput.value !== (params.name || "")) manualInput.value = params.name || "";
    search.disabled = state.applicationsStatus !== "ready" || !applications.length;
    wrapper.setAttribute("aria-busy", String(state.applicationsStatus === "loading"));
    status.classList.toggle("error", state.applicationsStatus === "error");
    if (state.applicationsStatus === "loading") {
      status.textContent = "Carregando aplicativos instalados…";
    } else if (state.applicationsStatus === "error") {
      status.textContent = `Não foi possível carregar os aplicativos: ${state.applicationsError}. Você pode informar o executável manualmente.`;
    } else if (!applications.length) {
      status.textContent = "Nenhum aplicativo instalado encontrado. Você pode informar o executável manualmente.";
    } else if (!filtered.length) {
      status.textContent = "Nenhum aplicativo corresponde à pesquisa.";
    } else {
      status.textContent = `${filtered.length} de ${applications.length} aplicativos`;
    }
  }

  select.addEventListener("change", () => {
    if (!isCurrent()) return;
    if (select.value === "") {
      manualMode = true;
      updateOptions();
      manualInput.focus();
      return;
    }
    const application = state.applications.find((app) => app.desktop_file === select.value);
    if (!application) return;
    manualMode = false;
    params.name = application.desktop_file;
    markDirty();
    updateOptions();
    importSelectedApplicationIcon(button, application);
  });

  const request = loadApplications();
  updateOptions();
  request.then(() => {
    if (isCurrent()) updateOptions();
  });
  return wrapper;
}

function renderActionFields(button) {
  elements.actionFields.replaceChildren();
  if (button.action === "command") {
    elements.actionFields.append(field("Comando", button.params.cmd, (value) => { button.params.cmd = value; }, { placeholder: "notify-send 'Olá'" }));
  } else if (button.action === "app") {
    elements.actionFields.append(applicationFields(button));
  } else if (button.action === "key") {
    elements.actionFields.append(field("Combinação de teclas", button.params.keys, (value) => { button.params.keys = value; }, { placeholder: "ctrl+alt+t" }));
  } else if (button.action === "obs") {
    elements.actionFields.append(obsActionField(button));
    const operation = button.params.action;
    if (operation === "toggle_scene") {
      elements.actionFields.append(
        field("Cena A", button.params.scene1, (value) => { button.params.scene1 = value; }),
        field("Cena B", button.params.scene2, (value) => { button.params.scene2 = value; }),
      );
    } else if (operation === "set_scene") {
      elements.actionFields.append(field("Cena", button.params.scene, (value) => { button.params.scene = value; }));
    } else if (operation === "toggle_source") {
      elements.actionFields.append(
        field("Cena", button.params.scene, (value) => { button.params.scene = value; }),
        field("Fonte", button.params.source, (value) => { button.params.source = value; }),
      );
    }
  }
}

function renderEditor() {
  const button = state.config.buttons[state.selected];
  const wide = state.selected === 13;
  const statsDisplay = wide && button.display_mode === "stats";
  const backgroundDisplay = wide && button.display_mode === "background";
  elements.editorTitle.textContent = wide ? "Botão 14 · tela larga" : `Botão ${state.selected + 1}`;
  elements.position.replaceChildren();
  state.config.buttons.forEach((_, index) => {
    if ((wide && index !== 13) || (!wide && index === 13)) return;
    const option = document.createElement("option");
    option.value = index;
    option.textContent = wide ? "Posição fixa da tela" : `Posição ${index + 1}`;
    elements.position.append(option);
  });
  elements.position.value = state.selected;
  elements.position.disabled = wide;
  elements.enabled.checked = button.enabled;
  elements.wideDisplayModeField.hidden = !wide;
  elements.wideDisplayMode.value = button.display_mode || "gif";
  elements.metricsControls.hidden = !statsDisplay;
  if (statsDisplay) {
    const style = button.metrics_style;
    elements.metricsView.value = style.view;
    elements.metricsLayout.closest(".field").hidden = style.view !== "text";
    elements.metricsLayout.value = style.layout;
    elements.metricsSize.value = style.size;
    elements.metricsSizeValue.textContent = `${style.size} px`;
    elements.metricsFontFamily.value = style.font_family;
    elements.metricsFontStyle.value = style.font_style;
    Object.entries(elements.metricsColors).forEach(([key, controls]) => {
      controls.color.value = style.colors[key].color;
      controls.label_color.value = style.colors[key].label_color;
      controls.line_color.value = style.colors[key].line_color;
      controls.line_color.closest(".field").hidden = style.view !== "history";
    });
    renderMetricsPreview(elements.metricsStylePreview, button);
  }
  elements.iconRow.hidden = statsDisplay || (backgroundDisplay && button.enabled);
  elements.iconPreview.classList.toggle("wide-display-preview", wide);
  elements.iconRow.classList.toggle("wide-icon-row", wide);
  elements.editorBody.classList.toggle("inactive", !button.enabled);
  const iconSource = button.icon_source || button.image;
  const iconScale = wide ? 100 : (button.icon_scale || 100);
  refreshIconOptions(iconSource);
  renderIconPreview(iconSource, iconScale, button.background_tile);
  elements.contentMarginField.hidden = backgroundDisplay;
  elements.contentMargin.value = contentMargin(button);
  elements.contentMarginValue.textContent = `${contentMargin(button)} px`;
  elements.logoScale.closest(".logo-size-field").hidden = wide;
  elements.logoScale.value = iconScale;
  elements.logoScaleValue.textContent = `${iconScale}%`;
  elements.upload.accept = wide ? "image/gif,.gif" : "image/png,image/jpeg,image/webp";
  elements.uploadText.textContent = wide ? "Enviar GIF" : "Enviar imagem";
  elements.iconHelp.textContent = wide
    ? "GIF animado. Ajustado para 458 × 196, até 300 quadros e 8 MB."
    : "PNG, JPG ou WebP. Ajustado para 196 × 196.";
  const actionEnabled = !wide || Boolean(button.action_enabled);
  elements.wideActionToggle.hidden = !wide;
  elements.wideActionEnabled.checked = actionEnabled;
  elements.labelField.hidden = !actionEnabled;
  elements.actionField.hidden = !actionEnabled;
  elements.actionFields.hidden = !actionEnabled;
  elements.label.value = button.label;
  elements.action.value = button.action;
  if (actionEnabled) {
    renderActionFields(button);
  } else {
    elements.actionFields.replaceChildren();
  }
}

function bindEvents() {
  elements.brightness.addEventListener("input", () => {
    state.config.brightness = Number(elements.brightness.value);
    elements.brightnessValue.textContent = `${elements.brightness.value}%`;
    markDirty();
  });
  elements.labelAlign.addEventListener("change", () => {
    state.config.label_style.Align = elements.labelAlign.value;
    markDirty();
  });
  elements.labelSize.addEventListener("input", () => {
    state.config.label_style.Size = Number(elements.labelSize.value);
    markDirty();
  });
  elements.showTitles.addEventListener("change", () => {
    state.config.label_style.ShowTitle = elements.showTitles.checked;
    markDirty();
    renderGrid();
  });
  [[elements.obsHost, "host"], [elements.obsPort, "port"], [elements.obsPassword, "password"]].forEach(([element, key]) => {
    element.addEventListener("input", () => {
      state.config.obs[key] = key === "port" ? Number(element.value) : element.value;
      markDirty();
    });
  });

  elements.position.addEventListener("change", () => {
    swapButtons(state.selected, Number(elements.position.value));
  });
  elements.enabled.addEventListener("change", () => {
    const button = state.config.buttons[state.selected];
    button.enabled = elements.enabled.checked;
    if (
      button.enabled
      && !button.image
      && !(state.selected === 13 && button.display_mode === "stats")
    ) {
      const extension = state.selected === 13 ? ".gif" : ".png";
      button.image = state.config.icons.find(
        (name) => name.toLowerCase().endsWith(extension)
      ) || "";
      button.icon_source = button.image;
      button.icon_scale = 100;
    }
    markDirty();
    renderGrid();
    renderEditor();
  });
  elements.icon.addEventListener("change", () => {
    const button = state.config.buttons[state.selected];
    button.image = elements.icon.value;
    button.icon_source = elements.icon.value;
    button.icon_scale = 100;
    elements.logoScale.value = 100;
    elements.logoScaleValue.textContent = "100%";
    markDirty();
    renderIconPreview(
      button.icon_source,
      button.icon_scale,
      button.background_tile,
    );
    renderGrid();
  });
  elements.wideDisplayMode.addEventListener("change", () => {
    const button = state.config.buttons[13];
    const requestedMode = elements.wideDisplayMode.value;
    if (
      requestedMode === "background"
      && !String(button.image || "").toLowerCase().endsWith(".png")
    ) {
      elements.wideDisplayMode.value = button.display_mode;
      toast("Aplique uma imagem de fundo antes de selecionar este modo", true);
      return;
    }
    button.display_mode = requestedMode;
    if (
      button.display_mode === "gif"
      && !String(button.image || "").toLowerCase().endsWith(".gif")
    ) {
      button.image = state.config.icons.find(
        (name) => name.toLowerCase().endsWith(".gif")
      ) || "";
      button.icon_source = button.image;
    }
    markDirty();
    renderGrid();
    renderEditor();
  });
  [elements.metricsView, elements.metricsLayout, elements.metricsSize, elements.metricsFontFamily, elements.metricsFontStyle,
    ...Object.values(elements.metricsColors).flatMap((controls) => Object.values(controls))]
    .forEach((control) => control.addEventListener("input", () => {
      const button = state.config.buttons[13];
      button.metrics_style = {
        layout: elements.metricsLayout.value,
        view: elements.metricsView.value,
        size: Number(elements.metricsSize.value),
        font_family: elements.metricsFontFamily.value,
        font_style: elements.metricsFontStyle.value,
        colors: Object.fromEntries(Object.entries(elements.metricsColors).map(([key, controls]) => [
          key, { color: controls.color.value, label_color: controls.label_color.value,
            line_color: controls.line_color.value },
        ])),
      };
      elements.metricsLayout.closest(".field").hidden = button.metrics_style.view !== "text";
      Object.values(elements.metricsColors).forEach((controls) => {
        controls.line_color.closest(".field").hidden = button.metrics_style.view !== "history";
      });
      elements.metricsSizeValue.textContent = `${button.metrics_style.size} px`;
      markDirty();
      renderGrid();
      renderMetricsPreview(elements.metricsStylePreview, button);
    }));
  elements.wideActionEnabled.addEventListener("change", () => {
    const button = state.config.buttons[13];
    button.action_enabled = elements.wideActionEnabled.checked;
    if (button.action_enabled && !button.action) {
      button.action = "command";
      button.params = { cmd: "" };
    }
    markDirty();
    renderEditor();
  });
  elements.contentMargin.addEventListener("input", () => {
    const button = state.config.buttons[state.selected];
    button.content_margin = Number(elements.contentMargin.value);
    elements.contentMarginValue.textContent = `${button.content_margin} px`;
    markDirty();
    renderGrid();
    if (state.selected === 13 && button.display_mode === "stats") {
      renderMetricsPreview(elements.metricsStylePreview, button);
    } else {
      renderIconPreview(
        button.icon_source || button.image,
        state.selected === 13 ? 100 : (button.icon_scale || 100),
        button.background_tile,
      );
    }
  });
  elements.logoScale.addEventListener("input", () => {
    const button = state.config.buttons[state.selected];
    button.icon_scale = Number(elements.logoScale.value);
    elements.logoScaleValue.textContent = `${button.icon_scale}%`;
    markDirty();
    renderIconPreview(
      button.icon_source || button.image,
      button.icon_scale,
      button.background_tile,
    );
    renderGrid();
  });
  elements.label.addEventListener("input", () => {
    state.config.buttons[state.selected].label = elements.label.value;
    markDirty();
    renderGrid();
  });
  elements.action.addEventListener("change", () => {
    const button = state.config.buttons[state.selected];
    button.action = elements.action.value;
    button.params = defaultParams(button.action);
    markDirty();
    renderActionFields(button);
  });
  elements.upload.addEventListener("change", uploadIcon);
  elements.mosaicUpload.addEventListener("change", selectMosaicImage);
  elements.mosaicScale.addEventListener("input", updateMosaicPreview);
  elements.mosaicDarkness.addEventListener("input", updateMosaicPreview);
  elements.mosaicIncludeWide.addEventListener("change", updateMosaicPreview);
  elements.editBackground.addEventListener("click", editCurrentBackground);
  elements.applyMosaic.addEventListener("click", applyMosaic);
  elements.save.addEventListener("click", saveAndApply);
  elements.saveLayout.addEventListener("click", saveNamedLayout);
  elements.loadLayout.addEventListener("click", loadNamedLayout);
  elements.deleteLayout.addEventListener("click", deleteNamedLayout);
  elements.layoutName.addEventListener("keydown", (event) => {
    if (event.key === "Enter") saveNamedLayout();
  });
  window.addEventListener("beforeunload", (event) => {
    if (state.dirty) event.preventDefault();
  });
}

async function uploadIcon() {
  const file = elements.upload.files[0];
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) {
    toast("A imagem deve ter no máximo 8 MB", true);
    elements.upload.value = "";
    return;
  }
  try {
    const data = await readFileAsDataUrl(file);
    const result = await api("/api/icons", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: file.name,
        data,
        wide: state.selected === 13,
      }),
    });
    if (!state.config.icons.includes(result.filename)) state.config.icons.push(result.filename);
    state.config.icons.sort();
    const button = state.config.buttons[state.selected];
    button.image = result.filename;
    button.icon_source = result.filename;
    button.icon_scale = 100;
    state.iconVersion = Date.now();
    markDirty();
    renderEditor();
    renderGrid();
    toast(state.selected === 13 ? "GIF preparado e adicionado" : "Imagem preparada e adicionada");
  } catch (error) {
    toast(error.message, true);
  } finally {
    elements.upload.value = "";
  }
}

function resetMosaicEditor() {
  clearTimeout(state.mosaicPreviewTimer);
  state.mosaicPreviewToken += 1;
  state.mosaicDraft = null;
  state.mosaicPreviewResult = null;
  elements.mosaicEditor.hidden = true;
}

function openMosaicEditor(draft, settings) {
  resetMosaicEditor();
  state.mosaicDraft = draft;
  elements.mosaicScale.value = settings.scale;
  elements.mosaicDarkness.value = settings.darkness;
  elements.mosaicIncludeWide.checked = settings.include_wide;
  elements.mosaicPreview.replaceChildren();
  elements.mosaicEditor.hidden = false;
  updateMosaicPreview();
  elements.mosaicEditor.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function editCurrentBackground() {
  const background = state.config.background;
  if (background) openMosaicEditor({ source: background.source }, background);
}

function renderMosaicPreview(result) {
  elements.mosaicPreview.replaceChildren();
  result.filenames.slice(0, 13).forEach((filename) => {
    const tile = document.createElement("div");
    tile.className = "background-tile";
    appendPreviewImage(tile, filename, "preview-background");
    elements.mosaicPreview.append(tile);
  });
  const wide = document.createElement("div");
  wide.className = "background-wide-slot";
  if (result.background.include_wide) {
    appendPreviewImage(wide, result.filenames[13], "preview-background");
  } else {
    wide.textContent = "Tela larga preservada";
  }
  elements.mosaicPreview.append(wide);
}

function updateMosaicPreview() {
  const draft = state.mosaicDraft;
  if (!draft) return;
  const settings = {
    scale: Number(elements.mosaicScale.value),
    darkness: Number(elements.mosaicDarkness.value),
    include_wide: elements.mosaicIncludeWide.checked,
  };
  elements.mosaicScaleValue.textContent = `${settings.scale}%`;
  elements.mosaicDarknessValue.textContent = `${settings.darkness}%`;
  elements.applyMosaic.disabled = true;
  state.mosaicPreviewResult = null;
  elements.mosaicPreviewStatus.textContent = "Preparando prévia…";
  elements.mosaicPreview.setAttribute("aria-busy", "true");
  clearTimeout(state.mosaicPreviewTimer);
  const token = ++state.mosaicPreviewToken;
  state.mosaicPreviewTimer = setTimeout(async () => {
    try {
      const result = await api("/api/mosaic", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...draft, ...settings }),
      });
      if (state.mosaicDraft !== draft) return;
      draft.source = result.background.source;
      delete draft.data;
      if (token !== state.mosaicPreviewToken) return;
      state.mosaicPreviewResult = result;
      renderMosaicPreview(result);
      elements.mosaicPreviewStatus.textContent = "Prévia dos recortes que serão aplicados";
      elements.applyMosaic.disabled = false;
    } catch (error) {
      if (token === state.mosaicPreviewToken) {
        elements.mosaicPreviewStatus.textContent = error.message;
        toast(error.message, true);
      }
    } finally {
      if (token === state.mosaicPreviewToken) {
        elements.mosaicPreview.setAttribute("aria-busy", "false");
      }
    }
  }, 180);
}

async function selectMosaicImage() {
  const file = elements.mosaicUpload.files[0];
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) {
    toast("A imagem deve ter no máximo 8 MB", true);
    elements.mosaicUpload.value = "";
    return;
  }
  try {
    const data = await readFileAsDataUrl(file);
    openMosaicEditor(
      { name: file.name, data },
      { scale: 100, darkness: 0, include_wide: false },
    );
  } catch (error) {
    toast("Não foi possível abrir a imagem", true);
  } finally {
    elements.mosaicUpload.value = "";
  }
}

function applyMosaic() {
  const result = state.mosaicPreviewResult;
  if (!result) return;
  state.config.background = { ...result.background };
  result.filenames.slice(0, 13).forEach((filename, index) => {
    state.config.buttons[index].background_tile = filename;
  });
  if (result.background.include_wide && result.filenames[13]) {
    const wide = state.config.buttons[13];
    wide.background_tile = result.filenames[13];
    if (wide.enabled) {
      wide.image = result.filenames[13];
      wide.icon_source = result.filenames[13];
      wide.icon_scale = 100;
      if (wide.display_mode !== "stats") wide.display_mode = "background";
    }
  }
  state.iconVersion = Date.now();
  markDirty();
  renderGrid();
  renderEditor();
  toast("Fundo preparado; use “Salvar e aplicar” para enviá-lo ao D200");
}

async function saveAndApply() {
  elements.save.disabled = true;
  elements.save.textContent = "Aplicando…";
  try {
    await Promise.all(state.applicationIconImports.values());
    const saved = await api("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.config),
    });
    state.config = saved;
    await api("/api/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    state.dirty = false;
    state.iconVersion = Date.now();
    elements.saveState.textContent = "Salvo e aplicado no dispositivo";
    renderGlobalSettings();
    renderGrid();
    renderEditor();
    await refreshStatus();
    toast("Configuração aplicada no D200");
  } catch (error) {
    elements.saveState.textContent = "Não foi possível aplicar";
    toast(error.message, true);
  } finally {
    elements.save.disabled = false;
    elements.save.textContent = "Salvar e aplicar";
  }
}

async function init() {
  try {
    const [config, layouts] = await Promise.all([
      api("/api/config"),
      api("/api/layouts"),
    ]);
    state.config = config;
    state.layouts = layouts.layouts;
    renderGlobalSettings();
    renderLayouts();
    renderGrid();
    renderEditor();
    bindEvents();
    await refreshStatus();
    window.setInterval(refreshStatus, 5000);
  } catch (error) {
    toast(`Falha ao carregar: ${error.message}`, true);
    elements.save.disabled = true;
    elements.saveLayout.disabled = true;
  }
}

init();
