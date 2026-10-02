import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function GET(
  _request: Request,
  {params}: {params: Promise<{groupId: string}>},
) {
  const {groupId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(`/api/v1/fact-conflicts/${groupId}`),
  );
}
