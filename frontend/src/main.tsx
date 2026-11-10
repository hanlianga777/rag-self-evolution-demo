import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { OperationProvider } from "./operation";
import "./styles.css";
import "./ui/ui.css";
import "./ui/extra.css";
import "./typography.css";
import "./pages/task024a-polish.css";

createRoot(document.getElementById("root")!).render(<StrictMode><OperationProvider><App /></OperationProvider></StrictMode>);
