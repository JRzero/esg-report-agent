import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function POST(
  request: Request,
  {params}: {params: Promise<{sectionId: string}>},
) {
  const {sectionId} = await params;
  const headers = new Headers();
  const key = request.headers.get('Idempotency-Key');
  if (key) headers.set('Idempotency-Key', key);
  return forwardServiceResponse(
    await serviceSessionFetch(
      `/api/v1/sections/${sectionId}/ai/writing-plan`,
      {method: 'POST', headers},
    ),
  );
}
