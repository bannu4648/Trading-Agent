const chatLog = document.getElementById("chat-log");
const sendBtn = document.getElementById("send-btn");
const tickersInput = document.getElementById("tickers");
const startInput = document.getElementById("start-date");
const endInput = document.getElementById("end-date");
const intervalInput = document.getElementById("interval");
const messageInput = document.getElementById("message");

function appendMessage(role, text, payload) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;

  const title = document.createElement("h3");
  title.textContent = role === "user" ? "You" : "Agent";

  const pre = document.createElement("pre");
  pre.textContent = text || "(no content)";

  wrapper.appendChild(title);
  wrapper.appendChild(pre);

  if (payload) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Show JSON payload";
    const jsonPre = document.createElement("pre");
    jsonPre.textContent = JSON.stringify(payload, null, 2);
    details.appendChild(summary);
    details.appendChild(jsonPre);
    wrapper.appendChild(details);
  }

  chatLog.appendChild(wrapper);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function setLoading(isLoading) {
  sendBtn.disabled = isLoading;
  sendBtn.textContent = isLoading ? "Running..." : "Send";
}

async function sendMessage() {
  const message = messageInput.value.trim();
  const tickers = tickersInput.value
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  const payload = {
    message,
    tickers: tickers.length ? tickers : null,
    start_date: startInput.value || null,
    end_date: endInput.value || null,
    interval: intervalInput.value || "1d",
  };

  appendMessage("user", message || JSON.stringify(payload));
  setLoading(true);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorData = await response.json();
      appendMessage("assistant", `Error: ${errorData.detail || response.statusText}`);
      return;
    }

    const data = await response.json();
    appendMessage("assistant", data.assistant_message || "Response received.", data.payload);
  } catch (error) {
    appendMessage("assistant", `Error: ${error.message}`);
  } finally {
    setLoading(false);
  }
}

sendBtn.addEventListener("click", (event) => {
  event.preventDefault();
  sendMessage();
});

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    sendMessage();
  }
});
