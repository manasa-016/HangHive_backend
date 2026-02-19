from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List, Dict, Set
import json

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        # room_id -> list of websockets
        self.rooms: Dict[str, List[WebSocket]] = {}
        # client_id -> current_room_id
        self.user_registry: Dict[int, str] = {}

    async def connect(self, websocket: WebSocket, client_id: int, room_id: str):
        # Check if user is already in another room
        if client_id in self.user_registry:
            # We can either reject or disconnect the old one. 
            # Let's disconnect the old one for a better user experience (switching rooms).
            # However, since we don't have the old websocket object easily accessible here 
            # (unless we store it), let's just update the registry.
            # In a real app, we'd find the old socket and close it.
            pass
        
        await websocket.accept()
        
        if room_id not in self.rooms:
            self.rooms[room_id] = []
        
        self.rooms[room_id].append(websocket)
        self.user_registry[client_id] = room_id

    def disconnect(self, websocket: WebSocket, client_id: int, room_id: str):
        if room_id in self.rooms:
            if websocket in self.rooms[room_id]:
                self.rooms[room_id].remove(websocket)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
        
        if client_id in self.user_registry and self.user_registry[client_id] == room_id:
            del self.user_registry[client_id]

    async def broadcast(self, message: dict, room_id: str):
        if room_id in self.rooms:
            for connection in self.rooms[room_id]:
                await connection.send_json(message)

