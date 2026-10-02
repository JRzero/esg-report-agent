'use client';

import {useState, type FormEvent} from 'react';
import {useRouter} from 'next/navigation';
import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {Selector} from '@astryxdesign/core/Selector';
import {TextInput} from '@astryxdesign/core/TextInput';
import {useCreateReport, useReports} from '@/lib/api/queries';

export function ReportList({projectId}: {projectId: string}) {
  const router = useRouter();
  const reports = useReports(projectId);
  const create = useCreateReport(projectId);
  const [title, setTitle] = useState('');
  const [language, setLanguage] = useState('zh-CN');
  const [message, setMessage] = useState('');

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setMessage('请输入报告名称');
      return;
    }
    setMessage('');
    try {
      const report = await create.mutateAsync({
        title: title.trim(),
        language,
      });
      router.push(`/projects/${projectId}/reports/${report.id}`);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : '创建报告失败');
    }
  }

  return (
    <div>
      <header>
        <h1 className="text-2xl font-semibold">报告</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 opacity-65">
          先建立报告与章节结构，再完成 Disclosure Mapping 和 Writing Plan。
          正文生成不在这一阶段直接启动。
        </p>
      </header>

      <section className="mt-6">
        <Card padding={5}>
          <form onSubmit={submit}>
            <h2 className="text-base font-semibold">创建报告</h2>
            <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_220px_auto] lg:items-end">
              <TextInput
                label="报告名称"
                value={title}
                onChange={setTitle}
                placeholder="例如 2026 ESG Report"
                width="100%"
                isRequired
              />
              <Selector
                label="语言"
                value={language}
                onChange={(value) => value && setLanguage(value)}
                options={[
                  {value: 'zh-CN', label: '简体中文'},
                  {value: 'en', label: 'English'},
                ]}
              />
              <Button
                label="创建报告"
                type="submit"
                variant="primary"
                isLoading={create.isPending}
              />
            </div>
            {message ? (
              <div className="mt-4 rounded-md border px-3 py-2 text-sm" role="status">
                {message}
              </div>
            ) : null}
          </form>
        </Card>
      </section>

      <section className="mt-8">
        <h2 className="text-base font-semibold">项目报告</h2>
        {!reports.isLoading && !reports.data?.length ? (
          <div className="py-10 text-sm opacity-60">当前项目还没有报告。</div>
        ) : null}
        <div className="mt-4 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {(reports.data ?? []).map((report) => (
            <Card key={report.id} padding={4}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-sm font-semibold">{report.title}</div>
                  <div className="mt-1 text-xs opacity-55">{report.language}</div>
                </div>
                <Badge label={report.status} variant="neutral" />
              </div>
              <div className="mt-4 text-xs opacity-55">
                创建于 {new Date(report.created_at).toLocaleString()}
              </div>
              <div className="mt-5">
                <Button
                  label="打开工作台"
                  variant="secondary"
                  href={`/projects/${projectId}/reports/${report.id}`}
                />
              </div>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
