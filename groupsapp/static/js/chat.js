/**
 * GroupsApp Chat – Client-side logic.
 *
 * Extracted from inline <script> in chat.html for maintainability.
 * Organised into logical sections:
 *   1. State
 *   2. Helpers
 *   3. WebSocket
 *   4. WS Event Handlers
 *   5. Message Rendering
 *   6. Room Opening (Private / Group)
 *   7. Conversations & Search
 *   8. File Upload
 *   9. Group Info Panel
 *  10. Group Creation Modal
 *  11. Initialisation
 */

"use strict";

// ═══════════════════════════════════════════════════════════════════
// 1. STATE
// ═══════════════════════════════════════════════════════════════════
/** @type {number|null} */
let MY_ID = null;
/** @type {string} */
let MY_USERNAME = "";
/** @type {WebSocket|null} */
let ws = null;
/**
 * Active room descriptor.
 * @type {{ kind: 'private'|'group', roomId: string, name: string, otherId?: number, groupId?: string }|null}
 */
let activeRoom = null;
/** @type {Object<string, 'sent'|'delivered'|'read'>} */
const pendingStatus = {};
/** @type {Set<string>} JSON-encoded {id, name} objects */
const selectedInitialMembers = new Set();


// ═══════════════════════════════════════════════════════════════════
// 2. HELPERS
// ═══════════════════════════════════════════════════════════════════

/** @returns {string|null} */
function getToken() {
    return localStorage.getItem("access_token");
}

/**
 * Authenticated fetch wrapper.
 * @param {string} path
 * @param {RequestInit} opts
 * @returns {Promise<Response>}
 */
async function apiFetch(path, opts = {}) {
    const token = getToken();
    return fetch(path, {
        ...opts,
        headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: "Bearer " + token } : {}),
            ...(opts.headers || {}),
        },
    });
}

function logout() {
    const rt = localStorage.getItem("refresh_token");
    if (rt) {
        apiFetch("/api/auth/logout", {
            method: "POST",
            body: JSON.stringify({ refresh_token: rt }),
        }).catch(() => {});
    }
    localStorage.clear();
    window.location.href = "/auth/login/";
}

/**
 * Escape HTML to prevent XSS.
 * @param {string} s
 * @returns {string}
 */
function escHtml(s) {
    if (!s) return "";
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

/**
 * Format an ISO date string to a short time (HH:MM).
 * @param {string} iso
 * @returns {string}
 */
function timeStr(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
    });
}


// ═══════════════════════════════════════════════════════════════════
// 3. WEBSOCKET
// ═══════════════════════════════════════════════════════════════════

