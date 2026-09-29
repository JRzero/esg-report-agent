from typing import Type, TypeVar
from pydantic import BaseModel
import httpx
from app.core.config import get_settings
T=TypeVar('T', bound=BaseModel)
class LLMGateway:
    async def generate_structured(self,system:str,user:str,schema:Type[T],model_profile:str='STRONG')->T:
        s=get_settings()
        if not s.llm_base_url: raise RuntimeError('LLM_BASE_URL is not configured')
        payload={'model':s.llm_model,'messages':[{'role':'system','content':system},{'role':'user','content':user}],'response_format':{'type':'json_object'}}
        headers={'Authorization':f'Bearer {s.llm_api_key}','Content-Type':'application/json'}
        async with httpx.AsyncClient(timeout=120) as c:
            r=await c.post(s.llm_base_url.rstrip('/')+'/chat/completions',json=payload,headers=headers); r.raise_for_status(); data=r.json()
        import json
        content=data['choices'][0]['message']['content']
        return schema.model_validate(json.loads(content))
