import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function POST(
  request: Request,
  {params}: {params: Promise<{versionId: string}>},
) {
  const {versionId} = await params;
  const idempotencyKey = request.headers.get('Idempotency-Key');
  const headers = new Headers();
  if (idempotencyKey) headers.set('Idempotency-Key', idempotencyKey);

  return forwardServiceResponse(
    await serviceSessionFetch(
      `/api/v1/document-versions/${versionId}/extract-facts`,
      {method: 'POST', headers},
    ),
  );
}
