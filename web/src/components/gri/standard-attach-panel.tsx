'use client';

import {useMemo, useState} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {Selector} from '@astryxdesign/core/Selector';
import {
  useAttachStandard,
  useProjectStandards,
  useStandards,
  useStandardVersions,
} from '@/lib/api/queries';

export function StandardAttachPanel({projectId}: {projectId: string}) {
  const standards = useStandards();
  const attached = useProjectStandards(projectId);
  const [selectedStandardId, setSelectedStandardId] = useState('');
  const [selectedVersionId, setSelectedVersionId] = useState('');
  const [message, setMessage] = useState('');

  const effectiveStandardId =
    selectedStandardId || standards.data?.[0]?.id || '';
  const versions = useStandardVersions(effectiveStandardId);
  const effectiveVersionId =
    selectedVersionId ||
    versions.data?.find((version) => version.status === 'ACTIVE')?.id ||
    versions.data?.[0]?.id ||
    '';
  const attach = useAttachStandard(projectId);

  const attachedVersionIds = useMemo(
    () => new Set((attached.data ?? []).map((item) => item.version.id)),
    [attached.data],
  );

  async function attachSelected() {
    if (!effectiveVersionId) return;
    setMessage('');
    try {
      await attach.mutateAsync(effectiveVersionId);
      setMessage('标准版本已挂载到项目。');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : '标准挂载失败');
    }
  }

  return (
    <Card padding={5}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold">项目报告标准</h2>
          <p className="mt-1 text-sm leading-6 opacity-65">
            挂载标准版本后，Service 会为项目创建 Disclosure 与 Requirement 状态。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(attached.data ?? []).map((item) => (
            <Badge
              key={item.id}
              label={`${item.standard.code} ${item.version.version_code}`}
              variant={item.is_primary ? 'blue' : 'neutral'}
            />
          ))}
        </div>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_1fr_auto] lg:items-end">
        <Selector
          label="标准"
          options={(standards.data ?? []).map((standard) => ({
            value: standard.id,
            label: `${standard.code} · ${standard.name}`,
            description: standard.publisher ?? undefined,
          }))}
          value={effectiveStandardId}
          onChange={(value) => {
            if (!value) return;
            setSelectedStandardId(value);
            setSelectedVersionId('');
          }}
          emptyText="当前没有可用标准"
        />
        <Selector
          label="版本"
          options={(versions.data ?? []).map((version) => ({
            value: version.id,
            label: `${version.version_code} · ${version.name}`,
            description:
              version.status === 'ACTIVE'
                ? 'Active'
                : version.status,
          }))}
          value={effectiveVersionId}
          onChange={(value) => value && setSelectedVersionId(value)}
          emptyText="该标准没有可用版本"
        />
        <Button
          label={
            attachedVersionIds.has(effectiveVersionId)
              ? '已挂载'
              : '挂载到项目'
          }
          variant="secondary"
          onClick={attachSelected}
          isLoading={attach.isPending}
          isDisabled={
            !effectiveVersionId ||
            attachedVersionIds.has(effectiveVersionId)
          }
        />
      </div>

      {message ? (
        <div className="mt-4 rounded-md border px-3 py-2 text-sm" role="status">
          {message}
        </div>
      ) : null}
    </Card>
  );
}
