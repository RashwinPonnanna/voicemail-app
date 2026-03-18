// ── WebRTC + Socket.IO Voice Calling ─────────────────────────────────────────

const socket = io();

let peerConnection = null;
let localStream    = null;
let currentCall    = null;   // username of the person we're talking to
let pendingOffer   = null;   // store incoming offer until user accepts

const iceServers = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' }
  ]
};

// ── UI helpers ────────────────────────────────────────────────────────────────

function openCallPanel() {
  document.getElementById('call-panel').classList.remove('hidden');
  socket.emit('get_online_users');
}

function closeCallPanel() {
  document.getElementById('call-panel').classList.add('hidden');
}

function setStatus(msg) {
  document.getElementById('call-status').textContent = msg;
}

function showCallControls(username) {
  document.getElementById('call-controls').classList.remove('hidden');
  document.getElementById('call-with-label').textContent = `In call with ${username}`;
}

function hideCallControls() {
  document.getElementById('call-controls').classList.add('hidden');
}

// ── Online users list ─────────────────────────────────────────────────────────

socket.on('online_users', users => {
  const list = document.getElementById('online-list');
  const others = users.filter(u => u !== CURRENT_USER);
  if (others.length === 0) {
    list.innerHTML = '<li class="no-users">No other users online</li>';
    return;
  }
  list.innerHTML = others.map(u => `
    <li>
      <button onclick="initiateCall('${u}')">
        <span class="online-dot"></span> ${u}
      </button>
    </li>
  `).join('');
});

// ── Initiate a call ───────────────────────────────────────────────────────────

async function initiateCall(target) {
  if (currentCall) { setStatus('Already in a call.'); return; }

  try {
    localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    document.getElementById('local-audio').srcObject = localStream;
  } catch (err) {
    setStatus('Microphone access denied.');
    return;
  }

  peerConnection = new RTCPeerConnection(iceServers);
  localStream.getTracks().forEach(t => peerConnection.addTrack(t, localStream));

  peerConnection.ontrack = e => {
    document.getElementById('remote-audio').srcObject = e.streams[0];
  };

  peerConnection.onicecandidate = e => {
    if (e.candidate) socket.emit('ice_candidate', { target, candidate: e.candidate });
  };

  const offer = await peerConnection.createOffer();
  await peerConnection.setLocalDescription(offer);

  socket.emit('call_user', { target, offer });
  currentCall = target;
  setStatus(`Calling ${target}…`);
}

// ── Handle call failed ────────────────────────────────────────────────────────

socket.on('call_failed', data => {
  setStatus(data.reason || 'Call failed.');
  cleanup();
});

// ── Incoming call ─────────────────────────────────────────────────────────────

socket.on('incoming_call', async data => {
  pendingOffer = data;
  document.getElementById('caller-name').textContent = `${data.from} is calling you`;
  document.getElementById('incoming-modal').classList.remove('hidden');
});

async function acceptCall() {
  document.getElementById('incoming-modal').classList.add('hidden');
  const data = pendingOffer;
  pendingOffer = null;

  try {
    localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    document.getElementById('local-audio').srcObject = localStream;
  } catch {
    setStatus('Microphone access denied.');
    return;
  }

  peerConnection = new RTCPeerConnection(iceServers);
  localStream.getTracks().forEach(t => peerConnection.addTrack(t, localStream));

  peerConnection.ontrack = e => {
    document.getElementById('remote-audio').srcObject = e.streams[0];
  };

  peerConnection.onicecandidate = e => {
    if (e.candidate) socket.emit('ice_candidate', { target: data.from, candidate: e.candidate });
  };

  await peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
  const answer = await peerConnection.createAnswer();
  await peerConnection.setLocalDescription(answer);

  socket.emit('call_answer', { target: data.from, answer });
  currentCall = data.from;
  openCallPanel();
  showCallControls(data.from);
  setStatus('');
}

function declineCall() {
  document.getElementById('incoming-modal').classList.add('hidden');
  if (pendingOffer) {
    socket.emit('end_call', { target: pendingOffer.from });
    pendingOffer = null;
  }
}

// ── Call answered ─────────────────────────────────────────────────────────────

socket.on('call_answered', async data => {
  if (!peerConnection) return;
  await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
  showCallControls(data.from);
  setStatus('');
});

// ── ICE candidates ────────────────────────────────────────────────────────────

socket.on('ice_candidate', async data => {
  if (peerConnection && data.candidate) {
    try { await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate)); } catch {}
  }
});

// ── End call ─────────────────────────────────────────────────────────────────

function endCall() {
  if (currentCall) socket.emit('end_call', { target: currentCall });
  cleanup();
}

socket.on('call_ended', () => {
  setStatus('Call ended.');
  cleanup();
});

function cleanup() {
  if (peerConnection) { peerConnection.close(); peerConnection = null; }
  if (localStream) { localStream.getTracks().forEach(t => t.stop()); localStream = null; }
  document.getElementById('local-audio').srcObject  = null;
  document.getElementById('remote-audio').srcObject = null;
  currentCall = null;
  hideCallControls();
  setTimeout(() => setStatus(''), 3000);
}
