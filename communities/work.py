from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List, Dict

app = FastAPI()

# ─── Work context definitions ──────────────────────────────────────────────────
WORK_CONTEXTS = {
    "school":   {"label": "🏫 School",   "description": "For school students & teachers"},
    "college":  {"label": "🎓 College",  "description": "For college students & faculty"},
    "office":   {"label": "💼 Office",   "description": "For workplace teams & professionals"},
    "personal": {"label": "🏠 Personal", "description": "For personal projects & freelancers"},
}


# ─── Connection manager ─────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        # room_id -> list of websockets
        self.rooms: Dict[str, List[WebSocket]] = {}
        # client_id -> (room_id, username)
        self.user_registry: Dict[int, Dict] = {}

    async def connect(self, websocket: WebSocket, client_id: int, room_id: str, username: str):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = []
        self.rooms[room_id].append(websocket)
        self.user_registry[client_id] = {"room": room_id, "username": username}

    def disconnect(self, websocket: WebSocket, client_id: int, room_id: str):
        if room_id in self.rooms:
            if websocket in self.rooms[room_id]:
                self.rooms[room_id].remove(websocket)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
        if client_id in self.user_registry and self.user_registry[client_id]["room"] == room_id:
            del self.user_registry[client_id]

    async def broadcast(self, message: dict, room_id: str):
        if room_id in self.rooms:
            for connection in self.rooms[room_id]:
                await connection.send_json(message)

    def get_username(self, client_id: int) -> str:
        return self.user_registry.get(client_id, {}).get("username", f"User #{client_id}")


manager = ConnectionManager()

