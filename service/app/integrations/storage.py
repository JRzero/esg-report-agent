from pathlib import Path
from typing import Protocol
from app.core.config import get_settings
class ObjectStorage(Protocol):
    async def put(self,key:str,data:bytes,content_type:str|None=None)->None: ...
    async def get(self,key:str)->bytes: ...
    async def signed_download_url(self,key:str,expires:int=900)->str: ...
class LocalStorage:
    def __init__(self,path:str): self.root=Path(path); self.root.mkdir(parents=True,exist_ok=True)
    async def put(self,key,data,content_type=None): p=self.root/key; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data)
    async def get(self,key): return (self.root/key).read_bytes()
    async def signed_download_url(self,key,expires=900): return f'file://{(self.root/key).absolute()}'
def storage()->ObjectStorage:
    s=get_settings()
    if s.storage_backend=='minio':
        try:
            from minio import Minio
            class MinioStorage:
                def __init__(self):
                    self.client=Minio(s.minio_endpoint,access_key=s.minio_access_key,secret_key=s.minio_secret_key,secure=s.minio_secure); self.bucket=s.minio_bucket
                    if not self.client.bucket_exists(self.bucket): self.client.make_bucket(self.bucket)
                async def put(self,key,data,content_type=None):
                    from io import BytesIO
                    self.client.put_object(self.bucket,key,BytesIO(data),len(data),content_type=content_type or 'application/octet-stream')
                async def get(self,key):
                    r=self.client.get_object(self.bucket,key)
                    try: return r.read()
                    finally: r.close(); r.release_conn()
                async def signed_download_url(self,key,expires=900):
                    from datetime import timedelta
                    return self.client.presigned_get_object(self.bucket,key,expires=timedelta(seconds=expires))
            return MinioStorage()
        except ImportError: pass
    return LocalStorage(s.local_storage_path)
