import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock cognito before importing journal-client
vi.mock('../src/lib/cognito', () => ({
  getIdToken: vi.fn(() => 'test-id-token'),
  getSession: vi.fn(() => ({ idToken: 'test-id-token', expiresAt: Date.now() + 3600_000 })),
  isAuthenticated: vi.fn(() => true),
}));

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

import {
  fetchPosts,
  fetchPost,
  createPost,
  deletePost,
  createComment,
  deleteComment,
  reportPost,
  requestUpload,
  uploadFile,
  fetchMe,
  JournalClientError,
} from '../src/lib/journal-client';

describe('journal-client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('fetchPosts', () => {
    it('calls correct URL with no params', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ posts: [], nextCursor: null }),
      });

      await fetchPosts();
      expect(mockFetch).toHaveBeenCalledWith('/api/blog/posts', { signal: undefined });
    });

    it('includes city and cursor params', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ posts: [], nextCursor: null }),
      });

      await fetchPosts('venice', 'cursor123');
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/blog/posts?city=venice&cursor=cursor123',
        { signal: undefined },
      );
    });

    it('throws JournalClientError on API error', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ error: { code: 'INTERNAL_ERROR', message: 'Server error' } }),
      });

      await expect(fetchPosts()).rejects.toThrow(JournalClientError);
      await expect(fetchPosts()).rejects.toMatchObject({ code: 'INTERNAL_ERROR', statusCode: 500 });
    });
  });

  describe('fetchPost', () => {
    it('calls correct URL', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ postId: 'p1', title: 'Test' }),
      });

      await fetchPost('p1');
      expect(mockFetch).toHaveBeenCalledWith('/api/blog/posts/p1', { signal: undefined });
    });

    it('throws on 404', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ error: { code: 'POST_NOT_FOUND', message: 'Not found' } }),
      });

      await expect(fetchPost('nope')).rejects.toMatchObject({ code: 'POST_NOT_FOUND' });
    });
  });

  describe('createPost', () => {
    it('sends POST with auth header and body', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 201,
        json: () => Promise.resolve({ post: { postId: 'new-1', title: 'Test' } }),
      });

      await createPost({ title: 'Test', city: 'Venice', body: 'A long enough body for the story...' });
      const [url, opts] = mockFetch.mock.calls[0]!;
      expect(url).toBe('/api/blog/posts');
      expect(opts.method).toBe('POST');
      expect(opts.headers).toMatchObject({
        'Content-Type': 'application/json',
        Authorization: 'Bearer test-id-token',
      });
      expect(JSON.parse(opts.body)).toMatchObject({ title: 'Test', city: 'Venice' });
    });
  });

  describe('deletePost', () => {
    it('sends DELETE with auth', async () => {
      mockFetch.mockResolvedValue({ ok: true, status: 204 });

      await deletePost('p1');
      const [url, opts] = mockFetch.mock.calls[0]!;
      expect(url).toBe('/api/blog/posts/p1');
      expect(opts.method).toBe('DELETE');
      expect(opts.headers).toMatchObject({ Authorization: 'Bearer test-id-token' });
    });
  });

  describe('createComment', () => {
    it('sends POST with body', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 201,
        json: () => Promise.resolve({ commentId: 'c1', postId: 'p1', author: { userId: 'u1', displayName: 'Jane' }, body: 'Hello', createdAt: '2024-01-01T00:00:00Z' }),
      });

      await createComment('p1', 'Hello');
      const [url, opts] = mockFetch.mock.calls[0]!;
      expect(url).toBe('/api/blog/posts/p1/comments');
      expect(opts.method).toBe('POST');
      expect(JSON.parse(opts.body)).toEqual({ body: 'Hello' });
    });
  });

  describe('deleteComment', () => {
    it('sends DELETE', async () => {
      mockFetch.mockResolvedValue({ ok: true, status: 204 });

      await deleteComment('p1', 'c1');
      const [url, opts] = mockFetch.mock.calls[0]!;
      expect(url).toBe('/api/blog/posts/p1/comments/c1');
      expect(opts.method).toBe('DELETE');
    });
  });

  describe('reportPost', () => {
    it('sends POST to report endpoint', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 202,
        json: () => Promise.resolve({ status: 'received' }),
      });

      await reportPost('p1');
      const [url, opts] = mockFetch.mock.calls[0]!;
      expect(url).toBe('/api/blog/posts/p1/report');
      expect(opts.method).toBe('POST');
    });
  });

  describe('requestUpload', () => {
    it('sends contentType in body', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ uploadUrl: 'https://s3.example.com', fields: { key: 'val' }, imageKey: 'img-1', maxBytes: 2_000_000, expiresInSeconds: 300 }),
      });

      await requestUpload('image/jpeg');
      const [url, opts] = mockFetch.mock.calls[0]!;
      expect(url).toBe('/api/blog/uploads');
      expect(JSON.parse(opts.body)).toEqual({ contentType: 'image/jpeg' });
    });
  });

  describe('uploadFile', () => {
    it('builds FormData with fields first and file last', async () => {
      mockFetch.mockResolvedValue({ ok: true, status: 201 });

      const file = new File(['data'], 'test.jpg', { type: 'image/jpeg' });
      await uploadFile('https://s3.example.com', { key: 'val', policy: 'abc' }, file);

      const [url, opts] = mockFetch.mock.calls[0]!;
      expect(url).toBe('https://s3.example.com');
      expect(opts.method).toBe('POST');
      expect(opts.body).toBeInstanceOf(FormData);
      // Verify no custom headers
      expect(opts.headers).toBeUndefined();
    });

    it('throws on non-success status', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 403 });

      const file = new File(['data'], 'test.jpg', { type: 'image/jpeg' });
      await expect(uploadFile('https://s3.example.com', {}, file)).rejects.toThrow('Image upload failed.');
    });
  });

  describe('fetchMe', () => {
    it('calls /api/blog/me with auth', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ author: { userId: 'u1', displayName: 'Jane' }, posts: [], postsRemainingToday: 3 }),
      });

      await fetchMe();
      const [url, opts] = mockFetch.mock.calls[0]!;
      expect(url).toBe('/api/blog/me');
      expect(opts.headers).toMatchObject({ Authorization: 'Bearer test-id-token' });
    });
  });
});
