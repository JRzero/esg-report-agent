import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function POST(
  _request: Request,
  {
    params,
  }: {
    params: Promise<{sectionId: string; disclosureId: string}>;
  },
) {
  const {sectionId, disclosureId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(
      `/api/v1/sections/${sectionId}/disclosures/${disclosureId}`,
      {method: 'POST'},
    ),
  );
}

export async function DELETE(
  _request: Request,
  {
    params,
  }: {
    params: Promise<{sectionId: string; disclosureId: string}>;
  },
) {
  const {sectionId, disclosureId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(
      `/api/v1/sections/${sectionId}/disclosures/${disclosureId}`,
      {method: 'DELETE'},
    ),
  );
}
