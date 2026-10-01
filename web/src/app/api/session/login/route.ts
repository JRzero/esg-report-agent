import {NextResponse} from 'next/server';
import {
  servicePublicFetch,
  setSessionTokens,
} from '@/lib/server/service-session';

type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

export async function POST(request: Request) {
  const body = (await request.json()) as {email?: string; password?: string};
  if (!body.email || !body.password) {
    return NextResponse.json(
      {error: {code: 'VALIDATION_FAILED', message: 'Email and password are required'}},
      {status: 422},
    );
  }

  const response = await servicePublicFetch('/api/v1/auth/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', Accept: 'application/json'},
    body: JSON.stringify({email: body.email, password: body.password}),
  });

  if (!response.ok) {
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: {
        'Content-Type':
          response.headers.get('content-type') ?? 'application/json; charset=utf-8',
      },
    });
  }

  const tokens = (await response.json()) as TokenResponse;
  await setSessionTokens(tokens);
  return NextResponse.json({authenticated: true});
}
