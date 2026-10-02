import {MaterialList} from '@/components/materials/material-list';
import {MaterialUploadPanel} from '@/components/materials/material-upload-panel';

export default async function MaterialsPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;

  return (
    <div>
      <header>
        <h1 className="text-2xl font-semibold">资料中心</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 opacity-65">
          管理企业 Evidence、历史资料、报告准则和行业 Reference。原文件进入对象存储，
          Anchor 与业务状态由 Service 管理。
        </p>
      </header>

      <section className="mt-6">
        <MaterialUploadPanel projectId={projectId} />
      </section>

      <section className="mt-8">
        <h2 className="text-base font-semibold">项目资料</h2>
        <div className="mt-4">
          <MaterialList projectId={projectId} />
        </div>
      </section>
    </div>
  );
}
