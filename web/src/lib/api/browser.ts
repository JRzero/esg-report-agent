import {ApiError, type ApiErrorBody} from './client';

export async function browserRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has('Accept')) headers.set('Accept', 'application/json');
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(path, {...init, headers, cache: 'no-store'});
  if (!response.ok) {
    let body: ApiErrorBody = {};
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // Ignore upstream non-JSON errors.
    }
    throw new ApiError(
      response.status,
      body.error?.code ?? 'HTTP_ERROR',
      body.error?.message ?? `Request failed with HTTP ${response.status}`,
      body.error?.request_id,
      body.error?.details,
    );
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
