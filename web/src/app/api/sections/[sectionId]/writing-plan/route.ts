import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function PUT(
  request: Request,
  {params}: {params: Promise<{sectionId: string}>},
) {
  const {sectionId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(`/api/v1/sections/${sectionId}/writing-plan`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: await request.text(),
    }),
  );
}