manager = ConnectionManager()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>HangHive - Community Chat</title>
        <style>
            :root {
                --primary: #056162;
                --bg: #0b141a;
                --text: #e9edef;
                --surface: #202c33;
                --sent-bg: #005c4b;
                --received-bg: #202c33;
                --system-bg: rgba(32, 44, 51, 0.6);
                --sidebar-bg: #111b21;
            }
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                background: var(--bg); 
                color: var(--text);
                display: flex;
                height: 100vh;
                overflow: hidden;
            }
            #sidebar {
                width: 300px;
                background: var(--sidebar-bg);
                border-right: 1px solid rgba(255, 255, 255, 0.1);
                display: flex;
                flex-direction: column;
            }
            #sidebar header {
                padding: 1rem;
                background: var(--surface);
                font-weight: bold;
                font-size: 1.2rem;
            }
            .community-item {
                padding: 1rem;
                cursor: pointer;
                transition: background 0.2s;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
            .community-item:hover {
                background: #2a3942;
            }
            .community-item.active {
                background: #2a3942;
                border-left: 4px solid var(--primary);
            }
            #main-chat {
                flex: 1;
                display: flex;
                flex-direction: column;
                background-image: url('https://user-images.githubusercontent.com/15075759/28719144-86dc0f70-73b1-11e7-911d-60d70fcded21.png');
                background-blend-mode: overlay;
                background-color: var(--bg);
            }
            header#chat-header {
                padding: 0.75rem 1.5rem;
                background: var(--surface);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            #chat-container {
                flex: 1;
                overflow-y: auto;
                padding: 1.5rem 5%;
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
            }
            .message-wrapper {
                display: flex;
                flex-direction: column;
                width: 100%;
            }
            .message {
                max-width: 65%;
                padding: 0.5rem 0.75rem;
                border-radius: 8px;
                word-wrap: break-word;
                line-height: 1.4;
                font-size: 0.9rem;
                box-shadow: 0 1px 0.5px rgba(0,0,0,0.13);
            }
            .received { background: var(--received-bg); align-self: flex-start; border-top-left-radius: 0; }
            .sent { background: var(--sent-bg); align-self: flex-end; border-top-right-radius: 0; }
            .system {
                align-self: center;
                font-size: 0.75rem;
                color: #8696a0;
                background: var(--system-bg);
                padding: 0.3rem 0.6rem;
                border-radius: 6px;
                margin: 0.75rem 0;
            }
            .sender-name { font-size: 0.75rem; color: #53bdeb; font-weight: 600; margin-bottom: 0.2rem; }
            #input-area {
                padding: 0.75rem 1.5rem;
                background: #202c33;
                display: flex;
                gap: 0.75rem;
            }
            input {
                flex: 1;
                background: #2a3942;
                border: none;
                padding: 0.6rem 1rem;
                border-radius: 8px;
                color: white;
                outline: none;
            }
            button {
                background: transparent;
                color: #8696a0;
                border: none;
                cursor: pointer;
            }
            #overlay {
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0,0,0,0.85);
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                z-index: 1000;
            }
            .join-card {
                background: var(--surface);
                padding: 2rem;
                border-radius: 12px;
                text-align: center;
                width: 90%;
                max-width: 400px;
            }
            select {
                width: 100%;
                padding: 0.8rem;
                margin: 1rem 0;
                background: #2a3942;
                color: white;
                border: 1px solid #3b4a54;
                border-radius: 8px;
            }
            .btn-primary {
                background: var(--primary);
                color: white;
                padding: 0.8rem 2rem;
                border-radius: 8px;
                border: none;
                font-weight: bold;
                width: 100%;
            }
        </style>
    </head>
    <body>
        <div id="overlay">
            <div class="join-card">
                <h2>Join a Community</h2>
                <p>Select a community to start hanging out</p>
                <select id="communitySelect">
                    <option value="general">General Lounge</option>
                    <option value="art">Art Exhibition</option>
                    <option value="gaming">Gaming Room</option>
                    <option value="friends">Friends Hub</option>
                    <option value="study">Study Group</option>
                </select>
                <button class="btn-primary" onclick="joinCommunity()">Join Community</button>
            </div>
        </div>

        <div id="sidebar">
            <header>Communities</header>
            <div id="community-list">
                <!-- Communities will be listed here -->
            </div>
        </div>

        <div id="main-chat">
            <header id="chat-header">
                <h1 id="current-community-name">HangHive</h1>
                <span id="ws-info" style="font-size: 0.8rem; color: #8696a0;"></span>
            </header>
            <div id="chat-container"></div>
            <form id="input-area" onsubmit="sendMessage(event)">
                <input type="text" id="messageText" autocomplete="off" placeholder="Type a message"/>
                <button type="submit">
                    <svg viewBox="0 0 24 24" height="24" width="24" fill="currentColor"><path d="M1.101 21.757L23.8 12.028 1.101 2.3l.011 7.912 13.623 1.816-13.623 1.817-.011 7.912z"></path></svg>
                </button>
            </form>
        </div>

        <script>
            var client_id = Date.now();
            var current_room = null;
            var ws = null;

            function joinCommunity() {
                const select = document.getElementById('communitySelect');
                const room_id = select.value;
                const room_name = select.options[select.selectedIndex].text;
                
                if (ws) ws.close();
                
                current_room = room_id;
                document.getElementById('overlay').style.display = 'none';
                document.getElementById('current-community-name').textContent = room_name;
                document.getElementById('ws-info').textContent = "My ID: " + client_id;
                document.getElementById('chat-container').innerHTML = '';
                
                startWebSocket(room_id);
            }

            function startWebSocket(room_id) {
                ws = new WebSocket(`ws://${window.location.host}/ws/${room_id}/${client_id}`);
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    const container = document.getElementById('chat-container');
                    const wrapper = document.createElement('div');
                    wrapper.classList.add('message-wrapper');
                    const message = document.createElement('div');
                    message.classList.add('message');
                    
                    if (data.type === 'system') {
                        message.classList.add('system');
                        message.textContent = data.content;
                    } else if (data.type === 'error') {
                        alert(data.content);
                        location.reload(); // Force rejoin/reset if blocked
                        return;
                    } else {
                        if (data.sender == client_id) {
                            message.classList.add('sent');
                            message.textContent = data.content;
                        } else {
                            message.classList.add('received');
                            const sender = document.createElement('div');
                            sender.classList.add('sender-name');
                            sender.textContent = "User #" + data.sender;
                            message.appendChild(sender);
                            const text = document.createTextNode(data.content);
                            message.appendChild(text);
                        }
                    }
                    
                    wrapper.appendChild(message);
                    container.appendChild(wrapper);
                    container.scrollTop = container.scrollHeight;
                };

                ws.onclose = function() {
                    console.log("WebSocket connection closed");
                };
            }

            function sendMessage(event) {
                var input = document.getElementById("messageText");
                if (input.value && ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(input.value);
                    input.value = '';
                }
                event.preventDefault();
            }
        </script>
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.websocket("/ws/{room_id}/{client_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, client_id: int):
    # Enforce one community at a time:
    # If client is already in the registry for a DIFFERENT room, we could reject.
    # But since the client closes the old connection before opening a new one, 
    # the disconnect handler for the old connection SHOULD have run.
    # However, if they open a new tab with the same ID (mocked here by Date.now()),
    # they would have different IDs usually.
    
    if client_id in manager.user_registry and manager.user_registry[client_id] != room_id:
        await websocket.accept()
        await websocket.send_json({"type": "error", "content": "You are already active in another community!"})
        await websocket.close()
        return

    await manager.connect(websocket, client_id, room_id)
    await manager.broadcast({"type": "system", "content": f"User #{client_id} joined {room_id}"}, room_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast({
                "type": "chat",
                "sender": client_id,
                "content": data
            }, room_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, client_id, room_id)
        await manager.broadcast({"type": "system", "content": f"User #{client_id} left {room_id}"}, room_id)


