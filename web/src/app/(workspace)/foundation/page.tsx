import {
  AIAction,
  CitationMarker,
  EvidenceCard,
  FactCard,
  GRICoverage,
  MissingItemCard,
} from '@/components/domain';

export default function FoundationPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <header>
        <div className="text-xs font-semibold uppercase tracking-widest opacity-50">
          Spec 009
        </div>
        <h1 className="mt-2 text-2xl font-semibold">Frontend Foundation</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 opacity-70">
          Astryx 负责基础 UI 语言，ESG Domain Components 负责 Evidence、Fact、
          GRI、Missing Data、Citation 与 AI 的业务语义。
        </p>
      </header>

      <section className="mt-8">
        <h2 className="text-base font-semibold">Evidence / Reference Boundary</h2>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <EvidenceCard
            sourceType="EVIDENCE"
            fileName="2026年度能源统计表.xlsx"
            locator="Sheet: 能源消耗 · Cell: B17"
            excerpt="年度购入电力 1,250,000 kWh。"
            usedBy="GRI 302-1 / Energy"
          />
          <EvidenceCard
            sourceType="REFERENCE"
            fileName="行业优秀ESG报告.pdf"
            locator="Page 42"
            excerpt="行业报告采用按环境主题组织的章节结构。"
            usedBy="写作结构参考"
          />
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-base font-semibold">Fact Center</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <FactCard
            name="员工总人数"
            value={1287}
            unit="人"
            period="2026"
            scope="集团"
            status="CONFIRMED"
            evidenceCount={2}
          />
          <FactCard
            name="Scope 1 排放"
            value="1,200"
            unit="tCO2e"
            period="2026"
            scope="集团"
            status="PENDING"
            evidenceCount={1}
          />
          <FactCard
            name="可再生电力占比"
            value="35"
            unit="%"
            period="2026"
            scope="集团"
            status="CONFLICT"
            evidenceCount={3}
          />
        </div>
      </section>

      <section className="mt-8 grid gap-4 lg:grid-cols-2">
        <div>
          <h2 className="text-base font-semibold">GRI Coverage</h2>
          <div className="mt-4">
            <GRICoverage
              code="GRI 2-7"
              title="Employees"
              covered={3}
              total={4}
              status="PARTIAL"
            />
          </div>
        </div>
        <div>
          <h2 className="text-base font-semibold">Missing Data</h2>
          <div className="mt-4">
            <MissingItemCard
              name="员工性别构成"
              description="GRI 2-7 要求披露按性别划分的员工人数，当前项目尚未形成已确认 Fact。"
              priority="HIGH"
              status="REQUESTED"
              suggestedMaterial="HR员工统计表"
            />
          </div>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-base font-semibold">Citation / AI</h2>
        <div className="mt-4 flex flex-col gap-4">
          <div>
            <CitationMarker index={1} label="能源统计表.xlsx · B17" />
          </div>
          <AIAction
            actions={[
              'rewrite',
              'shorten',
              'regenerate-from-evidence',
              'consistency-check',
            ]}
          />
        </div>
      </section>
    </div>
  );
}
