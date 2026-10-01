import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function GET() {
  return forwardServiceResponse(
    await serviceSessionFetch('/api/v1/auth/me'),
  );
}
