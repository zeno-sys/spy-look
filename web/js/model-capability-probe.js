(function () {
  const CAPABILITY_KEYS = [
    "chat_completion",
    "tool_calling",
    "json_mode",
    "thinking",
  ];

  const CAPABILITY_LABELS = {
    chat_completion: ["基础对话", "能否正常完成 Chat Completions 请求并返回文本"],
    tool_calling: ["工具调用", "是否支持 tools / tool_calls（Function Calling）"],
    json_mode: ["结构化输出", "是否支持 Pydantic parse 等价能力（json_schema + 严格解析）"],
    thinking: ["思考模式", "探测模型是否输出思考内容，以及能否通过参数控制开关"],
  };

  const CAPABILITY_ICONS = {
    chat_completion: ["cap-icon-chat", "聊"],
    tool_calling: ["cap-icon-tool", "具"],
    json_mode: ["cap-icon-json", "构"],
    thinking: ["cap-icon-thinking", "思"],
  };

  const MODELS_CACHE_TTL_MS = 5 * 60 * 1000;
  const CUSTOM_FETCH_DEBOUNCE_MS = 500;

  let optionsData = { upstreams: [] };
  const upstreamModelsCache = {};
  const customModelsCache = {};
  let customFetchTimer = null;

  function esc(text) {
    const d = document.createElement("div");
    d.textContent = text == null ? "" : String(text);
    return d.innerHTML;
  }

  function getMode() {
    const el = document.querySelector('input[name="probeMode"]:checked');
    return el ? el.value : "upstream";
  }

  function customCacheKey(uri, apiKey) {
    return uri + "\0" + apiKey;
  }

  function onModeChange() {
    const mode = getMode();
    document.getElementById("upstreamFields").classList.toggle("hidden", mode !== "upstream");
    document.getElementById("customFields").classList.toggle("hidden", mode !== "custom");
    if (mode === "custom") {
      onCustomCredentialsChange();
    }
  }

  function fillUpstreamSelect() {
    const sel = document.getElementById("upstreamSelect");
    const items = optionsData.upstreams || [];
    if (!items.length) {
      sel.innerHTML = '<option value="">暂无已启用上游</option>';
      resetModelSelect("暂无可用模型");
      return;
    }
    sel.innerHTML = items
      .map(
        (u) =>
          `<option value="${esc(u.id)}"${u.is_default ? " selected" : ""}>${esc(u.name)}${u.is_default ? "（默认）" : ""}</option>`
      )
      .join("");
    onUpstreamChange();
  }

  function resetModelSelect(placeholder, selectId) {
    const sel = document.getElementById(selectId || "modelSelect");
    sel.innerHTML = `<option value="">${esc(placeholder || "请先选择上游")}</option>`;
    sel.disabled = true;
  }

  function fillModelSelect(models, selectId) {
    const sel = document.getElementById(selectId || "modelSelect");
    const sorted = [...models].sort((a, b) =>
      String(a).localeCompare(String(b), undefined, { sensitivity: "base" })
    );
    if (!sorted.length) {
      resetModelSelect("未获取到可用模型", selectId);
      return;
    }
    sel.innerHTML = sorted
      .map((m, i) => `<option value="${esc(m)}"${i === 0 ? " selected" : ""}>${esc(m)}</option>`)
      .join("");
    sel.disabled = false;
  }

  function setModelSelectLoading(selectId, text) {
    const sel = document.getElementById(selectId);
    sel.disabled = true;
    sel.innerHTML = `<option value="">${esc(text)}</option>`;
  }

  async function loadModelsForUpstream(upstreamId) {
    if (!upstreamId) {
      resetModelSelect("请先选择上游");
      return;
    }

    const cached = upstreamModelsCache[upstreamId];
    if (cached && Date.now() - cached.at < MODELS_CACHE_TTL_MS) {
      fillModelSelect(cached.models);
      return;
    }

    setModelSelectLoading("modelSelect", "加载模型列表…");

    try {
      const res = await fetch(
        "/admin/model-capability-probe/models?upstream_id=" + encodeURIComponent(upstreamId)
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(formatApiError(data, "加载模型失败"));
      }
      const models = Array.isArray(data.models) ? data.models : [];
      upstreamModelsCache[upstreamId] = { at: Date.now(), models };
      fillModelSelect(models);
    } catch (err) {
      resetModelSelect("加载失败，请重选上游");
      console.error(err);
    }
  }

  function onUpstreamChange() {
    const upstreamId = document.getElementById("upstreamSelect").value;
    loadModelsForUpstream(upstreamId);
  }

  async function loadModelsForCustom(uri, apiKey) {
    if (!uri || !apiKey) {
      resetModelSelect("请先填写 API 地址与 Key", "customModelSelect");
      return;
    }

    const key = customCacheKey(uri, apiKey);
    const cached = customModelsCache[key];
    if (cached && Date.now() - cached.at < MODELS_CACHE_TTL_MS) {
      fillModelSelect(cached.models, "customModelSelect");
      return;
    }

    setModelSelectLoading("customModelSelect", "加载模型列表…");

    try {
      const res = await fetch("/admin/model-capability-probe/models/custom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uri, api_key: apiKey }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(formatApiError(data, "加载模型失败"));
      }
      const models = Array.isArray(data.models) ? data.models : [];
      customModelsCache[key] = { at: Date.now(), models };
      fillModelSelect(models, "customModelSelect");
    } catch (err) {
      resetModelSelect("加载失败，请检查地址与 Key", "customModelSelect");
      console.error(err);
    }
  }

  function onCustomCredentialsChange() {
    if (getMode() !== "custom") return;
    if (customFetchTimer) clearTimeout(customFetchTimer);
    const uri = document.getElementById("customUri").value.trim();
    const apiKey = document.getElementById("customApiKey").value.trim();
    if (!uri || !apiKey) {
      resetModelSelect("请先填写 API 地址与 Key", "customModelSelect");
      return;
    }
    customFetchTimer = setTimeout(() => {
      loadModelsForCustom(uri, apiKey);
    }, CUSTOM_FETCH_DEBOUNCE_MS);
  }

  function formatApiError(data, fallback) {
    const detail = data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
    }
    return fallback;
  }

  async function loadOptions() {
    const res = await fetch("/admin/model-capability-probe/options");
    if (!res.ok) throw new Error("加载选项失败");
    optionsData = await res.json();
    fillUpstreamSelect();
  }

  function setProbing(active, text) {
    document.getElementById("probeBtn").disabled = active;
    document.getElementById("probeStatus").textContent = text || "";
  }

  function buildProbeBody() {
    const mode = getMode();
    if (mode === "upstream") {
      const upstreamId = document.getElementById("upstreamSelect").value;
      const model = document.getElementById("modelSelect").value.trim();
      if (!upstreamId) throw new Error("请选择上游");
      if (!model) throw new Error("请选择模型");
      return { mode: "upstream", upstream_id: Number(upstreamId), model };
    }
    const uri = document.getElementById("customUri").value.trim();
    const apiKey = document.getElementById("customApiKey").value.trim();
    const model = document.getElementById("customModelSelect").value.trim();
    if (!uri) throw new Error("请填写 API 地址");
    if (!apiKey) throw new Error("请填写 API Key");
    if (!model) throw new Error("请选择模型");
    return { mode: "custom", uri, api_key: apiKey, model };
  }

  function fieldRow(label, value) {
    if (value == null || value === "") return "";
    return `<div class="row"><span class="label">${esc(label)}</span><span class="value">${value}</span></div>`;
  }

  function formatError(err) {
    const text = String(err);
    return esc(text.length > 500 ? text.slice(0, 500) + "…" : text);
  }

  function thinkingSubStatus(sub) {
    if (!sub || typeof sub !== "object") return { text: "请求失败", cls: "probe-badge-err" };
    if (sub.has_thinking === true) return { text: "有思考", cls: "probe-badge-ok" };
    if (sub.has_thinking === false) return { text: "无思考", cls: "probe-badge-dim" };
    return { text: "请求失败", cls: "probe-badge-err" };
  }

  function getThinkingControlInfo(item) {
    const mode = item.mode;
    if (mode === "hybrid") {
      return {
        cls: "thinking-callout-controllable",
        title: "支持思考 · 可控制开关",
        body: "模型会输出思考内容，且可通过 thinking 相关参数控制：开启参数时有思考，关闭参数时无思考。",
        tag: "可通过参数控制思考开关",
        tagCls: "yes",
      };
    }
    if (mode === "thinking_only") {
      return {
        cls: "thinking-callout-uncontrollable",
        title: "支持思考 · 不可控制开关",
        body: "模型会输出思考内容，但关闭 thinking 参数后仍会返回思考，无法通过参数关掉。",
        tag: "不可通过参数控制思考开关",
        tagCls: "no",
      };
    }
    if (mode === "not_supported") {
      return {
        cls: "thinking-callout-none",
        title: "不支持思考",
        body: "开启与关闭 thinking 参数时，均未检测到思考内容输出。",
        tag: null,
        tagCls: null,
      };
    }
    return {
      cls: "thinking-callout-unknown",
      title: "思考能力未明确",
      body: item.detail || "探测请求异常或行为不符合常见模式，无法判定思考能力与可控性。",
      tag: null,
      tagCls: null,
    };
  }

  function renderThinkingSection(item) {
    const info = getThinkingControlInfo(item);
    let html = `<div class="thinking-callout ${info.cls}">`;
    html += `<strong>${esc(info.title)}</strong>`;
    html += `<p>${esc(info.body)}</p>`;
    if (info.tag) {
      html += `<span class="thinking-control-tag ${info.tagCls}">${esc(info.tag)}</span>`;
    }
    html += "</div>";

    html += '<div class="thinking-probes">';
    [["enabled", "开启思考参数"], ["disabled", "关闭思考参数"]].forEach(([subKey, subLabel]) => {
      const sub = item[subKey];
      if (!sub || typeof sub !== "object") return;
      const st = thinkingSubStatus(sub);
      html += `<div class="thinking-probe">`;
      html += `<span class="thinking-probe-label">${esc(subLabel)}</span>`;
      html += `<span class="probe-badge ${st.cls}">${esc(st.text)}</span>`;
      if (sub.detail && sub.has_thinking) {
        html += `<div class="thinking-probe-detail">${esc(sub.detail)}</div>`;
      } else if (sub.error) {
        html += `<div class="thinking-probe-detail">${esc(String(sub.error).slice(0, 160))}</div>`;
      } else if (sub.content_preview) {
        html += `<div class="thinking-probe-detail">${esc(sub.content_preview)}</div>`;
      }
      html += "</div>";
    });
    html += "</div>";
    return html;
  }

  function cardStatusClass(skipped, supported) {
    if (skipped) return "cap-card--skip";
    if (supported) return "cap-card--ok";
    return "cap-card--err";
  }

  function renderCapabilityCard(key, item) {
    if (!item || typeof item !== "object") return "";

    const [title, desc] = CAPABILITY_LABELS[key] || [key, ""];
    const [iconCls, iconText] = CAPABILITY_ICONS[key] || ["cap-icon-chat", "?"];
    const skipped = String(item.detail || "").includes("跳过");
    const supported = !!item.supported;

    let badgeClass = "badge-err";
    let badgeText = "不支持";
    if (skipped) {
      badgeClass = "badge-skip";
      badgeText = "已跳过";
    } else if (supported) {
      badgeClass = "badge-ok";
      badgeText = "支持";
    }

    let body = "";
    if (key === "thinking" && !skipped) {
      body = renderThinkingSection(item);
    } else {
      let fields = "";
      if (item.detail) fields += fieldRow("说明", esc(item.detail));
      if (item.error) fields += fieldRow("错误", `<span style="color:var(--err)">${formatError(item.error)}</span>`);
      if (item.status_code != null) {
        const color = item.status_code === 200 ? "var(--ok)" : "var(--err)";
        fields += fieldRow("HTTP 状态", `<span style="color:${color}">${esc(item.status_code)}</span>`);
      }
      if (item.elapsed_ms != null) fields += fieldRow("耗时", esc(item.elapsed_ms + " ms"));
      if (item.finish_reason) fields += fieldRow("结束原因", esc(item.finish_reason));
      if (item.parsed != null) {
        fields += fieldRow(
          "解析结果",
          `<pre>${esc(JSON.stringify(item.parsed, null, 2))}</pre>`
        );
      }
      if (item.content_preview) fields += fieldRow("内容预览", esc(item.content_preview));
      if (fields) body = `<div class="cap-fields">${fields}</div>`;
    }

    let notes = "";
    if (item.legacy_format) notes += '<div class="cap-note">备注：使用旧版 function_call 格式</div>';
    if (item.param_rejected) notes += '<div class="cap-note">备注：服务端可能拒绝了 response_format / json_schema 参数</div>';

    return `
      <article class="cap-card ${cardStatusClass(skipped, supported)}">
        <div class="cap-card-accent"></div>
        <div class="cap-card-body">
          <div class="cap-card-head">
            <div class="cap-icon ${iconCls}">${esc(iconText)}</div>
            <div class="cap-title-block">
              <h3 class="cap-card-title">${esc(title)}</h3>
              <p class="cap-card-desc">${esc(desc)}</p>
            </div>
            <span class="badge ${badgeClass}">${badgeText}</span>
          </div>
          ${body}
          ${notes}
        </div>
      </article>`;
  }

  function computeReportStats(report) {
    let supportedCount = 0;
    let testedCount = 0;
    CAPABILITY_KEYS.forEach((key) => {
      const item = report[key];
      if (!item || typeof item !== "object") return;
      const skipped = String(item.detail || "").includes("跳过");
      if (skipped) return;
      testedCount += 1;
      if (item.supported) supportedCount += 1;
    });
    return { supportedCount, testedCount };
  }

  function buildSummaryText(supportedCount, testedCount) {
    if (testedCount === 0) return { text: "未能完成任何有效探测", cls: "summary-none" };
    if (supportedCount === testedCount) {
      return { text: `全部通过（${supportedCount}/${testedCount}）`, cls: "summary-ok" };
    }
    return { text: `部分通过（${supportedCount}/${testedCount}）`, cls: "summary-partial" };
  }

  function renderCapabilityReport(report) {
    const panel = document.getElementById("reportPanel");
    panel.classList.remove("hidden");

    const { supportedCount, testedCount } = computeReportStats(report);
    const summary = buildSummaryText(supportedCount, testedCount);
    const pct = testedCount ? Math.round((supportedCount / testedCount) * 100) : 0;

    const badgeEl = document.getElementById("reportSummaryBadge");
    badgeEl.className = "report-summary-badge " + summary.cls;
    badgeEl.textContent = summary.text;

    document.getElementById("reportProgress").innerHTML = `
      <div class="report-progress-track">
        <div class="report-progress-fill" style="width:${pct}%"></div>
      </div>
      <div class="report-progress-label">
        <span>能力通过率</span>
        <span>${supportedCount} / ${testedCount} 项（${pct}%）</span>
      </div>`;

    document.getElementById("reportMeta").innerHTML = `
      <div class="report-meta-item">
        <dt>服务地址</dt>
        <dd class="mono">${esc(report.uri || "-")}</dd>
      </div>
      <div class="report-meta-item">
        <dt>请求端点</dt>
        <dd class="mono">${esc(report.endpoint || "-")}</dd>
      </div>
      <div class="report-meta-item">
        <dt>模型名称</dt>
        <dd>${esc(report.model || "-")}</dd>
      </div>
      <div class="report-meta-item">
        <dt>总耗时</dt>
        <dd>${report.total_elapsed_ms != null ? esc(report.total_elapsed_ms + " ms") : "-"}</dd>
      </div>`;

    document.getElementById("reportCards").innerHTML = CAPABILITY_KEYS.map((key) =>
      renderCapabilityCard(key, report[key])
    ).join("");

    const summaryEl = document.getElementById("reportSummary");
    summaryEl.className = "report-summary " + summary.cls;
    const thinking = report.thinking;
    let thinkingHint = "";
    if (thinking && typeof thinking === "object" && !String(thinking.detail || "").includes("跳过")) {
      const info = getThinkingControlInfo(thinking);
      if (thinking.mode === "hybrid" || thinking.mode === "thinking_only") {
        thinkingHint = `思考模式：${info.title}。${info.body}`;
      }
    }
    summaryEl.textContent = thinkingHint
      ? `汇总：${summary.text}。${thinkingHint}`
      : `汇总：${summary.text}`;

    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function runProbe() {
    let body;
    try {
      body = buildProbeBody();
    } catch (err) {
      alert(err.message || String(err));
      return;
    }

    setProbing(true, "探测中，请稍候…");
    try {
      const res = await fetch("/admin/model-capability-probe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(formatApiError(data, "请求失败 " + res.status));
      }
      renderCapabilityReport(data);
      setProbing(false, "探测完成");
    } catch (err) {
      setProbing(false, "");
      alert(err.message || String(err));
    }
  }

  window.onModeChange = onModeChange;
  window.onUpstreamChange = onUpstreamChange;
  window.onCustomCredentialsChange = onCustomCredentialsChange;
  window.runProbe = runProbe;

  onModeChange();
  loadOptions().catch((err) => {
    document.getElementById("upstreamSelect").innerHTML =
      '<option value="">加载失败</option>';
    console.error(err);
  });
})();
