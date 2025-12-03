import asyncio
import multiprocessing as mp

from pymongo.collection import Collection

async def db_writer(count_queues: dict[int, mp.Queue], collection: Collection):
    print('[DB Writer] Started')
    try:
        while True:
            for camera_id, q in count_queues.items():
                try:
                    doc = q.get_nowait()
                    print('[DB Writer] Inserting document:', doc)
                    await asyncio.to_thread(collection.insert_one, doc)
                except Exception:
                    continue
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        print('[DB Writer] Cancelled')
        raise