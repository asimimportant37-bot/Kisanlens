// Run with BOTH servers up: python serve.py 5056 /nonexistent  (no model)  and  python serve.py 5055 <dir with a trained model>.
// Run: npm i jsdom@24 tough-cookie@4 && node ui_smoke.mjs. Note: it expects the 3-class SMOKE model metrics (28.6%); edit those two lines for your model.
// jsdom has no canvas/layout/navigation, so the "Not implemented" console noise for charts and redirects is expected.
import { JSDOM } from "jsdom";
import { CookieJar } from "tough-cookie";
import fs from "fs";

const jar = new CookieJar();
let fails = 0;
const ok = (cond, msg) => { console.log((cond ? "PASS " : "FAIL ") + msg); if (!cond) fails++; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const waitFor = async (fn, ms = 6000) => { const t = Date.now(); while (Date.now() - t < ms) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(50); } return null; };

async function open(base, path, { session } = {}) {
  const errors = [];
  const dom = await JSDOM.fromURL(base + path, {
    runScripts: "dangerously", resources: "usable", pretendToBeVisual: true, cookieJar: jar,
    beforeParse(w) {
      w.URL.createObjectURL = () => "blob:test"; w.URL.revokeObjectURL = () => {};
      w.confirm = () => true;
      if (session) w.sessionStorage.setItem("kisanlens:lastResult", session);
      w.addEventListener("error", (e) => errors.push(e.message));
      w.fetch = async (url, opts = {}) => {
        const abs = new URL(url, base).href;
        const headers = { ...(opts.headers || {}), Cookie: await jar.getCookieString(abs) };
        let body = opts.body;
        if (body && body.constructor && body.constructor.name === "FormData") {
          const fd = new FormData();
          for (const [k, v] of body.entries()) {
            if (typeof v === "string") fd.append(k, v);
            else { const buf = await new Promise((res) => { const fr = new w.FileReader(); fr.onload = () => res(Buffer.from(fr.result)); fr.readAsArrayBuffer(v); });
                   fd.append(k, new Blob([buf], { type: v.type }), v.name); }
          }
          body = fd;
        }
        const r = await fetch(abs, { ...opts, headers, body });
        for (const c of r.headers.getSetCookie()) await jar.setCookie(c, abs);
        return r;
      };
    },
  });
  dom.errors = errors;
  await waitFor(() => dom.window.document.documentElement.lang);
  await sleep(300);
  return dom;
}
const $ = (d, s) => d.window.document.querySelector(s);
const $$ = (d, s) => Array.from(d.window.document.querySelectorAll(s));
const txt = (d, s) => ($(d, s) ? $(d, s).textContent.trim() : null);

async function upload(dom, file, crop) {
  const w = dom.window;
  if (crop) w.document.querySelector(`input[name=crop][value=${crop}]`).checked = true;
  const buf = fs.readFileSync(file.path);
  const f = new w.File([buf], file.name, { type: file.type });
  const input = w.document.querySelector("#file-input");
  Object.defineProperty(input, "files", { value: [f], configurable: true });
  input.dispatchEvent(new w.Event("change"));
  await sleep(100);
}
const setLang = async (dom, l) => { const s = $(dom, "#lang-select"); s.value = l; s.dispatchEvent(new dom.window.Event("change")); await sleep(150); };

// ---------------------------------------------------------------- no-model server
{
  const B = "http://127.0.0.1:5056";
  const home = await open(B, "/");
  ok(txt(home, "h1") === "Healthy Crops. Smarter Farming.", "home: hero heading");
  ok($$(home, ".nav a").length === 5, "home: 5 nav links");
  ok(home.window.document.querySelectorAll(".grid-4 .card").length === 4, "home: 4 feature cards");
  await setLang(home, "hi");
  ok(/स्वस्थ फसल/.test(txt(home, "h1")), "home: switches to Hindi -> " + txt(home, "h1"));
  ok(home.window.document.documentElement.lang === "hi", "home: <html lang> updated");
  ok(home.errors.length === 0, "home: no JS errors " + home.errors.join("|"));

  const d = await open(B, "/detect");
  ok(!$(d, "#model-banner").hidden, "detect(no model): banner visible -> " + txt(d, "#model-banner").slice(0, 60));
  ok($(d, "#analyze-btn").disabled, "detect: analyze disabled before file");
  await upload(d, { path: "./notes.txt", name: "notes.txt", type: "text/plain" });
  ok(!$(d, "#form-error").hidden && /not supported/.test(txt(d, "#form-error")), "detect: rejects text file client-side -> " + txt(d, "#form-error"));
  await upload(d, { path: "./leaf.jpg", name: "leaf.jpg", type: "image/jpeg" });
  ok($(d, "#preview").classList.contains("is-visible") && !$(d, "#analyze-btn").disabled, "detect: preview shown, analyze enabled");
  $(d, "#detect-form").dispatchEvent(new d.window.Event("submit", { cancelable: true }));
  await waitFor(() => !$(d, "#form-error").hidden);
  ok(/not installed/.test(txt(d, "#form-error")), "detect(no model): clear error -> " + txt(d, "#form-error").slice(0, 70));
  ok(!d.window.sessionStorage.getItem("kisanlens:lastResult"), "detect(no model): NO result stored");
  await setLang(d, "hi");
  $(d, "#detect-form").dispatchEvent(new d.window.Event("submit", { cancelable: true }));
  await waitFor(() => /इंस्टॉल/.test(txt(d, "#form-error")));
  ok(/इंस्टॉल/.test(txt(d, "#form-error")), "detect(no model): error shown in Hindi");
  ok(d.errors.length === 0, "detect: no JS errors " + d.errors.join("|"));

  const lib = await open(B, "/diseases");
  await waitFor(() => $$(lib, ".disease-card").length);
  ok($$(lib, ".disease-card").length === 13, "library(no model): 13 documented classes -> " + $$(lib, ".disease-card").length);
  ok(!$(lib, "#lib-source").hidden, "library(no model): says model not installed -> " + txt(lib, "#lib-source").slice(0, 50));
  const s = $(lib, "#lib-search"); s.value = "blight"; s.dispatchEvent(new lib.window.Event("input")); await sleep(100);
  ok($$(lib, ".disease-card").length === 5, "library: search 'blight' -> 5 cards (got " + $$(lib, ".disease-card").length + ")");
  $$(lib, ".chip")[2].click(); await sleep(100);
  ok($$(lib, ".disease-card").length === 2, "library: potato + blight -> 2 cards");
  ok(lib.window.document.querySelectorAll(".disease-card svg").length === 2, "library: leaf illustrations render");
  ok($$(lib, "#lib-refs li a").length >= 4, "library: reference links listed");
  ok(lib.errors.length === 0, "library: no JS errors");

  const ab = await open(B, "/about");
  await waitFor(() => /No trained model/.test(txt(ab, "#metrics-body")));
  ok(/No trained model/.test(txt(ab, "#metrics-body")), "about(no model): shows no fabricated metrics");

  const rs = await open(B, "/results");
  ok(!$(rs, "#results-empty").hidden && $(rs, "#results-content").hidden, "results: empty state when nothing scanned");
}

