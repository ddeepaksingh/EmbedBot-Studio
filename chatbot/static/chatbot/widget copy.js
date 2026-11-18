(function () {
    const currentScript = document.currentScript;
    const BASE_URL = currentScript ? new URL(currentScript.src).origin : window.location.origin;

    const host = document.createElement("div");
    host.id = "embedbot-widget-root";
    document.body.appendChild(host);
    const shadow = host.attachShadow({ mode: "open" });

    let chatHistory = [];
    let isOpen = false;

    // डायनामिक टेक्स्ट वेरिएबल्स (डैशबोर्ड की भाषा के अनुसार बदलेंगे)
    let typingMsg = "Typing...";
    let errorMsg = "Unable to connect to the server.";
    let emptyMsg = "No response found.";

    function formatMarkdown(text) {
        let escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
        escaped = escaped.replace(/`([^`]+)`/g, "<code style='background:#e2e8f0;padding:1px 4px;border-radius:4px;font-size:12px;'>$1</code>");
        escaped = escaped.replace(/\n/g, "<br>");
        return escaped;
    }

    shadow.innerHTML = `
        <style>
            * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            .bubble-btn { position: fixed; bottom: 24px; right: 24px; width: 60px; height: 60px; border-radius: 50%; background: #2563eb; color: white; border: none; box-shadow: 0 10px 25px rgba(0,0,0,0.2); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: transform 0.2s ease; z-index: 999999; }
            .bubble-btn:hover { transform: scale(1.07); }
            .chat-window { position: fixed; bottom: 96px; right: 24px; width: 370px; max-width: calc(100vw - 32px); height: 520px; max-height: calc(100vh - 120px); background: #ffffff; border-radius: 16px; box-shadow: 0 12px 40px rgba(0,0,0,0.18); border: 1px solid #e2e8f0; display: none; flex-direction: column; overflow: hidden; z-index: 999999; }
            .chat-window.open { display: flex; }
            .header { background: #2563eb; color: white; padding: 16px; display: flex; align-items: center; justify-content: space-between; }
            .header-title { font-weight: 600; font-size: 15px; display: flex; align-items: center; gap: 8px; }
            .status-dot { width: 8px; height: 8px; background: #4ade80; border-radius: 50%; }
            .close-btn { background: none; border: none; color: white; font-size: 20px; cursor: pointer; line-height: 1; }
            .messages { flex: 1; padding: 16px; overflow-y: auto; background: #f8fafc; display: flex; flex-direction: column; gap: 10px; }
            .msg { max-width: 82%; padding: 10px 14px; border-radius: 14px; font-size: 13.5px; line-height: 1.45; word-wrap: break-word; }
            .msg.bot { background: #ffffff; color: #1e293b; align-self: flex-start; border: 1px solid #e2e8f0; border-bottom-left-radius: 4px; }
            .msg.user { background: #2563eb; color: #ffffff; align-self: flex-end; border-bottom-right-radius: 4px; }
            .input-area { padding: 12px; background: #ffffff; border-top: 1px solid #e2e8f0; display: flex; gap: 8px; }
            .input-area input { flex: 1; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 10px; font-size: 13.5px; outline: none; }
            .input-area input:focus { border-color: #2563eb; }
            .send-btn { background: #2563eb; color: white; border: none; border-radius: 10px; padding: 0 16px; font-weight: 600; font-size: 13px; cursor: pointer; }
            .send-btn:disabled { opacity: 0.6; cursor: not-allowed; }
        </style>
        <button class="bubble-btn" id="toggle-btn" title="Chat"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg></button>
        <div class="chat-window" id="chat-window">
            <div class="header" id="chat-header">
                <div class="header-title"><span class="status-dot"></span><span id="bot-name">Support</span></div>
                <button class="close-btn" id="close-btn">&times;</button>
            </div>
            <div class="messages" id="messages-box"></div>
            <form class="input-area" id="chat-form">
                <input type="text" id="chat-input" placeholder="Type here..." autocomplete="off" />
                <button type="submit" class="send-btn" id="send-btn">Send</button>
            </form>
        </div>
    `;

    const toggleBtn = shadow.getElementById("toggle-btn");
    const closeBtn = shadow.getElementById("close-btn");
    const chatWindow = shadow.getElementById("chat-window");
    const chatHeader = shadow.getElementById("chat-header");
    const botNameEl = shadow.getElementById("bot-name");
    const messagesBox = shadow.getElementById("messages-box");
    const chatForm = shadow.getElementById("chat-form");
    const chatInput = shadow.getElementById("chat-input");
    const sendBtn = shadow.getElementById("send-btn");

    let themeColor = "#2563eb";

    function addMessage(text, sender) {
        const div = document.createElement("div");
        div.className = `msg ${sender}`;
        if (sender === "user") {
            div.style.background = themeColor;
            div.textContent = text;
        } else {
            div.innerHTML = formatMarkdown(text);
        }
        messagesBox.appendChild(div);
        messagesBox.scrollTop = messagesBox.scrollHeight;
        return div;
    }

    function getLivePageContext() {
        const clone = document.body.cloneNode(true);
        const widgetEl = clone.querySelector("#embedbot-widget-root");
        if (widgetEl) widgetEl.remove();
        clone.querySelectorAll("script, style, nav, footer, noscript").forEach(el => el.remove());
        const cleanText = (clone.innerText || "").replace(/\s+/g, " ").trim();
        return { url: window.location.href, title: document.title || "", content: cleanText.slice(0, 6000) };
    }

    // सर्वर से भाषा और सेटिंग्स लोड करें
    fetch(`${BASE_URL}/api/config/`)
        .then(res => res.json())
        .then(cfg => {
            themeColor = cfg.theme_color || "#2563eb";
            toggleBtn.style.background = themeColor;
            chatHeader.style.background = themeColor;
            sendBtn.style.background = themeColor;
            botNameEl.textContent = cfg.bot_name || "Support Assistant";
            
            // UI Strings Apply करें
            if (cfg.input_placeholder) chatInput.placeholder = cfg.input_placeholder;
            if (cfg.typing_message) typingMsg = cfg.typing_message;
            if (cfg.error_message) errorMsg = cfg.error_message;
            if (cfg.empty_message) emptyMsg = cfg.empty_message;

            addMessage(cfg.welcome_message || "Hello!", "bot");
        })
        .catch(() => addMessage("Hello!", "bot"));

    toggleBtn.addEventListener("click", () => { isOpen = !isOpen; chatWindow.classList.toggle("open", isOpen); if (isOpen) chatInput.focus(); });
    closeBtn.addEventListener("click", () => { isOpen = false; chatWindow.classList.remove("open"); });

    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (!text) return;
        addMessage(text, "user");
        chatInput.value = "";
        sendBtn.disabled = true;
        
        const typingBubble = addMessage(typingMsg, "bot"); // डायनामिक टाइपिंग टेक्स्ट
        const pageContext = getLivePageContext();
        
        try {
            const res = await fetch(`${BASE_URL}/api/chat/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text, history: chatHistory, page_context: pageContext }),
            });
            const data = await res.json();
            typingBubble.innerHTML = formatMarkdown(data.reply || emptyMsg);
            chatHistory.push({ role: "user", text: text });
            chatHistory.push({ role: "assistant", text: data.reply || "" });
        } catch (err) { 
            typingBubble.textContent = errorMsg; 
        } finally { 
            sendBtn.disabled = false; chatInput.focus(); 
        }
    });
})();