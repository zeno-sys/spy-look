"""PP-DocLayoutV3（CPU / ONNX）版面检测服务。

检测标题 / 正文 / 表格 / 图片 / 公式等区域，输出 poly + category + 阅读顺序。
"""
from __future__ import annotations

import base64
import colorsys
import hashlib
import threading
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple, Union

import cv2
import numpy as np
import onnxruntime as ort

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SERVICE_DIR = Path(__file__).resolve().parent
_TOOL_DIR = Path(__file__).resolve().parents[1]
MODELS_SEARCH_DIRS = (
    _REPO_ROOT / "models",
    _SERVICE_DIR / "models",
    _TOOL_DIR / "models",
)

MODEL_NAME = "pp_doclayoutv3.onnx"
CONF_THRESH = 0.3
IMG_SIZE = (800, 800)  # (h, w)

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


def resolve_model(filename: str = MODEL_NAME) -> Path:
    for base in MODELS_SEARCH_DIRS:
        path = base / filename
        if path.is_file():
            return path
    searched = "\n".join(f"  - {d}" for d in MODELS_SEARCH_DIRS)
    raise FileNotFoundError(f"模型不存在: {filename}\n请放到以下任一目录:\n{searched}")


def expected_models_dir() -> Path:
    return MODELS_SEARCH_DIRS[0]


def label_zh(label: str) -> str:
    return LABEL_ZH.get(label, label)


def preprocess(img_rgb: np.ndarray) -> Tuple[np.ndarray, List[float]]:
    h, w = img_rgb.shape[:2]
    target_h, target_w = IMG_SIZE
    resized = cv2.resize(img_rgb, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
    blob = resized.astype(np.float32) / 255.0
    blob = blob.transpose(2, 0, 1)[None, ...]
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
    raw_boxes, box_nums = preds[0], preds[1]
    n = int(box_nums[0]) if len(box_nums) else 0
    if n <= 0:
        return []

    boxes = np.asarray(raw_boxes[:n], dtype=np.float32)
    keep_score = (boxes[:, 1] > conf_thresh) & (boxes[:, 0] > -1)
    boxes = boxes[keep_score]
    if len(boxes) == 0:
        return []

    keep_idx = nms(boxes)
    boxes = boxes[keep_idx]

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
    def __init__(
        self,
        model_path: Union[str, Path, None] = None,
        conf_thresh: float = CONF_THRESH,
    ):
        model_path = Path(model_path) if model_path else resolve_model()
        if not model_path.is_file():
            raise FileNotFoundError(f"模型不存在: {model_path}")

        self.conf_thresh = conf_thresh
        self.session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        meta = self.session.get_modelmeta().custom_metadata_map
        self.labels = meta.get("character", "").splitlines()

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


_model: PPDocLayoutV3CPU | None = None
_model_lock = threading.Lock()


def get_layout_model() -> PPDocLayoutV3CPU:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = PPDocLayoutV3CPU()
    return _model


def label_color(label: str) -> str:
    digest = hashlib.md5(label.encode("utf-8")).hexdigest()
    hue = (int(digest[:8], 16) % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.75, 0.95)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def img_to_data_uri(img_bgr: np.ndarray, quality: int = 92) -> str:
    ok, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("图像编码失败")
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def decode_image_bytes(data: bytes) -> np.ndarray:
    if not data:
        raise ValueError("上传文件为空")
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("无法解码图片，请确认文件为有效图像")
    return img


def build_layout_payload(
    img_bgr: np.ndarray,
    layout_res: List[dict],
) -> dict[str, Any]:
    h, w = img_bgr.shape[:2]
    items: list[dict[str, Any]] = []
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
                "score": float(det["score"]),
                "xmin": round(xmin, 2),
                "ymin": round(ymin, 2),
                "xmax": round(xmax, 2),
                "ymax": round(ymax, 2),
                "cx": round((xmin + xmax) / 2, 2),
                "cy": round((ymin + ymax) / 2, 2),
                "color": label_color(label),
            }
        )

    ordered_count = sum(1 for it in items if it["reading_order"] is not None)
    labels = sorted({it["label"] for it in items}, key=lambda x: label_zh(x))
    legend = [
        {"label": lb, "label_zh": label_zh(lb), "color": label_color(lb)}
        for lb in labels
    ]
    return {
        "width": w,
        "height": h,
        "image_data_uri": img_to_data_uri(img_bgr),
        "items": items,
        "legend": legend,
        "ordered_count": ordered_count,
        "count": len(items),
    }


def run_layout_on_bytes(data: bytes) -> dict[str, Any]:
    img_bgr = decode_image_bytes(data)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    model = get_layout_model()
    results = model.predict(img_rgb)
    return build_layout_payload(img_bgr, results)
