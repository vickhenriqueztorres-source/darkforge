import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const cache = new Map();

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
  const localRequire = (spec) => {
    if (spec.startsWith(".")) {
      const candidate = path.resolve(path.dirname(normalized), `${spec}.ts`);
      if (fs.existsSync(candidate)) return loadTsModule(candidate);
    }
    return require(spec);
  };
  const fn = new Function("exports", "require", "module", outputText);
  fn(mod.exports, localRequire, mod);
  cache.set(normalized, mod.exports);
  return mod.exports;
}

const testMod = loadTsModule(
  path.resolve(import.meta.dirname, "..", "src", "lib", "studio", "__tests__", "studio.test.ts")
);
const res = testMod.runStudioUnitTests();
console.log(`studio_ui_unit_tests: ${res.passed} suites passed`);
