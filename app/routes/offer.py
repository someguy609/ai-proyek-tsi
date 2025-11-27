from app.media.tracks import get_track
from aiortc import RTCPeerConnection, RTCSessionDescription
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix='/offer')

pcs = set()


@router.post('/')
async def offer(request: Request, camera_id: int):
    body = await request.json()
    if 'sdp' not in body:
        raise HTTPException(status_code=400, detail='Missing SDP offer')
    offer_sdp = body.get('sdp')
    offer_type = body.get('type')

    pc = RTCPeerConnection()
    pcs.add(pc)

    track = get_track(camera_id)
    if track is None:
        await pc.close()
        pcs.discard(pc)
        raise HTTPException(status_code=404, detail='Camera not available')

    pc.addTrack(track)
    
    @pc.on('connectionstatechange')
    async def on_state_change():
        if pc.connectionState in ['failed', 'closed']:
            await pc.close()
            pcs.discard(pc)

    offer = RTCSessionDescription(sdp=offer_sdp, type=offer_type)
    await pc.setRemoteDescription(offer)
    
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {
        'sdp': pc.localDescription.sdp,
        'type': pc.localDescription.type,
    }
