import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function POST(
  _request: Request,
  {params}: {params: Promise<{versionId: string}>},
) {
  const {versionId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(
      `/api/v1/document-versions/${versionId}/reprocess`,
      {method: 'POST'},
    ),
  );
}
