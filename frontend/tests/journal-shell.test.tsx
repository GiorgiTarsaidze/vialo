import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../src/lib/journal-client', () => ({
  fetchPosts: vi.fn(),
  fetchPost: vi.fn(),
  createPost: vi.fn(),
  deletePost: vi.fn(),
  fetchComments: vi.fn(),
  createComment: vi.fn(),
  deleteComment: vi.fn(),
  reportPost: vi.fn(),
  requestUpload: vi.fn(),
  uploadFile: vi.fn(),
  fetchMe: vi.fn(),
  JournalClientError: class JournalClientError extends Error {
    code: string;
    statusCode: number;
    constructor(code: string, message: string, statusCode: number) {
      super(message);
      this.code = code;
      this.statusCode = statusCode;
      this.name = 'JournalClientError';
    }
  },
}));

vi.mock('../src/lib/cognito', () => ({
  subscribeToSession: vi.fn(() => () => {}),
  getSession: vi.fn(() => null),
  getIdToken: vi.fn(() => null),
  saveSession: vi.fn(),
  clearSession: vi.fn(),
  isAuthenticated: vi.fn(() => false),
  startSignIn: vi.fn(),
  startSignUp: vi.fn(),
  signOut: vi.fn(),
  exchangeCode: vi.fn(),
  getRedirectUri: vi.fn(() => 'http://localhost:3000/auth/callback'),
}));

import { fetchPosts, fetchMe } from '../src/lib/journal-client';
import { getSession, isAuthenticated, signOut, subscribeToSession } from '../src/lib/cognito';
import { displayNameFromClaims } from '../src/hooks/use-auth';

const mockFetchPosts = fetchPosts as ReturnType<typeof vi.fn>;
const mockIsAuthenticated = isAuthenticated as ReturnType<typeof vi.fn>;
const mockGetSession = getSession as ReturnType<typeof vi.fn>;
const mockSignOut = signOut as ReturnType<typeof vi.fn>;

function makePost(overrides = {}) {
  return {
    postId: 'post-1',
    title: 'A day in Venice',
    city: 'Venice',
    cityKey: 'venice',
    excerpt: 'We walked along the canals...',
    coverImageUrl: null,
    author: { userId: 'user-1', displayName: 'Jane' },
    createdAt: new Date().toISOString(),
    commentCount: 2,
    hasRoute: true,
    stopCount: 5,
    ...overrides,
  };
}

/** Build an unsigned JWT whose payload carries the given claims. */
function tokenWith(claims: Record<string, unknown>): string {
  const b64 = btoa(JSON.stringify(claims)).replace(/\+/g, '-').replace(/\//g, '_');
  return `header.${b64}.signature`;
}

describe('displayNameFromClaims', () => {
  it('prefers nickname over every other claim', () => {
    expect(
      displayNameFromClaims({ nickname: 'Gio', preferred_username: 'g2', email: 'a@b.com' }),
    ).toBe('Gio');
  });

  it('falls through the claim order used by the backend', () => {
    expect(displayNameFromClaims({ preferred_username: 'walker' })).toBe('walker');
    expect(displayNameFromClaims({ name: 'Ana Lima' })).toBe('Ana Lima');
    expect(displayNameFromClaims({ given_name: 'Ana' })).toBe('Ana');
  });

  it('uses only the local part of an email, never the domain', () => {
    const name = displayNameFromClaims({ email: 'demo@vialo.place' });
    expect(name).toBe('demo');
    expect(name).not.toContain('@');
    expect(name).not.toContain('vialo.place');
  });

  it('falls back to Traveller when no usable claim exists', () => {
    expect(displayNameFromClaims({})).toBe('Traveller');
    expect(displayNameFromClaims({ email: 'not-an-email' })).toBe('Traveller');
  });

  it('returns null without claims and bounds long names at 40 characters', () => {
    expect(displayNameFromClaims(null)).toBeNull();
    expect(displayNameFromClaims({ nickname: 'x'.repeat(80) })).toHaveLength(40);
  });
});

describe('AppShell account control', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated.mockReturnValue(false);
    mockGetSession.mockReturnValue(null);
  });

  it('offers sign in when signed out', async () => {
    const { default: AppShell } = await import('../src/components/AppShell');
    render(
      <MemoryRouter>
        <AppShell onNewDay={vi.fn()} showBack={false}>
          <div>Content</div>
        </AppShell>
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('names the signed-in account and can sign out', async () => {
    mockIsAuthenticated.mockReturnValue(true);
    mockGetSession.mockReturnValue({
      idToken: tokenWith({ sub: 'user-1', email: 'demo@vialo.place' }),
      expiresAt: Date.now() + 3_600_000,
    });

    const { default: AppShell } = await import('../src/components/AppShell');
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AppShell onNewDay={vi.fn()} showBack={false}>
          <div>Content</div>
        </AppShell>
      </MemoryRouter>,
    );

    const chip = screen.getByRole('button', { name: /Signed in as demo/ });
    expect(chip).toBeInTheDocument();

    await user.click(chip);
    expect(screen.getByText('Signed in as')).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'My stories' })).toBeInTheDocument();

    await user.click(screen.getByRole('menuitem', { name: 'Sign out' }));
    expect(mockSignOut).toHaveBeenCalled();
  });

  it('never renders the full email address', async () => {
    mockIsAuthenticated.mockReturnValue(true);
    mockGetSession.mockReturnValue({
      idToken: tokenWith({ sub: 'user-1', email: 'demo@vialo.place' }),
      expiresAt: Date.now() + 3_600_000,
    });

    const { default: AppShell } = await import('../src/components/AppShell');
    const { container } = render(
      <MemoryRouter>
        <AppShell onNewDay={vi.fn()} showBack={false}>
          <div>Content</div>
        </AppShell>
      </MemoryRouter>,
    );
    expect(container.textContent).not.toContain('demo@vialo.place');
  });
});

