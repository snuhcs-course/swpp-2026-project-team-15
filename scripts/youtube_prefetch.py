# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Fill the server's YouTube video cache (thin wrapper; the code is app/dishes/prefetch.py).

python scripts/youtube_prefetch.py --cache data/dish-videos.json
python scripts/youtube_prefetch.py --cache data/dish-videos.json --live --max-requests 40
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from app.dishes.prefetch import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
