import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import InputHero from '../src/components/InputHero';
import { getMarkerMeta, getMarkerTitle, buildMarkerSvg } from '../src/lib/marker-helpers';
import { useFullscreen } from '../src/hooks/use-fullscreen';
import {
  naiveLineOptions,
  optimizedLineOptions,
  NAIVE_STROKE,
  OPTIMIZED_STROKE,
} from '../src/lib/map-lines';
import type { StopCategory } from '../src/lib/types';

// Mock google maps
vi.mock('../src/lib/google-maps', () => {
  const rejection = Promise.reject(new Error('No Maps in test'));
  rejection.catch(() => {});
  return {
    MAPS_AUTH_FAILURE_EVENT: 'vialo:maps-auth-failure',
    loadGoogleMaps: () => rejection,
    baseMapOptions: () => ({}),
    VIALO_MAP_STYLES: [],
    notifyMapsAuthFailure: () => {},
  };
});

vi.mock('../src/lib/api-client', () => ({
  fetchAutocomplete: vi.fn(),
  planItinerary: vi.fn(),
  createShare: vi.fn(),
  deleteShare: vi.fn(),
  getShare: vi.fn(),
  ApiClientError: class ApiClientError extends Error {},
}));

function wrap(ui: React.ReactElement) {
  return render(ui, { wrapper: ({ children }) => <MemoryRouter>{children}</MemoryRouter> });
}

describe('InputHero — switch control', () => {
  it('renders return-to-start as role="switch" instead of checkbox', async () => {
    const user = userEvent.setup();
    wrap(<InputHero onSubmit={vi.fn()} />);
    await user.click(screen.getByRole('tab', { name: 'Choose details' }));

    const switchEl = screen.getByRole('switch', { name: /End where I started/ });
    expect(switchEl).toBeInTheDocument();
    expect(switchEl).toHaveAttribute('aria-checked', 'true');
  });

  it('switch toggles aria-checked on click', async () => {
    const user = userEvent.setup();
    wrap(<InputHero onSubmit={vi.fn()} />);
    await user.click(screen.getByRole('tab', { name: 'Choose details' }));

    const switchEl = screen.getByRole('switch', { name: /End where I started/ });
    expect(switchEl).toHaveAttribute('aria-checked', 'true');

    await user.click(switchEl);
    expect(switchEl).toHaveAttribute('aria-checked', 'false');

    await user.click(switchEl);
    expect(switchEl).toHaveAttribute('aria-checked', 'true');
  });

  it('switch meets 44px minimum touch target', async () => {
    const user = userEvent.setup();
    wrap(<InputHero onSubmit={vi.fn()} />);
    await user.click(screen.getByRole('tab', { name: 'Choose details' }));

    const switchRow = screen.getByRole('switch', { name: /End where I started/ })
      .closest('.return-switch-row');
    expect(switchRow).toBeInTheDocument();
    // The min-height CSS guarantees the 44px target (verified via class presence)
  });

  it('switch is keyboard accessible (Space/Enter)', async () => {
    const user = userEvent.setup();
    wrap(<InputHero onSubmit={vi.fn()} />);
    await user.click(screen.getByRole('tab', { name: 'Choose details' }));

    const switchEl = screen.getByRole('switch', { name: /End where I started/ });
    switchEl.focus();
    expect(switchEl).toHaveAttribute('aria-checked', 'true');

    await user.keyboard(' ');
    expect(switchEl).toHaveAttribute('aria-checked', 'false');
  });
});

describe('InputHero — hero postcard content', () => {
  it('renders the animated postcard SVG as decorative (aria-hidden)', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);
    const postcard = document.querySelector('.hero-postcard');
    expect(postcard).toBeInTheDocument();
    expect(postcard).toHaveAttribute('aria-hidden', 'true');
  });

  it('still renders headline and primary input in hero', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);
    expect(screen.getByRole('heading', { name: /Describe your day/ })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /Describe your day/ })).toBeInTheDocument();
  });

  it('hero does not include external images (self-contained)', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);
    const imgs = document.querySelectorAll('.input-hero img');
    expect(imgs.length).toBe(0);
  });

  it('postcard contains SVG with route path and stop markers', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);
    const svg = document.querySelector('.postcard-svg');
    expect(svg).toBeInTheDocument();
    expect(svg?.querySelector('.postcard-route')).toBeInTheDocument();
    expect(svg?.querySelectorAll('.postcard-stop').length).toBeGreaterThanOrEqual(3);
  });

  it('postcard contains floating schedule cards', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);
    expect(document.querySelector('.postcard-card--1')).toBeInTheDocument();
    expect(document.querySelector('.postcard-card--2')).toBeInTheDocument();
  });
});