# ─── HTML Interface ─────────────────────────────────────────────────────────────
html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>HangHive – Work Community</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        :root {
            --primary:      #4f6ef7;
            --primary-dark: #3b55d4;
            --bg:           #0f1117;
            --surface:      #1a1d27;
            --surface2:     #232636;
            --border:       rgba(255,255,255,0.08);
            --text:         #e2e8f0;
            --muted:        #8892a4;
            --sent-bg:      #2d3f87;
            --recv-bg:      #1e2235;
            --sys-color:    #64748b;

            /* context accent colours */
            --school-color:   #f59e0b;
            --college-color:  #10b981;
            --office-color:   #3b82f6;
            --personal-color: #a855f7;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg);
            color: var(--text);
            height: 100vh;
            display: flex;
            overflow: hidden;
        }

        /* ── Overlay / Step screens ─────────────────────────── */
        #overlay {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.92);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            backdrop-filter: blur(6px);
        }

        .step-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 2.5rem 2rem;
            width: 95%;
            max-width: 520px;
            text-align: center;
            box-shadow: 0 25px 60px rgba(0,0,0,0.5);
            animation: fadeUp 0.35s ease;
        }

        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(20px); }
            to   { opacity: 1; transform: translateY(0); }
        }

        .step-card h2 {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 0.4rem;
        }

        .step-card p.subtitle {
            color: var(--muted);
            font-size: 0.9rem;
            margin-bottom: 1.8rem;
        }

        /* ── Step 1 – context grid ──────────────────────────── */
        .context-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.9rem;
            margin-bottom: 1.5rem;
        }

        .context-tile {
            background: var(--surface2);
            border: 2px solid transparent;
            border-radius: 14px;
            padding: 1.2rem 0.75rem;
            cursor: pointer;
            transition: border-color 0.2s, background 0.2s, transform 0.15s;
            user-select: none;
        }

        .context-tile:hover {
            background: #2b2f43;
            transform: translateY(-2px);
        }

        .context-tile.selected {
            border-color: var(--primary);
            background: rgba(79,110,247,0.12);
        }

        .context-tile .icon  { font-size: 2rem; display: block; margin-bottom: 0.45rem; }
        .context-tile .name  { font-weight: 600; font-size: 0.95rem; margin-bottom: 0.2rem; }
        .context-tile .desc  { font-size: 0.75rem; color: var(--muted); }

        /* accent borders per context */
        .context-tile[data-ctx="school"].selected   { border-color: var(--school-color);   background: rgba(245,158,11,0.1); }
        .context-tile[data-ctx="college"].selected  { border-color: var(--college-color);  background: rgba(16,185,129,0.1); }
        .context-tile[data-ctx="office"].selected   { border-color: var(--office-color);   background: rgba(59,130,246,0.1); }
        .context-tile[data-ctx="personal"].selected { border-color: var(--personal-color); background: rgba(168,85,247,0.1); }

        /* ── Step 2 – username input ────────────────────────── */
        #step2 { display: none; }

        .badge-selected {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: var(--surface2);
            border-radius: 50px;
            padding: 0.4rem 1rem;
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border);
        }

        .form-label {
            text-align: left;
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--muted);
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.4rem;
            display: block;
        }

        .form-input {
            width: 100%;
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.75rem 1rem;
            color: var(--text);
            font-size: 0.95rem;
            outline: none;
            transition: border-color 0.2s;
            margin-bottom: 1.5rem;
        }

        .form-input:focus {
            border-color: var(--primary);
        }

        /* ── Buttons ────────────────────────────────────────── */
        .btn {
            width: 100%;
            padding: 0.85rem;
            border: none;
            border-radius: 10px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s, transform 0.15s;
        }

        .btn:active { transform: scale(0.98); }

        .btn-primary {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            color: #fff;
        }

        .btn-primary:disabled {
            opacity: 0.45;
            cursor: not-allowed;
        }

        .btn-back {
            background: transparent;
            color: var(--muted);
            font-size: 0.85rem;
            width: auto;
            padding: 0.4rem 0;
            margin-top: 0.75rem;
            text-decoration: underline;
        }

        /* ── Main layout ────────────────────────────────────── */
        #sidebar {
            width: 280px;
            background: var(--surface);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
        }

        #sidebar .sidebar-header {
            padding: 1rem 1.25rem;
            background: var(--surface2);
            border-bottom: 1px solid var(--border);
        }

        #sidebar .sidebar-header h3 {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--muted);
            margin-bottom: 0.25rem;
        }

        #sidebar .sidebar-header p {
            font-weight: 700;
            font-size: 1rem;
        }

        #room-info {
            padding: 1rem 1.25rem;
            border-bottom: 1px solid var(--border);
        }

        #room-info .info-row {
            display: flex;
            justify-content: space-between;
            font-size: 0.82rem;
            margin-bottom: 0.4rem;
        }

        #room-info .info-label { color: var(--muted); }
        #room-info .info-value { font-weight: 600; }

        #online-list {
            flex: 1;
            overflow-y: auto;
            padding: 0.75rem 1.25rem;
        }

        #online-list h4 {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--muted);
            margin-bottom: 0.6rem;
        }

        .online-user {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.85rem;
            padding: 0.3rem 0;
            color: var(--text);
        }

        .online-dot {
            width: 8px; height: 8px;
            border-radius: 50%;
            background: #22c55e;
            flex-shrink: 0;
        }

        /* ── Chat area ──────────────────────────────────────── */
        #main-chat {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: var(--bg);
        }

        #chat-header {
            padding: 0.9rem 1.5rem;
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        #chat-header .room-title { font-weight: 700; font-size: 1rem; }
        #chat-header .room-sub   { font-size: 0.78rem; color: var(--muted); }

        #context-badge {
            font-size: 0.78rem;
            font-weight: 600;
            padding: 0.3rem 0.85rem;
            border-radius: 50px;
            border: 1px solid currentColor;
        }

        #chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 1.25rem 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
        }

        .msg-row { display: flex; flex-direction: column; }

        .msg-bubble {
            max-width: 62%;
            padding: 0.55rem 0.85rem;
            border-radius: 10px;
            font-size: 0.88rem;
            line-height: 1.45;
            word-break: break-word;
            box-shadow: 0 1px 2px rgba(0,0,0,0.2);
        }

        .msg-bubble.sent     { background: var(--sent-bg); align-self: flex-end; border-bottom-right-radius: 2px; }
        .msg-bubble.received { background: var(--recv-bg); align-self: flex-start; border-bottom-left-radius: 2px; }
        .msg-bubble.system   {
            align-self: center;
            background: transparent;
            color: var(--sys-color);
            font-size: 0.75rem;
            max-width: 90%;
            text-align: center;
            box-shadow: none;
            font-style: italic;
            margin: 0.5rem 0;
        }

        .sender-name {
            font-size: 0.73rem;
            font-weight: 600;
            color: #818cf8;
            margin-bottom: 0.2rem;
        }

        /* ── Input area ─────────────────────────────────────── */
        #input-area {
            padding: 0.85rem 1.5rem;
            background: var(--surface);
            border-top: 1px solid var(--border);
            display: flex;
            gap: 0.75rem;
            align-items: center;
        }

        #messageText {
            flex: 1;
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.65rem 1rem;
            color: var(--text);
            font-size: 0.9rem;
            outline: none;
            transition: border-color 0.2s;
        }

        #messageText:focus { border-color: var(--primary); }

        #sendBtn {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            border: none;
            border-radius: 10px;
            padding: 0.65rem 1.1rem;
            color: #fff;
            cursor: pointer;
            display: flex;
            align-items: center;
            transition: opacity 0.2s;
        }

        #sendBtn:hover { opacity: 0.85; }
    </style>
