"""版面检测单文件版（PP-DocLayoutV3 / CPU）

不依赖 rapid_doc.model.layout 多层封装，仅用 onnxruntime + opencv + numpy。
作用：检测标题 / 正文 / 表格 / 图片 / 公式等区域，输出 poly + category。
"""
from __future__ import annotations

import base64
import colorsys
import html
import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple, Union

import cv2
import numpy as np
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[1]
IMG_PATH = ROOT / "test_layout.png"
MODEL_PATH = Path(__file__).resolve().parent / "models" / "pp_doclayoutv3.onnx"

# 与 RapidLayout(PP_DOCLAYOUTV3) 默认一致
CONF_THRESH = 0.3
IMG_SIZE = (800, 800)  # (h, w)

# CategoryId（仅保留 V3 会用到的映射）
CATEGORY = {
    "Title": 0,
    "Text": 1,
    "Abandon": 2,
    "ImageBody": 3,
    "TableBody": 5,
    "InterlineEquationNumber_Layout": 9,
    "InlineEquation": 13,
    "InterlineEquation_YOLO": 14,
}

MARKDOWN_IGNORE_LABELS = {
    "number",
    "footnote",
    "header",
    "header_image",
    "footer",
    "footer_image",
    "aside_text",
}

# 不参与逻辑阅读顺序编号的类别（与官方后处理一致）
SKIP_ORDER_LABELS = {
    "figure_title",
    "vision_footnote",
    "image",
    "chart",
    "table",
    "header",
    "header_image",
    "footer",
    "footer_image",
    "footnote",
    "aside_text",
    "number",
}

# PP-DocLayoutV3 / V2 标签 → category_id
LABEL_TO_CATEGORY: Dict[str, int] = {
    "abstract": CATEGORY["Text"],
    "algorithm": CATEGORY["Text"],
    "aside_text": CATEGORY["Text"],
    "chart": CATEGORY["ImageBody"],
    "content": CATEGORY["Text"],
    "display_formula": CATEGORY["InterlineEquation_YOLO"],
    "doc_title": CATEGORY["Title"],
    "figure_title": CATEGORY["Text"],
    "footer": CATEGORY["Text"],
    "footer_image": CATEGORY["ImageBody"],
    "footnote": CATEGORY["Text"],
    "formula_number": CATEGORY["InterlineEquationNumber_Layout"],
    "header": CATEGORY["Text"],
    "header_image": CATEGORY["ImageBody"],
    "image": CATEGORY["ImageBody"],
    "inline_formula": CATEGORY["InlineEquation"],
    "number": CATEGORY["Text"],
    "paragraph_title": CATEGORY["Title"],
    "reference": CATEGORY["Text"],
    "reference_content": CATEGORY["Text"],
    "seal": CATEGORY["ImageBody"],
    "table": CATEGORY["TableBody"],
    "text": CATEGORY["Text"],
    "vertical_text": CATEGORY["Text"],
    "vision_footnote": CATEGORY["Text"],
}
LABEL_TO_CATEGORY = {
    k: (CATEGORY["Abandon"] if k in MARKDOWN_IGNORE_LABELS else v)
    for k, v in LABEL_TO_CATEGORY.items()
}

# 英文标签 → 中文展示名（HTML / 终端）
LABEL_ZH: Dict[str, str] = {
    "abstract": "摘要",
    "algorithm": "算法",
    "aside_text": "侧栏文本",
    "chart": "图表",
    "content": "目录/内容",
    "display_formula": "行间公式",
    "doc_title": "文档标题",
    "figure_title": "图题",
    "footer": "页脚",
    "footer_image": "页脚图",
    "footnote": "脚注",
    "formula_number": "公式编号",
    "header": "页眉",
    "header_image": "页眉图",
    "image": "图片",
    "inline_formula": "行内公式",
    "number": "页码/编号",
    "paragraph_title": "段落标题",
    "reference": "参考文献",
    "reference_content": "参考文献内容",
    "seal": "印章",
    "table": "表格",
    "text": "正文",
    "vertical_text": "竖排文本",
    "vision_footnote": "图注脚注",
}


def label_zh(label: str) -> str:
    return LABEL_ZH.get(label, label)


