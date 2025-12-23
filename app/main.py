import asyncio
import logging
import multiprocessing as mp
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core import config
from app.database import connect_database, disconnect_database
from app.media.tracks import create_track
from app.services import camera_worker, db_writer, webrtc_publisher
from app.routes import index_router, offer_router

logging.basicConfig(level=logging.INFO, format='%(levelname)s: \t%(message)s')
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Connecting to database and starting workers")
    connect_database(app)
    workers = []
    publishers = []
    cameras = config.MODEL_SOURCE
    frame_queues = []
    count_queues = {}

    for camera_id, camera_url in enumerate(cameras):
        logger.info(f"Starting worker for camera {camera_id + 1}: {camera_url}")
        track = create_track(camera_id + 1)
        frame_queue = mp.Queue(maxsize=1)
        frame_queues.append(frame_queue)
        counts_queue = mp.Queue()
        count_queues[camera_id + 1] = counts_queue
        locations = list(app.state.database['locations'].find(
            {'camera_id': camera_id + 1}))
        worker = camera_worker.CameraWorker(
            camera_id + 1,
            camera_url,
            config.MODEL_PATH,
            frame_queue,
            counts_queue,
            locations,
        )
        worker.daemon = True
        worker.start()
        workers.append(worker)
        publisher = asyncio.create_task(
            webrtc_publisher(camera_id, frame_queue, track)
        )
        publishers.append(publisher)

    count_collection = app.state.database['customer_counts']
    db_task = asyncio.create_task(db_writer(count_queues, count_collection))

    yield

    disconnect_database(app)

    for worker in workers:
        worker.stop()

    for q in frame_queues:
        try:
            q.put_nowait(None)
        except Exception:
            pass

    for task in publishers:
        task.cancel()

    await asyncio.gather(*publishers, return_exceptions=True)

    for worker in workers:
        worker.join(timeout=5)
        if worker.is_alive():
            worker.terminate()

    db_task.cancel()
    await asyncio.gather(db_task, return_exceptions=True)

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
