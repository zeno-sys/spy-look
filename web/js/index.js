let sortBy = "created_at";
    let sortDir = "desc";
    let currentPage = 1;
    let pageSize = 50;
    let lastItemsCount = 0;
    let modalRawText = "";
    let modalTitleText = "";
    let modalMergedView = false;
    let appListPage = 1;
    let appListPageSize = 50;
    let appListLastCount = 0;
    let sessionListPage = 1;
    let sessionListPageSize = 50;
    let sessionListLastCount = 0;

    function esc(s) {
      return String(s ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
    }
    function escAttr(s) {
      return String(s ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }
    function getAppIdFromUrl() {
      const raw = new URLSearchParams(window.location.search).get("app_id");
      if (raw == null) return null;
      const t = String(raw).trim();
      return t ? t : null;
    }
    function getSessionIdFromUrl() {
      const raw = new URLSearchParams(window.location.search).get("session_id");
      if (raw == null) return null;
      const t = String(raw).trim();
      return t ? t : null;
    }
    function syncUrlQuery(appId, sessionId) {
      const u = new URL(window.location.href);
      if (appId) u.searchParams.set("app_id", appId);
      else u.searchParams.delete("app_id");
      if (sessionId) u.searchParams.set("session_id", sessionId);
      else u.searchParams.delete("session_id");
      const qs = u.searchParams.toString();
      history.pushState({}, "", qs ? `${u.pathname}?${qs}` : u.pathname);
    }
    function applyRoute() {
      const aid = getAppIdFromUrl();
      const sid = getSessionIdFromUrl();
      const appsEl = document.getElementById("viewApps");
      const sessionsEl = document.getElementById("viewSessions");
      const logsEl = document.getElementById("viewLogs");
      const appInput = document.getElementById("app_id");
      const sessionInput = document.getElementById("session_id");
      appsEl.classList.add("hidden");
      sessionsEl.classList.add("hidden");
      logsEl.classList.add("hidden");
      if (!aid) {
        appsEl.classList.remove("hidden");
        appInput.value = "";
        appInput.readOnly = false;
        sessionInput.value = "";
        sessionInput.readOnly = false;
        document.getElementById("sessionsAppHint").textContent = "";
        document.getElementById("logsAppHint").textContent = "";
        document.getElementById("logsSessionHint").textContent = "";
        document.title = "Spy-Look · 应用列表";
        loadApps();
        return;
      }
      if (!sid) {
        sessionsEl.classList.remove("hidden");
        document.getElementById("sessionsAppHint").textContent = aid;
        sessionInput.value = "";
        sessionInput.readOnly = false;
        appInput.value = aid;
        appInput.readOnly = true;
        document.title = "Spy-Look · 会话列表";
        loadSessions();
        return;
      }
      logsEl.classList.remove("hidden");
      appInput.value = aid;
      appInput.readOnly = true;
      sessionInput.value = sid;
      sessionInput.readOnly = true;
      document.getElementById("logsAppHint").textContent = aid;
      document.getElementById("logsSessionHint").textContent = sid;
      document.title = "Spy-Look · 会话日志";
      currentPage = 1;
      updatePagerUI();
      searchLogs();
    }
    function goBackToApps() {
      appListPage = 1;
      sessionListPage = 1;
      syncUrlQuery(null, null);
      applyRoute();
    }
    function goBackToSessions() {
      const aid = getAppIdFromUrl();
      sessionListPage = 1;
      syncUrlQuery(aid, null);
      applyRoute();
    }
    function updateAppListPagerUI() {
      document.getElementById("appPageInfo").textContent = `第 ${appListPage} 页`;
      document.getElementById("appPrevPageBtn").disabled = appListPage <= 1;
      document.getElementById("appNextPageBtn").disabled =
        appListLastCount < appListPageSize;
    }
    function onAppListPageSizeChange() {
      const raw = document.getElementById("appPageSize").value;
      const parsed = Number(raw);
      appListPageSize = Number.isFinite(parsed) && parsed > 0 ? parsed : 50;
      appListPage = 1;
      loadApps();
    }
    function goAppListPrevPage() {
      if (appListPage <= 1) return;
      appListPage -= 1;
      loadApps();
    }
    function goAppListNextPage() {
      if (appListLastCount < appListPageSize) return;
      appListPage += 1;
      loadApps();
    }
    function openSessionsForApp(appId) {
      syncUrlQuery(appId, null);
      applyRoute();
    }
    function openSessionsForAppFromRow(tr) {
      const aid = tr && tr.dataset && tr.dataset.appId;
      if (aid) openSessionsForApp(aid);
    }
    function openSessionsForAppFromBtn(btn, ev) {
      if (ev) ev.stopPropagation();
      const aid = btn && btn.dataset && btn.dataset.appId;
      if (aid) openSessionsForApp(aid);
    }
    async function loadApps() {
      const tbody = document.getElementById("appTbody");
      tbody.innerHTML = "<tr><td colspan='5'>加载中...</td></tr>";
      try {
        const params = new URLSearchParams();
        params.set("limit", String(appListPageSize));
        params.set("offset", String((appListPage - 1) * appListPageSize));
        const res = await fetch("/logs/apps?" + params.toString());
        const data = await res.json();
        const total = Number(data.total) || 0;
        const maxPage = Math.max(1, Math.ceil(total / appListPageSize) || 1);
        if (appListPage > maxPage) {
          appListPage = maxPage;
          return loadApps();
        }
        const items = data.items || [];
        appListLastCount = items.length;
        updateAppListPagerUI();
        tbody.innerHTML = items.length
          ? items
              .map(
                (item) => `
        <tr class="link-row" data-app-id="${escAttr(item.app_id)}" onclick="openSessionsForAppFromRow(this)">
          <td><code>${esc(item.app_id)}</code></td>
          <td>${esc(item.log_count)}</td>
          <td>${esc(item.first_created_at)}</td>
          <td>${esc(item.last_created_at)}</td>
          <td><button type="button" class="ghost-btn action-btn" data-app-id="${escAttr(item.app_id)}" onclick="openSessionsForAppFromBtn(this, event)">查看会话</button></td>
        </tr>`
              )
              .join("")
          : "<tr><td colspan='5'>暂无应用</td></tr>";
      } catch (_) {
        appListLastCount = 0;
        updateAppListPagerUI();
        tbody.innerHTML = "<tr><td colspan='5'>加载失败</td></tr>";
      }
    }
    function updateSessionListPagerUI() {
      document.getElementById("sessionPageInfo").textContent = `第 ${sessionListPage} 页`;
      document.getElementById("sessionPrevPageBtn").disabled = sessionListPage <= 1;
      document.getElementById("sessionNextPageBtn").disabled =
        sessionListLastCount < sessionListPageSize;
    }
    function onSessionListPageSizeChange() {
      const raw = document.getElementById("sessionPageSize").value;
      const parsed = Number(raw);
      sessionListPageSize = Number.isFinite(parsed) && parsed > 0 ? parsed : 50;
      sessionListPage = 1;
      loadSessions();
    }
    function goSessionListPrevPage() {
      if (sessionListPage <= 1) return;
      sessionListPage -= 1;
      loadSessions();
    }
    function goSessionListNextPage() {
      if (sessionListLastCount < sessionListPageSize) return;
      sessionListPage += 1;
      loadSessions();
    }
    function openLogsForSession(sessionId) {
      const aid = getAppIdFromUrl();
      if (!aid) return;
      syncUrlQuery(aid, sessionId);
      applyRoute();
    }
    function openLogsForSessionFromRow(tr) {
      const sid = tr && tr.dataset && tr.dataset.sessionId;
      if (sid) openLogsForSession(sid);
    }
    function openLogsForSessionFromBtn(btn, ev) {
      if (ev) ev.stopPropagation();
      const sid = btn && btn.dataset && btn.dataset.sessionId;
      if (sid) openLogsForSession(sid);
    }
    async function loadSessions() {
      const aid = getAppIdFromUrl();
      const tbody = document.getElementById("sessionTbody");
      if (!aid) {
        tbody.innerHTML = "<tr><td colspan='5'>缺少 app_id</td></tr>";
        return;
      }
      tbody.innerHTML = "<tr><td colspan='5'>加载中...</td></tr>";
      try {
        const params = new URLSearchParams();
        params.set("app_id", aid);
        params.set("limit", String(sessionListPageSize));
        params.set("offset", String((sessionListPage - 1) * sessionListPageSize));
        const res = await fetch("/logs/sessions?" + params.toString());
        const data = await res.json();
        const total = Number(data.total) || 0;
        const maxPage = Math.max(1, Math.ceil(total / sessionListPageSize) || 1);
        if (sessionListPage > maxPage) {
          sessionListPage = maxPage;
          return loadSessions();
        }
        const items = data.items || [];
        sessionListLastCount = items.length;
        updateSessionListPagerUI();
        tbody.innerHTML = items.length
          ? items
              .map(
                (item) => `
        <tr class="link-row" data-session-id="${escAttr(item.session_id)}" onclick="openLogsForSessionFromRow(this)">
          <td><code>${esc(item.session_id)}</code></td>
          <td>${esc(item.log_count)}</td>
          <td>${esc(item.first_created_at)}</td>
          <td>${esc(item.last_created_at)}</td>
          <td><button type="button" class="ghost-btn action-btn" data-session-id="${escAttr(item.session_id)}" onclick="openLogsForSessionFromBtn(this, event)">查看日志</button></td>
        </tr>`
              )
              .join("")
          : "<tr><td colspan='5'>暂无会话</td></tr>";
      } catch (_) {
        sessionListLastCount = 0;
        updateSessionListPagerUI();
        tbody.innerHTML = "<tr><td colspan='5'>加载失败</td></tr>";
      }
    }
    function buildParams() {
      const params = new URLSearchParams();
      const path = document.getElementById("path").value.trim();
      const model = document.getElementById("model").value.trim();
      const appId = document.getElementById("app_id").value.trim();
      const sessionId = document.getElementById("session_id").value.trim();
      const clientIp = document.getElementById("client_ip").value.trim();
      const startTime = document.getElementById("start_time").value.trim();
      const endTime = document.getElementById("end_time").value.trim();
      if (path) params.set("path", path);
      if (model) params.set("model", model);
      if (appId) params.set("app_id", appId);
      if (sessionId) params.set("session_id", sessionId);
      if (clientIp) params.set("client_ip", clientIp);
      if (startTime) params.set("start_time", startTime);
      if (endTime) params.set("end_time", endTime);
      params.set("order_by", sortBy);
      params.set("order_dir", sortDir);
      params.set("limit", String(pageSize));
      params.set("offset", String((currentPage - 1) * pageSize));
      return params.toString();
    }
    function updateSortIndicators() {
      ["created_at", "status_code", "latency_ms"].forEach((k) => {
        document.getElementById(`sort-${k}`).textContent = (k === sortBy) ? (sortDir === "asc" ? "▲" : "▼") : "";
      });
    }
    function setSort(field) {
      if (sortBy === field) {
        sortDir = sortDir === "asc" ? "desc" : "asc";
      } else {
        sortBy = field;
        sortDir = "desc";
      }
      currentPage = 1;
      searchLogs();
    }
    function updatePagerUI() {
      document.getElementById("pageInfo").textContent = `第 ${currentPage} 页`;
      document.getElementById("prevPageBtn").disabled = currentPage <= 1;
      document.getElementById("nextPageBtn").disabled = lastItemsCount < pageSize;
    }
    function applyFilters() {
      currentPage = 1;
      searchLogs();
    }
    function onPageSizeChange() {
      const raw = document.getElementById("pageSize").value;
      const parsed = Number(raw);
      pageSize = Number.isFinite(parsed) && parsed > 0 ? parsed : 50;
      currentPage = 1;
      searchLogs();
    }
    function goPrevPage() {
      if (currentPage <= 1) return;
      currentPage -= 1;
      searchLogs();
    }
    function goNextPage() {
      if (lastItemsCount < pageSize) return;
      currentPage += 1;
      searchLogs();
    }
    async function deleteLog(logId) {
      const ok = window.confirm(`确认删除日志 #${logId} 吗？`);
      if (!ok) return;
      try {
        const res = await fetch(`/logs/${logId}`, { method: "DELETE" });
        const delData = await res.json().catch(() => ({}));
        if (!res.ok) {
          showToast(formatApiError(delData, "删除失败"));
          return;
        }
        showToast("删除成功");
        if (lastItemsCount === 1 && currentPage > 1) currentPage -= 1;
        await searchLogs();
      } catch (_) {
        showToast("删除失败");
      }
    }
    function statusBadge(statusCode) {
      const code = Number(statusCode);
      if (!Number.isFinite(code)) return `<span class="status-badge status-na">${esc(statusCode)}</span>`;
      const bucket = Math.floor(code / 100);
      const cls = bucket === 2 ? "status-2xx" : bucket === 3 ? "status-3xx" : bucket === 4 ? "status-4xx" : bucket === 5 ? "status-5xx" : "status-na";
      return `<span class="status-badge ${cls}">${code}</span>`;
    }
    function toEncodedPayload(value) {
      return encodeURIComponent(JSON.stringify(value ?? ""));
    }
    function toEncodedText(value) {
      return encodeURIComponent(String(value ?? ""));
    }
    async function copyText(text) {
      try {
        await navigator.clipboard.writeText(text);
        showToast("已复制");
      } catch (_) {
        showToast("复制失败");
      }
    }
    function copyJsonFromButton(btn) {
      const encoded = btn?.dataset?.copy || "";
      let text = "";
      try {
        text = decodeURIComponent(encoded);
      } catch (_) {
        text = String(encoded ?? "");
      }
      copyText(text);
    }
    let toastTimer = null;
    function formatApiError(data, fallback) {
      if (data == null) return fallback;
      if (typeof data === "string" && data.trim()) return data.trim();
      if (typeof data !== "object") return fallback;
      if (typeof data.detail === "string" && data.detail.trim()) return data.detail.trim();
      const err = data.error;
      if (err && typeof err === "object") {
        if (typeof err.message === "string" && err.message.trim()) return err.message.trim();
      }
      if (Array.isArray(data.detail)) {
        const parts = data.detail
          .map((item) => {
            if (typeof item === "string") return item;
            if (item && typeof item.msg === "string") return item.msg;
            return "";
          })
          .filter(Boolean);
        if (parts.length) return parts.join("；");
      }
      return fallback;
    }

    function showToast(message) {
      const toast = document.getElementById("toast");
      if (!toast) return;
      const text = String(message ?? "");
      toast.textContent = text;
      toast.classList.add("show");
      const duration = Math.min(5000, Math.max(1200, 1000 + text.length * 35));
      if (toastTimer) clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove("show"), duration);
    }
    function showModalFromButton(btn) {
      const title = btn?.dataset?.title || "";
      const encoded = btn?.dataset?.payload || "";
      let raw = "";
      try {
        raw = decodeURIComponent(encoded);
      } catch (_) {
        raw = String(encoded ?? "");
      }
      showModal(title, raw);
    }
    function buildNonStreamJsonFromSse(text) {
      const lines = String(text ?? "").split(/\r?\n/);
      let lastMeta = {};
      const choicesMap = new Map();
      let usage = null;
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const candidate = line.slice(5).trim();
        if (!candidate || candidate === "[DONE]") continue;
        try {
          const obj = JSON.parse(candidate);
          if (obj && typeof obj === "object") {
            lastMeta = {
              id: obj.id ?? lastMeta.id,
              object: obj.object ?? lastMeta.object,
              created: obj.created ?? lastMeta.created,
              model: obj.model ?? lastMeta.model,
              system_fingerprint: obj.system_fingerprint ?? lastMeta.system_fingerprint,
            };
            if (obj.usage && typeof obj.usage === "object") usage = obj.usage;
          }
          const choices = Array.isArray(obj?.choices) ? obj.choices : [];
          for (const choice of choices) {
            const idx = Number.isFinite(choice?.index) ? choice.index : 0;
            const existing = choicesMap.get(idx) || {
              index: idx,
              message: { role: "assistant", content: "", reasoning_content: "", tool_calls: [] },
              finish_reason: null,
            };
            const delta = choice?.delta || {};
            if (typeof delta.role === "string" && delta.role) existing.message.role = delta.role;
            if (typeof delta.content === "string" && delta.content) {
              existing.message.content = (existing.message.content || "") + delta.content;
            }
            if (typeof delta.reasoning_content === "string" && delta.reasoning_content) {
              existing.message.reasoning_content = (existing.message.reasoning_content || "") + delta.reasoning_content;
            }
            if (Array.isArray(delta.tool_calls)) {
              for (const t of delta.tool_calls) {
                const tIdx = Number.isFinite(t?.index) ? t.index : existing.message.tool_calls.length;
                const prev = existing.message.tool_calls[tIdx] || {
                  id: t?.id || null,
                  type: t?.type || "function",
                  function: { name: "", arguments: "" },
                };
                if (t?.id) prev.id = t.id;
                if (t?.type) prev.type = t.type;
                const fn = t?.function || {};
                if (typeof fn.name === "string" && fn.name) prev.function.name = fn.name;
                if (typeof fn.arguments === "string" && fn.arguments) {
                  prev.function.arguments = (prev.function.arguments || "") + fn.arguments;
                }
                existing.message.tool_calls[tIdx] = prev;
              }
            }
            if (choice?.finish_reason !== null && choice?.finish_reason !== undefined) {
              existing.finish_reason = choice.finish_reason;
            }
            if (choice?.message && typeof choice.message === "object") {
              const msg = choice.message;
              if (typeof msg.role === "string" && msg.role) existing.message.role = msg.role;
              if (typeof msg.content === "string" && msg.content) existing.message.content = msg.content;
              if (typeof msg.reasoning_content === "string" && msg.reasoning_content) existing.message.reasoning_content = msg.reasoning_content;
              if (Array.isArray(msg.tool_calls) && msg.tool_calls.length) existing.message.tool_calls = msg.tool_calls;
            }
            choicesMap.set(idx, existing);
          }
        } catch (_) {}
      }
      if (!choicesMap.size) return null;
      const choices = Array.from(choicesMap.values())
        .sort((a, b) => a.index - b.index)
        .map((c) => {
          const message = { ...c.message };
          if (!message.content) delete message.content;
          if (!message.reasoning_content) delete message.reasoning_content;
          if (!Array.isArray(message.tool_calls) || message.tool_calls.length === 0) delete message.tool_calls;
          return { index: c.index, message, finish_reason: c.finish_reason };
        });
      const result = {
        id: lastMeta.id ?? "stream-reconstructed",
        object: "chat.completion",
        created: lastMeta.created ?? Math.floor(Date.now() / 1000),
        model: lastMeta.model ?? "unknown",
        choices,
      };
      if (lastMeta.system_fingerprint) result.system_fingerprint = lastMeta.system_fingerprint;
      if (usage) result.usage = usage;
      return result;
    }
    function toggleStreamView() {
      modalMergedView = !modalMergedView;
      renderCurrentModal();
    }
    function renderCurrentModal() {
      const toggleBtn = document.getElementById("streamToggleBtn");
      const mergedObj = buildNonStreamJsonFromSse(modalRawText);
      const canMerge = modalTitleText === "response_body" && Boolean(mergedObj);
      toggleBtn.classList.toggle("hidden", !canMerge);
      if (canMerge) {
        toggleBtn.textContent = modalMergedView ? "查看原始流" : "转为非流式JSON";
      } else {
        modalMergedView = false;
      }
      if (canMerge && modalMergedView) {
        const pretty = JSON.stringify(mergedObj, null, 2);
        document.getElementById("modalContent").innerHTML = `<div class="json-block">
          <div class="json-block-title">
            <span>Reconstructed Non-Stream JSON</span>
            <span class="json-meta">
              ${pretty.length} chars
              <button class="copy-btn" onclick="copyJsonFromButton(this)" data-copy="${escAttr(toEncodedText(pretty))}">复制</button>
            </span>
          </div>
          <pre class="json-code">${highlightJson(pretty)}</pre>
        </div>`;
        return;
      }
      document.getElementById("modalContent").innerHTML = renderModalContent(modalRawText);
    }
    async function searchLogs() {
      updateSortIndicators();
      const tbody = document.getElementById("tbody");
      tbody.innerHTML = "<tr><td colspan='13'>加载中...</td></tr>";
      const res = await fetch("/logs?" + buildParams());
      const data = await res.json();
      const items = data.items || [];
      lastItemsCount = items.length;
      const rows = items.map(item => `
        <tr>
          <td>${esc(item.id)}</td>
          <td><code class="td-path-url">${esc(item.path)}</code></td>
          <td>${esc(item.model)}</td>
          <td>${statusBadge(item.status_code)}</td>
          <td>${esc(item.latency_ms)} ms</td>
          <td>${esc(item.client_ip)}</td>
          <td><code>${esc(item.app_id)}</code></td>
          <td>${esc(item.session_id)}</td>
          <td>${esc(item.input_tokens)}/${esc(item.output_tokens)}/${esc(item.total_tokens)}</td>
          <td><button class="ghost-btn action-btn" onclick="showModalFromButton(this)" data-title="request_body" data-payload="${escAttr(toEncodedPayload(item.request_body))}">查看</button></td>
          <td><button class="ghost-btn action-btn" onclick="showModalFromButton(this)" data-title="response_body" data-payload="${escAttr(toEncodedPayload(item.response_body))}">查看</button></td>
          <td><button class="danger-btn" onclick="deleteLog(${esc(item.id)})">删除</button></td>
          <td>${esc(item.created_at)}</td>
        </tr>
      `).join("");
      tbody.innerHTML = rows || "<tr><td colspan='13'>暂无数据</td></tr>";
      updatePagerUI();
    }
    function showModal(title, raw) {
      let text = "";
      try {
        text = JSON.parse(raw);
      } catch (_) {
        text = String(raw ?? "");
      }
      modalTitleText = title;
      modalRawText = text;
      modalMergedView = false;
      document.getElementById("modalTitle").textContent = title;
      renderCurrentModal();
      document.getElementById("modalMask").style.display = "flex";
    }
    function renderModalContent(text) {
      const blocks = parseJsonBlocks(text);
      if (!blocks.length) return esc(text);
      return blocks.map((obj, idx) => {
        const pretty = JSON.stringify(obj, null, 2);
        return `<div class="json-block">
          <div class="json-block-title">
            <span>JSON #${idx + 1}</span>
            <span class="json-meta">
              ${pretty.length} chars
              <button class="copy-btn" onclick="copyJsonFromButton(this)" data-copy="${escAttr(toEncodedText(pretty))}">复制</button>
            </span>
          </div>
          <pre class="json-code">${highlightJson(pretty)}</pre>
        </div>`;
      }).join("");
    }
    function parseJsonBlocks(text) {
      if (!text) return [];
      const blocks = [];
      const pushIfJson = (s) => {
        const candidate = s.trim();
        if (!candidate || candidate === "[DONE]") return;
        try {
          blocks.push(JSON.parse(candidate));
        } catch (_) {}
      };
      pushIfJson(text);
      if (blocks.length) return blocks;

      // 兼容 SSE 文本：data: {...}\n\ndata: {...}\n\ndata: [DONE]
      const lines = String(text).split(/\r?\n/);
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        pushIfJson(line.slice(5));
      }
      if (blocks.length) return blocks;

      // 兜底：逐行尝试多个 JSON
      for (const line of lines) {
        pushIfJson(line);
      }
      return blocks;
    }
    function highlightJson(prettyJson) {
      const escaped = esc(prettyJson);
      return escaped.replace(
        /("(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*")(\s*:)?|\b(true|false)\b|\bnull\b|-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?/g,
        (match, str, colon, boolVal) => {
          if (str) {
            const cls = colon ? "json-key" : "json-string";
            return `<span class="${cls}">${match}</span>`;
          }
          if (boolVal) return `<span class="json-boolean">${match}</span>`;
          if (match === "null") return `<span class="json-null">${match}</span>`;
          return `<span class="json-number">${match}</span>`;
        }
      );
    }
    function closeModal(event) {
      if (event && event.target !== event.currentTarget) return;
      document.getElementById("modalMask").style.display = "none";
    }

    function bashSingleQuoted(s) {
      return "'" + String(s).replace(/'/g, "'\"'\"'") + "'";
    }
    function buildCurlModels(base, key) {
      const root = String(base || "").replace(/\/$/, "");
      const url = `${root}/v1/models`;
      return (
        `curl -sS ${bashSingleQuoted(url)} \\\n` +
        `  -H ${bashSingleQuoted("Authorization: Bearer " + key)} \\\n` +
        `  -H ${bashSingleQuoted("Content-Type: application/json")}`
      );
    }
    function buildCurlChat(base, key, modelId) {
      const root = String(base || "").replace(/\/$/, "");
      const url = `${root}/v1/chat/completions`;
      const body = {
        model: modelId || "YOUR_MODEL_ID",
        messages: [{ role: "user", content: "你好" }],
        session_id: "default",
      };
      const json = JSON.stringify(body);
      return (
        `curl -sS ${bashSingleQuoted(url)} \\\n` +
        `  -H ${bashSingleQuoted("Authorization: Bearer " + key)} \\\n` +
        `  -H ${bashSingleQuoted("Content-Type: application/json")} \\\n` +
        `  -d ${bashSingleQuoted(json)}`
      );
    }

    function closeClientInfoModal(event) {
      if (event && event.target !== event.currentTarget) return;
      document.getElementById("clientInfoMask").style.display = "none";
    }

    async function openClientInfoModal() {
      const mask = document.getElementById("clientInfoMask");
      const bodyEl = document.getElementById("clientInfoBody");
      mask.style.display = "flex";
      bodyEl.className = "client-info-body muted";
      bodyEl.textContent = "加载中…";

      let info;
      try {
        const res = await fetch("/admin/client-info");
        info = await res.json().catch(() => ({}));
        if (!res.ok) {
          const detail =
            typeof info.detail === "string"
              ? info.detail
              : info.detail && typeof info.detail === "object"
                ? JSON.stringify(info.detail)
                : res.status;
          bodyEl.className = "client-info-body";
          bodyEl.textContent = "无法读取配置：" + detail;
          return;
        }
      } catch (e) {
        bodyEl.className = "client-info-body";
        bodyEl.textContent = "请求失败：" + String(e);
        return;
      }

      const base = info.gateway_base_url || "";
      const key = info.gateway_api_key || "";
      const curlKey = key || "YOUR_GATEWAY_API_KEY";
      const modelsUrl = info.v1_models_url || "";
      const chatUrl = info.v1_chat_completions_url || "";

      let models = [];
      let modelsErr = null;
      if (!key) {
        modelsErr =
          "数据库中尚无对外 API Key，请到「上游配置」页添加后再试。";
      } else {
        try {
          const r2 = await fetch(modelsUrl, {
            headers: {
              Authorization: "Bearer " + key,
              "Content-Type": "application/json",
            },
          });
          const j2 = await r2.json().catch(() => ({}));
          if (!r2.ok) {
            modelsErr =
              typeof j2.detail === "string"
                ? j2.detail
                : j2.error && j2.error.message
                  ? String(j2.error.message)
                  : JSON.stringify(j2);
          } else if (Array.isArray(j2.data)) {
            models = j2.data
              .map((x) => (x && x.id != null ? String(x.id) : ""))
              .filter(Boolean);
          } else {
            modelsErr = "响应中无 data 数组";
          }
        } catch (e) {
          modelsErr = String(e);
        }
      }

      const firstModel = models[0] || "";
      const curlModels = buildCurlModels(base, curlKey);
      const curlChat = buildCurlChat(base, curlKey, firstModel);

      const listHtml = models.length
        ? `<ol class="client-model-list">${models.map((id) => `<li><code>${esc(id)}</code></li>`).join("")}</ol>`
        : `<p class="muted" style="margin:0;">${
            modelsErr ? "未能拉取模型列表：" + esc(modelsErr) : "（无模型条目，请检查默认上游）"
          }</p>`;

      bodyEl.className = "client-info-body";
      bodyEl.innerHTML = `
        <p class="muted" style="margin-top:0;">以下为当前页面对应的网关根 URL；若经反向代理或域名访问，请替换为实际对外地址。</p>
        <div class="client-info-section">
          <div class="client-info-label">网关根 URL</div>
          <div class="client-info-value">${esc(base)}</div>
          <div class="client-info-label">列举模型</div>
          <div class="client-info-value">${esc(modelsUrl)}</div>
          <div class="client-info-label">对话补全</div>
          <div class="client-info-value">${esc(chatUrl)}</div>
        </div>
        <div class="client-info-section">
          <div class="client-info-label">网关 API Key（请求头 Authorization: Bearer …）</div>
          <div class="client-info-value" id="clientKeyField"></div>
          <div class="client-info-row">
            <button type="button" class="copy-btn" onclick="copyText(document.getElementById('clientKeyField').textContent)">复制 Key</button>
          </div>
        </div>
        <div class="client-info-section">
          <div class="client-info-label">可用模型（默认上游 /v1/models）</div>
          ${listHtml}
        </div>
        <div class="client-info-section">
          <div class="client-info-label">curl：列举模型</div>
          <div class="client-curl-wrap">
            <button type="button" class="copy-btn" onclick="copyText(document.getElementById('clientInfoCurlModels').textContent)">复制</button>
            <pre id="clientInfoCurlModels"></pre>
          </div>
        </div>
        <div class="client-info-section">
          <div class="client-info-label">curl：对话补全（含 session_id 便于日志归类）</div>
          <p class="muted" style="margin:0 0 8px;">模型已填${
            firstModel ? "列表首项 <code>" + esc(firstModel) + "</code>" : "占位符 YOUR_MODEL_ID"
          }，可按需修改。</p>
          <div class="client-curl-wrap">
            <button type="button" class="copy-btn" onclick="copyText(document.getElementById('clientInfoCurlChat').textContent)">复制</button>
            <pre id="clientInfoCurlChat"></pre>
          </div>
        </div>
      `;
      document.getElementById("clientKeyField").textContent = key
        ? key
        : "（无）请在「上游配置」添加对外 API Key（仅存数据库）。";
      document.getElementById("clientInfoCurlModels").textContent = curlModels;
      document.getElementById("clientInfoCurlChat").textContent = curlChat;
    }

    document.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      const cm = document.getElementById("clientInfoMask");
      if (cm && cm.style.display === "flex") closeClientInfoModal();
    });

    window.addEventListener("popstate", applyRoute);
    updatePagerUI();
    applyRoute();
