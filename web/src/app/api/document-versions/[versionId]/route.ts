import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function GET(
  _request: Request,
  {params}: {params: Promise<{versionId: string}>},
) {
  const {versionId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(`/api/v1/document-versions/${versionId}`),
  );
}
