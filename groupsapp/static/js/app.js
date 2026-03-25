// static/js/app.js

// -------------------------------------------------------------
// Core State & Logic
// -------------------------------------------------------------
let ws = null;
let activeRoomId = null;  // Format: "group_uuid", "channel_uuid", "private_userid"
let currentUser = null;
const API_BASE = '/api';

const fetchAuth = async (url, options = {}) => {
    let token = localStorage.getItem('access_token');
    if (!options.headers) options.headers = {};
    if (token) options.headers['Authorization'] = `Bearer ${token}`;

    let res = await fetch(url, options);

    // Auto-refresh token if 401
    if (res.status === 401) {
        const refresh = localStorage.getItem('refresh_token');
        if (refresh) {
            const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refresh })
            });
            if (refreshRes.ok) {
                const data = await refreshRes.json();
                localStorage.setItem('access_token', data.access_token);
                if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
                // Retry requested fetch
                options.headers['Authorization'] = `Bearer ${data.access_token}`;
                res = await fetch(url, options);
            } else {
                kickToLogin();
            }
        } else {
            kickToLogin();
        }
    }
    return res;
};

const kickToLogin = () => {
    localStorage.clear();
    window.location.href = '/auth/login/';
};

// -------------------------------------------------------------
// App Initialization
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    // Only run main app logic if we are on /app/ endpoint
    if (!window.location.pathname.startsWith('/app')) return;

    if (!localStorage.getItem('access_token')) {
        kickToLogin();
        return;
    }

    try {
        const res = await fetchAuth(`${API_BASE}/users/me`);
        if (res.ok) {
            currentUser = await res.json();
            document.getElementById('my-username').textContent = `${currentUser.username} (ID: ${currentUser.id})`;
            if (currentUser.avatar) {
                const img = document.getElementById('my-avatar');
                img.src = currentUser.avatar;
                img.classList.remove('hidden');
            }
            initWebSocket();
            loadGroupsList();
        } else {
            kickToLogin();
        }
    } catch {
        kickToLogin();
    }

    setupUIEventListeners();
});

// -------------------------------------------------------------
// WebSocket Logic
// -------------------------------------------------------------
function initWebSocket() {
    const token = localStorage.getItem('access_token');
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${wsProto}//${window.location.host}/ws/chat/?token=${token}`);

    ws.onopen = () => {
        console.log("WebSocket connected.");
        // Notify presence implicitly handled by connect/disconnect in consumer
    };

    ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        handleSocketEvent(data);
    };

    ws.onclose = (e) => {
        console.log("WebSocket closed", e.code);
        if (e.code === 4001) {
            kickToLogin(); // Token invalid
        } else {
            // Auto reconnect after 3s
            setTimeout(initWebSocket, 3000);
        }
    };
}

function handleSocketEvent(data) {
    if (data.error) {
        console.error("WS Error:", data.error);
        return;
    }

    const { event } = data;
    if (event === "new_message") {
        const msg = data.message;
        let messageRoomId = null;
        if (msg.type === 'group') messageRoomId = `group_${msg.group}`;
        else if (msg.type === 'channel') messageRoomId = `channel_${msg.channel}`;
        else if (msg.type === 'private') {
            const a = Math.min(msg.sender.id, msg.receiver);
            const b = Math.max(msg.sender.id, msg.receiver);
            messageRoomId = `private_${a}_${b}`;
        }

        const isMyMsg = msg.sender.id === currentUser.id;
        const roomMatch = activeRoomId === messageRoomId;
        
        if (roomMatch) {
            appendMessage(msg, true);
            // Mark as read immediately if we are actively viewing this room
            if (!isMyMsg && ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action: "mark_as_read", messageId: msg.id }));
            }
        }
        
        updateGroupListPreview(msg);

    } else if (event === "message_delivered") {
        updateMessageStatus(data.messageId, "delivered");
    } else if (event === "message_read") {
        updateMessageStatus(data.messageId, "read");
    } else if (event === "user_typing") {
        if (activeRoomId === data.roomId) {
            showTypingIndicator();
        }
    } else if (event === "presence_update") {
        // e.g., update member list online status
        updatePresence(data.userId, data.status);
    }
}

