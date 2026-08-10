import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import App from "./App.jsx";
import { clearValidationSession } from "./services/validationApi";

/** Browser refresh clears the flow and returns to the first page. */
function resetFlowOnBrowserRefresh() {
  const navigation = performance.getEntriesByType("navigation")[0];
  const isReload =
    navigation?.type === "reload" ||
    // Legacy fallback
    (typeof performance.navigation !== "undefined" &&
      performance.navigation.type === 1);

  if (!isReload) return;

  clearValidationSession();

  if (window.location.pathname !== "/") {
    window.location.replace("/");
  }
}

resetFlowOnBrowserRefresh();

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
