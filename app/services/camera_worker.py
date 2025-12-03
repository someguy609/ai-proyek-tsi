import multiprocessing as mp
import os
import time
import cv2
from datetime import datetime
from pymongo.collection import Collection
from typing import Optional
from ultralytics import YOLO

from app.utils import count_objects_in_regions


class CameraWorker(mp.Process):

    def __init__(
            self,
            camera_id: int,
            camera_url: str,
            model_path: str,
            frame_queue: mp.Queue,
            counts_queue: mp.Queue,
            regions: Optional[list[dict]] = None,
    ):
        super(CameraWorker, self).__init__()
        self.camera_id = camera_id
        self.camera_url = camera_url
        self.model_path = model_path
        self.frame_queue = frame_queue
        self.counts_queue = counts_queue
        self.regions = regions
        self._region_map = {r.get('name'): r for r in self.regions}
        self._counts = {}
        self._stop_event = mp.Event()

    def run(self):
        print(f'[Worker {self.camera_id}] Started (PID: {os.getpid()})')
        self.model = YOLO(self.model_path).to('cuda')
        last_db_flush_time = time.time()
        print(
            f'[Worker {self.camera_id}] Starting tracking loop for {self.camera_url}')
        while not self._stop_event.is_set():
            try:
                for result in self.model.track(
                    source=self.camera_url,
                    tracker='bytetrack.yaml',
                    stream=True,
                    persist=True,
                    conf=0.7,
                    verbose=False,
                    # stream_buffer=True,
                ):
                    if self._stop_event.is_set():
                        break
                    annotated_frame = result.plot()
                    try:
                        _, jpg = cv2.imencode('.jpg', annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                        frame_bytes = jpg.tobytes()
                        if not self.frame_queue.empty():
                            self.frame_queue.get_nowait()
                        self.frame_queue.put_nowait(frame_bytes)
                    except:
                        pass

                    self._counts = count_objects_in_regions(
                        result, self.regions, self._counts)

                    if time.time() - last_db_flush_time > 60.0:
                        timestamp = datetime.now().replace(second=0, microsecond=0)
                        for region_name, classes in self._counts.items():
                            region = self._region_map[region_name]
                            location_id = region['_id']
                            for class_name, id_set in classes.items():
                                doc = {
                                    'timestamp': timestamp,
                                    'camera_id': self.camera_id,
                                    'location_id': location_id,
                                    'gender': str(class_name),
                                    'count': int(len(id_set)),
                                }
                                try:
                                    self.counts_queue.put_nowait(doc)
                                except Exception:
                                    pass
                        self._counts = {}
                        last_db_flush_time = time.time()
            except Exception as e:
                print(f'[Worker {self.camera_id}] Error: {e}')
                time.sleep(1)

    def stop(self):
        self._stop_event.set()
        print(f'[Worker {self.camera_id}] Stopped')
