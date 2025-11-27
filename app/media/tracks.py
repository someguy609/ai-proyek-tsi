import asyncio
from aiortc import VideoStreamTrack
from av import VideoFrame
from typing import Optional


class AnnotatedFrameTrack(VideoStreamTrack):

    def __init__(self) -> None:
        super().__init__()
        self.frame = None
        self._lock = asyncio.Lock()

    async def recv(self) -> VideoFrame:
        pts, time_base = await self.next_timestamp()
        while self.frame is None:
            await asyncio.sleep(0.01)
        async with self._lock:
            frame = self.frame
        if hasattr(self.frame, 'plot'):
            frame = frame.plot()
        av_frame = VideoFrame.from_ndarray(frame, format='bgr24')
        av_frame.pts = pts
        av_frame.time_base = time_base
        return av_frame

    async def update(self, frame):
        async with self._lock:
            self.frame = frame


_tracks: dict[int, AnnotatedFrameTrack] = {}


def create_track(camera_id: int) -> AnnotatedFrameTrack:
    track = AnnotatedFrameTrack()
    _tracks[camera_id] = track
    return track


def get_track(camera_id: int) -> Optional[AnnotatedFrameTrack]:
    return _tracks.get(camera_id)


def unregister_track(camera_id: int) -> None:
    _tracks.pop(camera_id)
