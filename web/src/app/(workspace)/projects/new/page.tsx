import {ProjectCreateForm} from '@/components/projects/project-create-form';

export default function NewProjectPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <header>
        <div className="text-xs font-semibold uppercase tracking-widest opacity-50">
          Project
        </div>
        <h1 className="mt-2 text-2xl font-semibold">创建 ESG 项目</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 opacity-65">
          项目创建后，所有资料、Fact、GRI Mapping、报告内容和成员权限都以 Project 为边界。
        </p>
      </header>

      <section className="mt-8">
        <ProjectCreateForm />
      </section>
    </div>
  );
}
