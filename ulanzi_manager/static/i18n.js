/*
 * Interface translations.
 *
 * The UI is written in Brazilian Portuguese, which is also the translation key
 * (gettext style): app.js and index.html keep their Portuguese text, and each
 * other language maps that text to its own. Text with no entry is shown as-is.
 *
 * - Placeholders such as {name} are filled in by t(text, params).
 * - tc(context, text) disambiguates identical Portuguese words with different
 *   meanings; its entries are keyed "context|text".
 * - message(text) translates errors returned by the server, including
 *   "Botão N: ..." prefixes and messages that contain numbers.
 *
 * Keep one entry per line in the form "pt": "translation", so that
 * test_i18n.py can check every UI string has a translation.
 */
(function () {
  "use strict";

  const SOURCE_LANGUAGE = "pt-BR";
  const STORAGE_KEY = "ulanzi.language";
  const LANGUAGES = { "pt-BR": "Português", en: "English" };

  const TRANSLATIONS = {
    en: {
      // Page header and general settings
      "CONTROLADOR LOCAL": "LOCAL CONTROLLER",
      "Verificando dispositivo": "Checking device",
      "Verificando serviço": "Checking service",
      "Salvar e aplicar": "Save and apply",
      "DISPOSITIVO": "DEVICE",
      "Ajustes gerais": "General settings",
      "Configuração carregada": "Configuration loaded",
      "Brilho": "Brightness",
      "Posição do rótulo": "Label position",
      "Superior": "Top",
      "Centro": "Center",
      "Inferior": "Bottom",
      "Tamanho do texto": "Text size",
      "Exibir rótulos": "Show labels",
      "Conexão com OBS Studio": "OBS Studio connection",
      "Servidor": "Host",
      "Porta": "Port",
      "Senha": "Password",
      "Sem senha": "No password",

      // Saved layouts
      "PREDEFINIÇÕES": "PRESETS",
      "Layouts salvos": "Saved layouts",
      "Salve versões e restaure sem perder o layout atual": "Save versions and restore them without losing the current layout",
      "Nome do layout": "Layout name",
      "Ex.: Trabalho": "e.g. Work",
      "Salvar layout": "Save layout",
      "Carregar": "Load",
      "Excluir": "Delete",
      "Escolha um layout pela imagem abaixo. Carregar abre o layout no editor; “Salvar e aplicar” envia ao D200.": "Choose a layout from the previews below. Load opens it in the editor; “Save and apply” sends it to the D200.",
      "Nenhum layout salvo. Salve o layout atual para vê-lo aqui.": "No saved layouts yet. Save the current layout to see it here.",
      "Selecionar layout {name}": "Select layout {name}",
      "Carregando imagem…": "Loading preview…",
      "Não foi possível carregar a imagem: {error}": "Could not load the preview: {error}",
      "Informe um nome para o layout": "Enter a name for the layout",
      "Salvando…": "Saving…",
      "Layout “{name}” salvo": "Layout “{name}” saved",
      "Descartar alterações não salvas e carregar este layout?": "Discard unsaved changes and load this layout?",
      "Layout “{name}” carregado; falta aplicar": "Layout “{name}” loaded; not applied yet",
      "Layout “{name}” carregado no editor": "Layout “{name}” loaded into the editor",
      "Excluir o layout “{name}”?": "Delete the layout “{name}”?",
      "Layout “{name}” excluído": "Layout “{name}” deleted",

      // Button grid and background
      "Botões": "Buttons",
      "Arraste para reorganizar ou selecione para editar": "Drag to rearrange, or select to edit",
      "Escolher imagem de fundo": "Choose background image",
      "Edite a imagem antes de dividi-la entre os botões. A tela larga é opcional.": "Adjust the image before it is split across the buttons. The wide display is optional.",
      "Fundo atual": "Current background",
      "Prévia completa": "Full preview",
      "Prévia do fundo atual": "Current background preview",
      "Editar fundo atual": "Edit current background",
      "Prévia exata dos 13 botões e da tela larga": "Exact preview of the 13 buttons and the wide display",
      "Redimensionar fundo": "Resize background",
      "25–200%. Abaixo de 100%, a imagem fica centralizada com bordas pretas; 100% preenche a tela.": "25–200%. Below 100% the image is centered with black borders; 100% fills the screen.",
      "Escurecer fundo": "Darken background",
      "Incluir tela larga no fundo": "Include the wide display in the background",
      "Aplicar fundo nos botões": "Apply background to buttons",
      "Fundos antigos são recuperados dos recortes atuais; partes já cortadas e escurecidas não podem ser restauradas. Novas imagens mantêm o original.": "Older backgrounds are rebuilt from the current tiles, so parts already cropped or darkened cannot be restored. New images keep the original.",
      "Botões do Ulanzi D200": "Ulanzi D200 buttons",
      "Tela larga preservada": "Wide display unchanged",
      "Editar ou mover botão {number}": "Edit or move button {number}",
      "Preparando prévia…": "Preparing preview…",
      "Prévia dos recortes que serão aplicados": "Preview of the tiles that will be applied",
      "Não foi possível abrir a imagem": "Could not open the image",
      "Fundo preparado; use “Salvar e aplicar” para enviá-lo ao D200": "Background prepared; use “Save and apply” to send it to the D200",

      // Button editor
      "EDIÇÃO": "EDITOR",
      "Botão {number}": "Button {number}",
      "Botão 14 · tela larga": "Button 14 · wide display",
      "Ativo": "Enabled",
      "Posição no layout": "Position in layout",
      "Posição {number}": "Position {number}",
      "Posição fixa da tela": "Fixed display position",
      "Conteúdo da tela larga": "Wide display content",
      "CPU, RAM e GPU": "CPU, RAM and GPU",
      "GIF animado": "Animated GIF",
      "Imagem de fundo": "Background image",
      "Aplique uma imagem de fundo antes de selecionar este modo": "Apply a background image before selecting this mode",
      "Visualização das métricas": "Metrics view",
      "Valores em texto": "Text values",
      "Barras · estilo htop": "Bars · htop style",
      "Linhas contínuas · último minuto": "Line graph · last minute",
      "Layout das métricas": "Metrics layout",
      "Colunas · valores sobre os rótulos": "Columns · values above labels",
      "Linhas · rótulos à esquerda": "Rows · labels on the left",
      "Compacto · rótulos sobre os valores": "Compact · labels above values",
      "font|Fonte": "Font",
      "Sem serifa": "Sans serif",
      "Monoespaçada": "Monospace",
      "Serifada": "Serif",
      "Estilo da fonte": "Font style",
      "Negrito": "Bold",
      "Itálico": "Italic",
      "Negrito itálico": "Bold italic",
      "Valor": "Value",
      "Rótulo": "Label",
      "Linha": "Line",
      "Cor do valor de CPU": "CPU value color",
      "Cor do rótulo de CPU": "CPU label color",
      "Cor da linha de CPU": "CPU line color",
      "Cor do valor de RAM": "RAM value color",
      "Cor do rótulo de RAM": "RAM label color",
      "Cor da linha de RAM": "RAM line color",
      "Cor do valor de GPU": "GPU value color",
      "Cor do rótulo de GPU": "GPU label color",
      "Cor da linha de GPU": "GPU line color",
      "Prévia com valores de exemplo. No dispositivo, atualização a cada 1,5 segundo.": "Preview with sample values. On the device it updates every 1.5 seconds.",
      "Sem ícone": "No icon",
      "Ícone": "Icon",
      "Selecione um ícone": "Select an icon",
      "Selecione um GIF": "Select a GIF",
      "Prévia do ícone": "Icon preview",
      "Enviar imagem": "Upload image",
      "Enviar GIF": "Upload GIF",
      "PNG, JPG ou WebP. Ajustado para 196 × 196.": "PNG, JPG or WebP. Resized to 196 × 196.",
      "GIF animado. Ajustado para 458 × 196, até 300 quadros e 8 MB.": "Animated GIF. Resized to 458 × 196, up to 300 frames and 8 MB.",
      "GIF preparado e adicionado": "GIF prepared and added",
      "Imagem preparada e adicionada": "Image prepared and added",
      "Tamanho do logo": "Logo size",
      "Margem do conteúdo": "Content margin",
      "Afasta o conteúdo das bordas sem alterar a imagem de fundo.": "Moves the content away from the edges without changing the background image.",
      "Usar também como botão": "Also use as a button",
      "Nome exibido no botão": "Name shown on the button",

      // Actions
      "Ação": "Action",
      "Abrir aplicativo": "Open application",
      "Executar comando": "Run command",
      "Atalho de teclado": "Keyboard shortcut",
      "Comando": "Command",
      "notify-send 'Olá'": "notify-send 'Hello'",
      "Combinação de teclas": "Key combination",
      "Operação do OBS": "OBS operation",
      "Alternar entre cenas": "Switch between two scenes",
      "Ativar uma cena": "Switch to a scene",
      "Mostrar/ocultar fonte": "Show/hide a source",
      "Iniciar/parar gravação": "Start/stop recording",
      "Iniciar/parar transmissão": "Start/stop streaming",
      "Cena A": "Scene A",
      "Cena B": "Scene B",
      "Cena": "Scene",
      "obs|Fonte": "Source",
      "Pesquisar aplicativos": "Search applications",
      "Digite o nome do aplicativo": "Type the application name",
      "Aplicativo instalado": "Installed application",
      "Executável": "Executable",
      "{name} (fora da pesquisa)": "{name} (not in search results)",
      "Selecione um aplicativo": "Select an application",
      "Informar executável manualmente": "Enter an executable manually",
      "Carregando aplicativos instalados…": "Loading installed applications…",
      "Não foi possível carregar os aplicativos: {error}. Você pode informar o executável manualmente.": "Could not load applications: {error}. You can enter the executable manually.",
      "Nenhum aplicativo instalado encontrado. Você pode informar o executável manualmente.": "No installed applications found. You can enter the executable manually.",
      "Nenhum aplicativo corresponde à pesquisa.": "No applications match the search.",
      "{shown} de {total} aplicativos": "{shown} of {total} applications",
      "Aplicativo sem ícone disponível; ícone atual mantido": "This application has no icon; the current icon was kept",
      "Não foi possível obter o ícone: {error}": "Could not get the icon: {error}",

      // Status, saving and applying
      "Alterações não salvas": "Unsaved changes",
      "D200 conectado": "D200 connected",
      "D200 desconectado": "D200 disconnected",
      "Daemon ativo": "Daemon running",
      "Daemon parado": "Daemon stopped",
      "Status indisponível": "Status unavailable",
      "Serviço indisponível": "Service unavailable",
      "Aplicando…": "Applying…",
      "Salvo e aplicado no dispositivo": "Saved and applied to the device",
      "Configuração aplicada no D200": "Configuration applied to the D200",
      "Não foi possível aplicar": "Could not apply",
      "Falha ao carregar: {error}": "Failed to load: {error}",
      "Erro HTTP {status}": "HTTP error {status}",
      "A imagem deve ter no máximo 8 MB": "The image must be 8 MB or smaller",

      // Server error messages (web.py and config.py)
      "Aplicativo não encontrado na lista de aplicativos instalados": "Application not found in the list of installed applications",
      "O nome do layout contém caracteres inválidos": "The layout name contains invalid characters",
      "Identificador de layout inválido": "Invalid layout identifier",
      "Layout não encontrado": "Layout not found",
      "Não foi possível ler o layout": "Could not read the layout",
      "Layout salvo está corrompido": "The saved layout is corrupted",
      "Configuração do layout inválida": "Invalid layout configuration",
      "Brilho inválido": "Invalid brightness",
      "O brilho deve estar entre 0 e 100": "Brightness must be between 0 and 100",
      "Estilo dos rótulos inválido": "Invalid label style",
      "Porta do OBS inválida": "Invalid OBS port",
      "A porta do OBS deve estar entre 1 e 65535": "The OBS port must be between 1 and 65535",
      "A configuração deve conter exatamente 14 botões": "The configuration must contain exactly 14 buttons",
      "Arquivo de imagem inválido": "Invalid image file",
      "A imagem preparada deve ter no máximo 8 MB": "The prepared image must be 8 MB or smaller",
      "Formato de imagem não suportado": "Unsupported image format",
      "Ajustes da imagem de fundo inválidos": "Invalid background image settings",
      "Origem da imagem de fundo inválida": "Invalid background image source",
      "O tamanho do fundo deve estar entre 25% e 200%": "Background size must be between 25% and 200%",
      "O escurecimento deve estar entre 0% e 80%": "Darkening must be between 0% and 80%",
      "A opção de incluir a tela larga deve ser verdadeira ou falsa": "The include-wide-display option must be true or false",
      "A imagem original do fundo não está disponível; envie outra imagem": "The original background image is no longer available; upload another image",
      "Escolha uma imagem original ou um novo arquivo, não ambos": "Choose an original image or a new file, not both",
      "Falha ao reiniciar o daemon": "Failed to restart the daemon",
      "Content-Type deve ser application/json": "Content-Type must be application/json",
      "Content-Length inválido": "Invalid Content-Length",
      "Corpo da requisição vazio ou muito grande": "Request body is empty or too large",
      "JSON inválido": "Invalid JSON",
      "O corpo JSON deve ser um objeto": "The JSON body must be an object",
      "O GIF não pode ultrapassar 4096 px": "The GIF cannot exceed 4096 px",
      "A imagem não pode ultrapassar 40 megapixels": "The image cannot exceed 40 megapixels",
      "O botão 14 requer um GIF animado": "Button 14 requires an animated GIF",
      "O mosaico requer uma imagem estática": "The background requires a still image",
      "Use uma imagem PNG, JPG ou WebP": "Use a PNG, JPG or WebP image",
      "Erro interno": "Internal error",
      "modo de exibição inválido": "invalid display mode",
      "imagem inválida": "invalid image",
      "selecione um GIF animado": "select an animated GIF",
      "selecione uma imagem de fundo": "select a background image",
      "selecione uma imagem PNG": "select a PNG image",
      "selecione um ícone válido": "select a valid icon",
      "fundo do mosaico inválido": "invalid background tile",
      "tamanho do logo inválido": "invalid logo size",
      "o tamanho do logo deve estar entre 25% e 100%": "logo size must be between 25% and 100%",
      "ação inválida": "invalid action",
      "parâmetros inválidos": "invalid parameters",
      "ação OBS inválida": "invalid OBS action",
      "Espaço interno deve estar entre 0 e 48 px": "Content margin must be between 0 and 48 px",
      "Estilo das métricas inválido": "Invalid metrics style",
      "Layout das métricas inválido": "Invalid metrics layout",
      "Visualização das métricas inválida": "Invalid metrics view",
      "Tamanho das métricas deve estar entre 18 e 48 px": "Metrics text size must be between 18 and 48 px",
      "Família da fonte das métricas inválida": "Invalid metrics font family",
      "Estilo da fonte das métricas inválido": "Invalid metrics font style",
      "Cores individuais das métricas inválidas": "Invalid metrics colors",
      "Cor das métricas deve estar no formato #RRGGBB": "Metrics colors must use the #RRGGBB format",
    },
  };

  // Server messages that embed values. Each pattern matches the Portuguese
  // text and returns a key in TRANSLATIONS plus its parameters.
  const MESSAGE_PATTERNS = [
    [/^O nome do layout deve ter no máximo (\d+) caracteres$/, (m) => ["O nome do layout deve ter no máximo {count} caracteres", { count: m[1] }]],
    [/^O GIF pode ter no máximo (\d+) quadros$/, (m) => ["O GIF pode ter no máximo {count} quadros", { count: m[1] }]],
    [/^preencha (.+)$/, (m) => ["preencha {field}", { field: m[1] }]],
  ];
  Object.assign(TRANSLATIONS.en, {
    "O nome do layout deve ter no máximo {count} caracteres": "The layout name must be at most {count} characters",
    "O GIF pode ter no máximo {count} quadros": "The GIF can have at most {count} frames",
    "preencha {field}": "fill in {field}",
  });

  const TRANSLATED_ATTRIBUTES = ["placeholder", "aria-label", "title", "alt"];
  const staticEntries = [];
  let language = detectLanguage();

  function detectLanguage() {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved && Object.hasOwn(LANGUAGES, saved)) return saved;
    } catch (error) {
      // Storage can be unavailable (private windows, blocked site data).
    }
    const preferred = navigator.languages && navigator.languages.length
      ? navigator.languages
      : [navigator.language || ""];
    for (const tag of preferred) {
      const lower = String(tag).toLowerCase();
      if (lower.startsWith("pt")) return "pt-BR";
      if (lower.startsWith("en")) return "en";
    }
    return "en";
  }

  function interpolate(text, params) {
    if (!params) return text;
    return text.replace(/\{(\w+)\}/g, (match, name) => (
      Object.hasOwn(params, name) ? String(params[name]) : match
    ));
  }

  function lookup(key) {
    const table = TRANSLATIONS[language];
    return table && Object.hasOwn(table, key) ? table[key] : null;
  }

  // Translate Portuguese UI text into the current language.
  function t(text, params) {
    return interpolate(lookup(text) ?? text, params);
  }

  // Translate text whose Portuguese wording is shared by different meanings.
  function tc(context, text, params) {
    return interpolate(lookup(`${context}|${text}`) ?? text, params);
  }

  // Translate an error message returned by the server.
  function message(text) {
    if (typeof text !== "string" || !text) return text;
    const button = /^Botão (\d+): (.+)$/s.exec(text);
    if (button) return `${t("Botão {number}", { number: button[1] })}: ${message(button[2])}`;
    if (lookup(text) !== null) return t(text);
    for (const [pattern, toKey] of MESSAGE_PATTERNS) {
      const match = pattern.exec(text);
      if (match) {
        const [key, params] = toKey(match);
        return t(key, params);
      }
    }
    return text;
  }

  // Remember the original Portuguese text of the static page so it can be
  // translated again whenever the language changes.
  function textEntry(node, context) {
    return {
      node,
      context,
      source: node.data.trim(),
      leading: node.data.match(/^\s*/)[0],
      trailing: node.data.match(/\s*$/)[0],
    };
  }

  function recordStaticText(root) {
    // Words such as "Fonte" (font / OBS source) carry a data-i18n-context
    // attribute in index.html and are looked up as "context|text".
    root.querySelectorAll("[data-i18n-context]").forEach((element) => {
      const textNode = [...element.childNodes].find((child) => child.nodeType === Node.TEXT_NODE && child.data.trim());
      if (textNode) staticEntries.push(textEntry(textNode, element.getAttribute("data-i18n-context")));
    });
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    for (let node = walker.currentNode; node; node = walker.nextNode()) {
      if (node.nodeType === Node.TEXT_NODE) {
        const source = node.data.trim();
        if (source && lookupAny(source)) staticEntries.push(textEntry(node, null));
      } else {
        TRANSLATED_ATTRIBUTES.forEach((attribute) => {
          const value = node.getAttribute(attribute);
          if (value && lookupAny(value)) staticEntries.push({ element: node, attribute, source: value });
        });
      }
    }
  }

  function lookupAny(source) {
    return Object.values(TRANSLATIONS).some((table) => Object.hasOwn(table, source));
  }

  function applyStaticText() {
    staticEntries.forEach((entry) => {
      if (entry.attribute) {
        entry.element.setAttribute(entry.attribute, t(entry.source));
      } else {
        const text = entry.context ? tc(entry.context, entry.source) : t(entry.source);
        entry.node.data = `${entry.leading}${text}${entry.trailing}`;
      }
    });
  }

  function setLanguage(next) {
    if (!Object.hasOwn(LANGUAGES, next) || next === language) return;
    language = next;
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch (error) {
      // The choice still applies to this page view.
    }
    document.documentElement.lang = next;
    applyStaticText();
    window.dispatchEvent(new CustomEvent("ulanzi:languagechange", { detail: { language: next } }));
  }

  function setupSelector() {
    const select = document.getElementById("languageSelect");
    if (!select) return;
    Object.entries(LANGUAGES).forEach(([code, name]) => {
      const option = document.createElement("option");
      option.value = code;
      option.textContent = name;
      option.lang = code;
      select.append(option);
    });
    select.value = language;
    select.addEventListener("change", () => setLanguage(select.value));
  }

  function init() {
    recordStaticText(document.body);
    document.documentElement.lang = language;
    setupSelector();
    if (language !== SOURCE_LANGUAGE) applyStaticText();
  }

  window.i18n = { t, tc, message, setLanguage, get language() { return language; }, languages: LANGUAGES };
  init();
}());
