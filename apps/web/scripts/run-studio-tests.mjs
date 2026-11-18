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
      jsx: ts.JsxEmit.ReactJSX,
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
    if (spec.endsWith(".css")) {
      return new Proxy({}, { get: (_, prop) => String(prop) });
    }
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
const hqLayoutMod = loadTsModule(
  path.resolve(webSrcRoot, "components", "studio", "hq", "__tests__", "layoutHQ.test.ts")
);
const hqSignTextMod = loadTsModule(
  path.resolve(webSrcRoot, "components", "studio", "hq", "__tests__", "signText.test.ts")
);
const hqCrowdPoseMod = loadTsModule(
  path.resolve(webSrcRoot, "components", "studio", "hq", "__tests__", "crowdPose.test.ts")
);
const hqCameraMathMod = loadTsModule(
  path.resolve(webSrcRoot, "components", "studio", "hq", "__tests__", "cameraMath.test.ts")
);
const hqNavMod = loadTsModule(
  path.resolve(webSrcRoot, "lib", "studio", "__tests__", "hq-navigation.test.ts")
);
const hqA11yMod = loadTsModule(
  path.resolve(webSrcRoot, "components", "studio", "hq", "__tests__", "hq-a11y.test.ts")
);
const res = testMod.runStudioUnitTests();
const hqRes = hqStatusMod.runHqStatusTests();
const hqHookRes = hqHookMod.runHqOverviewHookTests();
const hqLayoutRes = hqLayoutMod.runLayoutHQTests();
const hqSignTextRes = hqSignTextMod.runSignTextTests();
const hqCrowdPoseRes = hqCrowdPoseMod.runCrowdPoseTests();
const hqCameraMathRes = hqCameraMathMod.runCameraMathTests();
const hqNavRes = hqNavMod.runHqNavigationTests();
const hqA11yRes = hqA11yMod.runHqA11yTests();
console.log(`studio_ui_unit_tests: ${res.passed} suites passed`);
console.log(`hq_status_unit_tests: ${hqRes} suites passed`);
console.log(`hq_overview_hook_tests: ${hqHookRes} suites passed`);
console.log(`hq_layout_unit_tests: ${hqLayoutRes} suites passed`);
console.log(`hq_signtext_unit_tests: ${hqSignTextRes} suites passed`);
console.log(`hq_crowdpose_unit_tests: ${hqCrowdPoseRes} suites passed`);
console.log(`hq_cameramath_unit_tests: ${hqCameraMathRes} suites passed`);
console.log(`hq_navigation_unit_tests: ${hqNavRes} suites passed`);
console.log(`hq_a11y_unit_tests: ${hqA11yRes} suites passed`);
