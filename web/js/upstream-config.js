function toast(msg) {
      const el = document.getElementById("toast");
      el.textContent = msg;
      el.classList.add("show");
      setTimeout(() => el.classList.remove("show"), 1600);
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
              <td><code>${escapeHtml(k.api_key_masked || "")}</code></td>
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
        : "<tr><td colspan='4' class='muted'>尚无对外 API Key，请在下方「添加」写入数据库</td></tr>";
    }

    async function loadGatewayClientKeys() {
      const tb = document.getElementById("gwKeyTbody");
      if (!tb) return;
      try {
        const res = await fetch("/admin/gateway-client-keys");
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          tb.innerHTML = "<tr><td colspan='4'>读取失败</td></tr>";
          return;
        }
        renderGatewayKeyRows(data.items || []);
      } catch (_) {
        tb.innerHTML = "<tr><td colspan='4'>读取失败</td></tr>";
      }
    }

    function focusNewGatewayKey() {
      const input = document.getElementById("gw_client_key_input");
      if (input) input.focus();
    }

    async function copyGatewayClientKey(id) {
      try {
        const res = await fetch(`/admin/gateway-client-keys/${id}`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          toast(typeof data.detail === "string" ? data.detail : "读取失败");
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
          toast(typeof data.detail === "string" ? data.detail : "删除失败");
          return;
        }
        toast("已删除");
        renderGatewayKeyRows(data.items || []);
      } catch (_) {
        toast("请求失败");
      }
    }

    async function addGatewayClientKey() {
      const input = document.getElementById("gw_client_key_input");
      const v = (input && input.value) ? input.value.trim() : "";
      if (!v) {
        toast("请输入要添加的 API Key");
        return;
      }
      try {
        const res = await fetch("/admin/gateway-client-keys", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ gateway_api_key: v }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          toast(typeof data.detail === "string" ? data.detail : "添加失败");
          return;
        }
        toast("已添加");
        input.value = "";
        renderGatewayKeyRows(data.items || []);
      } catch (_) {
        toast("请求失败");
      }
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
              const canSwitch = !!u.enabled && !u.is_default;
              const switchBtn = canSwitch
                ? `<button class="primary" type="button" style="padding:7px 12px;font-size:12px;" onclick="setDefault(${u.id})">切为对外</button>`
                : (isLive
                  ? '<button class="ghost" type="button" disabled title="当前仅此一条对外转发">当前对外</button>'
                  : '<button class="ghost" type="button" disabled title="请先启用该上游">切为对外</button>');
              return `
            <tr>
              <td>${u.id}</td>
              <td>${escapeHtml(u.name)}</td>
              <td><code>${escapeHtml(u.base_url)}</code></td>
              <td>${escapeHtml(u.api_key_masked || "")}</td>
              <td>${escapeHtml(u.timeout_seconds)}</td>
              <td>${u.trust_env ? "是" : "否"}</td>
              <td>${u.enabled ? "" : '<span class="badge badge-off">已禁用</span>'}</td>
              <td>${extCell}</td>
              <td>
                <div class="actions">
                  <button class="ghost" type="button" onclick="testById(${u.id})">可用模型</button>
                  ${switchBtn}
                  <button class="ghost" type="button" onclick="editRow(${u.id})">编辑</button>
                  <button class="ghost danger" type="button" onclick="removeRow(${u.id})">删除</button>
                </div>
              </td>
            </tr>`;
            }).join("")
          : "<tr><td colspan='9'>暂无上游；请在「新增上游」中填写（仅存本地 SQLite）</td></tr>";
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
          toast(data.detail || "创建失败");
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
          toast(typeof data.detail === "string" ? data.detail : "更新失败");
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
