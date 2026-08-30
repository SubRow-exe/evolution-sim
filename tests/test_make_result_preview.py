from pathlib import Path

from PIL import Image, ImageSequence

from tools.make_result_preview import make_preview


def _make_gif(path: Path, n: int = 6, size: tuple[int, int] = (80, 60)) -> None:
    frames = []
    for i in range(n):
        im = Image.new("RGB", size, (i * 30, 20, 40))
        frames.append(im)
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
    )


def test_make_preview_reduces_frames_and_size(tmp_path: Path) -> None:
    src = tmp_path / "src.gif"
    dst = tmp_path / "preview.gif"
    _make_gif(src)

    n_src, n_dst = make_preview(src, dst, max_size=40, stride=2, colors=32)

    assert (n_src, n_dst) == (6, 3)
    assert dst.is_file()
    with Image.open(dst) as im:
        frames = list(ImageSequence.Iterator(im))
        assert len(frames) == 3
        assert max(im.size) <= 40
        assert int(im.info["duration"]) == 200


def test_make_preview_validates_arguments(tmp_path: Path) -> None:
    src = tmp_path / "src.gif"
    dst = tmp_path / "preview.gif"
    _make_gif(src)

    for kwargs in (
        {"max_size": 0},
        {"stride": 0},
        {"colors": 1},
        {"colors": 257},
    ):
        try:
            make_preview(src, dst, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"ValueError expected for {kwargs}")
