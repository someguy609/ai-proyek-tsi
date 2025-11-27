import asyncio
import multiprocessing as mp

from app.media.tracks import AnnotatedFrameTrack


async def webrtc_publisher(
        camera_id: int,
        frame_queue: mp.Queue,
        track: AnnotatedFrameTrack
):
    print(f'[Publisher {camera_id}] Started')
    try:
        while True:
            try:
                annotated_frame = await asyncio.to_thread(frame_queue.get, timeout=0.1)
            except:
                await asyncio.sleep(0.001)
                continue
            await track.update(annotated_frame)
    except asyncio.CancelledError:
        print(f'[Publisher {camera_id}] Cancelled')
        raise
    except Exception as e:
        print(f'[Publisher {camera_id}] Error in update loop: {e}')
