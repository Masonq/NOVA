import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { setupTelegram } from "./tg.js";
import "./styles.css";
setupTelegram();
createRoot(document.getElementById("root")).render(<App />);