// ---------------------------------------------------------------- server with smoke model
{
  const B = "http://127.0.0.1:5055";
  const d = await open(B, "/detect");
  ok($(d, "#model-banner").hidden, "detect(model): no banner");
  await upload(d, { path: "./leaf.jpg", name: "leaf.jpg", type: "image/jpeg" }, "potato");
  d.window.document.querySelector("#detect-form").dispatchEvent(new d.window.Event("submit", { cancelable: true }));
  const stored = await waitFor(() => d.window.sessionStorage.getItem("kisanlens:lastResult"), 20000);
  ok(!!stored, "detect(model): result stored after submit");
  const result = JSON.parse(stored);
  ok(result.top3.length === 3 && result.image_url.startsWith("/api/image/"), "detect(model): result has top3 + private image url");

  const rs = await open(B, "/results", { session: stored });
  ok(!$(rs, "#results-content").hidden, "results: content visible");
  ok(txt(rs, "#res-name").length > 3, "results: prediction name -> " + txt(rs, "#res-name"));
  ok(/%$/.test(txt(rs, "#res-conf")), "results: confidence -> " + txt(rs, "#res-conf"));
  ok($$(rs, "#res-top3 li").length === 3, "results: 3 top predictions");
  ok($$(rs, "#res-symptoms li").length >= 2 && $$(rs, "#res-prevention li").length >= 2 && $$(rs, "#res-management li").length >= 1, "results: symptoms/prevention/management filled");
  ok($$(rs, "#results-warnings .alert").length === 1, "results: uncertainty warning displayed -> " + txt(rs, "#results-warnings").slice(0, 80));
  ok(!!$(rs, "#res-expert"), "results: expert-consult section present");
  ok(rs.window.document.querySelector("#res-img").getAttribute("src") === result.image_url, "results: image src set");
  await setLang(rs, "hi");
  ok(/आम लक्षण|प्रभावित|मॉडल/.test(rs.window.document.body.textContent) && /[ऀ-ॿ]/.test(txt(rs, "#res-name")), "results: re-renders in Hindi -> " + txt(rs, "#res-name"));
  $(rs, "#save-btn").click();
  await waitFor(() => !$(rs, "#res-action-msg").hidden);
  ok($(rs, "#res-action-msg").classList.contains("alert-ok"), "results: saved -> " + txt(rs, "#res-action-msg"));
  ok(rs.errors.length === 0, "results: no JS errors " + rs.errors.join("|"));

  const hist = await open(B, "/history");
  await waitFor(() => $$(hist, ".scan-card").length);
  ok($$(hist, ".scan-card").length === 1, "history: 1 saved scan listed");
  ok(/%/.test(txt(hist, ".scan-meta")), "history: confidence shown -> " + txt(hist, ".scan-meta"));
  const hs = $(hist, "#hist-search"); hs.value = "zzz"; hs.dispatchEvent(new hist.window.Event("input")); await sleep(100);
  ok($$(hist, ".scan-card").length === 0, "history: search filters out non-matching");
  hs.value = ""; hs.dispatchEvent(new hist.window.Event("input")); await sleep(100);
  ok($$(hist, ".scan-card").length === 1, "history: search cleared restores card");
  $(hist, ".scan-card .btn-danger").click();
  await waitFor(() => $$(hist, ".scan-card").length === 0);
  ok($$(hist, ".scan-card").length === 0 && !$(hist, "#hist-empty").hidden, "history: delete works -> empty state");
  ok(hist.errors.length === 0, "history: no JS errors " + hist.errors.join("|"));

  const lib = await open(B, "/diseases");
  await waitFor(() => $$(lib, ".disease-card").length);
  ok($$(lib, ".disease-card").length === 3, "library(model): lists exactly the model's 3 classes");

  const ab = await open(B, "/about");
  await waitFor(() => /Test accuracy/.test(txt(ab, "#metrics-body")));
  ok(/Test accuracy: 28\.6%/.test(txt(ab, "#metrics-body")), "about(model): shows MEASURED accuracy from metrics.json -> " + txt(ab, "#metrics-body").slice(0, 40));
}
console.log(fails ? `\n${fails} FAILED` : "\nALL UI CHECKS PASSED");
process.exit(fails ? 1 : 0);
