import asyncio
import json
import os
import time
import aiohttp_cors
import pymongo
from aiohttp import web
from aiortc import (
    MediaStreamTrack,
    RTCPeerConnection,
    RTCSessionDescription
)
from aiortc.contrib.media import MediaPlayer, MediaRelay
from av import VideoFrame
from collections import Counter
from dotenv import load_dotenv
from fractions import Fraction
from ultralytics import YOLO
from urllib.parse import quote_plus
from typing import Optional

load_dotenv()

db_host = os.environ['DB_HOST']
db_user = os.environ['DB_USER']
db_pass = os.environ['DB_PASS']
db_name = os.environ['DB_NAME']
db_uri = f"mongodb+srv://{db_user}:{quote_plus(db_pass)}@{db_host}/{db_name}?retryWrites=true&w=majority"

mongo_client = pymongo.MongoClient(db_uri)
db = mongo_client[db_name]

model = YOLO("v1.yolo11m_seg.pt").to('cuda')
input_dir = os.environ['MODEL_SOURCE']
ROOT = os.path.dirname(__file__)
pcs = set()


class YOLOInferenceTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()
        self.latest_frame = None
        self._lock = asyncio.Lock()

    async def recv(self) -> VideoFrame:
        while self.latest_frame is None:
            await asyncio.sleep(0.01)

        async with self._lock:
            frame = self.latest_frame

        if hasattr(frame, "plot"):
            frame = frame.plot()

        av_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        av_frame.pts = int(time.time() * 1000)
        av_frame.time_base = Fraction(1, 1000)
        return av_frame

    async def update(self, frame):
        async with self._lock:
            self.latest_frame = frame


async def run_inference(track: YOLOInferenceTrack):
    loop = asyncio.get_running_loop()

    def inference_loop():
        global counts
        while True:
            for frame in model.track(input_dir, tracker="bytetrack.yaml", conf=0.7, stream=True):
                asyncio.run_coroutine_threadsafe(track.update(frame), loop)
                # todo: push counts here
    await asyncio.to_thread(inference_loop)


async def infer_and_create_tracks() -> tuple[
    Optional[MediaStreamTrack],
    Optional[MediaStreamTrack]
]:
    yolo_inference_track = YOLOInferenceTrack()
    asyncio.create_task(run_inference(yolo_inference_track))
    return (None, yolo_inference_track)


async def index(request: web.Request) -> web.Response:
    content = open(os.path.join(ROOT, "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)


async def javascript(request: web.Request) -> web.Response:
    content = open(os.path.join(ROOT, "client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)


async def offer(request: web.Request) -> web.Response:
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange() -> None:
        print(f"connection state is {pc.connectionState}")
        if pc.connectionState == ["failed", 'closed', 'disconnected']:
            await pc.close()
            pcs.discard(pc)

    (audio, video) = await infer_and_create_tracks()
    print(video)
    if audio:
        audio_sender = pc.addTrack(audio)
    if video:
        video_sender = pc.addTrack(video)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps({
            "sdp": pc.localDescription.sdp, "type": pc.localDescription.type
        }),
    )


async def on_shutdown(app: web.Application) -> None:
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

if __name__ == "__main__":
    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_post("/offer", offer)

    cors_origins = os.environ["CORS_ALLOW_ORIGINS"].split(',')

    cors_methods = os.environ["CORS_ALLOW_METHODS"]
    if ',' in cors_methods:
        cors_methods = cors_methods.split(',')

    cors_headers = os.environ["CORS_ALLOW_HEADERS"]
    if ',' in cors_origins:
        cors_headers = cors_headers.split(',')

    cors = aiohttp_cors.setup(app, defaults={
        origin: aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            allow_headers=cors_headers,
            allow_methods=cors_methods,
            expose_headers=cors_headers,
        ) for origin in cors_origins
    })
    for route in list(app.router.routes()):
        cors.add(route)

    web.run_app(app, host="0.0.0.0", port=9876)
