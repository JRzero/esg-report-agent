import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function GET() {
  return forwardServiceResponse(
    await serviceSessionFetch('/api/v1/projects'),
  );
}

export async function POST(request: Request) {
  const body = await request.text();
  return forwardServiceResponse(
    await serviceSessionFetch('/api/v1/projects', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body,
    }),
  );
}
