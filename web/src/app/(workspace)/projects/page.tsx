import {Button} from '@astryxdesign/core/Button';
import {ProjectList} from '@/components/projects/project-list';

export default function ProjectsPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">ESG 项目</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 opacity-65">
            一个项目对应一个企业、一个报告年度和一份 ESG 报告。
          </p>
        </div>
        <Button label="创建项目" variant="primary" href="/projects/new" />
      </header>

      <section className="mt-8">
        <ProjectList />
      </section>
    </div>
  );
}
