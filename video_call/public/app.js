mdc.ripple.MDCRipple.attachTo(document.querySelector('.mdc-button'));

// ---------------- CONFIG ----------------
const configuration = {
  iceServers: [
    { urls: "stun:stun.l.google.com:19302" }
  ]
};

let peerConnection = null;
let localStream = null;
let remoteStream = null;
let roomDialog = null;
let roomId = null;

// ---------------- INIT ----------------
function init() {
  document.querySelector('#cameraBtn').addEventListener('click', openUserMedia);
  document.querySelector('#hangupBtn').addEventListener('click', hangUp);
  document.querySelector('#createBtn').addEventListener('click', createRoom);
  document.querySelector('#joinBtn').addEventListener('click', joinRoom);
  roomDialog = new mdc.dialog.MDCDialog(document.querySelector('#room-dialog'));
}

init();

// ---------------- OPEN CAMERA ----------------
async function openUserMedia() {
  localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
  document.querySelector('#localVideo').srcObject = localStream;

  remoteStream = new MediaStream();
  document.querySelector('#remoteVideo').srcObject = remoteStream;

  document.querySelector('#cameraBtn').disabled = true;
  document.querySelector('#createBtn').disabled = false;
  document.querySelector('#joinBtn').disabled = false;
  document.querySelector('#hangupBtn').disabled = false;
}

// ---------------- CREATE ROOM ----------------
async function createRoom() {
  const db = firebase.firestore();

  peerConnection = new RTCPeerConnection(configuration);

  // Add local tracks
  localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

  // Remote track listener
  peerConnection.ontrack = event => {
    event.streams[0].getTracks().forEach(track => remoteStream.addTrack(track));
  };

  const roomRef = await db.collection('rooms').add({});
  roomId = roomRef.id;

  document.querySelector('#currentRoom').innerText = `Room ID: ${roomId}`;

  // ICE candidates
  const callerCandidates = roomRef.collection('callerCandidates');
  peerConnection.onicecandidate = event => {
    if (event.candidate) {
      callerCandidates.add(event.candidate.toJSON());
    }
  };

  // Create offer
  const offer = await peerConnection.createOffer();
  await peerConnection.setLocalDescription(offer);
  await roomRef.set({ offer });

  // Listen for answer
  roomRef.onSnapshot(async snapshot => {
    const data = snapshot.data();
    if (data.answer && !peerConnection.currentRemoteDescription) {
      await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
    }
  });

  // Listen for remote ICE
  roomRef.collection('calleeCandidates').onSnapshot(snapshot => {
    snapshot.docChanges().forEach(change => {
      if (change.type === "added") {
        peerConnection.addIceCandidate(new RTCIceCandidate(change.doc.data()));
      }
    });
  });
}

// ---------------- JOIN ROOM ----------------
function joinRoom() {
  roomDialog.open();

  document.querySelector('#confirmJoinBtn').onclick = async () => {
    roomId = document.querySelector('#room-id').value;
    await joinRoomById(roomId);
  };
}

async function joinRoomById(id) {
  const db = firebase.firestore();
  const roomRef = db.collection('rooms').doc(id);
  const roomSnapshot = await roomRef.get();

  if (!roomSnapshot.exists) {
    alert("Room not found");
    return;
  }

  peerConnection = new RTCPeerConnection(configuration);

  // Add local tracks
  localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

  // Remote track listener
  peerConnection.ontrack = event => {
    event.streams[0].getTracks().forEach(track => remoteStream.addTrack(track));
  };

  // ICE candidates
  const calleeCandidates = roomRef.collection('calleeCandidates');
  peerConnection.onicecandidate = event => {
    if (event.candidate) {
      calleeCandidates.add(event.candidate.toJSON());
    }
  };

  // Set remote offer
  const offer = roomSnapshot.data().offer;
  await peerConnection.setRemoteDescription(new RTCSessionDescription(offer));

  // Create answer
  const answer = await peerConnection.createAnswer();
  await peerConnection.setLocalDescription(answer);

  await roomRef.update({ answer });

  // Listen for caller ICE
  roomRef.collection('callerCandidates').onSnapshot(snapshot => {
    snapshot.docChanges().forEach(change => {
      if (change.type === "added") {
        peerConnection.addIceCandidate(new RTCIceCandidate(change.doc.data()));
      }
    });
  });

  document.querySelector('#currentRoom').innerText = `Joined Room: ${id}`;
}

// ---------------- HANGUP ----------------
async function hangUp() {
  // Stop streams
  if (localStream) localStream.getTracks().forEach(track => track.stop());
  if (remoteStream) remoteStream.getTracks().forEach(track => track.stop());

  // Close connection
  if (peerConnection) peerConnection.close();
  peerConnection = null;

  document.querySelector('#localVideo').srcObject = null;
  document.querySelector('#remoteVideo').srcObject = null;

  // Delete room and candidates safely
  if (roomId) {
    const db = firebase.firestore();
    const roomRef = db.collection('rooms').doc(roomId);

    const calleeCandidates = await roomRef.collection('calleeCandidates').get();
    for (const doc of calleeCandidates.docs) await doc.ref.delete();

    const callerCandidates = await roomRef.collection('callerCandidates').get();
    for (const doc of callerCandidates.docs) await doc.ref.delete();

    await roomRef.delete();
  }

  roomId = null;

  // Reset buttons
  document.querySelector('#cameraBtn').disabled = false;
  document.querySelector('#createBtn').disabled = true;
  document.querySelector('#joinBtn').disabled = true;
  document.querySelector('#hangupBtn').disabled = true;
  document.querySelector('#currentRoom').innerText = '';

  alert("Call ended");
}