// -------------------------------------------------------------
// UI Renderers & Loaders
// -------------------------------------------------------------
async function loadGroupsList() {
    const container = document.getElementById('groups-list');
    const res = await fetchAuth(`${API_BASE}/groups/`);
    if (!res.ok) return;

    const groups = await res.json();
    container.innerHTML = '';
    
    if (groups.length === 0) {
        container.innerHTML = `<div class="p-4 text-center text-sm text-[#8696a0]">No groups yet. Create one!</div>`;
        // but we still want to show active chats!
    }

    groups.forEach(group => {
        // Render Group wrapper
        const el = document.createElement('div');
        el.className = "group-item w-full";
        
        let html = `
            <div class="flex items-center px-4 py-3 cursor-pointer hover:bg-wa-panel transition-colors border-b border-wa-panel/30" onclick="expandGroupChannels('${group.id}', '${group.name}')">
                <div class="w-12 h-12 rounded-full overflow-hidden shrink-0 bg-gray-600">
                    <img src="${group.avatar || 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='}" class="w-full h-full object-cover">
                </div>
                <div class="ml-4 flex-1 outline-none relative w-full overflow-hidden">
                    <div class="flex justify-between items-center mb-1">
                        <span class="text-wa-light truncate font-semibold">${group.name}</span>
                    </div>
                </div>
            </div>
            <!-- Channels subset hidden by default -->
            <div id="channels-${group.id}" class="hidden flex-col bg-[#182229]">
        `;

        if (group.channels) {
            group.channels.forEach(ch => {
                html += `
                <div class="flex items-center pl-16 pr-4 py-2 cursor-pointer hover:bg-wa-panel transition-colors border-b border-wa-panel/10" onclick="openRoom('channel', '${ch.id}', '#${ch.name} (in ${group.name})'); event.stopPropagation();">
                    <span class="text-[#8696a0] truncate text-sm"># ${ch.name}</span>
                </div>
                `;
            });
        }
        
        html += `</div>`;
        el.innerHTML = html;
        container.appendChild(el);
    });
    
    renderActivePrivateChats();
}

// Memory array for private chats during session
let activePrivateChats = [];

function renderActivePrivateChats() {
    const container = document.getElementById('groups-list');
    if (!container) return;
    document.querySelectorAll('.private-chat-preview').forEach(el => el.remove());
    
    // Reverse array to insert older ones first so unshift preserves order visually if we do container.firstChild insert
    const reversed = [...activePrivateChats].reverse();
    reversed.forEach(chat => {
        const el = document.createElement('div');
        el.id = `chat-preview-${chat.id}`;
        el.className = "private-chat-preview flex items-center px-4 py-3 cursor-pointer hover:bg-wa-panel transition-colors border-b border-wa-panel/30";
        el.onclick = () => openRoom('private', chat.id, chat.user.username || "Private Chat");
        el.innerHTML = `
            <div class="w-12 h-12 rounded-full overflow-hidden shrink-0 bg-gray-600">
                <img src="${chat.user.avatar || 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='}" class="w-full h-full object-cover">
            </div>
            <div class="ml-4 flex-1 outline-none relative w-full overflow-hidden">
                <div class="flex justify-between items-center mb-1">
                    <span class="text-wa-light truncate font-semibold">${chat.user.username || "Private Chat"}</span>
                    <span class="text-xs text-[#53bdeb] font-semibold">Active Chat</span>
                </div>
            </div>
        `;
        container.insertBefore(el, container.firstChild);
    });
}

// Search functionality
document.getElementById('search-input')?.addEventListener('input', async (e) => {
    const q = e.target.value.trim();
    if (!q) {
        loadGroupsList();
        return;
    }
    const container = document.getElementById('groups-list');
    container.innerHTML = '<div class="p-4 text-center text-sm text-[#8696a0]">Searching users...</div>';
    
    const res = await fetchAuth(`${API_BASE}/users/?q=${encodeURIComponent(q)}`);
    if (res.ok) {
        const users = await res.json();
        container.innerHTML = '';
        if (users.length === 0) {
            container.innerHTML = `<div class="p-4 text-center text-sm text-[#8696a0]">No users found.</div>`;
            return;
        }
        users.forEach(u => {
            const el = document.createElement('div');
            el.className = "flex items-center px-4 py-3 cursor-pointer hover:bg-wa-panel transition-colors border-b border-wa-panel/30";
            
            // Format canonical private room id
            const a = Math.min(currentUser.id, u.id);
            const b = Math.max(currentUser.id, u.id);
            const canonicalId = `${a}_${b}`;
            
            el.onclick = () => openRoom('private', canonicalId, u.username);
            el.innerHTML = `
                <div class="w-12 h-12 rounded-full overflow-hidden shrink-0 bg-gray-600">
                    <img src="${u.avatar || 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='}" class="w-full h-full object-cover">
                </div>
                <div class="ml-4 flex-1 outline-none relative w-full overflow-hidden">
                    <div class="flex justify-between items-center mb-1">
                        <span class="text-wa-light truncate font-semibold">${u.username}</span>
                    </div>
                    <span class="text-[#8696a0] text-sm hidden">Start private chat</span>
                </div>
            `;
            container.appendChild(el);
        });
    }
});

