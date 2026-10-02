import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function PATCH(
  request: Request,
  {params}: {params: Promise<{itemId: string}>},
) {
  const {itemId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(`/api/v1/missing-items/${itemId}`, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: await request.text(),
    }),
  );
}
