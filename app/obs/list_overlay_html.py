from __future__ import annotations


def render_comment_list_html() -> str:
    return """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Simple Comment Viewer List</title>
<style>
html, body {
  margin: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: transparent;
}
body {
  font-family: "Yu Gothic UI", "Meiryo", sans-serif;
}
#list-root {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 6px;
  padding: 10px;
  box-sizing: border-box;
  overflow: hidden;
  background: transparent;
  pointer-events: none;
}
.comment-row {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: start;
  column-gap: 8px;
  max-width: 100%;
  padding: 5px 8px;
  border-radius: 4px;
  background: rgba(0, 0, 0, .56);
  border: 1px solid rgba(255, 255, 255, .16);
  box-shadow: 0 2px 7px rgba(0, 0, 0, .22);
  opacity: 0;
  transform: translateY(10px);
  transition: opacity 180ms ease, transform 180ms ease;
}
.comment-row.show {
  opacity: 1;
  transform: translateY(0);
}
.comment-row.fade {
  opacity: 0;
}
.comment-name {
  min-width: 0;
  max-width: 170px;
  color: #8fd3ff;
  font-size: 20px;
  line-height: 1.25;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 1px 2px rgba(0,0,0,.95), 0 0 4px rgba(0,0,0,.85);
}
.comment-text {
  min-width: 0;
  color: #ffffff;
  font-size: 22px;
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
</style>
</head>
<body>
<div id="list-root"></div>
<script>
const root = document.getElementById("list-root");
let lastId = 0;
const maxRows = 18;
const rowLifetimeMs = 90000;

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
  const userId = String(event.user_id || "").trim();
  if (userId) return userId;
  return event.event_kind || "comment";
}

function addEvent(event) {
  const row = document.createElement("div");
  row.className = "comment-row";
  row.dataset.id = String(event.id || "");

  const name = document.createElement("div");
  name.className = "comment-name";
  if (event.event_kind && event.event_kind !== "chat" && event.event_kind !== "named_chat" && event.event_kind !== "anonymous_184_chat") {
    name.classList.add("comment-kind");
  }
  name.textContent = displayName(event);

  const text = document.createElement("div");
  text.className = "comment-text";
  text.textContent = stripNamePrefix(event);

  row.appendChild(name);
  row.appendChild(text);
  root.appendChild(row);
  requestAnimationFrame(() => row.classList.add("show"));

  while (root.children.length > maxRows) {
    root.removeChild(root.children[0]);
  }

  setTimeout(() => {
    row.classList.add("fade");
    setTimeout(() => row.remove(), 240);
  }, rowLifetimeMs);
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

poll();
</script>
</body>
</html>
"""
