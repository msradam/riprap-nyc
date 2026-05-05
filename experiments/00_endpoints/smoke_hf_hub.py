"""Hugging Face Hub: confirm a small Apache-2.0 model can be pulled.

We use sentence-transformers/all-MiniLM-L6-v2 (~80MB, Apache-2.0) as
the canary; it's tiny and unrelated to anything we'd ship, so it's a
clean network/HF-auth probe that doesn't pre-warm anything we care
about."""

import os
import sys
from pathlib import Path

from _runner import cache_path, cli, write_cache  # noqa: E402


def probe():
    cache_dir = Path(cache_path("hf_models").stem)  # just a folder name
    cache_dir = cache_path("hf_models", "_dir").with_suffix("")
    cache_dir.mkdir(exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache_dir))
    from huggingface_hub import snapshot_download
    p = snapshot_download(
        repo_id="sentence-transformers/all-MiniLM-L6-v2",
        cache_dir=str(cache_dir),
        allow_patterns=["config.json", "tokenizer_config.json"],
    )
    files = sorted([f.name for f in Path(p).iterdir()])
    write_cache("hf_hub", {"snapshot_path": p, "files": files})
    return True, f"snapshot OK ({len(files)} files): {files}", p


if __name__ == "__main__":
    sys.exit(cli("hf_hub", probe))