describe('StoryStrip', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated.mockReturnValue(false);
    mockGetSession.mockReturnValue(null);
  });

  it('renders nothing when the Journal is empty', async () => {
    mockFetchPosts.mockResolvedValue({ posts: [], nextCursor: null });
    const { default: StoryStrip } = await import('../src/components/StoryStrip');
    const { container } = render(
      <MemoryRouter>
        <StoryStrip />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mockFetchPosts).toHaveBeenCalled());
    expect(container.querySelector('.story-strip')).toBeNull();
  });

  it('renders nothing when the Journal is unreachable', async () => {
    mockFetchPosts.mockRejectedValue(new Error('network down'));
    const { default: StoryStrip } = await import('../src/components/StoryStrip');
    const { container } = render(
      <MemoryRouter>
        <StoryStrip />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mockFetchPosts).toHaveBeenCalled());
    expect(container.querySelector('.story-strip')).toBeNull();
  });

  it('shows stories and links to the Journal', async () => {
    const { default: StoryStrip } = await import('../src/components/StoryStrip');
    render(
      <MemoryRouter>
        <StoryStrip posts={[makePost(), makePost({ postId: 'post-2', title: 'Tbilisi walks' })]} />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Days people actually walked' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /All stories/ })).toHaveAttribute('href', '/journal');
    expect(screen.getAllByText('A day in Venice').length).toBeGreaterThan(0);
  });

  it('does not repeat a thin Journal to fill the band', async () => {
    const { default: StoryStrip } = await import('../src/components/StoryStrip');
    const { container } = render(
      <MemoryRouter>
        <StoryStrip posts={[makePost(), makePost({ postId: 'p2', title: 'Second' })]} />
      </MemoryRouter>,
    );
    // Two stories, two tiles. Padding a lane by repeating them would be
    // simulated content dressed up as a busy feed.
    expect(container.querySelectorAll('.story-strip__lane')).toHaveLength(1);
    expect(container.querySelectorAll('.story-strip__tile')).toHaveLength(2);
    expect(container.querySelector('.story-strip__track--static')).not.toBeNull();
  });

  it('hides the duplicated lane from assistive technology and the tab order', async () => {
    const { default: StoryStrip } = await import('../src/components/StoryStrip');
    const posts = [1, 2, 3, 4, 5].map((n) =>
      makePost({ postId: `p${n}`, title: `Story ${n}` }),
    );
    const { container } = render(
      <MemoryRouter>
        <StoryStrip posts={posts} />
      </MemoryRouter>,
    );
    const lanes = container.querySelectorAll('.story-strip__lane');
    expect(lanes).toHaveLength(2);
    expect(lanes[0]).not.toHaveAttribute('aria-hidden');
    expect(lanes[1]).toHaveAttribute('aria-hidden', 'true');
    // Every link inside the duplicate is removed from the tab order.
    lanes[1]!.querySelectorAll('a').forEach((a) => {
      expect(a).toHaveAttribute('tabindex', '-1');
    });
  });
});

