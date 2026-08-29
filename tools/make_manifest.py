"""実験生データのマニフェスト生成 (オンライン実行方針 §5-6)。

生データは巨大なため GitHub には置かず、Drive等の外部ストレージへ保存する。
GitHub 側には**何をどこへ保存したか**と**改竄・欠損を検出できるチェックサム**
だけを残し、「GitHubを見れば内容が分かり、必要なら生データを取得できる」
状態を作る。

    uv run python tools/make_manifest.py runs/exp04_baseline \
        --out experiments/exp04_actions/baseline \
        --archive exp04_baseline.tar.gz \
        --remote "gdrive:evolution-sim/exp04_actions/exp04_baseline.tar.gz"

出力:
    manifest.json  機械可読 (run一覧・各ファイルのSHA256・サイズ・保存先)
    MANIFEST.md    人が読む要約
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def run_summary(run_dir: Path) -> dict:
    """1 runの要点。生データが無くても後から素性が分かるようにする。"""
    out: dict = {"run": run_dir.name}
    meta = run_dir / "meta.json"
    if meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        out["seed"] = m.get("seed")
        out["git_sha"] = m.get("git_sha")
        env = m.get("numeric_environment") or {}
        out["env_key"] = env.get("env_key")
    cfg = run_dir / "config.json"
    if cfg.exists():
        c = json.loads(cfg.read_text(encoding="utf-8"))
        out["fixed_genes"] = c.get("fixed_genes")
    stats = run_dir / "stats.csv"
    if stats.exists():
        with open(stats, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if rows:
            last = rows[-1]
            out["final_tick"] = int(float(last["tick"]))
            out["final_population"] = int(float(last["population"]))
            out["n_lineages"] = int(float(last["n_lineages"]))
            out["top_lineage_frac"] = round(float(last["top_lineage_frac"]), 4)
    return out


def build(src: Path, archive: Path | None, remote: str | None) -> dict:
    runs = sorted(d for d in src.iterdir() if d.is_dir() and (d / "stats.csv").exists())
    files = []
    total = 0
    for p in sorted(src.rglob("*")):
        if p.is_file():
            size = p.stat().st_size
            total += size
            files.append({
                "path": str(p.relative_to(src)).replace("\\", "/"),
                "bytes": size,
                "sha256": sha256_of(p),
            })

    manifest = {
        "schema": 1,
        "experiment": src.name,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_runs": len(runs),
        "total_bytes": total,
        "storage": {
            "archive_name": archive.name if archive else None,
            "archive_sha256": sha256_of(archive) if archive and archive.exists() else None,
            "archive_bytes": archive.stat().st_size if archive and archive.exists() else None,
            "remote": remote,
            "note": "生データは上記remoteに保存。GitHubには要約とチェックサムのみ",
        },
        "runs": [run_summary(d) for d in runs],
        "files": files,
    }
    return manifest


def write_markdown(m: dict, path: Path) -> None:
    envs = sorted({r.get("env_key") for r in m["runs"] if r.get("env_key")})
    shas = sorted({r.get("git_sha") for r in m["runs"] if r.get("git_sha")})
    mb = m["total_bytes"] / 1024 ** 2
    lines = [
        f"# {m['experiment']} 生データ マニフェスト",
        "",
        f"- 作成: {m['created_utc']}",
        f"- run数: {m['n_runs']}",
        f"- 生データ容量: {mb:,.1f} MB ({len(m['files']):,} ファイル)",
        f"- 数値実行環境: {', '.join(envs) if envs else '不明'}",
        f"- コード: {', '.join(s[:12] for s in shas) if shas else '不明'}",
        "",
        "## 生データの所在",
        "",
    ]
    st = m["storage"]
    if st.get("remote"):
        lines += [
            f"- 保存先: `{st['remote']}`",
            f"- アーカイブ: `{st['archive_name']}`"
            + (f" ({st['archive_bytes'] / 1024 ** 2:,.1f} MB)" if st.get("archive_bytes") else ""),
            f"- SHA256: `{st['archive_sha256']}`",
            "",
            "取得後は上記SHA256で完全性を確認すること。",
        ]
    else:
        lines += ["- 外部ストレージへの保存は未実施 (Actions成果物のみ)"]
    lines += [
        "",
        "## run一覧",
        "",
        "| run | seed | 固定遺伝子 | 最終tick | 個体数 | 系統数 | 最大シェア |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in m["runs"]:
        fg = ", ".join(r.get("fixed_genes") or []) or "—"
        lines.append(
            f"| {r['run']} | {r.get('seed', '?')} | {fg} | "
            f"{r.get('final_tick', '?'):,} | {r.get('final_population', '?'):,} | "
            f"{r.get('n_lineages', '?')} | {r.get('top_lineage_frac', '?')} |"
        )
    lines += ["", "各ファイルのSHA256は `manifest.json` を参照。"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="実験生データのマニフェスト生成")
    ap.add_argument("src", help="実験ディレクトリ (runs/exp04_xxx)")
    ap.add_argument("--out", required=True, help="マニフェストの出力先ディレクトリ")
    ap.add_argument("--archive", default=None, help="作成済みアーカイブのパス")
    ap.add_argument("--remote", default=None, help="保存先の識別子 (例: gdrive:path/to.tar.gz)")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.is_dir():
        raise SystemExit(f"{src} がありません")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    m = build(src, Path(args.archive) if args.archive else None, args.remote)
    (out / "manifest.json").write_text(
        json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(m, out / "MANIFEST.md")

    print(f"{m['experiment']}: {m['n_runs']} run / "
          f"{m['total_bytes'] / 1024 ** 2:,.1f} MB / {len(m['files']):,} ファイル")
    print(f"-> {out / 'manifest.json'}")
    print(f"-> {out / 'MANIFEST.md'}")


if __name__ == "__main__":
    main()
