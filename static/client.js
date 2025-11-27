const NUM_CAMERAS = 2; // Change this to match your backend
const OFFER_URL = '/offer';

async function createViewer(cameraId) {
	const pc = new RTCPeerConnection({
		sdpSemantics: 'unified-plan',
		iceServers: [{ urls: ['stun:stun.l.google.com:19302'] }],
	});
	pc.addTransceiver('video', { direction: 'recvonly' });

	// Create container
	const wrapper = document.createElement('div');
	wrapper.classList.add('camera-box');

	const title = document.createElement('h3');
	title.innerText = `Camera ${cameraId}`;

	const video = document.createElement('video');
	video.autoplay = true;
	video.playsInline = true;
	video.controls = false;

	const button = document.createElement('button');
	button.innerText = 'Connect';
	button.onclick = () => connect(pc, cameraId, video);

	wrapper.appendChild(title);
	wrapper.appendChild(video);
	wrapper.appendChild(button);

	document.getElementById('app').appendChild(wrapper);
}

async function connect(pc, cameraId, videoElement) {
	pc.ontrack = (ev) => {
		console.log('📡 Track received for camera', cameraId);
		videoElement.srcObject = ev.streams[0];
	};

	const offer = await pc.createOffer();
	await pc.setLocalDescription(offer);

	const response = await fetch(`${OFFER_URL}?camera_id=${cameraId}`, {
		method: 'POST',
		body: JSON.stringify({
			sdp: pc.localDescription.sdp,
			type: pc.localDescription.type,
		}),
		headers: { 'Content-Type': 'application/json' },
	});

	const answer = await response.json();
	await pc.setRemoteDescription(answer);
	console.log('Connected to camera:', cameraId);
}

// Startup
for (let i = 1; i <= NUM_CAMERAS; i++) {
	createViewer(i);
}
