const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const cors = require("cors");

const app = express();
app.use(cors());
app.use(express.static(__dirname));

const server = http.createServer(app);

const io = new Server(server, {
  cors: {
    origin: "*",
  },
});

const voiceRooms = {};

io.on("connection", (socket) => {
  console.log("User connected:", socket.id);

  socket.on("join-voice-room", (roomId) => {
    socket.join(roomId);

    if (!voiceRooms[roomId]) {
      voiceRooms[roomId] = [];
    }

    voiceRooms[roomId].push(socket.id);

    socket.to(roomId).emit("user-joined", socket.id);

    socket.emit(
      "existing-users",
      voiceRooms[roomId].filter((id) => id !== socket.id)
    );
  });

  socket.on("webrtc-signal", ({ targetId, signal }) => {
    io.to(targetId).emit("webrtc-signal", {
      from: socket.id,
      signal,
    });
  });

  socket.on("disconnect", () => {
    for (let roomId in voiceRooms) {
      voiceRooms[roomId] = voiceRooms[roomId].filter(
        (id) => id !== socket.id
      );
      socket.to(roomId).emit("user-left", socket.id);
    }
  });
});

server.listen(5000, () => {
  console.log("🚀 Voice signaling server running on port 5000");
});
