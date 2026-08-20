/**
 * Category-aware marker metadata helpers.
 * Provides visual glyphs, shapes, and colors for stop markers on maps.
 * Never relies on color alone — each category has a distinct glyph + shape.
 */

import type { StopCategory } from './types';

export interface MarkerMeta {
  /** Unicode glyph for the category */
  glyph: string;
  /** SVG path shape for the marker background */
  shape: 'circle' | 'square' | 'diamond' | 'hexagon';
  /** Label for accessibility */
  categoryLabel: string;
  /** Fill color for the marker */
  fillColor: string;
}

const CATEGORY_MAP: Record<StopCategory, MarkerMeta> = {
  landmark: {
    glyph: '▲',
    shape: 'circle',
    categoryLabel: 'Landmark',
    fillColor: '#6f3e59',
  },
  museum_gallery: {
    glyph: '▦',
    shape: 'square',
    categoryLabel: 'Museum / Gallery',
    fillColor: '#6f3e59',
  },
  historic_religious_site: {
    glyph: '✦',
    shape: 'diamond',
    categoryLabel: 'Historic / Religious',
    fillColor: '#6f3e59',
  },
  quick_viewpoint: {
    glyph: '◉',
    shape: 'circle',
    categoryLabel: 'Viewpoint',
    fillColor: '#6f3e59',
  },
  neighborhood_market_park: {
    glyph: '♣',
    shape: 'hexagon',
    categoryLabel: 'Neighborhood / Market / Park',
    fillColor: '#456a50',
  },
  food_break: {
    glyph: '◆',
    shape: 'diamond',
    categoryLabel: 'Food',
    fillColor: '#d89b2b',
  },
  experience_tour: {
    glyph: '★',
    shape: 'hexagon',
    categoryLabel: 'Experience / Tour',
    fillColor: '#6a4fa3',
  },
  other: {
    glyph: '•',
    shape: 'circle',
    categoryLabel: 'Stop',
    fillColor: '#6f3e59',
  },
};

/** Get marker visual metadata for a stop category */
export function getMarkerMeta(category: StopCategory): MarkerMeta {
  return CATEGORY_MAP[category] ?? CATEGORY_MAP.other;
}

/** Get the marker title combining sequence number, name, and category */
export function getMarkerTitle(
  sequenceNumber: number,
  name: string,
  category: StopCategory,
): string {
  const meta = getMarkerMeta(category);
  return `${sequenceNumber}. ${name} (${meta.categoryLabel})`;
}

/**
 * Build a data URL for a custom SVG marker with sequence number and category glyph.
 * The marker includes both the number (for order) and a small category indicator (for type).
 */
export function buildMarkerSvg(
  sequenceNumber: number,
  category: StopCategory,
  type: 'stop' | 'origin' | 'destination' | 'origin-destination' = 'stop',
): string {
  const meta = getMarkerMeta(category);
  const size = 36;
  const half = size / 2;

  if (type === 'origin' || type === 'destination' || type === 'origin-destination') {
    const label =
      type === 'origin' ? 'S' : type === 'destination' ? 'E' : 'S/E';
    const fill = type === 'origin' ? '#2b2326' : '#6f3e59';
    const textFill = type === 'origin' ? '#ffffff' : '#ffffff';
    return `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <circle cx="${half}" cy="${half}" r="${half - 2}" fill="${fill}" stroke="#ffffff" stroke-width="2.5"/>
  <text x="${half}" y="${half + 5}" text-anchor="middle" font-family="Inter,system-ui,sans-serif" font-size="12" font-weight="700" fill="${textFill}">${label}</text>
</svg>`)}`;
  }

  // Stop marker: numbered circle with category glyph indicator
  const bgShape = getShapeSvg(meta.shape, half, half, half - 2, meta.fillColor);

  return `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  ${bgShape}
  <text x="${half}" y="${half + 5}" text-anchor="middle" font-family="Inter,system-ui,sans-serif" font-size="13" font-weight="700" fill="#ffffff">${sequenceNumber}</text>
  <circle cx="29" cy="29" r="5.5" fill="#fff8ea" stroke="${meta.fillColor}" stroke-width="1.5"/>
  <text x="29" y="32" text-anchor="middle" font-family="Inter,system-ui,sans-serif" font-size="7" font-weight="700" fill="${meta.fillColor}">${meta.glyph}</text>
</svg>`)}`;
}

function getShapeSvg(
  shape: MarkerMeta['shape'],
  cx: number,
  cy: number,
  r: number,
  fill: string,
): string {
  switch (shape) {
    case 'circle':
      return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${fill}" stroke="#ffffff" stroke-width="2"/>`;
    case 'square':
      return `<rect x="${cx - r}" y="${cy - r}" width="${r * 2}" height="${r * 2}" rx="4" fill="${fill}" stroke="#ffffff" stroke-width="2"/>`;
    case 'diamond': {
      const points = `${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`;
      return `<polygon points="${points}" fill="${fill}" stroke="#ffffff" stroke-width="2"/>`;
    }
    case 'hexagon': {
      const pts = Array.from({ length: 6 }, (_, i) => {
        const angle = (Math.PI / 3) * i - Math.PI / 2;
        return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
      }).join(' ');
      return `<polygon points="${pts}" fill="${fill}" stroke="#ffffff" stroke-width="2"/>`;
    }
  }
}
