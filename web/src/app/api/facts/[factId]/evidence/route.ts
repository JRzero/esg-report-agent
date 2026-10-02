import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function GET(
  _request: Request,
  {params}: {params: Promise<{factId: string}>},
) {
  const {factId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(`/api/v1/facts/${factId}/evidence`),
  );
}
