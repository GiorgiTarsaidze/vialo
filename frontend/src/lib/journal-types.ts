/**
 * Journal (blog) API types — mirrors backend camelCase JSON contract.
 */
import type { ItineraryResponse } from './types';

export interface Author {
  userId: string;
  displayName: string;
}

export interface PostSummary {
  postId: string;
  title: string;
  city: string;
  cityKey: string;
  excerpt: string;
  coverImageUrl: string | null;
  author: Author;
  createdAt: string;
  commentCount: number;
  hasRoute: boolean;
  stopCount: number;
}

export interface Post extends PostSummary {
  body: string;
  itinerary: ItineraryResponse | null;
}

export interface Comment {
  commentId: string;
  postId: string;
  author: Author;
  body: string;
  createdAt: string;
}

export interface PostsResponse {
  posts: PostSummary[];
  nextCursor: string | null;
}

export interface CreatePostPayload {
  title: string;
  city: string;
  body: string;
  coverImageKey?: string;
  itinerary?: ItineraryResponse;
}

export interface CreatePostResponse {
  post: Post;
}

export interface CommentsResponse {
  comments: Comment[];
}

export interface UploadResponse {
  uploadUrl: string;
  fields: Record<string, string>;
  imageKey: string;
  maxBytes: number;
  expiresInSeconds: number;
}

export interface MeResponse {
  author: Author;
  posts: PostSummary[];
  postsRemainingToday: number;
}

export interface JournalApiError {
  error: {
    code: string;
    message: string;
  };
}

/** Slugify a city name exactly as the backend does. */
export function slugifyCity(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/\s+/g, ' ')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}
