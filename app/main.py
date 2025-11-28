import asyncio
import multiprocessing as mp
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core import config
from app.database import connect_database, disconnect_database
from app.media.tracks import create_track
from app.services import camera_worker, webrtc_publisher
from app.routes import index_router, offer_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    connect_database(app)
    workers = []
    publishers = []
    cameras = config.MODEL_SOURCE
    for camera_id, camera_url in enumerate(cameras):
        track = create_track(camera_id + 1)
        frame_queue = mp.Queue(maxsize=1)
        locations = list(app.state.database['locations'].find({'camera_id': camera_id + 1}))
        print(locations)
        count_collection = app.state.database['customer_counts']
        worker = camera_worker.CameraWorker(
            camera_id,
            camera_url,
            config.MODEL_PATH,
            frame_queue,
            locations,
        )
        worker.start()
        workers.append(worker)
        publisher = asyncio.create_task(
            webrtc_publisher(camera_id, frame_queue, track)
        )
        publishers.append(publisher)
    yield
    disconnect_database(app)
    for task in publishers:
        task.cancel()
    asyncio.get_event_loop().run_until_complete(
        asyncio.gather(*publishers, return_exceptions=True)
    )
    for worker in workers:
        worker.stop()

    for worker in workers:
        worker.join(timeout=5)
        if worker.is_alive():
            worker.terminate()

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
