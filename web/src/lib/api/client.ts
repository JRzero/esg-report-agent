export type ApiErrorBody = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
    request_id?: string;
  };
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId?: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export type ApiClientOptions = {
  baseUrl?: string;
  getAccessToken?: () => string | null;
};

export class ApiClient {
  private readonly baseUrl: string;
  private readonly getAccessToken?: () => string | null;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl =
      options.baseUrl ??
      process.env.NEXT_PUBLIC_SERVICE_BASE_URL ??
      'http://localhost:8000';
    this.getAccessToken = options.getAccessToken;
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    if (!headers.has('Accept')) headers.set('Accept', 'application/json');
    if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    const token = this.getAccessToken?.();
    if (token) headers.set('Authorization', `Bearer ${token}`);

    const response = await fetch(new URL(path, this.baseUrl), {
      ...init,
      headers,
      cache: 'no-store',
    });

    if (!response.ok) {
      let body: ApiErrorBody = {};
      try {
        body = (await response.json()) as ApiErrorBody;
      } catch {
        // Non-JSON upstream error.
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
}
