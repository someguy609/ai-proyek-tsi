import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO

from app.core import config
from app.media.tracks import create_track
from app.services import camera_worker
from app.routes import index_router, offer_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    workers = []
    cameras = config.MODEL_SOURCE
    for camera_id, camera_url in enumerate(cameras):
        track = create_track(camera_id + 1)
        worker = camera_worker.CameraWorker(
            camera_id,
            camera_url,
            YOLO(config.MODEL_PATH),
            track,
            [],
            None
        )
        await worker.start()
        workers.append(worker)
        # task = asyncio.create_task(camera_worker.camera_task(
        #     camera_id=camera_id,
        #     camera_url=camera_url,
        #     model=model,
        #     track=track
        # ))
        # inference_tasks.append(task)
    yield
    for worker in workers:
        await worker.stop()
    # await asyncio.gather(*inference_tasks, return_exceptions=True)

app = FastAPI(
    title=config.APP_NAME,
    debug=config.DEBUG,
    lifespan=lifespan
)

app.mount('/static', StaticFiles(directory='static'), name='static')
app.include_router(offer_router)
app.include_router(index_router)

app.add_middleware(CORSMiddleware,
                   allow_origins=config.CORS_ALLOW_ORIGINS,
                   allow_methods=config.CORS_ALLOW_METHODS,
                   allow_headers=config.CORS_ALLOW_HEADERS,
                   allow_credentials=config.CORS_ALLOW_CREDENTIALS)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app,
                host=config.APP_HOST,
                port=config.APP_PORT)
