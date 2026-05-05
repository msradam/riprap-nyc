"""Publish TerraMind-NYC adapters to Hugging Face.

Pushes to msradam/TerraMind-NYC-Adapters with a clean structure:
    adapter_name/
        adapter_config.json
        adapter_model.safetensors
        decoder_head.safetensors
        eval/metrics_lora.json
        splits/test.txt
        MODEL_CARD.md
plus a top-level README.md (copied from the family-level docs).

Per ADR-004 the TerraMind base is referenced by ID, NOT redistributed.
Per ADR-005 the eval metrics in metrics_lora.json must have been
computed against the locked test split; we sanity-check this before
pushing.

Usage:
    python3 shared/publish_hf.py --all
    python3 shared/publish_hf.py --adapter buildings_nyc

Env: HF_TOKEN must be set (read+write) for the msradam org. See
https://huggingface.co/settings/tokens.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml
from huggingface_hub import HfApi, create_repo, upload_folder

REPO_ID = "msradam/TerraMind-NYC-Adapters"


def validate(adapter_dir: Path) -> tuple[bool, list[str]]:
    issues = []
    needed = [
        "config.yaml",
        "output/adapter_model.safetensors",
        "output/decoder_head.safetensors",
        "output/adapter_config.json",
        "MODEL_CARD.md",
        "eval/metrics_lora.json",
    ]
    for f in needed:
        if not (adapter_dir / f).exists():
            issues.append(f"missing: {f}")

    metrics_path = adapter_dir / "eval/metrics_lora.json"
    if metrics_path.exists():
        m = json.loads(metrics_path.read_text())
        for required_key in ("test/mIoU", "test/loss"):
            if required_key not in m:
                issues.append(f"metrics missing {required_key}")
        # Accept either an aggregated array or per-class IoU_0..N keys.
        per_class_present = ("test/per_class_IoU" in m
                              or any(k.startswith("test/IoU_") for k in m))
        if not per_class_present:
            issues.append("metrics missing per-class IoU "
                          "(test/per_class_IoU OR test/IoU_<i>)")
    return (len(issues) == 0), issues


def stage(adapter_dir: Path, stage_dir: Path):
    """Copy adapter artefacts into a clean subdir for upload."""
    name = adapter_dir.name
    target = stage_dir / name
    target.mkdir(parents=True, exist_ok=True)

    for src_rel, dst_rel in [
        ("output/adapter_model.safetensors",  "adapter_model.safetensors"),
        ("output/decoder_head.safetensors",   "decoder_head.safetensors"),
        ("output/adapter_config.json",        "adapter_config.json"),
        ("MODEL_CARD.md",                     "README.md"),
    ]:
        src = adapter_dir / src_rel
        if src.exists():
            (target / dst_rel).write_bytes(src.read_bytes())

    eval_dir = target / "eval"
    eval_dir.mkdir(exist_ok=True)
    (eval_dir / "metrics_lora.json").write_bytes(
        (adapter_dir / "eval/metrics_lora.json").read_bytes())
    for k in ("metrics_full_ft.json", "metrics_zero_shot.json"):
        if (adapter_dir / "eval" / k).exists():
            (eval_dir / k).write_bytes(
                (adapter_dir / "eval" / k).read_bytes())

    splits_dir = target / "splits"
    splits_dir.mkdir(exist_ok=True)
    cfg = yaml.safe_load((adapter_dir / "config.yaml").read_text())
    test_split_src = cfg["data"]["init_args"].get("test_split")
    if test_split_src:
        # Path is on the droplet; user must rsync down before publish.
        local = Path(test_split_src)
        if not local.exists():
            local = adapter_dir / "splits" / "test.txt"
        if local.exists():
            (splits_dir / "test.txt").write_bytes(local.read_bytes())


def push(stage_dir: Path, repo_id: str, token: str | None = None):
    api = HfApi()
    create_repo(repo_id, token=token, exist_ok=True, repo_type="model")
    upload_folder(folder_path=str(stage_dir), repo_id=repo_id, token=token,
                  commit_message="Phase 18 LoRA adapter publish")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path,
                    default=Path(__file__).resolve().parent.parent / "adapters")
    ap.add_argument("--adapter", help="single adapter name, otherwise --all required")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--repo-id", default=REPO_ID)
    ap.add_argument("--token", default=os.environ.get("HF_TOKEN"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.all and not args.adapter:
        sys.exit("either --all or --adapter <name>")

    targets = ([args.root / args.adapter] if args.adapter
               else sorted(p for p in args.root.iterdir()
                           if p.is_dir() and (p / "config.yaml").exists()
                           and not p.name.startswith("_")))

    print(f"Publishing {len(targets)} adapter(s) to {args.repo_id}\n")
    issues_total = []
    for d in targets:
        ok, issues = validate(d)
        print(f"  {d.name}: {'OK' if ok else 'INVALID'}")
        if not ok:
            for i in issues:
                print(f"    - {i}")
            issues_total.extend(issues)

    if issues_total:
        sys.exit("\nFix the validation issues above before publishing.")

    if args.dry_run:
        print("\n[dry-run] would stage and push.")
        return

    stage_dir = Path("/tmp/tmnyc_stage")
    if stage_dir.exists():
        import shutil
        shutil.rmtree(stage_dir)
    stage_dir.mkdir()
    for d in targets:
        stage(d, stage_dir)

    push(stage_dir, args.repo_id, token=args.token)
    print(f"\nPushed to https://huggingface.co/{args.repo_id}")


if __name__ == "__main__":
    sys.exit(main())
