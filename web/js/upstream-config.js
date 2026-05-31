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

    function toast(msg) {
      const el = document.getElementById("toast");
      if (!el) return;
      const text = String(msg ?? "");
      el.textContent = text;
      el.classList.add("show");
      const duration = Math.min(5000, Math.max(1600, 1200 + text.length * 35));
      if (toast._timer) clearTimeout(toast._timer);
      toast._timer = setTimeout(() => el.classList.remove("show"), duration);
    }
    function renderGatewayKeyRows(items) {
      const tb = document.getElementById("gwKeyTbody");
      if (!tb) return;
      const rows = items && items.length ? items : [];
      tb.innerHTML = rows.length
        ? rows
            .map(
              (k) => `
            <tr>
              <td>${k.id}</td>
              <td class="gw-app-id-cell">
                <div class="gw-app-id-inner">
                  <code class="gw-app-id-display" data-key-id="${k.id}">${escapeHtml(k.app_id || "")}</code>
                  <button class="ghost gw-app-id-edit-btn" type="button" title="修改 app_id" onclick="editGatewayAppId(${k.id})">编辑</button>
                </div>
              </td>
              <td><code class="key-masked">${escapeHtml(k.api_key_masked || "")}</code></td>
              <td>${escapeHtml(k.created_at || "—")}</td>
              <td>
                <div class="actions">
                  <button class="ghost" type="button" onclick="copyGatewayClientKey(${k.id})">复制</button>
                  <button class="ghost danger" type="button" onclick="deleteGatewayClientKey(${k.id})">删除</button>
                </div>
              </td>
            </tr>`
            )
            .join("")
        : "<tr><td colspan='5' class='muted'>尚无对外 API Key，请点击「新增密钥」</td></tr>";
    }

    async function loadGatewayClientKeys() {
      const tb = document.getElementById("gwKeyTbody");
      if (!tb) return;
      try {
        const res = await fetch("/admin/gateway-client-keys");
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          tb.innerHTML = "<tr><td colspan='5'>读取失败</td></tr>";
          return;
        }
        renderGatewayKeyRows(data.items || []);
      } catch (_) {
        tb.innerHTML = "<tr><td colspan='5'>读取失败</td></tr>";
      }
    }

    function setGwKeyCreateError(message) {
      const el = document.getElementById("gwKeyCreateError");
      if (!el) return;
      if (message) {
        el.textContent = message;
        el.hidden = false;
      } else {
        el.textContent = "";
        el.hidden = true;
      }
    }

    async function openCreateGatewayKeyModal() {
      const form = document.getElementById("gwKeyCreateForm");
      if (form) form.reset();
      setGwKeyCreateError("");
      const bd = document.getElementById("gwKeyCreateBackdrop");
      if (!bd) return;
      bd.classList.add("open");
      bd.setAttribute("aria-hidden", "false");
      await generateGatewayApiKey();
      requestAnimationFrame(() => {
        const appInput = document.getElementById("gw_create_app_id");
        if (appInput) appInput.focus();
      });
    }

    function closeCreateGatewayKeyModal() {
      const bd = document.getElementById("gwKeyCreateBackdrop");
      if (bd) {
        bd.classList.remove("open");
        bd.setAttribute("aria-hidden", "true");
      }
      setGwKeyCreateError("");
    }

    document.getElementById("gwKeyCreateBackdrop")?.addEventListener("click", () =>
      closeCreateGatewayKeyModal()
    );

    async function generateGatewayApiKey() {
      const input = document.getElementById("gw_create_key");
      const btn = document.getElementById("gw_generate_key_btn");
      if (btn) btn.disabled = true;
      setGwKeyCreateError("");
      try {
        const res = await fetch("/admin/gateway-client-keys/generate", { method: "POST" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          setGwKeyCreateError(formatApiError(data, "生成失败"));
          return;
        }
        const key = String(data.gateway_api_key || "").trim();
        if (!key) {
          setGwKeyCreateError("服务端未返回密钥");
          return;
        }
        if (input) {
          input.value = key;
        }
        toast("已生成 API Key");
      } catch (_) {
        setGwKeyCreateError("请求失败，请稍后重试");
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async function copyGatewayClientKey(id) {
      try {
        const res = await fetch(`/admin/gateway-client-keys/${id}`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          toast(formatApiError(data, "读取失败"));
          return;
        }
        const text = data.api_key || "";
        if (!text) {
          toast("无密钥内容");
          return;
        }
        try {
          await navigator.clipboard.writeText(text);
          toast("已复制完整密钥");
        } catch (_) {
          window.prompt("请手动复制：", text);
        }
      } catch (_) {
        toast("请求失败");
      }
    }

    async function deleteGatewayClientKey(id) {
      if (!confirm(`删除对外密钥 id=${id}？已使用该密钥的客户端将立即无法访问。`)) return;
      try {
        const res = await fetch(`/admin/gateway-client-keys/${id}`, { method: "DELETE" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          toast(formatApiError(data, "删除失败"));
          return;
        }
        toast("已删除");
        renderGatewayKeyRows(data.items || []);
      } catch (_) {
        toast("请求失败");
      }
    }

    let editAppIdKeyId = null;

    function setAppIdEditError(message) {
      const el = document.getElementById("appIdEditError");
      if (!el) return;
      if (message) {
        el.textContent = message;
        el.hidden = false;
      } else {
        el.textContent = "";
        el.hidden = true;
      }
    }

    function openEditAppIdModal(id, currentAppId) {
      editAppIdKeyId = id;
      const hint = document.getElementById("appIdKeyHint");
      if (hint) hint.textContent = `正在修改对外密钥 id=${id} 的应用标识`;
      const input = document.getElementById("app_id_edit_input");
      if (input) {
        input.value = currentAppId || "";
        input.classList.remove("input-invalid");
      }
      setAppIdEditError("");
      const bd = document.getElementById("appIdBackdrop");
      if (!bd) return;
      bd.classList.add("open");
      bd.setAttribute("aria-hidden", "false");
      requestAnimationFrame(() => {
        if (input) {
          input.focus();
          input.select();
        }
      });
    }

    function closeEditAppIdModal() {
      const bd = document.getElementById("appIdBackdrop");
      if (bd) {
        bd.classList.remove("open");
        bd.setAttribute("aria-hidden", "true");
      }
      editAppIdKeyId = null;
      setAppIdEditError("");
      const input = document.getElementById("app_id_edit_input");
      if (input) input.classList.remove("input-invalid");
    }

    function editGatewayAppId(id) {
      const el = document.querySelector(`.gw-app-id-display[data-key-id="${id}"]`);
      const current = el ? el.textContent.trim() : "";
      openEditAppIdModal(id, current);
    }

    async function submitEditAppId(ev) {
      if (ev) ev.preventDefault();
      const id = editAppIdKeyId;
      if (!id) return;
      const input = document.getElementById("app_id_edit_input");
      const trimmed = input ? String(input.value || "").trim() : "";
      if (!trimmed) {
        if (input) input.classList.add("input-invalid");
        setAppIdEditError("app_id 不能为空");
        if (input) input.focus();
        return;
      }
      if (input) input.classList.remove("input-invalid");
      setAppIdEditError("");
      const saveBtn = document.querySelector("#appIdEditForm button[type='submit']");
      if (saveBtn) saveBtn.disabled = true;
      try {
        const res = await fetch(`/admin/gateway-client-keys/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ app_id: trimmed }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const msg = formatApiError(data, "更新失败");
          setAppIdEditError(msg);
          if (input) input.classList.add("input-invalid");
          return;
        }
        toast("app_id 已更新");
        closeEditAppIdModal();
        renderGatewayKeyRows(data.items || []);
      } catch (_) {
        setAppIdEditError("请求失败，请稍后重试");
      } finally {
        if (saveBtn) saveBtn.disabled = false;
      }
    }

    document.getElementById("appIdBackdrop")?.addEventListener("click", () => closeEditAppIdModal());

    async function onCreateGatewayKey(ev) {
      if (ev) ev.preventDefault();
      const appInput = document.getElementById("gw_create_app_id");
      const keyInput = document.getElementById("gw_create_key");
      const appId = appInput ? String(appInput.value || "").trim() : "";
      const key = keyInput ? String(keyInput.value || "").trim() : "";
      if (!appId) {
        if (appInput) appInput.classList.add("input-invalid");
        setGwKeyCreateError("app_id 不能为空");
        if (appInput) appInput.focus();
        return;
      }
      if (appInput) appInput.classList.remove("input-invalid");
      if (!key) {
        setGwKeyCreateError("请等待密钥生成，或点击「重新生成」");
        await generateGatewayApiKey();
        return;
      }
      if (keyInput) keyInput.classList.remove("input-invalid");
      setGwKeyCreateError("");
      const saveBtn = document.querySelector("#gwKeyCreateForm button[type='submit']");
      if (saveBtn) saveBtn.disabled = true;
      try {
        const res = await fetch("/admin/gateway-client-keys", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ app_id: appId, gateway_api_key: key }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          setGwKeyCreateError(formatApiError(data, "保存失败"));
          return;
        }
        const plain = String(data.api_key || "").trim();
        if (plain) {
          try {
            await navigator.clipboard.writeText(plain);
            toast("已添加，完整 Key 已复制到剪贴板");
          } catch (_) {
            window.prompt("已添加，请妥善保存完整 Key（仅此一次）：", plain);
          }
        } else {
          toast("已添加");
        }
        closeCreateGatewayKeyModal();
        renderGatewayKeyRows(data.items || []);
      } catch (_) {
        setGwKeyCreateError("请求失败，请稍后重试");
      } finally {
        if (saveBtn) saveBtn.disabled = false;
      }
    }
    function upstreamProbeHint(data) {
      if (!data || typeof data !== "object") return "无法连接上游";
      if (data.error) return String(data.error);
      if (data.upstream_status_code != null) {
        return `上游 HTTP ${data.upstream_status_code}`;
      }
      return "上游返回异常";
    }

    function renderSwitchButton(u, probe) {
      const btnStyle = 'padding:7px 12px;font-size:12px;';
      const isLive = !!u.is_default && !!u.enabled;
      if (isLive) {
        return `<button class="ghost" type="button" disabled title="当前仅此一条对外转发">当前对外</button>`;
      }
      if (!u.enabled) {
        return `<button class="ghost" type="button" disabled title="请先启用该上游">切为对外</button>`;
      }
      if (!probe || probe.pending) {
        return `<button class="primary" type="button" disabled style="${btnStyle}" title="正在检测上游可用性">切为对外</button>`;
      }
      if (!probe.ok) {
        const hint = escapeHtml(probe.hint || "上游不可用");
        return `<button class="primary" type="button" disabled style="${btnStyle}" title="${hint}">切为对外</button>`;
      }
      return `<button class="primary" type="button" style="${btnStyle}" onclick="setDefault(${u.id})">切为对外</button>`;
    }

    function setUpstreamSwitchButton(u, probe) {
      const wrap = document.querySelector(
        `tr[data-upstream-id="${u.id}"] .upstream-switch-wrap`
      );
      if (wrap) wrap.innerHTML = renderSwitchButton(u, probe);
    }

    function renderUpstreamStatusBadge(u, probe) {
      if (!u.enabled) {
        return '<span class="badge badge-off">已禁用</span>';
      }
      if (!probe || probe.pending) {
        return '<span class="badge badge-pending">检测中</span>';
      }
      if (probe.ok) {
        return '<span class="badge badge-ok" title="拉取 /models 成功">可用</span>';
      }
      const hint = escapeHtml(probe.hint || "不可用");
      return `<span class="badge badge-err" title="${hint}">不可用</span>`;
    }

    function setUpstreamStatusCell(id, html) {
      const cell = document.querySelector(
        `tr[data-upstream-id="${id}"] td.upstream-status-cell`
      );
      if (cell) cell.innerHTML = html;
    }

    async function probeUpstreamRow(u) {
      if (!u.enabled) return;
      try {
        const res = await fetch("/admin/upstreams/test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: Number(u.id) }),
        });
        const data = await res.json().catch(() => ({}));
        const ok = res.ok && data.ok === true;
        setUpstreamStatusCell(
          u.id,
          renderUpstreamStatusBadge(u, {
            ok,
            hint: ok ? "" : upstreamProbeHint(data),
          })
        );
        setUpstreamSwitchButton(u, {
          ok,
          hint: ok ? "" : upstreamProbeHint(data),
        });
      } catch (e) {
        setUpstreamStatusCell(
          u.id,
          renderUpstreamStatusBadge(u, { ok: false, hint: String(e) })
        );
        setUpstreamSwitchButton(u, { ok: false, hint: String(e) });
      }
    }

    async function probeAllEnabledUpstreams(items) {
      const enabled = (items || []).filter((u) => u.enabled);
      await Promise.all(enabled.map((u) => probeUpstreamRow(u)));
    }

    async function loadList() {
      const tb = document.getElementById("tbody");
      tb.innerHTML = "<tr><td colspan='9'>加载中…</td></tr>";
      try {
        const res = await fetch("/admin/upstreams");
        const data = await res.json();
        const items = data.items || [];
        tb.innerHTML = items.length
          ? items.map((u) => {
              const isLive = !!u.is_default && !!u.enabled;
              const extCell = isLive
                ? '<span class="badge badge-def">当前对外</span>'
                : (u.is_default && !u.enabled
                  ? '<span class="badge badge-off" title="已禁用，网关不会选用">标记默认但未启用</span>'
                  : '<span class="muted">—</span>');
              const switchBtn = renderSwitchButton(
                u,
                u.enabled ? { pending: true } : null
              );
              const statusCell = renderUpstreamStatusBadge(
                u,
                u.enabled ? { pending: true } : null
              );
              return `
            <tr data-upstream-id="${u.id}">
              <td>${u.id}</td>
              <td>${escapeHtml(u.name)}</td>
              <td><code>${escapeHtml(u.base_url)}</code></td>
              <td><span class="key-masked">${escapeHtml(u.api_key_masked || "")}</span></td>
              <td>${escapeHtml(u.timeout_seconds)}</td>
              <td>${u.trust_env ? "是" : "否"}</td>
              <td class="upstream-status-cell">${statusCell}</td>
              <td>${extCell}</td>
              <td>
                <div class="actions">
                  <button class="ghost" type="button" onclick="testById(${u.id})">可用模型</button>
                  <span class="upstream-switch-wrap">${switchBtn}</span>
                  <button class="ghost" type="button" onclick="editRow(${u.id})">编辑</button>
                  <button class="ghost danger" type="button" onclick="removeRow(${u.id})">删除</button>
                </div>
              </td>
            </tr>`;
            }).join("")
          : "<tr><td colspan='9'>暂无上游；请在「新增上游」中填写（仅存本地 SQLite）</td></tr>";
        if (items.length) {
          probeAllEnabledUpstreams(items);
        }
      } catch (e) {
        tb.innerHTML = "<tr><td colspan='9'>加载失败</td></tr>";
        toast("加载失败");
      } finally {
        await loadGatewayClientKeys();
      }
    }
    function escapeHtml(s) {
      return String(s ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }
    function openCreateModal() {
      const f = document.getElementById("createForm");
      f.reset();
      document.getElementById("c_enabled").checked = true;
      document.getElementById("c_timeout").value = "60";
      const bd = document.getElementById("createBackdrop");
      bd.classList.add("open");
      bd.setAttribute("aria-hidden", "false");
    }
    function closeCreateModal() {
      const bd = document.getElementById("createBackdrop");
      bd.classList.remove("open");
      bd.setAttribute("aria-hidden", "true");
    }
    document.getElementById("createBackdrop").addEventListener("click", () => closeCreateModal());

    async function onCreate(ev) {
      ev.preventDefault();
      const body = {
        name: document.getElementById("c_name").value.trim(),
        base_url: document.getElementById("c_base").value.trim(),
        api_key: document.getElementById("c_key").value,
        timeout_seconds: Number(document.getElementById("c_timeout").value) || 60,
        trust_env: document.getElementById("c_trust").checked,
        enabled: document.getElementById("c_enabled").checked,
        is_default: document.getElementById("c_default").checked,
      };
      try {
        const res = await fetch("/admin/upstreams", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          toast(formatApiError(data, "创建失败"));
          return;
        }
        toast("已保存");
        closeCreateModal();
        document.getElementById("createForm").reset();
        document.getElementById("c_enabled").checked = true;
        document.getElementById("c_timeout").value = "60";
        loadList();
      } catch (_) {
        toast("请求失败");
      }
    }
    function openTestModal() {
      const bd = document.getElementById("testBackdrop");
      bd.classList.add("open");
      bd.setAttribute("aria-hidden", "false");
    }
    function closeTestModal() {
      const bd = document.getElementById("testBackdrop");
      bd.classList.remove("open");
      bd.setAttribute("aria-hidden", "true");
    }
    /** @returns {{ items: { id: string, owned_by: string }[] } | null} */
    function parseModelsFromTestPayload(data) {
      if (!data || typeof data !== "object" || data.ok !== true) return null;
      const body = data.body;
      if (!body || typeof body !== "object") return null;
      const arr = body.data;
      if (!Array.isArray(arr)) return null;
      const items = [];
      for (const row of arr) {
        if (!row || typeof row !== "object") continue;
        const id = row.id != null ? String(row.id).trim() : "";
        if (!id) continue;
        const owned_by = row.owned_by != null ? String(row.owned_by) : "";
        items.push({ id, owned_by });
      }
      return { items };
    }

    function paintTestModal(title, summaryLine, summaryClass, mode, payload) {
      document.getElementById("testModalTitle").textContent = title;
      const sum = document.getElementById("testModalSummary");
      if (summaryLine) {
        sum.style.display = "block";
        sum.className = "test-summary " + (summaryClass || "");
        sum.textContent = summaryLine;
      } else {
        sum.style.display = "none";
        sum.textContent = "";
        sum.className = "test-summary";
      }
      const plain = document.getElementById("testModalPlain");
      const wrap = document.getElementById("testModelListWrap");
      const list = document.getElementById("testModelList");
      const countEl = document.getElementById("testModelCount");
      if (mode === "list") {
        const items = payload.items || [];
        plain.style.display = "none";
        wrap.style.display = "block";
        countEl.textContent = `共 ${items.length} 个模型`;
        list.innerHTML = items
          .map((m) => {
            const meta = m.owned_by
              ? `<span class="meta"> · ${escapeHtml(m.owned_by)}</span>`
              : "";
            return `<li><code>${escapeHtml(m.id)}</code>${meta}</li>`;
          })
          .join("");
      } else {
        plain.style.display = "block";
        wrap.style.display = "none";
        list.innerHTML = "";
        countEl.textContent = "";
        plain.textContent = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
      }
      openTestModal();
    }

    document.getElementById("testBackdrop").addEventListener("click", () => closeTestModal());

    async function runTest(payload) {
      paintTestModal("拉取模型列表…", null, null, "plain", "请求中…");
      try {
        const res = await fetch("/admin/upstreams/test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          paintTestModal("HTTP " + res.status, null, null, "plain", data);
          toast("请求失败");
          return;
        }
        const ms = data.latency_ms != null ? `${data.latency_ms} ms` : "—";
        const sc = data.upstream_status_code != null ? String(data.upstream_status_code) : "—";
        const ok = data.ok === true;
        const line = `HTTP ${sc} · 耗时 ${ms}` + (ok ? "" : " · upstream 判定失败");
        const parsed = parseModelsFromTestPayload(data);
        if (ok && parsed) {
          paintTestModal("连接成功", line, "ok", "list", parsed);
        } else {
          paintTestModal(ok ? "连接成功" : "上游返回错误", line, ok ? "ok" : "err", "plain", data);
        }
        toast(ok ? "连接成功" : "上游返回错误");
        const rowItem = { id: Number(payload.id), enabled: true };
        if (payload.id != null) {
          setUpstreamStatusCell(
            payload.id,
            renderUpstreamStatusBadge(rowItem, {
              ok,
              hint: ok ? "" : upstreamProbeHint(data),
            })
          );
        }
      } catch (e) {
        paintTestModal("请求异常", null, null, "plain", String(e));
        toast("请求失败");
      }
    }
    async function testById(id) {
      await runTest({ id: Number(id) });
    }
    async function setDefault(id) {
      if (!confirm("将此上游设为当前对外服务？/v1/models 与 /v1/chat/completions 将立即走该配置，且全局仅一条生效。")) return;
      try {
        const res = await fetch(`/admin/upstreams/${id}/set-default`, { method: "POST" });
        if (!res.ok) {
          toast("操作失败（需已启用）");
          return;
        }
        toast("已切换对外服务上游");
        loadList();
      } catch (_) {
        toast("请求失败");
      }
    }
    async function removeRow(id) {
      if (!confirm(`删除上游 #${id}？`)) return;
      try {
        const res = await fetch(`/admin/upstreams/${id}`, { method: "DELETE" });
        if (!res.ok) {
          toast("删除失败");
          return;
        }
        toast("已删除");
        loadList();
      } catch (_) {
        toast("请求失败");
      }
    }
    let editUpstreamId = null;
    let editWasDefault = false;

    function closeEditModal() {
      const bd = document.getElementById("editBackdrop");
      bd.classList.remove("open");
      bd.setAttribute("aria-hidden", "true");
      editUpstreamId = null;
    }

    function openEditModal(u) {
      editUpstreamId = u.id;
      editWasDefault = !!u.is_default;
      document.getElementById("editIdHint").textContent = `正在编辑 id=${u.id}` + (u.api_key_masked ? ` · 当前密钥 ${u.api_key_masked}` : "");
      document.getElementById("e_name").value = u.name || "";
      document.getElementById("e_base").value = u.base_url || "";
      document.getElementById("e_key").value = "";
      document.getElementById("e_timeout").value = String(u.timeout_seconds ?? 60);
      document.getElementById("e_trust").checked = !!u.trust_env;
      document.getElementById("e_enabled").checked = !!u.enabled;
      const wrap = document.getElementById("e_default_wrap");
      const note = document.getElementById("e_default_note");
      const eDef = document.getElementById("e_default");
      if (editWasDefault) {
        wrap.style.display = "none";
        eDef.checked = true;
        note.style.display = "block";
      } else {
        wrap.style.display = "";
        eDef.checked = false;
        note.style.display = "none";
      }
      const bd = document.getElementById("editBackdrop");
      bd.classList.add("open");
      bd.setAttribute("aria-hidden", "false");
    }

    document.getElementById("editBackdrop").addEventListener("click", () => closeEditModal());
    document.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      if (document.getElementById("testBackdrop").classList.contains("open")) {
        closeTestModal();
        return;
      }
      if (document.getElementById("appIdBackdrop").classList.contains("open")) {
        closeEditAppIdModal();
        return;
      }
      if (document.getElementById("createBackdrop").classList.contains("open")) {
        closeCreateModal();
        return;
      }
      if (document.getElementById("editBackdrop").classList.contains("open")) {
        closeEditModal();
      }
    });

    async function editRow(id) {
      let u;
      try {
        const res = await fetch(`/admin/upstreams/${id}`);
        if (!res.ok) {
          toast("读取失败");
          return;
        }
        u = await res.json();
      } catch (_) {
        toast("读取失败");
        return;
      }
      openEditModal(u);
    }

    async function submitEdit() {
      const id = editUpstreamId;
      if (!id) return;
      const name = document.getElementById("e_name").value.trim();
      const base_url = document.getElementById("e_base").value.trim();
      if (!name || !base_url) {
        toast("名称与 Base URL 必填");
        return;
      }
      const wantDefault = document.getElementById("e_default").checked;
      const enabled = document.getElementById("e_enabled").checked;
      if (wantDefault && !editWasDefault && !enabled) {
        toast("设为对外服务需先勾选「启用」");
        return;
      }
      const patch = {
        name,
        base_url,
        timeout_seconds: Number(document.getElementById("e_timeout").value) || 60,
        trust_env: document.getElementById("e_trust").checked,
        enabled,
      };
      const api_key = document.getElementById("e_key").value;
      if (api_key.trim()) patch.api_key = api_key.trim();
      try {
        const res = await fetch(`/admin/upstreams/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          toast(formatApiError(data, "更新失败"));
          return;
        }
        if (wantDefault && !editWasDefault) {
          const r2 = await fetch(`/admin/upstreams/${id}/set-default`, { method: "POST" });
          if (!r2.ok) {
            toast("已保存条目，但切换对外服务失败（请确认已启用）");
            closeEditModal();
            loadList();
            return;
          }
        }
        toast("已更新");
        closeEditModal();
        loadList();
      } catch (_) {
        toast("请求失败");
      }
    }
    loadList();
