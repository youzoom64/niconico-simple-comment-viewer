from __future__ import annotations

from app.obs.google_fonts import render_google_fonts_head_links


def render_comment_list_html() -> str:
    return """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Simple Comment Viewer List</title>
__GOOGLE_FONTS_HEAD__
<style>
:root {
  --page-background: rgba(0, 0, 0, 1);
  --background-opacity: 1;
  --row-background: rgba(0, 0, 0, 0);
  --row-gap: 0px;
  --row-min-height: 0px;
  --icon-size: 36px;
  --icon-column: 36px;
  --icon-display: block;
  --name-width: 170px;
  --list-font-family: "Yu Gothic UI";
  --name-font-size: 20px;
  --text-font-size: 22px;
  --name-color: #8fd3ff;
  --text-color: #ffffff;
}
html, body {
  margin: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: var(--page-background);
}
body {
  font-family: "Yu Gothic UI", "Meiryo", sans-serif;
}
#background {
  position: fixed;
  inset: 0;
  background-position: center;
  background-size: cover;
  background-repeat: no-repeat;
  background-color: var(--page-background);
  opacity: var(--background-opacity);
  display: block;
}
#list-root {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: var(--row-gap);
  padding: 0;
  box-sizing: border-box;
  overflow: hidden;
  background: var(--page-background);
  pointer-events: none;
}
.comment-row {
  display: grid;
  grid-template-columns: var(--icon-column) var(--name-width) 1fr;
  align-items: start;
  column-gap: 8px;
  max-width: 100%;
  padding: 4px 8px;
  min-height: var(--row-min-height);
  border-radius: 0;
  background: var(--row-background);
  border: 0;
  box-shadow: none;
  opacity: 0;
  transform: none;
  transition: opacity 120ms ease;
}
.comment-row.show {
  opacity: 1;
  transform: none;
}
.comment-row.fade {
  opacity: 0;
}
.comment-name {
  min-width: 0;
  width: var(--name-width);
  color: var(--name-color);
  font-family: var(--list-font-family);
  font-size: var(--name-font-size);
  line-height: 1.25;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 1px 2px rgba(0,0,0,.95), 0 0 4px rgba(0,0,0,.85);
}
.comment-text {
  min-width: 0;
  color: var(--text-color);
  font-family: var(--list-font-family);
  font-size: var(--text-font-size);
  line-height: 1.28;
  font-weight: 700;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-shadow: 0 1px 2px rgba(0,0,0,.95), 0 0 4px rgba(0,0,0,.85);
}
.comment-kind {
  color: #ffd978;
}
.comment-icon {
  width: var(--icon-size);
  height: var(--icon-size);
  border-radius: 4px;
  object-fit: cover;
  display: var(--icon-display);
}
</style>
</head>
<body>
<div id="background"></div>
<div id="list-root"></div>
<script>
const doc = document.documentElement;
const background = document.getElementById("background");
const root = document.getElementById("list-root");
let lastId = 0;
let currentSettings = {};

function clampNumber(value, fallback, min, max) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.max(min, Math.min(max, number));
}

function hexToRgb(hex) {
  const normalized = String(hex || "").trim().replace(/^#/, "");
  if (!/^[0-9a-fA-F]{6}$/.test(normalized)) return [0, 0, 0];
  return [
    parseInt(normalized.slice(0, 2), 16),
    parseInt(normalized.slice(2, 4), 16),
    parseInt(normalized.slice(4, 6), 16)
  ];
}

function applySettings(settings) {
  currentSettings = settings || {};
  const showIcons = Boolean(currentSettings.show_icons);
  const iconSize = clampNumber(currentSettings.icon_size, 36, 12, 128);
  const nameWidth = clampNumber(currentSettings.name_width, 170, 40, 600);
  const rowGap = clampNumber(currentSettings.row_gap, 0, 0, 80);
  const rowOpacity = clampNumber(currentSettings.row_background_opacity, 0.56, 0, 1);
  const backgroundOpacity = clampNumber(currentSettings.background_opacity, 0.75, 0, 1);
  const [r, g, b] = hexToRgb(currentSettings.row_background_color || "#000000");

  doc.style.setProperty("--icon-size", `${iconSize}px`);
  doc.style.setProperty("--icon-column", showIcons ? `${iconSize}px` : "0px");
  doc.style.setProperty("--icon-display", showIcons ? "block" : "none");
  doc.style.setProperty("--row-min-height", showIcons ? `${iconSize}px` : "0px");
  doc.style.setProperty("--name-width", `${nameWidth}px`);
  doc.style.setProperty("--list-font-family", currentSettings.font_family || "Yu Gothic UI");
  doc.style.setProperty("--name-font-size", `${clampNumber(currentSettings.name_font_size, 20, 8, 96)}px`);
  doc.style.setProperty("--text-font-size", `${clampNumber(currentSettings.text_font_size, 22, 8, 96)}px`);
  doc.style.setProperty("--name-color", currentSettings.name_color || "#8fd3ff");
  doc.style.setProperty("--text-color", currentSettings.text_color || "#ffffff");
  doc.style.setProperty("--row-background", `rgba(${r}, ${g}, ${b}, ${rowOpacity})`);
  doc.style.setProperty("--page-background", `rgba(${r}, ${g}, ${b}, ${rowOpacity})`);
  doc.style.setProperty("--row-gap", `${rowGap}px`);
  doc.style.setProperty("--background-opacity", String(backgroundOpacity));

  if (currentSettings.background_url) {
    background.style.backgroundImage = `url("${String(currentSettings.background_url).replaceAll('"', "%22")}")`;
  } else {
    background.style.backgroundImage = "";
  }
}

function stripNamePrefix(event) {
  const name = (event.display_name || "").trim();
  const text = String(event.text || "");
  if (name && text.startsWith(`${name}:`)) {
    return text.slice(name.length + 1);
  }
  return text;
}

function displayName(event) {
  const name = (event.display_name || "").trim();
  if (name) return name;
  return "";
}

function addEvent(event) {
  const row = document.createElement("div");
  row.className = "comment-row";
  row.dataset.id = String(event.id || "");

  const name = document.createElement("div");
  name.className = "comment-name";
  if (
    event.event_kind &&
    event.event_kind !== "chat" &&
    event.event_kind !== "named_chat" &&
    event.event_kind !== "registered_user_chat" &&
    event.event_kind !== "anonymous_184_chat"
  ) {
    name.classList.add("comment-kind");
  }
  name.textContent = displayName(event);

  const icon = document.createElement("img");
  icon.className = "comment-icon";
  icon.alt = "";
  if (event.icon_url) {
    icon.src = event.icon_url;
  }

  const text = document.createElement("div");
  text.className = "comment-text";
  text.textContent = stripNamePrefix(event);

  row.appendChild(icon);
  row.appendChild(name);
  row.appendChild(text);
  root.appendChild(row);
  requestAnimationFrame(() => row.classList.add("show"));
}

async function refreshSettings() {
  try {
    const response = await fetch("/list-settings", {cache: "no-store"});
    applySettings(await response.json());
  } catch (_error) {
    applySettings({});
  }
}

async function poll() {
  while (true) {
    try {
      const response = await fetch(`/events?after=${lastId}&timeout=25`, {cache: "no-store"});
      const payload = await response.json();
      for (const event of payload.events || []) {
        lastId = Math.max(lastId, Number(event.id || 0));
        addEvent(event);
      }
    } catch (_error) {
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
}

refreshSettings();
setInterval(refreshSettings, 1000);
poll();
</script>
</body>
</html>
""".replace("__GOOGLE_FONTS_HEAD__", render_google_fonts_head_links())
