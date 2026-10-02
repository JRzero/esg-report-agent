'use client';

import {useState, type FormEvent} from 'react';
import {useRouter} from 'next/navigation';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {FileInput} from '@astryxdesign/core/FileInput';
import {Selector} from '@astryxdesign/core/Selector';
import {TextInput} from '@astryxdesign/core/TextInput';
import {useUploadDocument} from '@/lib/api/queries';
import type {DocumentSourceType} from '@/lib/api/types';
import {materialSourcePolicy} from '@/lib/materials/source-policy';

const sourceOptions = (Object.keys(materialSourcePolicy) as DocumentSourceType[]).map(
  (value) => ({
    value,
    label: materialSourcePolicy[value].label,
    description: materialSourcePolicy[value].description,
  }),
);

export function MaterialUploadPanel({projectId}: {projectId: string}) {
  const router = useRouter();
  const upload = useUploadDocument(projectId);
  const [file, setFile] = useState<File | null>(null);
  const [sourceType, setSourceType] = useState<DocumentSourceType>('EVIDENCE');
  const [categoryCode, setCategoryCode] = useState('');
  const [error, setError] = useState('');

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError('请选择要上传的文件');
      return;
    }
    setError('');
    const formData = new FormData();
    formData.set('file', file);
    formData.set('source_type', sourceType);
    if (categoryCode.trim()) formData.set('category_code', categoryCode.trim());

    try {
      const result = await upload.mutateAsync(formData);
      router.push(`/projects/${projectId}/materials/${result.document_id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '上传失败');
    }
  }

  return (
    <Card padding={5}>
      <form onSubmit={submit}>
        <h2 className="text-base font-semibold">上传资料</h2>
        <p className="mt-1 text-sm opacity-65">
          上传前先确定资料角色。Reference 和 Standard 不会作为当前企业 Fact 的证据来源。
        </p>

        <div className="mt-5 grid gap-4 lg:grid-cols-[1.3fr_0.8fr_0.8fr]">
          <FileInput
            label="文件"
            value={file}
            onChange={(value) =>
              setFile(Array.isArray(value) ? value[0] ?? null : value)
            }
            accept=".pdf,.docx,.xlsx,.xlsm,.pptx,.txt,.md,.csv"
            maxSize={50 * 1024 * 1024}
            mode="dropzone"
            description="PDF、DOCX、XLSX/XLSM、PPTX、TXT、MD、CSV；最大 50 MB"
            isRequired
          />
          <Selector
            label="资料类型"
            options={sourceOptions}
            value={sourceType}
            onChange={(value) => value && setSourceType(value as DocumentSourceType)}
          />
          <TextInput
            label="分类编码"
            value={categoryCode}
            onChange={setCategoryCode}
            placeholder="例如 employees"
            isOptional
          />
        </div>

        <div className="mt-4 rounded-md border px-3 py-2 text-xs opacity-75">
          {materialSourcePolicy[sourceType].description}
        </div>

        {error ? <div className="mt-4 text-sm" role="alert">{error}</div> : null}

        <div className="mt-5">
          <Button
            label="上传并解析"
            type="submit"
            variant="primary"
            isLoading={upload.isPending}
          />
        </div>
      </form>
    </Card>
  );
}