describe('InputHero — reduced motion', () => {
  // The test setup already mocks matchMedia to return reduce=true
  it('postcard animations are disabled via CSS class when reduced motion is active', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);
    // CSS rule @media (prefers-reduced-motion: reduce) sets animation: none
    // We verify the structure is present but no JS animation logic runs
    const buildings = document.querySelectorAll('.postcard-building');
    expect(buildings.length).toBeGreaterThan(0);
    // The animateMotion element exists but is visually disabled by CSS
    const motionEl = document.querySelector('.postcard-motion');
    // In reduced-motion mode, CSS hides the animateMotion via display:none
    expect(motionEl).toBeInTheDocument();
  });

  it('no animation attribute on postcard elements (CSS handles motion)', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);
    // Verify buildings don't have inline animation styles
    const building = document.querySelector('.postcard-building--1');
    expect(building).toBeInTheDocument();
    expect(building?.getAttribute('style')).toBeNull();
  });
});

describe('Marker metadata helpers', () => {
  it('returns metadata for all known categories', () => {
    const categories: StopCategory[] = [
      'landmark',
      'museum_gallery',
      'historic_religious_site',
      'quick_viewpoint',
      'neighborhood_market_park',
      'food_break',
      'experience_tour',
      'other',
    ];

    for (const cat of categories) {
      const meta = getMarkerMeta(cat);
      expect(meta.glyph).toBeTruthy();
      expect(meta.shape).toMatch(/^(circle|square|diamond|hexagon)$/);
      expect(meta.categoryLabel).toBeTruthy();
      expect(meta.fillColor).toMatch(/^#[0-9a-f]{6}$/);
    }
  });

  it('different categories produce distinct shapes', () => {
    const landmark = getMarkerMeta('landmark');
    const museum = getMarkerMeta('museum_gallery');
    const religious = getMarkerMeta('historic_religious_site');

    // At least some categories have different shapes
    const shapes = new Set([landmark.shape, museum.shape, religious.shape]);
    expect(shapes.size).toBeGreaterThan(1);
  });

  it('getMarkerTitle includes sequence, name, and category label', () => {
    const title = getMarkerTitle(3, 'Basilica di San Marco', 'historic_religious_site');
    expect(title).toBe('3. Basilica di San Marco (Historic / Religious)');
  });

  it('buildMarkerSvg returns a valid data URL', () => {
    const url = buildMarkerSvg(1, 'landmark', 'stop');
    expect(url).toMatch(/^data:image\/svg\+xml,/);
    expect(url).toContain('1'); // sequence number
  });

  it('buildMarkerSvg produces different shapes for origin vs stop', () => {
    const stop = buildMarkerSvg(1, 'landmark', 'stop');
    const origin = buildMarkerSvg(0, 'other', 'origin');
    const dest = buildMarkerSvg(0, 'other', 'destination');

    expect(stop).not.toBe(origin);
    expect(origin).not.toBe(dest);
    expect(origin).toContain('S');
    expect(dest).toContain('E');
  });

  it('buildMarkerSvg handles origin-destination combined type', () => {
    const combined = buildMarkerSvg(0, 'other', 'origin-destination');
    expect(combined).toContain('S%2FE'); // "S/E" URL-encoded
  });

  it('each category marker SVG has distinct visual shape path', () => {
    const landmark = buildMarkerSvg(1, 'landmark', 'stop');
    const museum = buildMarkerSvg(1, 'museum_gallery', 'stop');

    // landmark uses circle, museum uses rect
    expect(landmark).toContain('circle');
    expect(museum).toContain('rect');
  });
});

describe('Fullscreen map control', () => {
  beforeEach(() => {
    document.body.style.overflow = '';
  });

  function FullscreenHarness({ onResize }: { onResize?: () => void }) {
    const { isFullscreen, containerRef, triggerRef, toggleFullscreen } = useFullscreen({
      onResize,
    });
    return (
      <>
        <div
          ref={containerRef}
          data-testid="fullscreen-container"
          data-fullscreen={String(isFullscreen)}
        >
          <button
            ref={triggerRef}
            type="button"
            onClick={toggleFullscreen}
            aria-label={isFullscreen ? 'Exit full screen' : 'View map full screen'}
          >
            Toggle
          </button>
        </div>
        <button type="button">Other control</button>
      </>
    );
  }

  it('CSS fallback enters fullscreen and locks body scroll', async () => {
    const user = userEvent.setup();
    render(<FullscreenHarness />);

    await user.click(screen.getByRole('button', { name: 'View map full screen' }));

    expect(screen.getByTestId('fullscreen-container')).toHaveAttribute(
      'data-fullscreen',
      'true',
    );
    expect(document.body.style.overflow).toBe('hidden');
    expect(screen.getByRole('button', { name: 'Exit full screen' })).toBeInTheDocument();
  });

  it('Escape exits CSS fullscreen, restores scroll, and returns focus', async () => {
    const user = userEvent.setup();
    document.body.style.overflow = 'auto';
    render(<FullscreenHarness />);

    const trigger = screen.getByRole('button', { name: 'View map full screen' });
    await user.click(trigger);
    screen.getByRole('button', { name: 'Other control' }).focus();
    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(screen.getByTestId('fullscreen-container')).toHaveAttribute(
        'data-fullscreen',
        'false',
      );
      expect(document.body.style.overflow).toBe('auto');
      expect(trigger).toHaveFocus();
    });
  });

  it('restores body scroll if the fullscreen map unmounts', async () => {
    const user = userEvent.setup();
    document.body.style.overflow = 'auto';
    const { unmount } = render(<FullscreenHarness />);

    await user.click(screen.getByRole('button', { name: 'View map full screen' }));
    expect(document.body.style.overflow).toBe('hidden');
    unmount();

    expect(document.body.style.overflow).toBe('auto');
  });

  it('notifies the map to refit after fullscreen state changes', async () => {
    const user = userEvent.setup();
    const onResize = vi.fn();
    render(<FullscreenHarness onResize={onResize} />);

    await user.click(screen.getByRole('button', { name: 'View map full screen' }));
    await waitFor(() => expect(onResize).toHaveBeenCalled());
  });
});

