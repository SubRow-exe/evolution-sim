"""GitHub閲覧用の軽量GIF previewを生成する (V1.2.2)。

科学runが生成したGIFを後処理で縮小・フレーム間引きするだけで、
シミュレーション状態やRNGには一切触れない。

例:
    uv run python tools/make_result_preview.py input.gif output.gif
    uv run python tools/make_result_preview.py input.gif output.gif --max-size 480 --stride 2 --colors 128
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageSequence


def make_preview(
    src: Path,
    dst: Path,
    *,
    max_size: int = 480,
    stride: int = 2,
    colors: int = 128,
) -> tuple[int, int]:
    """src GIFを軽量化してdstへ保存し、(元フレーム数, 出力フレーム数)を返す。"""
    if max_size <= 0:
        raise ValueError("max_size must be > 0")
    if stride <= 0:
        raise ValueError("stride must be > 0")
    if not 2 <= colors <= 256:
        raise ValueError("colors must be between 2 and 256")
    if not src.is_file():
        raise FileNotFoundError(src)

    with Image.open(src) as im:
        base_duration = int(im.info.get("duration", 167))
        # ImageSequence.Iteratorは同じ内部Imageを使い回すため、その場でRGB化+copyする。
        # 後からlist化した参照を処理すると全要素が最終フレーム相当になる場合がある。
        source_frames = [
            frame.convert("RGB").copy() for frame in ImageSequence.Iterator(im)
        ]
        if not source_frames:
            raise ValueError(f"GIF has no frames: {src}")

        out_frames: list[Image.Image] = []
        for i, frame in enumerate(source_frames):
            if i % stride != 0:
                continue
            f = frame.copy()
            f.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            f = f.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors)
            out_frames.append(f.copy())

    if not out_frames:
        raise ValueError("no frames selected")

    dst.parent.mkdir(parents=True, exist_ok=True)
    # 間引いた分だけ1フレームの表示時間を伸ばし、全体の再生時間を概ね維持する。
    duration = max(1, base_duration * stride)
    out_frames[0].save(
        dst,
        save_all=True,
        append_images=out_frames[1:],
        duration=duration,
        loop=0,
        optimize=True,
        disposal=2,
    )
    return len(source_frames), len(out_frames)


def main() -> None:
    ap = argparse.ArgumentParser(description="GitHub閲覧用の軽量GIF previewを生成")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--max-size", type=int, default=480)
    ap.add_argument("--stride", type=int, default=2)
    ap.add_argument("--colors", type=int, default=128)
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    n_src, n_dst = make_preview(
        src,
        dst,
        max_size=args.max_size,
        stride=args.stride,
        colors=args.colors,
    )
    print(f"preview: {src} -> {dst} ({n_src} frames -> {n_dst} frames)")


if __name__ == "__main__":
    main()
