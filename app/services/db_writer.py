import asyncio
import logging
import multiprocessing as mp

from pymongo.collection import Collection

logger = logging.getLogger(__name__)

async def db_writer(count_queues: dict[int, mp.Queue], collection: Collection):
    logger.info('DB Writer started')
    try:
        while True:
            for camera_id, q in count_queues.items():
                try:
                    doc = q.get_nowait()
                    logger.debug(f'DB Writer inserting document: {doc}')
                    await asyncio.to_thread(collection.insert_one, doc)
                except Exception:
                    continue
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        logger.info('DB Writer cancelled')
        raise
