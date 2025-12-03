import asyncio
import numpy as np
import cv2
import multiprocessing as mp

from app.media.tracks import AnnotatedFrameTrack

def _get_and_decode(frame_queue: mp.Queue, timeout: float = 0.1):
    try:
        frame_bytes = frame_queue.get(timeout=timeout)
        arr = np.frombuffer(frame_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        raise

async def webrtc_publisher(
        camera_id: int,
        frame_queue: mp.Queue,
        track: AnnotatedFrameTrack
):
    print(f'[Publisher {camera_id}] Started')
    try:
        while True:
            try:
                annotated_frame = await asyncio.to_thread(_get_and_decode, frame_queue, timeout=0.1)
            except asyncio.CancelledError:
                raise asyncio.CancelledError()
            except Exception as e:
                await asyncio.sleep(0.001)
                continue
            await track.update(annotated_frame)
    except asyncio.CancelledError:
        print(f'[Publisher {camera_id}] Cancelled')
        raise
    except Exception as e:
        print(f'[Publisher {camera_id}] Error in update loop: {e}')
