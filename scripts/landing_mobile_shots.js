/* Mobile screenshots for the landing carousel (landing/img/mc-<screen>-<lang>-<theme>.webp), taken from the
   live demo at 390x844 @2x. Needs playwright-core + Chromium and ffmpeg; serve landing/ first, e.g.
   PW=/path/to/playwright-core CHROME=/path/to/chrome node scripts/landing_mobile_shots.js http://localhost:8765 */
const { chromium } = require(process.env.PW || "playwright-core");
const { execFileSync } = require("child_process");
const fs = require("fs"), os = require("os"), path = require("path");
const base = (process.argv[2] || "http://localhost:8765").replace(/\/$/, "");
const out = path.join(__dirname, "..", "landing", "img"), tmp = fs.mkdtempSync(path.join(os.tmpdir(), "mc-"));
(async () => {
  const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
  for (const lang of ["es", "en"]) for (const theme of ["light", "dark"]) {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, colorScheme: theme });
    const p = await ctx.newPage();
    const go = async h => { await p.goto("about:blank"); await p.goto(`${base}/demo/${lang === "en" ? "?lang=en" : ""}${h}`); await p.waitForLoadState("networkidle"); await p.waitForTimeout(700); };
    const shot = async n => {
      await p.waitForTimeout(400); const f = path.join(tmp, `${n}.png`); await p.screenshot({ path: f });
      execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-i", f, "-vf", "scale=450:-1", "-c:v", "libwebp", "-quality", "78", path.join(out, `mc-${n}-${lang}-${theme}.webp`)]);
    };
    await go("#/recetas"); await shot("lista");
    await go("#/receta/10"); await shot("detalle");
    await p.evaluate(() => { const h = [...document.querySelectorAll("h2,h3")].find(x => /Ingredient/.test(x.textContent)); if (h) scrollTo(0, h.getBoundingClientRect().top + scrollY - 70); }); await shot("ingredientes");
    await p.evaluate(() => scrollTo(0, 0)); await p.click("#cookBtn"); await p.waitForTimeout(800); await shot("cocina");
    for (const [h, n] of [["#/planificador", "planificador"], ["#/compra", "compra"], ["#/importar", "importar"], ["#/ajustes", "ajustes"]]) { await go(h); await shot(n); }
    await ctx.close();
  }
  await b.close();
})();