</head>
<body>

<!-- ── Overlay: two-step join flow ───────────────────────────────────────── -->
<div id="overlay">

    <!-- Step 1: choose work context -->
    <div class="step-card" id="step1">
        <h2>👋 Welcome to Work</h2>
        <p class="subtitle">Select your work context to join the right community</p>

        <div class="context-grid">
            <div class="context-tile" data-ctx="school" onclick="selectContext(this)">
                <span class="icon">🏫</span>
                <div class="name">School</div>
                <div class="desc">Students & Teachers</div>
            </div>
            <div class="context-tile" data-ctx="college" onclick="selectContext(this)">
                <span class="icon">🎓</span>
                <div class="name">College</div>
                <div class="desc">Students & Faculty</div>
            </div>
            <div class="context-tile" data-ctx="office" onclick="selectContext(this)">
                <span class="icon">💼</span>
                <div class="name">Office</div>
                <div class="desc">Teams & Professionals</div>
            </div>
            <div class="context-tile" data-ctx="personal" onclick="selectContext(this)">
                <span class="icon">🏠</span>
                <div class="name">Personal</div>
                <div class="desc">Projects & Freelancers</div>
            </div>
        </div>

        <button class="btn btn-primary" id="nextBtn" disabled onclick="goToStep2()">Continue →</button>
    </div>

    <!-- Step 2: enter username -->
    <div class="step-card" id="step2">
        <h2>Almost There!</h2>
        <p class="subtitle">Enter a display name to join your workspace</p>

        <div id="selected-badge" class="badge-selected"></div>

        <label class="form-label" for="usernameInput">Your Name</label>
        <input class="form-input" id="usernameInput" type="text"
               placeholder="e.g. Alex Kumar"
               maxlength="30"
               oninput="validateStep2()"
               onkeydown="if(event.key==='Enter') joinWork()"/>

        <button class="btn btn-primary" id="joinBtn" disabled onclick="joinWork()">Join Workspace</button>
        <button class="btn btn-back" onclick="goToStep1()">← Back</button>
    </div>
</div>

<!-- ── Main app ──────────────────────────────────────────────────────────── -->
<div id="sidebar">
    <div class="sidebar-header">
        <h3>Work Community</h3>
        <p id="sidebar-context-name">—</p>
    </div>

    <div id="room-info">
        <div class="info-row">
            <span class="info-label">Context</span>
            <span class="info-value" id="info-context">—</span>
        </div>
        <div class="info-row">
            <span class="info-label">Your Name</span>
            <span class="info-value" id="info-username">—</span>
        </div>
    </div>

    <div id="online-list">
        <h4>Online Members</h4>
        <div id="members-list"></div>
    </div>
</div>

<div id="main-chat">
    <header id="chat-header">
        <div>
            <div class="room-title" id="room-title">Work Chat</div>
            <div class="room-sub"  id="room-sub">Select a context to begin</div>
        </div>
        <span id="context-badge"></span>
    </header>

    <div id="chat-container"></div>

    <form id="input-area" onsubmit="sendMessage(event)">
        <input type="text" id="messageText" placeholder="Type a message…" autocomplete="off"/>
        <button type="submit" id="sendBtn">
            <svg viewBox="0 0 24 24" height="18" width="18" fill="currentColor">
                <path d="M1.101 21.757L23.8 12.028 1.101 2.3l.011 7.912 13.623 1.816-13.623 1.817-.011 7.912z"/>
            </svg>
        </button>
    </form>
</div>

