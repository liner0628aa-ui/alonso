"""Pretrained person detector. Bottom-centre bbox is only a foot-point proxy."""
from hashlib import sha256
from pathlib import Path
from time import perf_counter

import numpy as np


def ground_point(bbox):
    b = np.asarray(bbox, dtype=float)
    if b.shape != (4,) or not np.isfinite(b).all() or b[2] <= b[0] or b[3] <= b[1]:
        raise ValueError('Invalid finite xyxy bounding box')
    return float((b[0]+b[2])/2), float(b[3])


def person_detections(prediction, *, threshold):
    if isinstance(threshold, bool) or not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('Detection threshold must be in [0,1]')
    arrays = {key: value.detach().cpu().numpy() if hasattr(value, 'detach') else np.asarray(value)
              for key, value in prediction.items() if key in ('boxes', 'labels', 'scores')}
    boxes, labels, scores = (arrays[key] for key in ('boxes', 'labels', 'scores'))
    if boxes.shape != (len(scores), 4) or labels.shape != scores.shape or scores.ndim != 1:
        raise ValueError('Inconsistent detector output shapes')
    if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError('Invalid detector confidence')
    result = []
    for box, label, score in zip(boxes, labels, scores):
        if label == 1 and score >= threshold:
            ground_point(box)
            result.append(dict(bbox=box.astype(float).tolist(), detector_confidence=float(score)))
    return result


class PersonDetector:
    """CPU inference only; no training, custom network, or silent random weights."""
    def __init__(self, *, threshold=.1, cache_dir):
        import torch
        import torchvision
        from torchvision.models.detection import (ssdlite320_mobilenet_v3_large,
                                                  SSDLite320_MobileNet_V3_Large_Weights)
        person_detections(dict(boxes=np.empty((0, 4)), labels=np.array([]), scores=np.array([])),
                          threshold=threshold)
        self.threshold = threshold
        self.torch = torch
        torch.set_num_threads(1)
        torch.manual_seed(0)
        torch.use_deterministic_algorithms(True)
        weights = SSDLite320_MobileNet_V3_Large_Weights.COCO_V1
        path = Path(cache_dir) / Path(weights.url).name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            torch.hub.download_url_to_file(weights.url, str(path), hash_prefix=path.stem.rsplit('-', 1)[-1])
        digest = sha256(path.read_bytes()).hexdigest()
        if not digest.startswith(path.stem.rsplit('-', 1)[-1]):
            raise ValueError('Detector weights checksum mismatch')
        state = torch.load(path, map_location='cpu', weights_only=True)
        self.model = ssdlite320_mobilenet_v3_large(weights=None, weights_backbone=None,
                                                 num_classes=len(weights.meta['categories']))
        self.model.load_state_dict(state)
        self.model.eval()
        self.metadata = dict(name='ssdlite320_mobilenet_v3_large', torchvision_version=torchvision.__version__,
            torch_version=torch.__version__, weights='COCO_V1', weights_url=weights.url,
            weights_sha256=digest, code_license='BSD-3-Clause',
            weights_terms='TorchVision pretrained-model terms; COCO source-image rights separate',
            confidence_threshold=threshold, device='cpu', runtime_s=0., frames_inferred=0)

    def detect(self, frame_bgr):
        if frame_bgr.dtype != np.uint8 or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
            raise ValueError('Decoder must supply uint8 BGR image')
        rgb = frame_bgr[:, :, ::-1].copy()
        tensor = self.torch.from_numpy(rgb).permute(2, 0, 1).float()/255
        started = perf_counter()
        with self.torch.inference_mode():
            prediction = self.model([tensor])[0]
        self.metadata['runtime_s'] += perf_counter()-started
        self.metadata['frames_inferred'] += 1
        return person_detections(prediction, threshold=self.threshold)
