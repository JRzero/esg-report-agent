import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function POST(
  request: Request,
  {params}: {params: Promise<{factId: string}>},
) {
  const {factId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(`/api/v1/facts/${factId}/reject`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: await request.text(),
    }),
  );
}
