const compact = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
const full = new Intl.NumberFormat("pt-BR");

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value >= 10_000 ? compact.format(value) : full.format(value);
}

export function formatFullCount(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return full.format(value);
}

export function formatDuration(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined) return null;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const ss = s.toString().padStart(2, "0");
  return h > 0 ? `${h}:${m.toString().padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

export function formatAgeDays(days: number | null | undefined): string {
  if (days === null || days === undefined) return "data desconhecida";
  if (days < 1 / 24) return "agora";
  if (days < 1) return `há ${Math.max(1, Math.round(days * 24))} h`;
  if (days < 30) return `há ${Math.round(days)} d`;
  if (days < 365) return `há ${Math.round(days / 30)} meses`;
  const years = Math.round(days / 365);
  return `há ${years} ${years === 1 ? "ano" : "anos"}`;
}

export function formatRelativeIso(iso: string | null | undefined): string {
  if (!iso) return "nunca";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return "data desconhecida";
  const mins = Math.max(0, Math.round((Date.now() - dt.getTime()) / 60000));
  if (mins < 1) return "agora mesmo";
  if (mins < 60) return `há ${mins} min`;
  return formatAgeDays(mins / 1440);
}

export function formatRatio(ratio: number | null | undefined): string | null {
  if (ratio === null || ratio === undefined) return null;
  return `${ratio.toFixed(1).replace(".", ",")}x`;
}
