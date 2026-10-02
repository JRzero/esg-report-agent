'use client';

import {useState} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {FileInput} from '@astryxdesign/core/FileInput';
import {Selector} from '@astryxdesign/core/Selector';
import {
  getDocumentDownloadUrl,
  useDocument,
  useExtractFacts,
  useReprocessVersion,
  useUploadDocumentVersion,
} from '@/lib/api/queries';
import {
  canExtractFacts,
  materialSourcePolicy,
} from '@/lib/materials/source-policy';
import {formatFileSize} from '@/lib/materials/anchor-locator';
import {AnchorViewer} from './anchor-viewer';
import {ProjectTaskPanel} from './project-task-panel';

const statusVariant: Record<
  string,
  'neutral' | 'warning' | 'green' | 'error'
> = {
  PENDING: 'warning',
  PROCESSING: 'warning',
  READY: 'green',
  SUCCESS: 'green',
  DISABLED: 'neutral',
  FAILED: 'error',
};

function StatusBadge({label, value}: {label: string; value: string}) {
  return (
    <div>
      <div className="text-xs opacity-50">{label}</div>
      <div className="mt-1">
        <Badge label={value} variant={statusVariant[value] ?? 'neutral'} />
      </div>
    </div>
  );
}

export function DocumentEvidenceViewer({
  projectId,
  documentId,
  initialVersionId,
  focusAnchorId,
}: {
  projectId: string;
  documentId: string;
  initialVersionId?: string;
  focusAnchorId?: string;
}) {
  const detail = useDocument(documentId);
  const [selectedVersionId, setSelectedVersionId] = useState(initialVersionId ?? '');
  const [newVersionFile, setNewVersionFile] = useState<File | null>(null);
  const [message, setMessage] = useState('');

  const versions = detail.data?.versions ?? [];
  const document = detail.data?.document;
  const effectiveVersionId =
    selectedVersionId || versions[0]?.id || '';
  const selectedVersion =
    versions.find((item) => item.id === effectiveVersionId) ?? versions[0];

  const uploadVersion = useUploadDocumentVersion(documentId);
  const reprocess = useReprocessVersion(documentId, selectedVersion?.id ?? '');
  const extract = useExtractFacts(projectId, documentId, selectedVersion?.id ?? '');

  if (detail.isLoading || !document) {
    return <div className="py-10 text-sm opacity-60">正在加载资料详情…</div>;
  }

  const policy = materialSourcePolicy[document.source_type];
  const extractionAllowed =
    canExtractFacts(document.source_type) &&
    selectedVersion?.evidence_parse_status === 'READY';

  async function download() {
    if (!selectedVersion) return;
    setMessage('');
    try {
      const result = await getDocumentDownloadUrl(selectedVersion.id);
      window.open(result.download_url, '_blank', 'noopener,noreferrer');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : '下载链接获取失败');
    }
  }

  async function uploadNewVersion() {
    if (!newVersionFile) {
      setMessage('请选择新版本文件');
      return;
    }
    setMessage('');
    try {
      const result = await uploadVersion.mutateAsync(newVersionFile);
      setNewVersionFile(null);
      setSelectedVersionId(result.version_id);
      setMessage('新版本已上传，正在解析。');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : '版本上传失败');
    }
  }

  async function reprocessCurrent() {
    if (!selectedVersion) return;
    setMessage('');
    try {
      await reprocess.mutateAsync();
      setMessage('已重新提交解析任务。');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : '重新解析失败');
    }
  }

  async function extractFacts() {
    if (!selectedVersion || !extractionAllowed) return;
    setMessage('');
    try {
      const result = await extract.mutateAsync();
      setMessage(`Fact Extraction 已入队：${result.task_id}`);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Fact Extraction 提交失败');
    }
  }

  return (
    <div>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="truncate text-2xl font-semibold">{document.name}</h1>
            <Badge label={policy.label} variant={policy.badge} />
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 opacity-65">
            {policy.description}
          </p>
        </div>
      </header>

      {document.source_type !== 'EVIDENCE' ? (
        <Card padding={4}>
          <div className="text-sm font-semibold">Source Boundary</div>
          <div className="mt-2 text-sm leading-6 opacity-70">{policy.description}</div>
          {document.source_type === 'REFERENCE' ||
          document.source_type === 'STANDARD' ? (
            <div className="mt-2 text-xs font-medium">
              此资料不会在 UI 中开放 Fact Extraction。
            </div>
          ) : null}
        </Card>
      ) : null}

      <section className="mt-6 grid gap-4 xl:grid-cols-[1fr_340px]">
        <Card padding={5}>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold">Document Version</h2>
              <p className="mt-1 text-sm opacity-60">
                原文件版本不可变；上传新版本会创建新的 Version。
              </p>
            </div>
            <Selector
              label="版本"
              isLabelHidden
              options={versions.map((version) => ({
                value: version.id,
                label: `v${version.version_no} · ${version.original_filename}`,
              }))}
              value={selectedVersion?.id ?? ''}
              onChange={(value) => value && setSelectedVersionId(value)}
              width={280}
            />
          </div>

          {selectedVersion ? (
            <>
              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatusBadge label="Validation" value={selectedVersion.validation_status} />
                <StatusBadge label="Evidence Parse" value={selectedVersion.evidence_parse_status} />
                <StatusBadge label="Context" value={selectedVersion.context_status} />
                <StatusBadge label="Classification" value={selectedVersion.classification_status} />
              </div>

              <div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-xs opacity-60">
                <span>{selectedVersion.file_extension?.toUpperCase() ?? 'FILE'}</span>
                <span>{formatFileSize(selectedVersion.file_size)}</span>
                <span>SHA256 {selectedVersion.sha256.slice(0, 12)}…</span>
                <span>上传：{new Date(selectedVersion.uploaded_at).toLocaleString()}</span>
              </div>

              {selectedVersion.parse_error ? (
                <div className="mt-4 rounded-md border px-3 py-2 text-sm">
                  {selectedVersion.parse_error}
                </div>
              ) : null}

              <div className="mt-5 flex flex-wrap gap-2">
                <Button label="下载原文件" variant="secondary" onClick={download} />
                <Button
                  label="重新解析"
                  variant="secondary"
                  onClick={reprocessCurrent}
                  isLoading={reprocess.isPending}
                />
                <Button
                  label="提取 Fact"
                  variant="primary"
                  onClick={extractFacts}
                  isLoading={extract.isPending}
                  isDisabled={!extractionAllowed}
                />
              </div>

              {!extractionAllowed ? (
                <div className="mt-3 text-xs opacity-60">
                  {canExtractFacts(document.source_type)
                    ? 'Evidence Parse 必须 READY 后才能触发 Fact Extraction。'
                    : `${policy.label} 不允许作为当前企业 Fact Extraction 来源。`}
                </div>
              ) : null}
            </>
          ) : null}
        </Card>

        <Card padding={4}>
          <h2 className="text-base font-semibold">上传新版本</h2>
          <p className="mt-1 text-xs leading-5 opacity-60">
            新文件保留同一 Document 身份，但生成新的不可变 DocumentVersion。
          </p>
          <div className="mt-4">
            <FileInput
              label="新版本文件"
              value={newVersionFile}
              onChange={(value) =>
                setNewVersionFile(Array.isArray(value) ? value[0] ?? null : value)
              }
              accept=".pdf,.docx,.xlsx,.xlsm,.pptx,.txt,.md,.csv"
              maxSize={50 * 1024 * 1024}
              width="100%"
            />
          </div>
          <div className="mt-4">
            <Button
              label="上传版本"
              variant="secondary"
              onClick={uploadNewVersion}
              isLoading={uploadVersion.isPending}
              isDisabled={!newVersionFile}
            />
          </div>
        </Card>
      </section>

      {message ? (
        <div className="mt-4 rounded-md border px-3 py-2 text-sm" role="status">
          {message}
        </div>
      ) : null}

      <div className="mt-8 grid gap-8 xl:grid-cols-[minmax(0,1fr)_360px]">
        {selectedVersion ? (
          <AnchorViewer
            versionId={selectedVersion.id}
            focusAnchorId={
              selectedVersion.id === initialVersionId ? focusAnchorId : undefined
            }
          />
        ) : null}
        <ProjectTaskPanel projectId={projectId} />
      </div>
    </div>
  );
}
