import assert from "node:assert/strict";
import { channelInitials, desaturateHex, fitSignText } from "../signText";

export function runSignTextTests(): number {
  let passed = 0;

  // 1. Short name keeps max fontSize without truncation
  const shortFit = fitSignText("O Outro Lado", 2.25);
  assert.equal(shortFit.text, "O Outro Lado");
  assert.equal(shortFit.fontSize, 0.26);
  assert.equal(shortFit.truncated, false);
  passed++;

  // 2. Medium name scales between 0.17 and 0.26 without truncation
  const medFit = fitSignText("Crônicas da Noite Oculta", 2.25);
  assert.ok(medFit.fontSize >= 0.17 && medFit.fontSize <= 0.26);
  assert.equal(medFit.truncated, false);
  passed++;

  // 3. Very long name truncates with ellipsis at min fontSize 0.17
  const longName = "Viajante Zero 🚀 — Expedições Extremas & Relatos Reais do Fim do Mundo";
  const longFit = fitSignText(longName, 2.25);
  assert.equal(longFit.fontSize, 0.17);
  assert.equal(longFit.truncated, true);
  assert.ok(longFit.text.endsWith("…"));
  assert.ok(longFit.text.length < longName.length);
  passed++;

  // 4. Accented and emoji strings keep valid UTF-16 codepoints (no broken surrogate pairs)
  const emojiFit = fitSignText("Canal Épico 🚀✨🔥 Aventura Sem Fim 1234567890", 2.0);
  assert.equal(emojiFit.truncated, true);
  assert.equal(Array.from(emojiFit.text).some((c) => c === "\uFFFD"), false);
  assert.ok(channelInitials("Sonar 0300") === "S0");
  assert.ok(channelInitials("Éden") === "ÉD");
  assert.equal(desaturateHex("#ff0000", 0), "#4c4c4c");
  passed++;

  return passed;
}
