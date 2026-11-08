import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { OperationProvider } from "./operation";
import "./styles.css";
import "./ui/ui.css";

createRoot(document.getElementById("root")!).render(<StrictMode><OperationProvider><App /></OperationProvider></StrictMode>);
