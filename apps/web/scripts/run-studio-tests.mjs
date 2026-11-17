import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const cache = new Map();

const webSrcRoot = path.resolve(import.meta.dirname, "..", "src");

function loadTsModule(filePath) {
  const normalized = path.resolve(filePath);
  if (cache.has(normalized)) return cache.get(normalized);
  const source = fs.readFileSync(normalized, "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
  });
  const mod = { exports: {} };
  cache.set(normalized, mod.exports);
  const resolveCandidate = (base) => {
    for (const ext of [".ts", ".tsx", "/index.ts", "/index.tsx"]) {
      const candidate = `${base}${ext}`;
      if (fs.existsSync(candidate)) return loadTsModule(candidate);
    }
    return null;
  };
  const localRequire = (spec) => {
    if (spec.startsWith(".")) {
      const loaded = resolveCandidate(path.resolve(path.dirname(normalized), spec));
      if (loaded) return loaded;
    }
    if (spec.startsWith("@/")) {
      const loaded = resolveCandidate(path.resolve(webSrcRoot, spec.slice(2)));
      if (loaded) return loaded;
    }
    return require(spec);
  };
  const fn = new Function("exports", "require", "module", outputText);
  fn(mod.exports, localRequire, mod);
  cache.set(normalized, mod.exports);
  return mod.exports;
}

const testMod = loadTsModule(
  path.resolve(webSrcRoot, "lib", "studio", "__tests__", "studio.test.ts")
);
const hqStatusMod = loadTsModule(
  path.resolve(webSrcRoot, "lib", "studio", "__tests__", "hq-status.test.ts")
);
const hqHookMod = loadTsModule(
  path.resolve(webSrcRoot, "lib", "studio", "__tests__", "hq-overview-hook.test.ts")
);
const res = testMod.runStudioUnitTests();
const hqRes = hqStatusMod.runHqStatusTests();
const hqHookRes = hqHookMod.runHqOverviewHookTests();
console.log(`studio_ui_unit_tests: ${res.passed} suites passed`);
console.log(`hq_status_unit_tests: ${hqRes} suites passed`);
console.log(`hq_overview_hook_tests: ${hqHookRes} suites passed`);
