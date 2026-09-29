from dataclasses import dataclass
import httpx
from app.core.config import get_settings

@dataclass
class ContextSearchResult:
    uri:str
    content:str=''
    abstract:str=''
    score:float|None=None
    metadata:dict|None=None

class OpenVikingAdapter:
    """Thin HTTP adapter over the public OpenViking API.

    Raw HTTP local-file ingestion uses temp_upload then add_resource, matching the
    documented server contract. Business code never depends on raw response shapes.
    """
    def __init__(self):
        s=get_settings(); self.base=s.openviking_base_url.rstrip('/')
        self.headers={'X-API-Key':s.openviking_api_key} if s.openviking_api_key else {}

    async def upload_temp(self, filename:str, data:bytes)->str:
        async with httpx.AsyncClient(timeout=60) as c:
            r=await c.post(f'{self.base}/api/v1/resources/temp_upload', files={'file':(filename,data)}, headers=self.headers)
            r.raise_for_status(); payload=r.json()
        return payload['result']['temp_file_id']

    async def add_bytes(self, filename:str, data:bytes, to_uri:str, reason:str='ESG project evidence')->dict:
        temp_id=await self.upload_temp(filename,data)
        body={'temp_file_id':temp_id,'to':to_uri,'reason':reason,'wait':False}
        async with httpx.AsyncClient(timeout=60) as c:
            r=await c.post(f'{self.base}/api/v1/resources',json=body,headers={**self.headers,'Content-Type':'application/json'})
            r.raise_for_status(); payload=r.json()
        return payload.get('result',payload)

    async def get_task(self,task_id:str)->dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.get(f'{self.base}/api/v1/tasks/{task_id}',headers=self.headers); r.raise_for_status(); payload=r.json()
        return payload.get('result',payload)

    async def find(self,query:str,target_uri:str,limit:int=10)->list[ContextSearchResult]:
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.post(f'{self.base}/api/v1/search/find',json={'query':query,'target_uri':target_uri,'limit':limit},headers={**self.headers,'Content-Type':'application/json'}); r.raise_for_status(); data=r.json()
        payload=data.get('result',data)
        rows=payload.get('results',payload if isinstance(payload,list) else [])
        return [ContextSearchResult(uri=x.get('uri',''),content=x.get('content',''),abstract=x.get('abstract',''),score=x.get('score'),metadata=x) for x in rows]
