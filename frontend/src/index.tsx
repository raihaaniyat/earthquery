import "./index.css";
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";

// Apply the saved theme before first paint to avoid a white flash in dark mode.
(function applyInitialTheme() {
  let theme = "dark";
  try {
    if (localStorage.getItem("satquery-theme") === "light") theme = "light";
  } catch {
    theme = "dark";
  }
  document.documentElement.setAttribute("data-theme", theme);
})();

const rootEl = document.getElementById("root");
if (rootEl) {
  ReactDOM.createRoot(rootEl).render(<App />);
}