window.expandGroupChannels = (groupId, groupName) => {
    const chDiv = document.getElementById(`channels-${groupId}`);
    if (chDiv.classList.contains('hidden')) {
        chDiv.classList.remove('hidden');
        chDiv.classList.add('flex');
    } else {
        chDiv.classList.add('hidden');
        chDiv.classList.remove('flex');
    }
    // Also open the group room itself
    openRoom('group', groupId, groupName);
};

window.openRoom = async (type, id, displayName) => {
    activeRoomId = `${type}_${id}`;
    document.getElementById('no-chat-selected').classList.add('hidden');
    document.getElementById('active-chat-name').textContent = displayName;
    document.getElementById('message-input').disabled = false;
    document.getElementById('messages-list').innerHTML = '';
    
    // Join room via WS
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: "join_room", roomId: activeRoomId }));
    }

    // Load History
    let url = `${API_BASE}/messages/channel/${id}/`; // fallback for channels
    if (type === 'group') url = `${API_BASE}/messages/group/${id}/`;
    if (type === 'private') {
        const ids = id.split('_');
        const otherId = String(ids[0]) === String(currentUser.id) ? ids[1] : ids[0];
        url = `${API_BASE}/messages/private/${otherId}/`;
    }

    const res = await fetchAuth(url);
    if (res.ok) {
        const data = await res.json();
        const results = data.results || data; 
        const reversed = [...results].reverse();
        reversed.forEach(m => {
            appendMessage(m, false);
            // Mark unread messages as read when catching up in the active room
            if (m.sender.id !== currentUser.id && ws && ws.readyState === WebSocket.OPEN) {
                 const iReadIt = m.statuses && m.statuses.some(s => s.user.id === currentUser.id && s.status === 'read');
                 if (!iReadIt) {
                     ws.send(JSON.stringify({ action: "mark_as_read", messageId: m.id }));
                 }
            }
        });
        scrollToBottom();
    }
    
    // Load Info
    loadRoomInfo(type, id);
};

// -------------------------------------------------------------
// Message Logic
// -------------------------------------------------------------
function appendMessage(msg, smoothScroll = false) {
    if (document.getElementById(`msg-${msg.id}`)) return; // Prevents duplicate rendering!

    const container = document.getElementById('messages-list');
    const isMe = msg.sender.id === currentUser.id;
    
    const div = document.createElement('div');
    div.id = `msg-${msg.id}`;
    div.className = `max-w-[85%] rounded-lg p-2 text-sm relative message-in ${isMe ? 'bg-wa-outgoing self-end text-wa-light' : 'bg-wa-incoming self-start text-wa-light'}`;
    
    let contentHtml = '';
    const tokenParams = msg.file_url ? (msg.file_url.includes('?') ? `&token=${localStorage.getItem('access_token')}` : `?token=${localStorage.getItem('access_token')}`) : '';
    const secureUrl = msg.file_url ? `${msg.file_url}${tokenParams}` : '';

    if (msg.message_type === 'image' && msg.file_url) {
        contentHtml = `<img src="${secureUrl}" class="chat-image mb-1" onclick="window.open(this.src)"/>`;
    } else if (msg.message_type === 'file' && msg.file_url) {
        contentHtml = `<div class="bg-black/20 p-2 rounded flex items-center mb-1 cursor-pointer" onclick="window.open('${secureUrl}')"><span class="material-symbols-outlined mr-2">description</span> Document</div>`;
    }

    contentHtml += `<div class="break-words">${escapeHTML(msg.content)}</div>`;

    // Status ticks (only if isMe)
    let statusIcon = '';
    if (isMe) {
        const statusStr = msg.statuses && msg.statuses.length ? getMinStatus(msg.statuses) : 'sent';
        let iconHtml = "check";
        let iconColor = "text-[#8696a0]";
        if (statusStr === "delivered") iconHtml = "done_all";
        if (statusStr === "read") { iconHtml = "done_all"; iconColor = "text-[#53bdeb]"; }
        
        statusIcon = `<span id="status-${msg.id}" class="material-symbols-outlined text-[14px] ml-1 inline align-middle ${iconColor}">${iconHtml}</span>`;
    }

    const timeString = new Date(msg.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

    div.innerHTML = `
        ${!isMe ? `<div class="text-[12px] font-semibold text-[#53bdeb] mb-0.5">${msg.sender.username}</div>` : ''}
        ${contentHtml}
        <div class="text-[11px] text-right text-gray-400 mt-1 float-right flex items-center ml-2">
            ${timeString} ${statusIcon}
        </div>
        <div class="clear-both"></div>
    `;

    container.appendChild(div);

    if (smoothScroll) {
        scrollToBottom();
    }
}

function scrollToBottom() {
    const el = document.getElementById('messages-container');
    if (el) el.scrollTop = el.scrollHeight;
}

function getMinStatus(statuses) {
    // If ANY read -> read, else if ANY delivered -> delivered, else sent
    if (statuses.some(s => s.status === 'read')) return 'read';
    if (statuses.some(s => s.status === 'delivered')) return 'delivered';
    return 'sent';
}

function updateMessageStatus(msgId, statusVar) {
    const el = document.getElementById(`status-${msgId}`);
    if (el) {
        el.textContent = "done_all";
        if (statusVar === "read") {
            el.classList.remove("text-[#8696a0]");
            el.classList.add("text-[#53bdeb]");
        }
    }
}

let typingTimer;
function showTypingIndicator() {
    const ind = document.getElementById('typing-indicator');
    if (ind) {
        ind.classList.remove('hidden');
        clearTimeout(typingTimer);
        scrollToBottom();
        typingTimer = setTimeout(() => {
            ind.classList.add('hidden');
        }, 3000);
    }
}

function updateGroupListPreview(msg) {
    if (msg.type !== 'private') return;
    
    const otherUser = String(msg.sender.id) === String(currentUser.id) ? {id: msg.receiver, username: "User"} : msg.sender;
    const a = Math.min(currentUser.id, otherUser.id);
    const b = Math.max(currentUser.id, otherUser.id);
    const canonicalId = `${a}_${b}`;
    
    const exists = activePrivateChats.find(c => c.id === canonicalId);
    if (!exists) {
        activePrivateChats.unshift({
            id: canonicalId,
            user: otherUser
        });
        renderActivePrivateChats();
    }
}

function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}

