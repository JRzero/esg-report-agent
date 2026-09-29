from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api.router import router
from app.core.config import get_settings
from app.core.errors import DomainError
s=get_settings()
app=FastAPI(title=s.app_name,version='0.1.0')
app.include_router(router)
@app.exception_handler(DomainError)
async def domain_error(request:Request,exc:DomainError):
    rid=request.headers.get('X-Request-ID',str(uuid4()))
    return JSONResponse(status_code=exc.status_code,content={'error':{'code':exc.code,'message':exc.message,'details':exc.details,'request_id':rid}})
@app.get('/health',tags=['Health'])
async def health(): return {'status':'ok'}
@app.get('/ready',tags=['Health'])
async def ready(): return {'status':'ready'}
