import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { setupTelegram, inTelegram } from "./tg.js";
import "./styles.css";
setupTelegram();
createRoot(document.getElementById("root")).render(<App />);

// Installable app outside Telegram: offline screen + fast repeat visits. Pages always come fresh from the network.
if ("serviceWorker" in navigator && !inTelegram && location.protocol === "https:") {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
// Android/desktop Chrome offer installation: keep the event for the "Install" button in the profile.
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); window.__installPrompt = e; window.dispatchEvent(new Event("nova:installable")); });
