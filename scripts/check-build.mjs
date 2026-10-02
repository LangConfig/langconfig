import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

// Follow static imports in Vite's manifest, including indirect imports. Route
// chunks may use these vendors dynamically, but the entry must stay lightweight.
const manifest = JSON.parse(await readFile(new URL("../dist/.vite/manifest.json", import.meta.url), "utf8"));
const entries = Object.keys(manifest).filter((key) => manifest[key].isEntry);
assert(entries.length > 0, "Build manifest has no application entry");
const visited = new Set();
function checkStaticImports(key) {
  if (visited.has(key)) return;
  visited.add(key);
  const chunk = manifest[key];
  assert(chunk, `Missing manifest entry: ${key}`);
  assert(!/vendor-(3d|export)-/.test(chunk.file), `Lazy vendor loaded by app entry: ${chunk.file}`);
  for (const dependency of chunk.imports ?? []) checkStaticImports(dependency);
}
entries.forEach(checkStaticImports);
console.log("Build check passed: 3D and export vendors remain lazy.");
