import multiprocessing as mp
import os
import time

from pymongo.collection import Collection
from ultralytics import YOLO


class CameraWorker(mp.Process):

    def __init__(
            self,
            camera_id: int,
            camera_url: str,
            model_path: str,
            frame_queue: mp.Queue,
            regions: list[dict],
            collection: Collection | None,
    ):
        super(CameraWorker, self).__init__()
        self.camera_id = camera_id
        self.camera_url = camera_url
        self.model_path = model_path
        self.frame_queue = frame_queue
        self.regions = regions
        self.collection = collection
        self._stop_event = mp.Event()

    def run(self):
        print(f'[Worker {self.camera_id}] Started (PID: {os.getpid()})')
        self.model = YOLO(self.model_path).to('cuda')
        counts_buffer = []
        last_db_flush_time = time.time()
        print(
            f'[Worker {self.camera_id}] Starting tracking loop for {self.camera_url}')
        try:
            for result in self.model.track(
                source=self.camera_url,
                tracker='bytetrack.yaml',
                stream=True,
                persist=True,
                conf=0.7,
                verbose=False,
            ):
                if self._stop_event.is_set():
                    break
                annotated_frame = result.plot()
                try:
                    if not self.frame_queue.empty():
                        self.frame_queue.get_nowait()
                    self.frame_queue.put_nowait(annotated_frame)
                except:
                    pass

                if self.regions:
                    if time.time() - last_db_flush_time > 1.0:
                        # count here ig
                        doc = {}
                        last_db_flush_time = time.time()
        except Exception as e:
            pass

    def stop(self):
        self._stop_event.set()
        print(f'[Worker {self.camera_id}] Stopped')
