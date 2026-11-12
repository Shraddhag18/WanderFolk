import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, type Config } from "./api";
import TripPage from "./Trip";
import { ToastHost } from "./ui";
import "./styles.css";

// The open trip lives in the address bar as ?trip=<id>, the same invite links the first version used.
const currentTrip = () => new URLSearchParams(location.search).get("trip") ?? "";

function App() {
  const [tripId, setTripId] = useState(currentTrip);
  const [config, setConfig] = useState<Config | null>(null);

  useEffect(() => {
    const onPop = () => setTripId(currentTrip());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    api<Config>("/config").then(setConfig).catch(() => setConfig(null));
  }, []);

  if (!tripId) {
    location.replace("/");
    return null;
  }
  return <TripPage key={tripId} tripId={tripId} config={config} />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ToastHost>
      <App />
    </ToastHost>
  </StrictMode>,
);

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
