/**
 * Journal API client — same-origin /api/blog/* requests.
 */
import type {
  PostsResponse,
  Post,
  CommentsResponse,
  Comment,
  CreatePostPayload,
  CreatePostResponse,
  UploadResponse,
  MeResponse,
  JournalApiError,
} from './journal-types';
import { getIdToken } from './cognito';

export class JournalClientError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly statusCode: number,
  ) {
    super(message);
    this.name = 'JournalClientError';
  }
}

function authHeaders(): Record<string, string> {
  const token = getIdToken();
  if (!token) {
    throw new JournalClientError('UNAUTHENTICATED', 'Sign in required.', 401);
  }
  return { Authorization: `Bearer ${token}` };
}

function isJournalApiError(v: unknown): v is JournalApiError {
  if (typeof v !== 'object' || v === null) return false;
  const obj = v as Record<string, unknown>;
  if (typeof obj['error'] !== 'object' || obj['error'] === null) return false;
  const err = obj['error'] as Record<string, unknown>;
  return typeof err['code'] === 'string' && typeof err['message'] === 'string';
}

async function handleError(response: Response): Promise<never> {
  const body = await response.json().catch(() => null);
  if (isJournalApiError(body)) {
    throw new JournalClientError(body.error.code, body.error.message, response.status);
  }
  throw new JournalClientError(
    'UNKNOWN_ERROR',
    `Request failed with status ${response.status}`,
    response.status,
  );
}

export async function fetchPosts(
  city?: string,
  cursor?: string,
  signal?: AbortSignal,
): Promise<PostsResponse> {
  const params = new URLSearchParams();
  if (city) params.set('city', city);
  if (cursor) params.set('cursor', cursor);
  const qs = params.toString();
  const url = `/api/blog/posts${qs ? `?${qs}` : ''}`;
  const response = await fetch(url, { signal });
  if (!response.ok) await handleError(response);
  return response.json() as Promise<PostsResponse>;
}

export async function fetchPost(postId: string, signal?: AbortSignal): Promise<Post> {
  const response = await fetch(`/api/blog/posts/${encodeURIComponent(postId)}`, { signal });
  if (!response.ok) await handleError(response);
  return response.json() as Promise<Post>;
}

export async function createPost(payload: CreatePostPayload): Promise<CreatePostResponse> {
  const response = await fetch('/api/blog/posts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  });
  if (!response.ok) await handleError(response);
  return response.json() as Promise<CreatePostResponse>;
}

export async function deletePost(postId: string): Promise<void> {
  const response = await fetch(`/api/blog/posts/${encodeURIComponent(postId)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!response.ok && response.status !== 204) await handleError(response);
}

export async function fetchComments(postId: string, signal?: AbortSignal): Promise<CommentsResponse> {
  const response = await fetch(`/api/blog/posts/${encodeURIComponent(postId)}/comments`, { signal });
  if (!response.ok) await handleError(response);
  return response.json() as Promise<CommentsResponse>;
}

export async function createComment(postId: string, body: string): Promise<Comment> {
  const response = await fetch(`/api/blog/posts/${encodeURIComponent(postId)}/comments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ body }),
  });
  if (!response.ok) await handleError(response);
  return response.json() as Promise<Comment>;
}

export async function deleteComment(postId: string, commentId: string): Promise<void> {
  const response = await fetch(
    `/api/blog/posts/${encodeURIComponent(postId)}/comments/${encodeURIComponent(commentId)}`,
    { method: 'DELETE', headers: authHeaders() },
  );
  if (!response.ok && response.status !== 204) await handleError(response);
}

export async function reportPost(postId: string): Promise<void> {
  const response = await fetch(`/api/blog/posts/${encodeURIComponent(postId)}/report`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!response.ok) await handleError(response);
}

export async function requestUpload(contentType: string): Promise<UploadResponse> {
  const response = await fetch('/api/blog/uploads', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ contentType }),
  });
  if (!response.ok) await handleError(response);
  return response.json() as Promise<UploadResponse>;
}

export async function uploadFile(
  uploadUrl: string,
  fields: Record<string, string>,
  file: File,
): Promise<void> {
  const formData = new FormData();
  // Fields FIRST, file LAST
  for (const [key, value] of Object.entries(fields)) {
    formData.append(key, value);
  }
  formData.append('file', file);

  const response = await fetch(uploadUrl, {
    method: 'POST',
    body: formData,
    // NO custom headers, no credentials
  });
  if (response.status !== 201 && response.status !== 204 && !response.ok) {
    throw new JournalClientError('UPLOAD_FAILED', 'Image upload failed.', response.status);
  }
}

export async function fetchMe(signal?: AbortSignal): Promise<MeResponse> {
  const response = await fetch('/api/blog/me', {
    headers: authHeaders(),
    signal,
  });
  if (!response.ok) await handleError(response);
  return response.json() as Promise<MeResponse>;
}