<script>
    // ── State ──────────────────────────────────────────────────────────────────
    var CLIENT_ID   = Date.now();
    var selectedCtx = null;
    var username    = '';
    var ws          = null;

    var CTX_META = {
        school:   { label: '🏫 School',   color: '#f59e0b' },
        college:  { label: '🎓 College',  color: '#10b981' },
        office:   { label: '💼 Office',   color: '#3b82f6' },
        personal: { label: '🏠 Personal', color: '#a855f7' },
    };

    var onlineMembers = {};   // id -> name

    // ── Step 1 ─────────────────────────────────────────────────────────────────
    function selectContext(tile) {
        document.querySelectorAll('.context-tile').forEach(t => t.classList.remove('selected'));
        tile.classList.add('selected');
        selectedCtx = tile.dataset.ctx;
        document.getElementById('nextBtn').disabled = false;
    }

    function goToStep2() {
        if (!selectedCtx) return;
        var meta = CTX_META[selectedCtx];
        document.getElementById('selected-badge').innerHTML =
            '<span>' + meta.label + '</span>' +
            '<span style="color:var(--muted);font-weight:400">workspace selected</span>';
        document.getElementById('step1').style.display = 'none';
        document.getElementById('step2').style.display = 'block';
        document.getElementById('usernameInput').focus();
    }

    // ── Step 2 ─────────────────────────────────────────────────────────────────
    function goToStep1() {
        document.getElementById('step2').style.display = 'none';
        document.getElementById('step1').style.display = 'block';
    }

    function validateStep2() {
        var val = document.getElementById('usernameInput').value.trim();
        document.getElementById('joinBtn').disabled = val.length < 2;
    }

    // ── Join ───────────────────────────────────────────────────────────────────
    function joinWork() {
        var nameInput = document.getElementById('usernameInput').value.trim();
        if (!nameInput || nameInput.length < 2) return;
        username = nameInput;

        // Hide overlay, update sidebar
        document.getElementById('overlay').style.display = 'none';

        var meta = CTX_META[selectedCtx];

        // Sidebar
        document.getElementById('sidebar-context-name').textContent = meta.label;
        document.getElementById('info-context').textContent  = meta.label;
        document.getElementById('info-username').textContent = username;

        // chat header
        document.getElementById('room-title').textContent = meta.label + ' Workspace';
        document.getElementById('room-sub').textContent   = 'Work chat for ' + meta.label.replace(/^[^ ]+ /, '');

        // badge
        var badge = document.getElementById('context-badge');
        badge.textContent  = meta.label;
        badge.style.color  = meta.color;
        badge.style.borderColor = meta.color;

        connectWebSocket();
    }

    // ── WebSocket ──────────────────────────────────────────────────────────────
    function connectWebSocket() {
        var room_id = 'work_' + selectedCtx;
        ws = new WebSocket(
            'ws://' + window.location.host +
            '/ws/work/' + room_id + '/' + CLIENT_ID + '?username=' + encodeURIComponent(username)
        );

        ws.onmessage = function(event) {
            var data = JSON.parse(event.data);
            handleMessage(data);
        };

        ws.onclose = function() {
            appendSystem('⚠️ Disconnected from workspace.');
        };

        ws.onerror = function() {
            appendSystem('❌ Connection error. Please refresh.');
        };
    }

    function handleMessage(data) {
        if (data.type === 'system') {
            appendSystem(data.content);
        } else if (data.type === 'members') {
            onlineMembers = data.members;
            renderMembers();
        } else if (data.type === 'chat') {
            appendChat(data);
        } else if (data.type === 'error') {
            alert(data.content);
            location.reload();
        }
    }

    // ── Rendering ──────────────────────────────────────────────────────────────
    function appendSystem(text) {
        var container = document.getElementById('chat-container');
        var el = document.createElement('div');
        el.classList.add('msg-row');
        var bubble = document.createElement('div');
        bubble.classList.add('msg-bubble', 'system');
        bubble.textContent = text;
        el.appendChild(bubble);
        container.appendChild(el);
        container.scrollTop = container.scrollHeight;
    }

    function appendChat(data) {
        var container = document.getElementById('chat-container');
        var row = document.createElement('div');
        row.classList.add('msg-row');

        var bubble = document.createElement('div');
        bubble.classList.add('msg-bubble');
        var isSelf = (data.sender_id == CLIENT_ID);

        if (isSelf) {
            bubble.classList.add('sent');
            bubble.textContent = data.content;
        } else {
            bubble.classList.add('received');
            var nameEl = document.createElement('div');
            nameEl.classList.add('sender-name');
            nameEl.textContent = data.sender_name || ('User #' + data.sender_id);
            bubble.appendChild(nameEl);
            bubble.appendChild(document.createTextNode(data.content));
        }

        row.appendChild(bubble);
        container.appendChild(row);
        container.scrollTop = container.scrollHeight;
    }

    function renderMembers() {
        var list = document.getElementById('members-list');
        list.innerHTML = '';
        Object.entries(onlineMembers).forEach(function([id, name]) {
            var el = document.createElement('div');
            el.classList.add('online-user');
            el.innerHTML = '<span class="online-dot"></span>' +
                           '<span>' + escapeHtml(name) + (id == CLIENT_ID ? ' (you)' : '') + '</span>';
            list.appendChild(el);
        });
    }

    function escapeHtml(str) {
        return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    // ── Send ───────────────────────────────────────────────────────────────────
    function sendMessage(event) {
        event.preventDefault();
        var input = document.getElementById('messageText');
        var text  = input.value.trim();
        if (text && ws && ws.readyState === WebSocket.OPEN) {
            ws.send(text);
            input.value = '';
        }
    }
</script>
</body>
</html>
"""


# ─── Online members tracker ─────────────────────────────────────────────────────
class WorkConnectionManager(ConnectionManager):
    """Extends ConnectionManager with named-member tracking."""

    def __init__(self):
        super().__init__()
        # room_id -> {client_id: username}
        self.room_members: Dict[str, Dict[int, str]] = {}

    async def connect(self, websocket: WebSocket, client_id: int, room_id: str, username: str):
        await super().connect(websocket, client_id, room_id, username)
        if room_id not in self.room_members:
            self.room_members[room_id] = {}
        self.room_members[room_id][client_id] = username

    def disconnect(self, websocket: WebSocket, client_id: int, room_id: str):
        super().disconnect(websocket, client_id, room_id)
        if room_id in self.room_members:
            self.room_members[room_id].pop(client_id, None)
            if not self.room_members[room_id]:
                del self.room_members[room_id]

    def get_members_dict(self, room_id: str) -> Dict[int, str]:
        return self.room_members.get(room_id, {})


work_manager = WorkConnectionManager()


# ─── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws/work/{room_id}/{client_id}")
async def work_websocket(
    websocket: WebSocket,
    room_id: str,
    client_id: int,
    username: str = "Anonymous",
):
    # Validate the context embedded in room_id (format: work_<context>)
    parts = room_id.split("_", 1)
    context = parts[1] if len(parts) == 2 else ""
    if context not in WORK_CONTEXTS:
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "content": f"Invalid work context '{context}'. Choose: school, college, office, personal."
        })
        await websocket.close()
        return

    # Reject if already active in a different room
    if client_id in work_manager.user_registry:
        existing_room = work_manager.user_registry[client_id]["room"]
        if existing_room != room_id:
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "content": "You are already active in another workspace!"
            })
            await websocket.close()
            return

    await work_manager.connect(websocket, client_id, room_id, username)

    # Broadcast join notice and updated member list
    await work_manager.broadcast(
        {"type": "system", "content": f"{username} joined the {WORK_CONTEXTS[context]['label']} workspace"},
        room_id,
    )
    await work_manager.broadcast(
        {"type": "members", "members": {str(k): v for k, v in work_manager.get_members_dict(room_id).items()}},
        room_id,
    )

    try:
        while True:
            text = await websocket.receive_text()
            await work_manager.broadcast(
                {
                    "type":        "chat",
                    "sender_id":   client_id,
                    "sender_name": username,
                    "content":     text,
                },
                room_id,
            )
    except WebSocketDisconnect:
        work_manager.disconnect(websocket, client_id, room_id)
        await work_manager.broadcast(
            {"type": "system", "content": f"{username} left the workspace"},
            room_id,
        )
        # Push updated member list after disconnect
        remaining = {str(k): v for k, v in work_manager.get_members_dict(room_id).items()}
        if remaining:
            await work_manager.broadcast(
                {"type": "members", "members": remaining},
                room_id,
            )
