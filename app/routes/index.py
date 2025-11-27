import os
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/", include_in_schema=False)
async def root():
    return FileResponse(os.path.join("static", "index.html"))


@router.get('/health')
async def health():
    return {
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
    }
