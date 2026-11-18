export const HQ_CHANNEL_COLORS = [
  "#3f8f8a", // teal
  "#b0563a", // rust
  "#7d8f4a", // olive
  "#4f6f9a", // slate
  "#c2913a", // ochre
  "#8a5577", // plum
  "#5a7a5a", // moss
  "#a8735a", // clay
] as const;

export function hashChannelId(channelId: string): number {
  let h = 2166136261;
  for (let i = 0; i < channelId.length; i++) {
    h ^= channelId.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/**
 * Deterministic curated color assignment per channelId.
 * Avoids repeating the same color in adjacent studios on the same corridor side.
 */
export function assignChannelColors(channelIds: readonly string[]): Map<string, string> {
  const result = new Map<string, string>();
  const lastColorBySide = new Map<string, number>();
  const limit = Math.min(channelIds.length, 24);

  for (let i = 0; i < limit; i++) {
    const id = channelIds[i];
    const wing = i < 12 ? 0 : 1;
    const localIdx = wing === 0 ? i : i - 12;
    const side = localIdx % 2 === 0 ? "north" : "south";
    const sideKey = `${wing}:${side}`;

    let colorIdx = hashChannelId(id) % HQ_CHANNEL_COLORS.length;
    const prevIdx = lastColorBySide.get(sideKey);
    if (prevIdx !== undefined && colorIdx === prevIdx) {
      colorIdx = (colorIdx + 1) % HQ_CHANNEL_COLORS.length;
    }
    lastColorBySide.set(sideKey, colorIdx);
    result.set(id, HQ_CHANNEL_COLORS[colorIdx]);
  }

  for (let i = limit; i < channelIds.length; i++) {
    const id = channelIds[i];
    if (!result.has(id)) {
      result.set(id, HQ_CHANNEL_COLORS[hashChannelId(id) % HQ_CHANNEL_COLORS.length]);
    }
  }

  return result;
}
