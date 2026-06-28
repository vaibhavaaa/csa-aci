// Resolve the live-events WebSocket against the CURRENT origin so it works
// everywhere the HTTP API does:
//   • `vite dev`  → ws://localhost:5174/ws/live → Vite proxy (vite.config.js) → backend
//   • production  → ws://localhost/ws/live      → nginx (infra/nginx.conf)    → backend
// An explicit VITE_WS_URL still overrides if you need a cross-origin backend.
function defaultWsUrl() {
  if (typeof window === "undefined") return "ws://localhost/ws/live";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/live`;
}

const WS_URL = import.meta.env.VITE_WS_URL || defaultWsUrl();

export function createSocket() {
  return new WebSocket(WS_URL);
}
