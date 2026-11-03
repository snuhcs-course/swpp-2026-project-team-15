# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""Visual overlap between two frames from ORB matches and a RANSAC homography.

Needs OpenCV and numpy, which the server environment does not include:

    PYTHONPATH=research uv run --with opencv-python-headless --with numpy \
        python -m experiments.capture.overlap_orb --help

On real fridge footage this failed for 62% of frame pairs (featureless shelves, glare, motion),
which is why the app spreads frames in time instead of grouping them by overlap. Treat a
``reliable=False`` result as "unknown", not as "no overlap".
"""

from __future__ import annotations

ORB_SIDE = 512  # long side of the grayscale copy used for matching
MIN_INLIERS = 12


def _cv():
    import cv2  # noqa: PLC0415 - optional dependency, imported on use
    import numpy as np  # noqa: PLC0415

    return cv2, np


def features(gray, side: int = ORB_SIDE):
    """ORB keypoints and descriptors of a grayscale image, shrunk to ``side`` on its long edge."""
    cv2, _ = _cv()
    h, w = gray.shape
    scale = side / max(h, w)
    small = cv2.resize(gray, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    return cv2.ORB_create(nfeatures=500).detectAndCompute(small, None), small.shape


def overlap(fa, fb, shape: tuple[int, int]) -> tuple[float, bool]:
    """Shared area (0..1) of frame b projected into frame a, and whether the estimate holds."""
    cv2, np = _cv()
    (ka, da), (kb, db) = fa, fb
    if da is None or db is None or len(ka) < 8 or len(kb) < 8:
        return 0.0, False
    matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
    if len(matches) < MIN_INLIERS:
        return 0.0, False
    src = np.float32([kb[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst = np.float32([ka[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    hom, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    if hom is None or int(mask.sum()) < MIN_INLIERS:
        return 0.0, False
    h, w = shape
    rect = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    quad = cv2.perspectiveTransform(rect.reshape(-1, 1, 2), hom).reshape(-1, 2).astype(np.float32)
    area, _ = cv2.intersectConvexConvex(rect, quad)
    return max(0.0, min(1.0, float(area) / (w * h))), True


if __name__ == "__main__":
    import argparse

    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
