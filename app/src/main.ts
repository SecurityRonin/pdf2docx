import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import * as pdfjs from "pdfjs-dist";
// Bundled worker: a CDN worker would fail offline and is blocked by the CSP.
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

type Report = { ok: boolean; out_path: string; engine: string; detail: string };

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const openBtn = $<HTMLButtonElement>("open");
const convertBtn = $<HTMLButtonElement>("convert");
const revealBtn = $<HTMLButtonElement>("reveal");
const statusEl = $<HTMLElement>("status");
const pagesEl = $<HTMLElement>("pages");
const dropzone = $<HTMLElement>("dropzone");
const engineEl = $<HTMLElement>("engine");

let currentPath: string | null = null;
let lastOut: string | null = null;

function setStatus(html: string, tone: "info" | "ok" | "err" = "info") {
  statusEl.innerHTML = html;
  statusEl.dataset.tone = tone;
}

const esc = (s: string) =>
  s.replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!,
  );

async function loadPdf(path: string) {
  currentPath = path;
  lastOut = null;
  revealBtn.hidden = true;
  setStatus(`<p class="muted">Reading ${esc(basename(path))}…</p>`);

  let data: ArrayBuffer;
  try {
    const bytes = await invoke<ArrayBuffer>("read_pdf", { path });
    data = bytes instanceof ArrayBuffer ? bytes : new Uint8Array(bytes as number[]).buffer;
  } catch (e) {
    setStatus(`<p class="err">${esc(String(e))}</p>`, "err");
    return;
  }

  try {
    const doc = await pdfjs.getDocument({ data }).promise;
    pagesEl.innerHTML = "";
    const ratio = window.devicePixelRatio || 1;
    const scale = Math.min(1.4, 760 / 612) * ratio;

    for (let n = 1; n <= doc.numPages; n++) {
      const page = await doc.getPage(n);
      const viewport = page.getViewport({ scale });
      const canvas = document.createElement("canvas");
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      canvas.style.width = `${Math.floor(viewport.width / ratio)}px`;
      pagesEl.appendChild(canvas);
      await page.render({ canvasContext: canvas.getContext("2d")!, viewport }).promise;
    }
    dropzone.hidden = true;
    pagesEl.hidden = false;
    convertBtn.disabled = false;
    setStatus(
      `<p class="muted">${doc.numPages} page${doc.numPages === 1 ? "" : "s"} loaded.</p>`,
    );
  } catch (e) {
    setStatus(`<p class="err">Cannot render this PDF: ${esc(String(e))}</p>`, "err");
  }
}

const basename = (p: string) => p.split(/[\\/]/).pop() || p;

async function chooseAndLoad() {
  const picked = await open({
    multiple: false,
    filters: [{ name: "PDF", extensions: ["pdf"] }],
  });
  if (typeof picked === "string") await loadPdf(picked);
}

async function convert() {
  if (!currentPath) return;
  convertBtn.disabled = true;
  setStatus(`<p class="muted">Converting…</p>`);

  const dst = await save({
    defaultPath: currentPath.replace(/\.pdf$/i, "") + ".docx",
    filters: [{ name: "Word document", extensions: ["docx"] }],
  });
  if (!dst) {
    convertBtn.disabled = false;
    setStatus(`<p class="muted">Cancelled.</p>`);
    return;
  }

  try {
    const r = await invoke<Report>("convert", { src: currentPath, dst });
    lastOut = r.out_path;
    revealBtn.hidden = false;
    engineEl.textContent = `engine: ${r.engine}`;
    setStatus(
      `<p class="ok">Converted.</p><p class="muted">${esc(basename(r.out_path))} · ${esc(r.detail)}</p>`,
      "ok",
    );
  } catch (e) {
    setStatus(`<p class="err">${esc(String(e))}</p>`, "err");
  } finally {
    convertBtn.disabled = false;
  }
}

openBtn.addEventListener("click", chooseAndLoad);
convertBtn.addEventListener("click", convert);
revealBtn.addEventListener("click", async () => {
  if (lastOut) await invoke("reveal", { path: lastOut });
});

// Drag and drop onto the window.
getCurrentWebview().onDragDropEvent((event) => {
  if (event.payload.type === "drop") {
    const pdf = event.payload.paths.find((p) => /\.pdf$/i.test(p));
    if (pdf) void loadPdf(pdf);
  }
});