function connectWS() {
    const token = getToken();
    if (!token) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/chat/?token=${token}`);

    ws.onopen = () => {
        console.log("WS connected");
        if (activeRoom) joinRoom(activeRoom.roomId);
    };

    ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        handleWsEvent(data);
    };

    ws.onclose = () => {
        console.log("WS disconnected, retrying…");
        setTimeout(connectWS, 3000);
    };
}

/**
 * Send a JSON payload over the WebSocket (if open).
 * @param {object} payload
 */
function wsSend(payload) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(payload));
    }
}

/** @param {string} roomId */
function joinRoom(roomId) {
    wsSend({ action: "join_room", roomId });
}


// ═══════════════════════════════════════════════════════════════════
// 4. WS EVENT HANDLERS
// ═══════════════════════════════════════════════════════════════════

/** @param {object} data */
function handleWsEvent(data) {
    switch (data.event) {
        case "new_message":
            onNewMessage(data.message);
            break;
        case "message_delivered":
            onStatusUpdate(data.messageId, "delivered");
            break;
        case "message_read":
            onStatusUpdate(data.messageId, "read");
            break;
        case "user_typing":
            onTyping(data);
            break;
        case "presence_update":
            break;
    }
}


// ═══════════════════════════════════════════════════════════════════
// 5. MESSAGE RENDERING
// ═══════════════════════════════════════════════════════════════════

/**
 * Return an HTML snippet for the message status icon.
 * @param {'sent'|'delivered'|'read'} status
 * @returns {string}
 */
function statusIcon(status) {
    if (status === "read")
        return '<span class="msg-tick read">✓✓</span>';
    if (status === "delivered")
        return '<span class="msg-tick delivered">✓✓</span>';
    return '<span class="msg-tick sent">✓</span>';
}

/**
 * Build a DOM element for a single message bubble.
 * @param {object} msg
 * @param {string} [status='sent']
 * @returns {HTMLDivElement}
 */
function buildMessageEl(msg, status = "sent") {
    const isMine = msg.sender.id === MY_ID;
    const el = document.createElement("div");
    el.dataset.msgId = msg.id;
    el.className = `flex ${isMine ? "justify-end" : "justify-start"} mb-1 px-4 relative`;

    const actualStatus = isMine
        ? pendingStatus[msg.id] || status || "sent"
        : null;

    let contentHtml = `<p class="break-words leading-relaxed ${msg.message_type === "image" ? "pb-1" : "pb-3"}">${escHtml(msg.content)}</p>`;
    if (msg.message_type === "image" && msg.file_url) {
        contentHtml += `<img src="${msg.file_url}" class="msg-image" onclick="window.open('${msg.file_url}', '_blank')">`;
    }

    const bubble = `
        <div class="relative max-w-[85%] min-w-[80px] px-3 py-1.5 rounded-lg text-sm shadow
            ${isMine ? "bg-[#005c4b] text-[#e9edef] rounded-tr-none" : "bg-[#202c33] text-[#e9edef] rounded-tl-none"}">
            ${!isMine && activeRoom?.kind !== "private" ? `<p class="text-xs font-semibold text-[#00a884] mb-0.5">${escHtml(msg.sender.username)}</p>` : ""}
            ${contentHtml}
            <div class="${msg.message_type === "image" ? "mt-1 mb-1" : "absolute bottom-1 right-2"} flex items-center gap-1 justify-end">
                <span class="text-[10px] text-[#8696a0]">${timeStr(msg.created_at)}</span>
                ${isMine ? statusIcon(actualStatus) : ""}
            </div>
        </div>`;
    el.innerHTML = bubble;
    return el;
}

/**
 * Determine which room a message belongs to.
 * @param {object} msg
 * @returns {string|null}
 */
function getRoomIdFromMsg(msg) {
    if (msg.type === "private") {
        const otherId =
            msg.sender.id === MY_ID ? msg.receiver : msg.sender.id;
        const ids = [String(MY_ID), String(otherId)].sort();
        return `private_${ids[0]}_${ids[1]}`;
    }
    if (msg.type === "group") return `group_${msg.group}`;
    if (msg.type === "channel") return `channel_${msg.channel}`;
    return null;
}

/** @param {object} msg */
function onNewMessage(msg) {
    const roomId = getRoomIdFromMsg(msg);
    if (!roomId) return;

    const isMine = msg.sender.id === MY_ID;

    // Update sidebar
    const convData = {
        kind: msg.type,
        id:
            msg.type === "private"
                ? isMine
                    ? msg.receiver
                    : msg.sender.id
                : msg.type === "group"
                  ? msg.group
                  : msg.channel,
        name:
            msg.type === "private"
                ? isMine
                    ? activeRoom?.name || "User"
                    : msg.sender.username
                : "Group",
        last_message: msg,
    };
    if (convData.kind === "private" && !isMine)
        convData.name = msg.sender.username;
    addConversationToDom(convData, true);

    // Deduplicate
    if (document.querySelector(`[data-msg-id="${msg.id}"]`)) return;

    if (activeRoom && activeRoom.roomId === roomId) {
        const list = document.getElementById("messages-list");
        const st = isMine ? "sent" : null;
        const el = buildMessageEl(msg, st);
        list.appendChild(el);
        list.parentElement.scrollTo({
            top: list.parentElement.scrollHeight,
            behavior: "smooth",
        });

        if (!isMine) {
            wsSend({ action: "mark_as_read", messageId: msg.id });
        }
    }
}

/**
 * Update a message's status tick in the DOM.
 * @param {string} messageId
 * @param {'sent'|'delivered'|'read'} newStatus
 */
function onStatusUpdate(messageId, newStatus) {
    const rank = { sent: 1, delivered: 2, read: 3 };
    if (
        !pendingStatus[messageId] ||
        rank[newStatus] > rank[pendingStatus[messageId]]
    ) {
        pendingStatus[messageId] = newStatus;
    }
    const msgEl = document.querySelector(`[data-msg-id="${messageId}"]`);
    if (msgEl) {
        const tick = msgEl.querySelector(".msg-tick");
        if (tick) tick.outerHTML = statusIcon(pendingStatus[messageId]);
    }
}

let typingTimer;
/** @param {object} data */
function onTyping(data) {
    if (data.userId === MY_ID) return;
    if (activeRoom && activeRoom.roomId === data.roomId) {
        const ind = document.getElementById("typing-indicator");
        ind.classList.remove("hidden");
        clearTimeout(typingTimer);
        typingTimer = setTimeout(() => ind.classList.add("hidden"), 2000);
    }
}


// ═══════════════════════════════════════════════════════════════════
// 6. ROOM OPENING
// ═══════════════════════════════════════════════════════════════════

/**
 * Open a private chat with another user.
 * @param {{ id: number, username: string }} otherUser
 */
async function openPrivateChat(otherUser) {
    const ids = [String(MY_ID), String(otherUser.id)].sort();
    const roomId = `private_${ids[0]}_${ids[1]}`;

    document.getElementById("no-chat-selected").classList.add("hidden");
    document.getElementById("active-chat-name").textContent =
        otherUser.username;
    document.getElementById("active-chat-status").textContent = "online";

    document.getElementById("message-input").disabled = false;
    document.getElementById("message-input").focus();
    const list = document.getElementById("messages-list");
    list.innerHTML = "";
    document.getElementById("typing-indicator").classList.add("hidden");

    activeRoom = {
        kind: "private",
        roomId,
        name: otherUser.username,
        otherId: otherUser.id,
    };

    joinRoom(roomId);

    try {
        const res = await apiFetch(`/api/messages/private/${otherUser.id}/`);
        if (res.ok) {
            const data = await res.json();
            const messages = data.results || data;
            const sorted = Array.isArray(messages)
                ? messages.slice().reverse()
                : [];

            sorted.forEach((msg) => {
                const el = buildMessageEl(msg, msg.status);
                list.appendChild(el);
            });

            list.parentElement.scrollTop = list.parentElement.scrollHeight;

            sorted.forEach((msg) => {
                if (msg.sender.id !== MY_ID && msg.status !== "read") {
                    wsSend({ action: "mark_as_read", messageId: msg.id });
                }
            });
        }
    } catch (e) {
        console.error("History load failed:", e);
    }
}

/**
 * Open a group chat.
 * @param {{ id: string, name: string }} group
 */
async function openGroupChat(group) {
    const roomId = `group_${group.id}`;
    document.getElementById("no-chat-selected").classList.add("hidden");
    document.getElementById("active-chat-name").textContent = group.name;
    document.getElementById("active-chat-status").textContent = "group";
    document.getElementById("message-input").disabled = false;
    document.getElementById("message-input").focus();
    const list = document.getElementById("messages-list");
    list.innerHTML = "";

    activeRoom = {
        kind: "group",
        roomId,
        name: group.name,
        groupId: group.id,
    };
    joinRoom(roomId);

    try {
        const res = await apiFetch(`/api/messages/group/${group.id}/`);
        if (res.ok) {
            const data = await res.json();
            const messages = data.results || data;
            const sorted = Array.isArray(messages)
                ? messages.slice().reverse()
                : [];
            sorted.forEach((msg) => {
                const el = buildMessageEl(msg, msg.status);
                list.appendChild(el);
            });
            list.parentElement.scrollTop = list.parentElement.scrollHeight;
        }
    } catch (e) {
        console.error("Group history fail:", e);
    }
}


// ═══════════════════════════════════════════════════════════════════
// 7. CONVERSATIONS & SEARCH
// ═══════════════════════════════════════════════════════════════════

function sendMessage() {
    const input = document.getElementById("message-input");
    const content = input.value.trim();
    if (!content || !activeRoom) return;
    input.value = "";

    wsSend({
        action: "send_message",
        roomId: activeRoom.roomId,
        content,
        messageType: "text",
    });
}

/**
 * Search users and render results in the sidebar.
 * @param {string} query
 */
async function searchUsers(query) {
    const list = document.getElementById("groups-list");
    const loading = document.getElementById("loading-groups");

    [...list.querySelectorAll(".group-item,.user-item")].forEach((el) =>
        el.remove()
    );
    loading.textContent = "Searching…";
    loading.classList.remove("hidden");

    try {
        const res = await apiFetch(
            `/api/users/search/?q=${encodeURIComponent(query)}`
        );
        loading.classList.add("hidden");
        if (!res.ok) return;
        const users = await res.json();

        if (users.length === 0) {
            loading.textContent = "No results found.";
            loading.classList.remove("hidden");
            return;
        }

        users.forEach((u) => {
            if (u.id === MY_ID) return;
            const item = document.createElement("div");
            item.className =
                "user-item flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-wa-panel transition-colors border-b border-wa-border";
            item.innerHTML = `
                <div class="w-12 h-12 rounded-full bg-[#00a884] flex items-center justify-center text-lg font-bold text-white shrink-0">
                    ${u.username[0].toUpperCase()}
                </div>
                <div class="flex-1 min-w-0">
                    <p class="font-semibold text-wa-light truncate">${escHtml(u.username)}</p>
                    <p class="text-xs text-[#8696a0] truncate">${escHtml(u.email)}</p>
                </div>`;
            item.addEventListener("click", () => openPrivateChat(u));
            list.appendChild(item);
        });
    } catch (e) {
        console.error("Search failed:", e);
    }
}

async function loadConversations() {
    const list = document.getElementById("groups-list");
    const loading = document.getElementById("loading-groups");

    loading.textContent = "Loading chats…";
    loading.classList.remove("hidden");
    [...list.querySelectorAll(".group-item,.user-item,.conv-item")].forEach(
        (el) => el.remove()
    );

    try {
        const res = await apiFetch("/api/messages/conversations/");
        if (!res.ok) {
            const errText = await res.text();
            console.error("Conversations API error:", res.status, errText);
            loading.textContent = "Error loading chats (" + res.status + ")";
            loading.classList.remove("hidden");
            return;
        }
        const conversations = await res.json();
        loading.classList.add("hidden");

        if (conversations.length === 0) {
            loading.textContent = "Use the search bar to find users!";
            loading.classList.remove("hidden");
            return;
        }

        conversations.forEach((c) => addConversationToDom(c));
    } catch (e) {
        console.error("Conversations load failed:", e);
        loading.textContent = "Error: " + e.message;
        loading.classList.remove("hidden");
    }
}

/**
 * Add or update a conversation item in the sidebar.
 * @param {object} c
 * @param {boolean} [moveToTop=false]
 */
function addConversationToDom(c, moveToTop = false) {
    const list = document.getElementById("groups-list");
    const existing = list.querySelector(`[data-conv-id="${c.kind}_${c.id}"]`);
    if (existing) existing.remove();

    const item = document.createElement("div");
    item.dataset.convId = `${c.kind}_${c.id}`;
    item.className =
        "conv-item flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-wa-panel transition-colors border-b border-wa-border";
    if (activeRoom && activeRoom.roomId === `${c.kind}_${c.id}`)
        item.classList.add("active");

    const lastMsgText = c.last_message
        ? c.last_message.message_type === "image"
            ? "📷 Photo"
            : c.last_message.content
        : c.kind === "group"
          ? "No messages yet"
          : "Private chat";

    item.innerHTML = `
        <div class="w-12 h-12 rounded-full ${c.kind === "private" ? "bg-[#00a884]" : "bg-gray-600"} flex items-center justify-center text-lg font-semibold text-white shrink-0">
            ${c.name[0].toUpperCase()}
        </div>
        <div class="flex-1 min-w-0">
            <div class="flex justify-between items-baseline mb-0.5">
                <p class="font-semibold text-wa-light truncate pr-2">${escHtml(c.name)}</p>
                <span class="text-[11px] text-[#8696a0] shrink-0">${c.last_message ? timeStr(c.last_message.created_at) : ""}</span>
            </div>
            <p class="text-xs text-[#8696a0] truncate">${escHtml(lastMsgText)}</p>
        </div>`;

    item.addEventListener("click", () => {
        [...list.querySelectorAll(".conv-item")].forEach((el) =>
            el.classList.remove("active")
        );
        item.classList.add("active");
        if (c.kind === "private") {
            openPrivateChat({ id: c.id, username: c.name });
        } else {
            openGroupChat(c);
        }
    });

    if (moveToTop) {
        list.prepend(item);
    } else {
        list.appendChild(item);
    }
}


// ═══════════════════════════════════════════════════════════════════
// 8. FILE UPLOAD
// ═══════════════════════════════════════════════════════════════════

/**
 * Upload a file to the server.
 * @param {File} file
 * @returns {Promise<string|null>} The URL, or null on failure.
 */
async function uploadFile(file) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("type", file.type.startsWith("image/") ? "image" : "file");

    try {
        const token = getToken();
        const res = await fetch("/api/files/upload/", {
            method: "POST",
            headers: { Authorization: "Bearer " + token },
            body: formData,
        });

        if (res.ok) {
            const data = await res.json();
            return data.url;
        }
    } catch (e) {
        console.error("Upload failed:", e);
    }
    return null;
}

/**
 * Upload and send an image message.
 * @param {File} file
 */
async function sendImage(file) {
    const url = await uploadFile(file);
    if (!url || !activeRoom) return;

    wsSend({
        action: "send_message",
        roomId: activeRoom.roomId,
        content: "",
        messageType: "image",
        fileUrl: url,
    });
}


// ═══════════════════════════════════════════════════════════════════
// 9. GROUP INFO PANEL
// ═══════════════════════════════════════════════════════════════════

async function openGroupInfo() {
    if (!activeRoom) return;
    const panel = document.getElementById("right-panel");
    panel.style.width = "350px";

    document.getElementById("info-name").textContent = activeRoom.name;
    document.getElementById("info-desc").textContent =
        activeRoom.kind === "group" ? "Group chat" : "Private chat";

    document
        .getElementById("add-member-search-container")
        .classList.add("hidden");
    document.getElementById("add-member-input").value = "";

    const membersList = document.getElementById("info-members");
    membersList.innerHTML =
        '<div class="p-4 text-center text-xs text-[#8696a0]">Loading members…</div>';

    const addBtn = document.getElementById("btn-add-member");
    addBtn.classList.add("hidden");

    if (activeRoom.kind === "group" && activeRoom.groupId) {
        try {
            const res = await apiFetch(
                `/api/groups/${activeRoom.groupId}/members/`
            );
            if (res.ok) {
                const members = await res.json();
                membersList.innerHTML = "";

                const me = members.find((m) => m.user.id === MY_ID);
                const isAdmin = me && me.role === "admin";
                if (isAdmin) addBtn.classList.remove("hidden");

                members.forEach((m) => {
                    const row = document.createElement("div");
                    row.className =
                        "flex items-center gap-3 px-6 py-3 hover:bg-wa-panel transition-colors";
                    row.innerHTML = `
                        <div class="w-10 h-10 rounded-full bg-gray-600 flex items-center justify-center text-sm font-bold text-white uppercase">
                            ${m.user.username[0]}
                        </div>
                        <div class="flex-1 min-w-0">
                            <p class="text-sm text-wa-light font-semibold truncate">${m.user.username} ${m.user.id === MY_ID ? "(You)" : ""}</p>
                            <p class="text-[10px] text-[#8696a0] uppercase">${m.role}</p>
                        </div>`;
                    membersList.appendChild(row);
                });
            }
        } catch (e) {
            console.error("Error fetching members:", e);
        }
    } else {
        membersList.innerHTML = "";
        const row = document.createElement("div");
        row.className = "flex items-center gap-3 px-6 py-3";
        row.innerHTML = `
            <div class="w-10 h-10 rounded-full bg-[#00a884] flex items-center justify-center text-sm font-bold text-white uppercase">${activeRoom.name[0]}</div>
            <div class="flex-1 min-w-0"><p class="text-sm text-wa-light font-semibold">${activeRoom.name}</p></div>`;
        membersList.appendChild(row);
    }
}


// ═══════════════════════════════════════════════════════════════════
// 10. GROUP CREATION MODAL – renderSelectedMembers
// ═══════════════════════════════════════════════════════════════════

function renderSelectedMembers() {
    const container = document.getElementById("selected-members");
    container.innerHTML = "";
    if (selectedInitialMembers.size === 0) {
        container.innerHTML =
            '<span class="text-xs text-gray-500 italic p-1">No members selected yet…</span>';
        return;
    }
    selectedInitialMembers.forEach((userStr) => {
        const u = JSON.parse(userStr);
        const chip = document.createElement("div");
        chip.className =
            "bg-[#00a884] text-[#111b21] px-2 py-1 rounded-full text-xs font-bold flex items-center gap-1";
        chip.innerHTML = `${u.name} <span class="material-symbols-outlined text-xs cursor-pointer hover:text-white">close</span>`;
        chip.querySelector("span").addEventListener("click", () => {
            selectedInitialMembers.delete(userStr);
            renderSelectedMembers();
        });
        container.appendChild(chip);
    });
}


// ═══════════════════════════════════════════════════════════════════
// 11. INITIALISATION
// ═══════════════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", async () => {
    if (!getToken()) {
        window.location.href = "/auth/login/";
        return;
    }

    // ── Load profile ──────────────────────────────────────────────
    try {
        const res = await apiFetch("/api/users/me/");
        if (res.status === 401) {
            logout();
            return;
        }
        const user = await res.json();
        MY_ID = user.id;
        MY_USERNAME = user.username;
        document.getElementById("my-username").textContent = user.username;
        if (user.avatar) {
            const img = document.getElementById("my-avatar");
            img.src = user.avatar;
            img.classList.remove("hidden");
        }
    } catch (e) {
        console.error("Profile fetch failed:", e);
    }

    connectWS();
    await loadConversations();

    // ── Core Event Listeners ──────────────────────────────────────
    document.getElementById("btn-logout").addEventListener("click", logout);

    // Attachment
    document.getElementById("btn-attach").addEventListener("click", () => {
        document.getElementById("file-input").click();
    });
    document
        .getElementById("file-input")
        .addEventListener("change", async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            if (file.type.startsWith("image/")) {
                await sendImage(file);
            } else {
                alert("Currently only images are supported for direct sending.");
            }
            e.target.value = "";
        });

    const input = document.getElementById("message-input");
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        } else if (activeRoom) {
            wsSend({ action: "typing", roomId: activeRoom.roomId });
        }
    });

    document
        .getElementById("btn-send-message")
        .addEventListener("click", sendMessage);

    // ── Search ────────────────────────────────────────────────────
    let searchTimer;
    document
        .getElementById("search-input")
        .addEventListener("input", (e) => {
            clearTimeout(searchTimer);
            const q = e.target.value.trim();
            if (!q) {
                loadConversations();
                return;
            }
            searchTimer = setTimeout(() => searchUsers(q), 350);
        });

    // ── Group Creation Modal ──────────────────────────────────────
    document
        .getElementById("btn-create-group")
        .addEventListener("click", () => {
            document
                .getElementById("modal-create-group")
                .classList.remove("hidden");
            document.getElementById("new-group-name").focus();
            selectedInitialMembers.clear();
            renderSelectedMembers();
        });

    document
        .getElementById("btn-cancel-group")
        .addEventListener("click", () => {
            document
                .getElementById("modal-create-group")
                .classList.add("hidden");
            selectedInitialMembers.clear();
        });

    let groupSearchTimer;
    const groupSearchInput = document.getElementById("group-user-search");
    const groupSearchResults = document.getElementById(
        "group-search-results"
    );

    groupSearchInput.addEventListener("input", (e) => {
        clearTimeout(groupSearchTimer);
        const q = e.target.value.trim();
        if (!q) {
            groupSearchResults.classList.add("hidden");
            return;
        }
        groupSearchTimer = setTimeout(async () => {
            const res = await apiFetch(
                `/api/users/search/?q=${encodeURIComponent(q)}`
            );
            if (res.ok) {
                const users = await res.json();
                groupSearchResults.innerHTML = "";
                if (users.length > 0) {
                    groupSearchResults.classList.remove("hidden");
                    users.forEach((u) => {
                        if (u.id === MY_ID) return;
                        const item = document.createElement("div");
                        item.className =
                            "px-4 py-2 hover:bg-wa-panel cursor-pointer text-sm border-b border-wa-border last:border-0";
                        item.textContent = u.username;
                        item.addEventListener("click", () => {
                            selectedInitialMembers.add(
                                JSON.stringify({
                                    id: u.id,
                                    name: u.username,
                                })
                            );
                            groupSearchInput.value = "";
                            groupSearchResults.classList.add("hidden");
                            renderSelectedMembers();
                        });
                        groupSearchResults.appendChild(item);
                    });
                } else {
                    groupSearchResults.classList.add("hidden");
                }
            }
        }, 300);
    });

    document
        .getElementById("btn-submit-group")
        .addEventListener("click", async () => {
            const name = document
                .getElementById("new-group-name")
                .value.trim();
            if (!name) return;

            const initial_members = Array.from(selectedInitialMembers).map(
                (s) => JSON.parse(s).id
            );

            const res = await apiFetch("/api/groups/", {
                method: "POST",
                body: JSON.stringify({ name, initial_members }),
            });
            if (res.ok) {
                document
                    .getElementById("modal-create-group")
                    .classList.add("hidden");
                document.getElementById("new-group-name").value = "";
                selectedInitialMembers.clear();
                await loadConversations();
            }
        });

    // ── Group Info Panel ──────────────────────────────────────────
    document
        .getElementById("chat-header")
        .addEventListener("click", () => {
            if (!activeRoom) return;
            openGroupInfo();
        });

    document
        .getElementById("btn-close-right")
        .addEventListener("click", () => {
            document.getElementById("right-panel").style.width = "0";
        });

    // Add Member in Group Info
    document
        .getElementById("btn-add-member")
        .addEventListener("click", () => {
            const container = document.getElementById(
                "add-member-search-container"
            );
            container.classList.toggle("hidden");
            if (!container.classList.contains("hidden"))
                document.getElementById("add-member-input").focus();
        });

    let addMemberTimer;
    document
        .getElementById("add-member-input")
        .addEventListener("input", (e) => {
            clearTimeout(addMemberTimer);
            const q = e.target.value.trim();
            const resultsDiv = document.getElementById(
                "add-member-results"
            );
            if (!q) {
                resultsDiv.classList.add("hidden");
                return;
            }

            addMemberTimer = setTimeout(async () => {
                const res = await apiFetch(
                    `/api/users/search/?q=${encodeURIComponent(q)}`
                );
                if (res.ok) {
                    const users = await res.json();
                    resultsDiv.innerHTML = "";
                    if (users.length > 0) {
                        resultsDiv.classList.remove("hidden");
                        users.forEach((u) => {
                            const item = document.createElement("div");
                            item.className =
                                "px-3 py-2 hover:bg-wa-panel cursor-pointer text-xs border-b border-wa-border last:border-0";
                            item.textContent = u.username;
                            item.addEventListener("click", async () => {
                                const addRes = await apiFetch(
                                    `/api/groups/${activeRoom.groupId}/members/`,
                                    {
                                        method: "POST",
                                        body: JSON.stringify({
                                            userId: u.id,
                                        }),
                                    }
                                );
                                if (addRes.ok) {
                                    resultsDiv.classList.add("hidden");
                                    document.getElementById(
                                        "add-member-input"
                                    ).value = "";
                                    document
                                        .getElementById(
                                            "add-member-search-container"
                                        )
                                        .classList.add("hidden");
                                    openGroupInfo();
                                } else {
                                    const err = await addRes.json();
                                    alert(
                                        err.error?.message ||
                                            "Error adding member"
                                    );
                                }
                            });
                            resultsDiv.appendChild(item);
                        });
                    } else {
                        resultsDiv.classList.add("hidden");
                    }
                }
            }, 300);
        });
});
