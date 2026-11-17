export interface SignTextFit {
  text: string;
  fontSize: number;
  truncated: boolean;
}

const MAX_FONT_SIZE = 0.26;
const MIN_FONT_SIZE = 0.17;
const NARROW_CHARS = new Set(["i", "l", "I", "1", ".", ",", ":", ";", "!", "|", "'", "`", "í", "ì", "î", "ï"]);
const WIDE_CHARS = new Set(["W", "M", "w", "m", "O", "Q", "G", "D", "H", "N", "U", "—", "–"]);

function charWidthUnits(ch: string): number {
  if (ch === " ") return 0.3;
  if (NARROW_CHARS.has(ch)) return 0.32;
  if (WIDE_CHARS.has(ch)) return 0.78;
  const cp = ch.codePointAt(0) ?? 0;
  if (cp > 0x1f00) return 0.95; // emoji / CJK / symbol
  if (ch >= "A" && ch <= "Z") return 0.68;
  return 0.56;
}

function measureUnits(chars: string[]): number {
  let sum = 0;
  for (const ch of chars) sum += charWidthUnits(ch);
  return sum;
}

/**
 * Fits a channel display name onto a 1-line 3D sign between fontSize 0.26 and 0.17,
 * falling back to ellipsis truncation only when even 0.17 exceeds maxWidth.
 */
export function fitSignText(name: string, maxWidth = 2.25): SignTextFit {
  const clean = name.trim().replace(/\s+/g, " ") || "Canal";
  const chars = Array.from(clean);
  const units = measureUnits(chars);
  const safeMax = Math.max(0.4, maxWidth);

  if (units * MAX_FONT_SIZE <= safeMax) {
    return { text: clean, fontSize: MAX_FONT_SIZE, truncated: false };
  }

  const scaled = safeMax / Math.max(units, 1e-4);
  if (scaled >= MIN_FONT_SIZE) {
    return {
      text: clean,
      fontSize: Math.round(scaled * 1000) / 1000,
      truncated: false,
    };
  }

  const maxUnitsAtMin = safeMax / MIN_FONT_SIZE;
  const ellipsisUnits = 0.75;
  const budget = Math.max(0.5, maxUnitsAtMin - ellipsisUnits);

  let used = 0;
  const kept: string[] = [];
  for (const ch of chars) {
    const w = charWidthUnits(ch);
    if (used + w > budget) break;
    kept.push(ch);
    used += w;
  }
  const prefix = kept.join("").trimEnd() || chars[0] || "C";
  return {
    text: `${prefix}…`,
    fontSize: MIN_FONT_SIZE,
    truncated: true,
  };
}

export function channelInitials(name: string): string {
  const words = name
    .trim()
    .split(/\s+/)
    .map((w) => Array.from(w).filter((ch) => /[\p{L}\p{N}]/u.test(ch)).join(""))
    .filter(Boolean);
  if (words.length === 0) return "DF";
  if (words.length === 1) {
    return Array.from(words[0]).slice(0, 2).join("").toUpperCase();
  }
  const first = Array.from(words[0])[0] ?? "";
  const second = Array.from(words[1])[0] ?? "";
  return `${first}${second}`.toUpperCase();
}

export function desaturateHex(hex: string, saturationFactor = 0.4): string {
  const clean = hex.replace("#", "");
  if (clean.length !== 6) return hex;
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) return hex;
  const luma = 0.299 * r + 0.587 * g + 0.114 * b;
  const mix = (c: number) => Math.max(0, Math.min(255, Math.round(luma + (c - luma) * saturationFactor)));
  const toHex = (n: number) => n.toString(16).padStart(2, "0");
  return `#${toHex(mix(r))}${toHex(mix(g))}${toHex(mix(b))}`;
}
