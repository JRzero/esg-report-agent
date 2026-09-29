import asyncio
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.models import User,Tenant,TenantMembership,MetricDefinition,Standard,StandardVersion,Disclosure,DisclosureRequirement
async def main():
    async with SessionLocal() as s:
        async with s.begin():
            tenant=await s.scalar(select(Tenant).where(Tenant.code=='demo'))
            if not tenant: tenant=Tenant(name='Demo ESG Consulting',code='demo'); s.add(tenant); await s.flush()
            user=await s.scalar(select(User).where(User.email=='admin@example.com'))
            if not user: user=User(email='admin@example.com',name='Admin',password_hash=hash_password('admin123')); s.add(user); await s.flush()
            m=await s.scalar(select(TenantMembership).where(TenantMembership.tenant_id==tenant.id,TenantMembership.user_id==user.id))
            if not m: s.add(TenantMembership(tenant_id=tenant.id,user_id=user.id,tenant_role='ADMIN'))
            for code,name,typ,unit in [('EMPLOYEE_TOTAL','Employee total','NUMBER','person'),('GHG_SCOPE1','Scope 1 emissions','NUMBER','tCO2e'),('GHG_SCOPE2','Scope 2 emissions','NUMBER','tCO2e'),('ENERGY_CONSUMPTION','Energy consumption','NUMBER','MWh')]:
                if not await s.scalar(select(MetricDefinition).where(MetricDefinition.tenant_id.is_(None),MetricDefinition.code==code)): s.add(MetricDefinition(code=code,name=name,data_type=typ,default_unit=unit))
            std=await s.scalar(select(Standard).where(Standard.code=='GRI'))
            if not std: std=Standard(code='GRI',name='GRI Standards',publisher='Global Reporting Initiative'); s.add(std); await s.flush()
            ver=await s.scalar(select(StandardVersion).where(StandardVersion.standard_id==std.id,StandardVersion.version_code=='2021'))
            if not ver: ver=StandardVersion(standard_id=std.id,version_code='2021',name='GRI 2021'); s.add(ver); await s.flush()
            if not await s.scalar(select(Disclosure).where(Disclosure.standard_version_id==ver.id,Disclosure.code=='GRI 2-7')):
                d=Disclosure(standard_version_id=ver.id,code='GRI 2-7',title='Employees'); s.add(d); await s.flush(); s.add_all([DisclosureRequirement(disclosure_id=d.id,requirement_code='a',content='Report the total number of employees.',required_data_json={'metric_codes':['EMPLOYEE_TOTAL']}),DisclosureRequirement(disclosure_id=d.id,requirement_code='b',content='Report breakdowns required by the standard.')])
    print('seed complete: admin@example.com / admin123')
if __name__=='__main__': asyncio.run(main())