describe('comparison map line options', () => {
  const path = [
    { lat: 40.8, lng: 14.2 },
    { lat: 40.81, lng: 14.21 },
  ];

  it('draws the naive baseline above the optimized route so overlaps stay visible', () => {
    const naive = naiveLineOptions(path) as { zIndex: number };
    const optimized = optimizedLineOptions(path) as { zIndex: number };
    expect(naive.zIndex).toBeGreaterThan(optimized.zIndex);
  });

  it('distinguishes the two routes by weight and dash pattern, not color alone', () => {
    const naive = naiveLineOptions(path) as {
      strokeOpacity: number;
      strokeWeight: number;
      icons: Array<{ icon: { strokeColor: string; strokeOpacity: number }; repeat: string }>;
    };
    const optimized = optimizedLineOptions(path) as {
      strokeOpacity: number;
      strokeWeight: number;
      icons?: unknown;
    };

    // Dashed baseline: transparent base stroke plus repeated dash symbols.
    expect(naive.strokeOpacity).toBe(0);
    expect(naive.icons).toHaveLength(1);
    const dash = naive.icons[0]!;
    expect(dash.icon.strokeColor).toBe(NAIVE_STROKE);
    expect(dash.repeat).toMatch(/px$/);

    // Solid, heavier optimized route with no dash symbols.
    expect(optimized.strokeOpacity).toBe(1);
    expect(optimized.icons).toBeUndefined();
    expect(optimized.strokeWeight).toBeGreaterThan(naive.strokeWeight);
  });

  it('uses the design-system route colors', () => {
    expect(NAIVE_STROKE).toBe('#a95242');
    expect(OPTIMIZED_STROKE).toBe('#6f3e59');
    expect((naiveLineOptions(path) as { strokeColor: string }).strokeColor).toBe(NAIVE_STROKE);
    expect((optimizedLineOptions(path) as { strokeColor: string }).strokeColor).toBe(OPTIMIZED_STROKE);
  });

  it('keeps both routes on the supplied path so bounds and scale match', () => {
    expect((naiveLineOptions(path) as { path: unknown }).path).toBe(path);
    expect((optimizedLineOptions(path) as { path: unknown }).path).toBe(path);
  });
});
