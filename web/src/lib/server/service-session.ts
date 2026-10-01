import {cookies} from 'next/headers';

const ACCESS_COOKIE = 'esg_access';
const REFRESH_COOKIE = 'esg_refresh';

type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

function serviceBaseUrl() {
  return (
    process.env.SERVICE_BASE_URL ??
    process.env.NEXT_PUBLIC_SERVICE_BASE_URL ??
    'http://localhost:8000'
  ).replace(/\/$/, '');
}

const cookieBase = {
  httpOnly: true,
  sameSite: 'lax' as const,
  secure: process.env.NODE_ENV === 'production',
  path: '/',
};

export async function setSessionTokens(tokens: TokenResponse) {
  const store = await cookies();
  store.set(ACCESS_COOKIE, tokens.access_token, {
    ...cookieBase,
    maxAge: tokens.expires_in,
  });
  store.set(REFRESH_COOKIE, tokens.refresh_token, {
    ...cookieBase,
    maxAge: 14 * 24 * 60 * 60,
  });
}

export async function clearSessionTokens() {
  const store = await cookies();
  store.delete(ACCESS_COOKIE);
  store.delete(REFRESH_COOKIE);
}

export async function hasSessionCookie() {
  const store = await cookies();
  return Boolean(store.get(ACCESS_COOKIE)?.value || store.get(REFRESH_COOKIE)?.value);
}

export async function servicePublicFetch(path: string, init: RequestInit = {}) {
  return fetch(`${serviceBaseUrl()}${path}`, {
    ...init,
    cache: 'no-store',
  });
}

async function refreshSession(refreshToken: string): Promise<TokenResponse | null> {
  const response = await servicePublicFetch('/api/v1/auth/refresh', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', Accept: 'application/json'},
    body: JSON.stringify({refresh_token: refreshToken}),
  });

  if (!response.ok) return null;
  return (await response.json()) as TokenResponse;
}

async function authorizedFetch(
  path: string,
  accessToken: string,
  init: RequestInit,
) {
  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${accessToken}`);
  if (!headers.has('Accept')) headers.set('Accept', 'application/json');
  return servicePublicFetch(path, {...init, headers});
}

export async function serviceSessionFetch(path: string, init: RequestInit = {}) {
  const store = await cookies();
  const accessToken = store.get(ACCESS_COOKIE)?.value;
  const refreshToken = store.get(REFRESH_COOKIE)?.value;

  if (!accessToken && !refreshToken) {
    return Response.json(
      {error: {code: 'AUTH_REQUIRED', message: 'Authentication required'}},
      {status: 401},
    );
  }

  if (accessToken) {
    const response = await authorizedFetch(path, accessToken, init);
    if (response.status !== 401) return response;
  }

  if (!refreshToken) {
    await clearSessionTokens();
    return Response.json(
      {error: {code: 'AUTH_REQUIRED', message: 'Authentication required'}},
      {status: 401},
    );
  }

  const refreshed = await refreshSession(refreshToken);
  if (!refreshed) {
    await clearSessionTokens();
    return Response.json(
      {error: {code: 'AUTH_EXPIRED', message: 'Session expired'}},
      {status: 401},
    );
  }

  await setSessionTokens(refreshed);
  return authorizedFetch(path, refreshed.access_token, init);
}

export async function forwardServiceResponse(response: Response) {
  const body = await response.text();
  return new Response(body, {
    status: response.status,
    headers: {
      'Content-Type':
        response.headers.get('content-type') ?? 'application/json; charset=utf-8',
    },
  });
}