// -------------------------------------------------------------
// Interactive UI logic
// -------------------------------------------------------------
function setupUIEventListeners() {
    const btnLogout = document.getElementById('btn-logout');
    if (btnLogout) btnLogout.onclick = async () => {
        const refresh = localStorage.getItem('refresh_token');
        if (refresh) {
            await fetchAuth(`${API_BASE}/auth/logout`, {
                method: 'POST',
                headers:{ 'Content-Type': 'application/json' },
                body: JSON.stringify({refresh_token: refresh})
            });
        }
        kickToLogin();
    };

    const inputArea = document.getElementById('message-input');
    if (inputArea) {
        inputArea.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && inputArea.value.trim() !== '') {
                sendMessageViaWS();
            }
            if (ws && activeRoomId) {
                ws.send(JSON.stringify({action: 'typing', roomId: activeRoomId}));
            }
        });
    }

    const btnSend = document.getElementById('btn-send-message');
    if (btnSend) {
        btnSend.onclick = () => {
            if (inputArea.value.trim() !== '') sendMessageViaWS();
        };
    }

    const btnAttach = document.getElementById('btn-attach');
    if (btnAttach) {
        btnAttach.onclick = () => {
            document.getElementById('file-input').click();
        };
    }

    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const isImg = file.type.startsWith('image/');
            const formData = new FormData();
            formData.append('file', file);
            formData.append('type', isImg ? 'image' : 'file');

            try {
                const res = await fetch(`${API_BASE}/files/upload/`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
                    body: formData
                });

                if (res.ok) {
                    const data = await res.json();
                    if (ws && activeRoomId) {
                        ws.send(JSON.stringify({
                            action: 'send_message',
                            roomId: activeRoomId,
                            content: file.name,
                            messageType: data.type,
                            fileUrl: data.fileUrl
                        }));
                    }
                } else {
                    alert("Upload failed. Max size is 10MB for images, 50MB for files.");
                }
            } catch (err) {
                console.error(err);
                alert("Error uploading file.");
            }
            e.target.value = ''; 
        };
    }

    document.getElementById('btn-emoji')?.addEventListener('click', () => {
        const input = document.getElementById('message-input');
        if (input) {
            input.value += '😀';
            input.focus();
        }
    });

    const rightPanel = document.getElementById('right-panel');
    const chatHeader = document.getElementById('chat-header');
    if (chatHeader && rightPanel) {
        chatHeader.onclick = () => {
            rightPanel.classList.remove('w-0');
            rightPanel.classList.add('w-80');
        };
    }
    
    const btnCloseRight = document.getElementById('btn-close-right');
    if (btnCloseRight && rightPanel) {
        btnCloseRight.onclick = () => {
            rightPanel.classList.add('w-0');
            rightPanel.classList.remove('w-80');
        };
    }

    const btnCreateGroup = document.getElementById('btn-create-group');
    if (btnCreateGroup) {
        btnCreateGroup.onclick = () => {
            document.getElementById('modal-create-group').classList.remove('hidden');
        };
    }
    
    const btnCancelGroup = document.getElementById('btn-cancel-group');
    if (btnCancelGroup) {
        btnCancelGroup.onclick = () => {
            document.getElementById('modal-create-group').classList.add('hidden');
        };
    }
    
    const btnSubmitGroup = document.getElementById('btn-submit-group');
    if (btnSubmitGroup) {
        btnSubmitGroup.onclick = async () => {
            const name = document.getElementById('new-group-name').value;
            if (!name) return;
            const res = await fetchAuth(`${API_BASE}/groups/`, {
                method: 'POST',
                headers:{ 'Content-Type': 'application/json' },
                body: JSON.stringify({name, subscription_type: 'open'})
            });
            if (res.ok) {
                document.getElementById('modal-create-group').classList.add('hidden');
                document.getElementById('new-group-name').value = '';
                loadGroupsList(); 
            }
        };
    }
}

