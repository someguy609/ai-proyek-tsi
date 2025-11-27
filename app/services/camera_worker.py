import asyncio
from datetime import datetime
import threading
import time

from pymongo.collection import Collection
from ultralytics import YOLO

from app.media.tracks import AnnotatedFrameTrack
from app.utils.count_objects import count_objects_in_regions


class CameraWorker:

    def __init__(
            self,
            camera_id: int,
            camera_url: str,
            model: YOLO,
            track: AnnotatedFrameTrack,
            regions: list[dict],
            collection: Collection | None,
    ):
        self.camera_id = camera_id
        self.camera_url = camera_url
        self.model = model
        self.track = track
        self.regions = regions
        self.collection = collection

        self._yolo_task = None
        self._counts_task = None
        self._stop_event = asyncio.Event()

        self._results_queue = asyncio.Queue(maxsize=1)
        self._counts_queue = asyncio.Queue(maxsize=64)

    async def _yolo_worker(self) -> None:
        loop = asyncio.get_running_loop()

        def run():
            while not self._stop_event.is_set():
                try:
                    for result in self.model.track(
                        source=self.camera_url,
                        tracker='bytetrack.yaml',
                        stream=True,
                        persist=False,
                        conf=0.7,
                    ):
                        if self._stop_event.is_set():
                            break
                        asyncio.run_coroutine_threadsafe(
                            self.track.update(result), loop
                        )
                        try:
                            self._results_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        self._results_queue.put_nowait(result)
                except Exception as e:
                    print('[YOLO Worker] Exception: ', e)
        await asyncio.to_thread(run)

    async def _count_worker(self, interval: float = 1.0) -> None:
        # loop = asyncio.get_running_loop()
        while not self._stop_event.is_set():
            await asyncio.sleep(interval)
            try:
                result = await self._results_queue.get()
                if result is None:
                    continue
                counts = 1 # todo fix later
                # try:
                #     raise
                # except:
                #     counts = 1
                doc = {
                    'camera_id': self.camera_id,
                    'timestamp': datetime.now(),
                    # add gender here
                    'counts': counts,
                }
                try:
                    if self._counts_queue.full():
                        self._counts_queue.get_nowait()
                    self._counts_queue.put_nowait(doc)
                except asyncio.QueueFull:
                    pass
            except asyncio.CancelledError:
                break

    async def _db_worker(self, batch_size: int = 50, flush_interval: float = 1.0) -> None:
        # loop = asyncio.get_running_loop()
        buffer = []
        last_flush = time.time()
        while not self._stop_event.is_set():
            # aggregate as well
            delta = time.time() - last_flush
            timeout = max(0, flush_interval - delta)
            try:
                doc = await asyncio.wait_for(self._counts_queue.get(), timeout=timeout)
                buffer.append(doc)
                if len(buffer) > batch_size:
                    buffer = buffer[-batch_size:]
            except asyncio.TimeoutError:
                pass
            if len(buffer) >= batch_size or (buffer and delta >= flush_interval):
                batch = buffer
                buffer = []
                last_flush = time.time()
                try:
                    pass
                    # await loop.run_in_executor(None, self.collection.insert_many, batch)
                except Exception as e:
                    print(f'[Camera {self.camera_id}] Mongo error: {e}')

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._yolo_task = loop.create_task(self._yolo_worker())
        self._count_task = loop.create_task(self._count_worker())
        self._db_task = loop.create_task(self._db_worker())

    async def stop(self) -> None:
        self._stop_event.set()
        tasks = [self._yolo_task, self._count_task, self._db_task]
        for t in tasks:
            if t is not None:
                t.cancel()
        if tasks:
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )
        while not self._results_queue.empty():
            try:
                self._results_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        while not self._counts_queue.empty():
            try:
                self._counts_queue.get_nowait()
            except asyncio.QueueEmpty:
                break


async def camera_task(camera_id: int, camera_url: str, model: YOLO, track: AnnotatedFrameTrack, regions=None, collection=None) -> None:
    """
    camera_id: int
    camera_url: RTSP/HTTP stream string
    model: ultralytics.YOLO instance
    track: AnnotatedFrameTrack (has async update(frame) coroutine)
    regions: list of dicts like {'name': 'zone1', 'x1':0, 'y1':0, 'x2':100, 'y2':100}
    collection: pymongo Collection (blocking) -> insert_one will run in executor
    """
    loop = asyncio.get_running_loop()
    results_queue = asyncio.Queue(maxsize=64)

    latest_counts = None
    counts_lock = asyncio.Lock()

    stop_event = threading.Event()

    def producer():
        try:
            for result in model.track(camera_url, tracker='bytetrack.yaml', conf=0.7, stream=True, persist=True):
                # push result into asyncio queue from background thread
                if stop_event.is_set():
                    break
                loop.call_soon_threadsafe(results_queue.put_nowait, result)
        except Exception as e:
            # push exception into queue to let consumer log it
            loop.call_soon_threadsafe(results_queue.put_nowait, e)

    async def publisher():
        try:
            while True:
                now = datetime.now()
                sleep_time = 1.0 - (now.microsecond / 1_000)
                await asyncio.sleep(sleep_time)
                timestamp = datetime.now().replace(microsecond=0)  # for now
                async with counts_lock:
                    snapshot = latest_counts
                if not snapshot:
                    continue
                doc = {
                    'camera_id': camera_id,
                    'timestamp': timestamp,
                    'counts': snapshot
                }
                print(doc)
                # await loop.run_in_executor(None, collection.insert_one, doc)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f'[Camera {camera_id}] publisher error: {e}')

    producer_task = loop.run_in_executor(None, producer)
    publisher_task = asyncio.create_task(publisher())

    try:
        while True:
            result = await results_queue.get()
            # If producer signaled an exception, log and continue
            if isinstance(result, Exception):
                print(f'[Camera {camera_id}] inference error: {result}')
                await asyncio.sleep(1.0)
                continue

            # get annotated frame (numpy BGR) for WebRTC
            try:
                annotated = result.plot()  # numpy.ndarray (BGR, uint8)
            except Exception as e:
                print(
                    f'[Camera {camera_id}] failed to render annotated frame: {e}')
                annotated = None

            if annotated is not None:
                try:
                    await track.update(annotated)
                except Exception as e:
                    print(f'[Camera {camera_id}] track update error: {e}')

            # count objects in regions and persist to MongoDB (run blocking insert in executor)
            try:
                print('published')
                # counts = count_objects_in_regions(result, regions)
                # doc = {
                #     'camera_id': camera_id,
                #     'timestamp': datetime.now(),
                #     'counts': counts,
                # }
                # await loop.run_in_executor(None, collection.insert_one, doc)
            except Exception as e:
                print(f'[Camera {camera_id}] db insert/count error: {e}')

    except asyncio.CancelledError:
        # cancel background producer and re-raise to allow outer cancellation handling
        stop_event.set()
        # producer_task.cancel()
        publisher_task.cancel()
        # try:
        #     await producer_task
        # except Exception:
        #     pass
        try:
            await publisher_task
        except Exception:
            pass
        raise
    except Exception as e:
        print(f'[Camera {camera_id}] unexpected error: {e}')
    finally:
        # best-effort cleanup
        # if not producer_task.done():
        #     producer_task.cancel()
        #     try:
        #         await producer_task
        #     except Exception:
        #         pass
        if not publisher_task.done():
            publisher_task.cancel()
            try:
                await publisher_task
            except Exception:
                pass
