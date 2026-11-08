import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Gallery } from "./Gallery";
import "../styles.css";
import "./ui.css";

/* 开发用样板页入口：npm run dev 后打开 http://127.0.0.1:5174/ui-gallery.html */
createRoot(document.getElementById("root")!).render(<StrictMode><Gallery /></StrictMode>);
