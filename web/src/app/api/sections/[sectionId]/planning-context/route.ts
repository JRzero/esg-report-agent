import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function GET(
  _request: Request,
  {params}: {params: Promise<{sectionId: string}>},
) {
  const {sectionId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(
      `/api/v1/sections/${sectionId}/planning-context`,
    ),
  );
}
