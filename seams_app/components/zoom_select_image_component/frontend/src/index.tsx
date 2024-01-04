import React from "react"
import { createRoot } from 'react-dom/client';
import ZoomSelectImageComponent from "./ZoomSelectImageComponent"


const root = createRoot(document.getElementById("root")!);
root.render(
  <React.StrictMode>
    <ZoomSelectImageComponent />
  </React.StrictMode>
);
