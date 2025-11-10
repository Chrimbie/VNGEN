from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path


def collect_assets(doc: dict) -> set[str]:
    assets: set[str] = set()
    for track, items in (doc.get("tracks") or {}).items():
        for entry in items or []:
            data = entry.get("data", {})
            for key in ("value", "background"):
                val = data.get(key)
                if isinstance(val, str) and val:
                    assets.add(val)
            if track == "MENU":
                bg = data.get("background")
                if isinstance(bg, str) and bg:
                    assets.add(bg)
    return assets


def copy_assets(asset_root: Path, assets: set[str], dest: Path):
    for rel in assets:
        src = (asset_root / rel).resolve()
        if not src.exists():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


def build_project(project_file: Path, platform: str, output: Path):
    project_file = project_file.resolve()
    with open(project_file, "r", encoding="utf-8") as fh:
        doc = json.load(fh)

    build_dir = output / platform
    assets_dir = build_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    copy_assets(project_file.parent, collect_assets(doc), assets_dir)

    shutil.copy2(project_file, build_dir / project_file.name)
    (build_dir / "README.txt").write_text(
        f"Build for {platform}\\nProject: {project_file.name}\\nAssets copied: {len(list(assets_dir.rglob('*')))} files\\n",
        encoding="utf-8",
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Compile VNGEN project into runnable package.")
    parser.add_argument("project", type=Path, help="Path to project JSON file")
    parser.add_argument("--platform", choices=["windows", "mac", "linux"], default="windows")
    parser.add_argument("--output", type=Path, default=Path("build"), help="Output directory root")
    return parser.parse_args()


def main():
    args = parse_args()
    build_project(args.project, args.platform, args.output)
    print(f"Build complete: {(args.output / args.platform).resolve()}")


if __name__ == "__main__":
    main()