def preprocess(img_rgb: np.ndarray) -> Tuple[np.ndarray, List[float]]:
    """Resize + normalize + CHW；返回 (input, scale_factor=[h_scale, w_scale])."""
    h, w = img_rgb.shape[:2]
    target_h, target_w = IMG_SIZE
    resized = cv2.resize(img_rgb, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
    blob = resized.astype(np.float32) / 255.0
    blob = blob.transpose(2, 0, 1)[None, ...]  # 1x3xHxW
    scale_factor = [target_h / h, target_w / w]
    return blob, scale_factor


def _iou(box1: Sequence[float], box2: Sequence[float]) -> float:
    x1, y1, x2, y2 = box1
    x1_p, y1_p, x2_p, y2_p = box2
    xi1, yi1 = max(x1, x1_p), max(y1, y1_p)
    xi2, yi2 = min(x2, x2_p), min(y2, y2_p)
    inter = max(0, xi2 - xi1 + 1) * max(0, yi2 - yi1 + 1)
    a1 = (x2 - x1 + 1) * (y2 - y1 + 1)
    a2 = (x2_p - x1_p + 1) * (y2_p - y1_p + 1)
    return inter / float(a1 + a2 - inter + 1e-6)


def nms(boxes: np.ndarray, iou_same: float = 0.6, iou_diff: float = 0.98) -> List[int]:
    """同类别 / 跨类别使用不同 IoU 阈值的 NMS。boxes: [cls, score, x1, y1, x2, y2, ...]"""
    if len(boxes) == 0:
        return []
    order = np.argsort(boxes[:, 1])[::-1]
    keep: List[int] = []
    while len(order) > 0:
        cur = int(order[0])
        keep.append(cur)
        rest = order[1:]
        if len(rest) == 0:
            break
        filtered = []
        for i in rest:
            thr = iou_same if boxes[i, 0] == boxes[cur, 0] else iou_diff
            if _iou(boxes[cur, 2:6], boxes[i, 2:6]) < thr:
                filtered.append(int(i))
        order = np.array(filtered, dtype=np.int64)
    return keep


def postprocess(
    preds: Sequence[np.ndarray],
    labels: List[str],
    ori_wh: Tuple[int, int],
    conf_thresh: float = CONF_THRESH,
) -> List[dict]:
    """简化后处理：阈值过滤 → NMS → 按 order 排序 → 转 poly。忽略 mask / 复杂 merge。"""
    raw_boxes, box_nums = preds[0], preds[1]
    n = int(box_nums[0]) if len(box_nums) else 0
    if n <= 0:
        return []

    boxes = np.asarray(raw_boxes[:n], dtype=np.float32)
    # [cls, score, xmin, ymin, xmax, ymax, (order)]
    keep_score = (boxes[:, 1] > conf_thresh) & (boxes[:, 0] > -1)
    boxes = boxes[keep_score]
    if len(boxes) == 0:
        return []

    keep_idx = nms(boxes)
    boxes = boxes[keep_idx]

    # V3 第 7 列为模型预测的逻辑阅读顺序，先按该列排序
    if boxes.shape[1] >= 7:
        boxes = boxes[np.argsort(boxes[:, 6])]

    w, h = ori_wh
    results = []
    reading_idx = 1
    for box in boxes:
        cls_id = int(box[0])
        score = float(box[1])
        xmin = float(max(0, box[2]))
        ymin = float(max(0, box[3]))
        xmax = float(min(w, box[4]))
        ymax = float(min(h, box[5]))
        if xmax <= xmin or ymax <= ymin:
            continue
        label = labels[cls_id] if 0 <= cls_id < len(labels) else str(cls_id)
        model_order = int(box[6]) if boxes.shape[1] >= 7 else -1
        if label in SKIP_ORDER_LABELS:
            reading_order = None
        else:
            reading_order = reading_idx
            reading_idx += 1
        results.append(
            {
                "category_id": LABEL_TO_CATEGORY.get(label, CATEGORY["Text"]),
                "original_label": label,
                "original_order": model_order,
                "reading_order": reading_order,
                "poly": [xmin, ymin, xmax, ymin, xmax, ymax, xmin, ymax],
                "score": round(score, 3),
            }
        )
    return results


class PPDocLayoutV3CPU:
    """PP-DocLayoutV3 单文件推理（强制 CPU）。"""

    def __init__(self, model_path: Path | str = MODEL_PATH, conf_thresh: float = CONF_THRESH):
        model_path = Path(model_path)
        if not model_path.is_file():
            raise FileNotFoundError(f"模型不存在: {model_path}")

        self.conf_thresh = conf_thresh
        self.session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        meta = self.session.get_modelmeta().custom_metadata_map
        self.labels = meta.get("character", "").splitlines()
        print(f"[PPDocLayoutV3] model={model_path.name}  device=CPU  labels={len(self.labels)}")

    def predict(self, img_rgb: np.ndarray) -> List[dict]:
        h, w = img_rgb.shape[:2]
        blob, scale_factor = preprocess(img_rgb)
        feeds = {
            "image": blob,
            "scale_factor": np.array([scale_factor], dtype=np.float32),
            "im_shape": np.array([[IMG_SIZE[0], IMG_SIZE[1]]], dtype=np.float32),
        }
        preds = self.session.run(None, feeds)
        return postprocess(preds, self.labels, ori_wh=(w, h), conf_thresh=self.conf_thresh)

def _label_color(label: str) -> str:
    """按标签名生成稳定、易区分的颜色。"""
    hue = (hash(label) % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.75, 0.95)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _img_to_data_uri(img_bgr: np.ndarray) -> str:
    ok, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        raise RuntimeError("图像编码失败")
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def html_output(
    img_bgr: np.ndarray,
    layout_res: List[dict],
    save_path: Union[str, Path, None] = None,
    title: str = "PP-DocLayoutV3 布局检测结果",
) -> Path:
    """将检测结果写成可对比的 HTML 页面（原图叠框 + 阅读顺序路径 + 列表联动）。"""
    if save_path is None:
        save_path = ROOT / "model_demo" / "layout_result.html"
    save_path = Path(save_path)

    h, w = img_bgr.shape[:2]
    items = []
    for i, det in enumerate(layout_res):
        poly = det["poly"]
        xmin, ymin, xmax, ymax = poly[0], poly[1], poly[4], poly[5]
        label = det["original_label"]
        items.append(
            {
                "id": i,
                "label": label,
                "label_zh": label_zh(label),
                "category_id": det["category_id"],
                "model_order": det.get("original_order", -1),
                "reading_order": det.get("reading_order"),
                "score": det["score"],
                "xmin": round(xmin, 2),
                "ymin": round(ymin, 2),
                "xmax": round(xmax, 2),
                "ymax": round(ymax, 2),
                "cx": round((xmin + xmax) / 2, 2),
                "cy": round((ymin + ymax) / 2, 2),
                "color": _label_color(label),
            }
        )

    ordered_count = sum(1 for it in items if it["reading_order"] is not None)
    labels = sorted({it["label"] for it in items}, key=lambda x: label_zh(x))
    legend = [
        {"label": lb, "label_zh": label_zh(lb), "color": _label_color(lb)}
        for lb in labels
    ]
    img_uri = _img_to_data_uri(img_bgr)
    data_json = json.dumps(
        {"width": w, "height": h, "items": items, "legend": legend, "ordered_count": ordered_count},
        ensure_ascii=False,
    )

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)}</title>
<style>
  :root {{
    --bg: #f4f5f7;
    --panel: #ffffff;
    --text: #1f2937;
    --muted: #6b7280;
    --line: #e5e7eb;
    --accent: #2563eb;
    --order: #dc2626;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: var(--bg); color: var(--text);
  }}
  header {{
    padding: 14px 20px; background: var(--panel); border-bottom: 1px solid var(--line);
    display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between;
  }}
  header h1 {{ margin: 0; font-size: 18px; font-weight: 650; }}
  header .meta {{ color: var(--muted); font-size: 13px; }}
  .toolbar {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
  .toolbar label {{ font-size: 13px; color: var(--muted); display: flex; gap: 6px; align-items: center; }}
  .toolbar input[type="range"] {{ width: 120px; }}
  main {{
    display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(300px, 0.85fr);
    gap: 14px; padding: 14px; height: calc(100vh - 64px);
  }}
  .panel {{
    background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
    overflow: hidden; display: flex; flex-direction: column; min-height: 0;
  }}
  .panel-title {{
    padding: 10px 14px; border-bottom: 1px solid var(--line); font-size: 13px;
    color: var(--muted); display: flex; justify-content: space-between; gap: 8px;
  }}
  .viewer {{
    flex: 1; overflow: auto; padding: 12px; background:
      linear-gradient(45deg, #eceff3 25%, transparent 25%),
      linear-gradient(-45deg, #eceff3 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, #eceff3 75%),
      linear-gradient(-45deg, transparent 75%, #eceff3 75%);
    background-size: 20px 20px; background-position: 0 0, 0 10px, 10px -10px, -10px 0;
  }}
  .canvas-wrap {{ position: relative; display: inline-block; line-height: 0; box-shadow: 0 8px 24px rgba(0,0,0,.08); }}
  .canvas-wrap img {{ display: block; max-width: 100%; height: auto; }}
  .canvas-wrap svg {{
    position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none;
  }}
  .canvas-wrap .box {{
    fill: transparent; stroke-width: 2; pointer-events: all; cursor: pointer;
    vector-effect: non-scaling-stroke;
  }}
  .canvas-wrap .box.active {{ fill: rgba(37,99,235,.16); stroke-width: 3; }}
  .canvas-wrap .lbl {{
    font-size: 12px; paint-order: stroke; stroke: rgba(0,0,0,.55); stroke-width: 3px;
    fill: #fff; pointer-events: none;
  }}
  .canvas-wrap .order-badge {{ pointer-events: none; }}
  .canvas-wrap .order-badge circle {{ fill: var(--order); stroke: #fff; stroke-width: 2; }}
  .canvas-wrap .order-badge text {{
    fill: #fff; font-size: 13px; font-weight: 700; text-anchor: middle; dominant-baseline: central;
    paint-order: normal; stroke: none;
  }}
  .canvas-wrap .order-path {{
    fill: none; stroke: var(--order); stroke-width: 2.5; stroke-dasharray: 8 6;
    opacity: .85; vector-effect: non-scaling-stroke;
  }}
  .canvas-wrap .order-arrow {{ fill: var(--order); opacity: .9; }}
  .list {{ flex: 1; overflow: auto; }}
  .row {{
    display: grid; grid-template-columns: 36px 1fr auto; gap: 8px; align-items: center;
    padding: 10px 12px; border-bottom: 1px solid var(--line); cursor: pointer;
  }}
  .row:hover, .row.active {{ background: #eff6ff; }}
  .row.unordered {{ opacity: .55; }}
  .ord {{
    width: 28px; height: 28px; border-radius: 50%; background: var(--order); color: #fff;
    display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700;
  }}
  .ord.none {{ background: #9ca3af; font-size: 11px; }}
  .row .name {{ font-size: 13px; font-weight: 600; }}
  .row .sub {{ font-size: 12px; color: var(--muted); margin-top: 2px; }}
  .row .score {{ font-variant-numeric: tabular-nums; font-size: 13px; color: var(--accent); font-weight: 650; }}
  .legend {{
    display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 12px; border-bottom: 1px solid var(--line);
  }}
  .legend span {{
    display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted);
    background: #f9fafb; border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px;
  }}
  .legend i {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
  @media (max-width: 960px) {{
    main {{ grid-template-columns: 1fr; height: auto; }}
    .panel {{ min-height: 360px; }}
  }}
</style>
</head>
<body>
<header>
  <div>
    <h1>{html.escape(title)}</h1>
    <div class="meta">
      共 <b id="count">0</b> 个框 · 逻辑阅读顺序 <b id="orderCount">0</b> 步 · 图像 {w}×{h}
    </div>
  </div>
  <div class="toolbar">
    <label><input type="checkbox" id="toggleBoxes" checked/> 显示框</label>
    <label><input type="checkbox" id="toggleLabels" checked/> 显示标签</label>
    <label><input type="checkbox" id="toggleOrder" checked/> 阅读顺序序号</label>
    <label><input type="checkbox" id="togglePath" checked/> 阅读顺序连线</label>
    <label><input type="checkbox" id="onlyOrdered"/> 仅看有序块</label>
    <label>透明度 <input type="range" id="opacity" min="10" max="100" value="100"/></label>
    <label>筛选
      <select id="filterLabel"><option value="">全部</option></select>
    </label>
  </div>
</header>
<main>
  <section class="panel">
    <div class="panel-title">
      <span>原图 · 检测框 · 逻辑阅读顺序</span>
      <span>红色序号与虚线表示阅读路径 1→2→…</span>
    </div>
    <div class="viewer">
      <div class="canvas-wrap" id="canvasWrap">
        <img id="srcImg" src="{img_uri}" alt="source"/>
        <svg id="overlay" xmlns="http://www.w3.org/2000/svg"></svg>
      </div>
    </div>
  </section>
  <section class="panel">
    <div class="panel-title"><span>按阅读顺序排列</span><span id="visibleCount"></span></div>
    <div class="legend" id="legend"></div>
    <div class="list" id="list"></div>
  </section>
</main>
<script>
const DATA = {data_json};
const overlay = document.getElementById('overlay');
const listEl = document.getElementById('list');
const legendEl = document.getElementById('legend');
const filterEl = document.getElementById('filterLabel');
const toggleLabels = document.getElementById('toggleLabels');
const toggleBoxes = document.getElementById('toggleBoxes');
const toggleOrder = document.getElementById('toggleOrder');
const togglePath = document.getElementById('togglePath');
const onlyOrdered = document.getElementById('onlyOrdered');
const opacityEl = document.getElementById('opacity');
let activeId = null;

document.getElementById('count').textContent = DATA.items.length;
document.getElementById('orderCount').textContent = DATA.ordered_count;
DATA.legend.forEach(x => {{
  const s = document.createElement('span');
  s.innerHTML = `<i style="background:${{x.color}}"></i>${{x.label_zh}}`;
  legendEl.appendChild(s);
  const opt = document.createElement('option');
  opt.value = x.label; opt.textContent = x.label_zh;
  filterEl.appendChild(opt);
}});

function filteredItems() {{
  const f = filterEl.value;
  let items = DATA.items.filter(it => !f || it.label === f);
  if (onlyOrdered.checked) items = items.filter(it => it.reading_order != null);
  // 有序块按阅读顺序，无序块排后
  return items.slice().sort((a, b) => {{
    const ao = a.reading_order == null ? 1e9 : a.reading_order;
    const bo = b.reading_order == null ? 1e9 : b.reading_order;
    if (ao !== bo) return ao - bo;
    return a.id - b.id;
  }});
}}

function svgEl(name, attrs) {{
  const el = document.createElementNS('http://www.w3.org/2000/svg', name);
  Object.entries(attrs || {{}}).forEach(([k, v]) => el.setAttribute(k, v));
  return el;
}}

function drawOrderPath(ordered) {{
  if (ordered.length < 2) return;
  const pts = ordered.map(it => `${{it.cx}},${{it.cy}}`).join(' ');
  overlay.appendChild(svgEl('polyline', {{
    class: 'order-path', points: pts
  }}));
  for (let i = 0; i < ordered.length - 1; i++) {{
    const a = ordered[i], b = ordered[i + 1];
    const dx = b.cx - a.cx, dy = b.cy - a.cy;
    const len = Math.hypot(dx, dy) || 1;
    const ux = dx / len, uy = dy / len;
    // 箭头画在线段 70% 处
    const ax = a.cx + ux * len * 0.7;
    const ay = a.cy + uy * len * 0.7;
    const s = 8;
    const p1x = ax - ux * s - uy * s * 0.55;
    const p1y = ay - uy * s + ux * s * 0.55;
    const p2x = ax - ux * s + uy * s * 0.55;
    const p2y = ay - uy * s - ux * s * 0.55;
    overlay.appendChild(svgEl('polygon', {{
      class: 'order-arrow',
      points: `${{ax}},${{ay}} ${{p1x}},${{p1y}} ${{p2x}},${{p2y}}`
    }}));
  }}
}}

function render() {{
  const items = filteredItems();
  const orderedAll = DATA.items
    .filter(it => it.reading_order != null)
    .slice()
    .sort((a, b) => a.reading_order - b.reading_order);
  document.getElementById('visibleCount').textContent =
    `显示 ${{items.length}} / ${{DATA.items.length}} · 有序 ${{orderedAll.length}}`;
  const showBox = toggleBoxes.checked;
  const showLabel = toggleLabels.checked;
  const showOrder = toggleOrder.checked;
  const showPath = togglePath.checked;
  const op = Number(opacityEl.value) / 100;
  overlay.setAttribute('viewBox', `0 0 ${{DATA.width}} ${{DATA.height}}`);
  overlay.innerHTML = '';

  if (showPath) drawOrderPath(orderedAll);

  if (showBox) {{
    items.forEach(it => {{
      const g = svgEl('g', {{}});
      g.style.opacity = String(op);
      const rect = svgEl('rect', {{
        class: 'box' + (activeId === it.id ? ' active' : ''),
        x: it.xmin, y: it.ymin,
        width: Math.max(1, it.xmax - it.xmin),
        height: Math.max(1, it.ymax - it.ymin),
        stroke: it.color,
      }});
      rect.addEventListener('click', () => selectItem(it.id, true));
      g.appendChild(rect);

      if (showOrder && it.reading_order != null) {{
        const badge = svgEl('g', {{ class: 'order-badge' }});
        const r = 12;
        const bx = it.xmin + r + 2;
        const by = it.ymin + r + 2;
        badge.appendChild(svgEl('circle', {{ cx: bx, cy: by, r }}));
        const t = svgEl('text', {{ x: bx, y: by }});
        t.textContent = String(it.reading_order);
        badge.appendChild(t);
        g.appendChild(badge);
      }}

      if (showLabel) {{
        const t = svgEl('text', {{
          class: 'lbl',
          x: it.xmin + (it.reading_order != null && showOrder ? 30 : 2),
          y: Math.max(14, it.ymin - 4),
        }});
        t.textContent = `${{it.label_zh}} ${{it.score.toFixed(3)}}`;
        g.appendChild(t);
      }}
      overlay.appendChild(g);
    }});
  }} else if (showOrder) {{
    // 仅序号模式
    orderedAll.forEach(it => {{
      const badge = svgEl('g', {{ class: 'order-badge' }});
      badge.style.opacity = String(op);
      const r = 12;
      badge.appendChild(svgEl('circle', {{ cx: it.cx, cy: it.cy, r }}));
      const t = svgEl('text', {{ x: it.cx, y: it.cy }});
      t.textContent = String(it.reading_order);
      badge.appendChild(t);
      overlay.appendChild(badge);
    }});
  }}

  listEl.innerHTML = '';
  items.forEach(it => {{
    const row = document.createElement('div');
    const hasOrder = it.reading_order != null;
    row.className = 'row' + (activeId === it.id ? ' active' : '') + (hasOrder ? '' : ' unordered');
    const ordText = hasOrder ? String(it.reading_order) : '—';
    row.innerHTML = `
      <div class="ord ${{hasOrder ? '' : 'none'}}">${{ordText}}</div>
      <div>
        <div class="name">${{it.label_zh}}</div>
        <div class="sub">${{it.label}} · 模型序=${{it.model_order}} · score=${{it.score.toFixed(3)}}</div>
      </div>
      <div class="score">${{hasOrder ? 'R' + it.reading_order : '无序'}}</div>`;
    row.addEventListener('click', () => selectItem(it.id, true));
    listEl.appendChild(row);
  }});
}}

function selectItem(id, scrollList) {{
  activeId = id;
  render();
  if (scrollList) {{
    const row = listEl.querySelector('.row.active');
    if (row) row.scrollIntoView({{ block: 'nearest', behavior: 'smooth' }});
  }}
}}

[filterEl, toggleLabels, toggleBoxes, toggleOrder, togglePath, onlyOrdered].forEach(el =>
  el.addEventListener('change', render)
);
opacityEl.addEventListener('input', render);
render();
</script>
</body>
</html>
"""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(page, encoding="utf-8")
    print(f"[html] 已生成: {save_path.resolve()}")
    return save_path


def main():
    image = cv2.imread(str(IMG_PATH))
    if image is None:
        raise FileNotFoundError(f"读图失败: {IMG_PATH}")
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    model = PPDocLayoutV3CPU()
    layout_res = model.predict(image_rgb)

    for item in layout_res:
        zh = label_zh(item["original_label"])
        ro = item.get("reading_order")
        ro_s = f"R{ro}" if ro is not None else "—"
        print(
            f"order={ro_s:<4} label={zh:<8} ({item['original_label']:<16}) "
            f"score={item['score']:.3f}"
        )

    html_output(image, layout_res)


if __name__ == "__main__":
    main()