describe('JournalLanding city filter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated.mockReturnValue(false);
    mockGetSession.mockReturnValue(null);
  });

  it('keeps every city listed after a filter is applied', async () => {
    const all = {
      posts: [
        makePost({ postId: 'p1', city: 'Venice', title: 'Venice one' }),
        makePost({ postId: 'p2', city: 'Naples', title: 'Naples one' }),
        makePost({ postId: 'p3', city: 'Tbilisi', title: 'Tbilisi one' }),
      ],
      nextCursor: null,
    };
    mockFetchPosts.mockImplementation((slug?: string) => {
      if (!slug) return Promise.resolve(all);
      return Promise.resolve({
        posts: all.posts.filter((p) => p.city.toLowerCase() === slug),
        nextCursor: null,
      });
    });

    const { default: JournalLanding } = await import('../src/components/JournalLanding');
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <JournalLanding />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Naples' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'Naples' }));

    // The filter row must still offer the other cities, otherwise the only way
    // back is "All cities". This regressed when cities were derived from the
    // visible posts rather than the unfiltered feed.
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Naples' })).toHaveAttribute('aria-pressed', 'true');
    });
    expect(screen.getByRole('button', { name: 'Venice' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tbilisi' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'All cities' })).toBeInTheDocument();
  });

  it('names the city in the empty state when a filter finds nothing', async () => {
    mockFetchPosts.mockImplementation((slug?: string) => {
      if (!slug) {
        return Promise.resolve({
          posts: [
            makePost({ postId: 'p1', city: 'Venice' }),
            makePost({ postId: 'p2', city: 'Naples' }),
          ],
          nextCursor: null,
        });
      }
      return Promise.resolve({ posts: [], nextCursor: null });
    });

    const { default: JournalLanding } = await import('../src/components/JournalLanding');
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <JournalLanding />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByRole('button', { name: 'Naples' })).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: 'Naples' }));

    await waitFor(() => {
      expect(screen.getByText('No stories from Naples yet')).toBeInTheDocument();
    });
  });
});


describe('session changes reach an already-mounted header', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated.mockReturnValue(false);
    mockGetSession.mockReturnValue(null);
  });

  it('subscribes to same-tab session changes', async () => {
    const { default: AppShell } = await import('../src/components/AppShell');
    render(
      <MemoryRouter>
        <AppShell onNewDay={vi.fn()} showBack={false}>
          <div>Content</div>
        </AppShell>
      </MemoryRouter>,
    );
    // Without this subscription the header keeps showing "Sign in" after a
    // successful auth callback, because the storage event does not fire in the
    // tab that wrote the session.
    expect(subscribeToSession).toHaveBeenCalled();
  });

  it('re-reads the session when the subscription fires', async () => {
    const sub = subscribeToSession as ReturnType<typeof vi.fn>;
    let notify = () => {};
    sub.mockImplementation((fn: () => void) => {
      notify = fn;
      return () => {};
    });

    const { default: AppShell } = await import('../src/components/AppShell');
    render(
      <MemoryRouter>
        <AppShell onNewDay={vi.fn()} showBack={false}>
          <div>Content</div>
        </AppShell>
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument();

    mockIsAuthenticated.mockReturnValue(true);
    mockGetSession.mockReturnValue({
      idToken: tokenWith({ sub: 'user-1', email: 'demo@vialo.place' }),
      expiresAt: Date.now() + 3_600_000,
    });
    await act(async () => { notify(); });

    expect(screen.getByRole('button', { name: /Signed in as demo/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sign in' })).not.toBeInTheDocument();
  });
});

describe('JournalEditor keeps the handed-over day', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated.mockReturnValue(true);
    mockGetSession.mockReturnValue({
      idToken: tokenWith({ sub: 'user-1', email: 'demo@vialo.place' }),
      expiresAt: Date.now() + 3_600_000,
    });
    sessionStorage.clear();
  });

  it('survives the re-render caused by the allowance fetch', async () => {
    const itinerary = {
      locality: { name: 'Naples' },
      window: { localStart: '10:00', localEnd: '18:00' },
      stops: [{ name: 'a' }, { name: 'b' }, { name: 'c' }],
    };
    sessionStorage.setItem('vialo.journal.draft_itinerary', JSON.stringify(itinerary));
    (fetchMe as ReturnType<typeof vi.fn>).mockResolvedValue({
      author: { userId: 'user-1', displayName: 'demo' },
      posts: [],
      postsRemainingToday: 5,
    });

    const { default: JournalEditor } = await import('../src/components/JournalEditor');
    render(
      <MemoryRouter>
        <JournalEditor />
      </MemoryRouter>,
    );

    // Reading sessionStorage in the render body consumed the entry on the first
    // render and returned null on every render after it, so the attached route
    // vanished as soon as the allowance arrived and no story carried a route.
    await waitFor(() => {
      expect(screen.getByText('5 left today')).toBeInTheDocument();
    });
    expect(screen.getByText('Your computed day')).toBeInTheDocument();
    expect(screen.getByLabelText('Attach this day to the story')).toBeChecked();
  });
});