function sendMessageViaWS() {
    const input = document.getElementById('message-input');
    const content = input.value.trim();
    if (ws && ws.readyState === WebSocket.OPEN && content) {
        ws.send(JSON.stringify({
            action: 'send_message',
            roomId: activeRoomId,
            content: content,
            messageType: 'text'
        }));
        input.value = '';
    }
}

async function loadRoomInfo(type, id) {
    const membersContainer = document.getElementById('info-members');
    const nameEl = document.getElementById('info-name');
    const descEl = document.getElementById('info-desc');
    
    if (type === 'group') {
        const res = await fetchAuth(`${API_BASE}/groups/${id}/`);
        if (res.ok) {
            const group = await res.json();
            nameEl.textContent = group.name;
            descEl.textContent = group.description || 'No description';
            
            const avatarImg = document.getElementById('info-avatar');
            if (avatarImg) {
                avatarImg.src = group.avatar || "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=";
            }
            
            const mRes = await fetchAuth(`${API_BASE}/groups/${id}/members/`);
            if (mRes.ok) {
                const members = await mRes.json();
                membersContainer.innerHTML = '';
                members.forEach(m => {
                    membersContainer.innerHTML += `
                        <div class="flex items-center gap-3 py-2">
                            <div class="w-10 h-10 rounded-full bg-gray-600 overflow-hidden shrink-0">
                                <img src="${m.user.avatar || 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='}" class="w-full h-full object-cover">
                            </div>
                            <div class="flex-1">
                                <span class="text-wa-light">${m.user.username} <span class="text-xs text-[#8696a0] ml-2 font-normal">${m.role} (ID: ${m.user.id})</span></span>
                            </div>
                        </div>
                    `;
                });

                const isOwnerOrAdmin = members.some(m => m.user.id === currentUser.id && (m.role === 'admin' || m.role === 'owner'));
                if (isOwnerOrAdmin) {
                    membersContainer.innerHTML += `
                        <div class="mt-4 border-t border-wa-border pt-4">
                            <input type="number" id="new-member-id" placeholder="User ID to add" class="w-full bg-[#2a3942] rounded px-3 py-2 text-sm text-wa-light outline-none mb-2">
                            <button onclick="addMemberToGroup('${id}')" class="w-full bg-[#00a884] text-[#111b21] rounded py-2 text-sm font-semibold hover:bg-[#008f6f]">Add Member</button>
                        </div>
                    `;
                }
            }
        }
    } else if (type === 'private') {
         nameEl.textContent = "Private Chat";
         descEl.textContent = "End-to-end encrypted";
         membersContainer.innerHTML = '<div class="text-[#8696a0] text-sm">Just you and the other user.</div>';
    } else if (type === 'channel') {
         nameEl.textContent = "Channel";
         descEl.textContent = "Part of a group";
         membersContainer.innerHTML = '<div class="text-[#8696a0] text-sm">Members are managed at the group level.</div>';
    }
}

window.addMemberToGroup = async (groupId) => {
    const input = document.getElementById('new-member-id');
    const userId = parseInt(input.value);
    if (!userId) return;
    
    const res = await fetchAuth(`${API_BASE}/groups/${groupId}/members/`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ userId })
    });
    if (res.ok) {
        if (input) input.value = '';
        loadRoomInfo('group', groupId);
    } else {
        const d = await res.json();
        alert("Failed to add member: " + (d.error?.message || ""));
    }
};

function updatePresence(userId, status) {
    // Left empty for now
}
