#!/usr/bin/env python3
# _main.py
# 使い方: exeにWAVをドラッグ&ドロップ → 同じ場所に "<元ファイル名>.wav.txt" を出力
import sys, struct, subprocess, shutil
from pathlib import Path

# ログ
import traceback, datetime
from pathlib import Path
LOG_DIR = Path.home()/ "Library/Logs/WavLoopInspector"
LOG_DIR.mkdir(parents=True, exist_ok=True)
def log(msg):
    print(msg)
    with (LOG_DIR/"run.log").open("a", encoding="utf-8") as fp:
        fp.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")

def find_wavs(paths):
    wavs = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for fp in p.rglob("*.wav"):
                wavs.append(fp)
        elif p.suffix.lower() in [".wav", ".wave"] and p.is_file():
            wavs.append(p)
    # 重複除去・ソート
    seen = set(); out=[]
    for w in sorted(wavs):
        if w.resolve() not in seen:
            seen.add(w.resolve()); out.append(w)
    return out

def read_wav_info(path: Path):
    # 必要最小限のRIFF/WAVE + fmt + data + smpl 解析
    with path.open("rb") as f:
        data = f.read()

    def u32le(off): return struct.unpack_from("<I", data, off)[0]
    def u16le(off): return struct.unpack_from("<H", data, off)[0]

    if data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("Not a RIFF/WAVE")

    # チャンク走査
    off = 12
    fmt = {}
    wav = {
        "channels": None, "samplerate": None, "bits": None,
        "total_samples": None, "duration_ms": None,
        "loop_start": None, "loop_end": None
    }
    data_bytes = None

    while off + 8 <= len(data):
        cid = data[off:off+4]; csz = u32le(off+4); cdata_off = off+8
        if cid == b"fmt ":
            fmt["audiofmt"]  = u16le(cdata_off + 0)
            wav["channels"]  = u16le(cdata_off + 2)
            wav["samplerate"]= u32le(cdata_off + 4)
            wav["bits"]      = u16le(cdata_off + 14) if csz >= 16 else None
        elif cid == b"data":
            data_bytes = csz
        elif cid == b"smpl":
            # smpl ヘッダ 36bytes 以降に SampleLoop 構造体が並ぶ
            if csz >= 36+24:
                num_loops = u32le(cdata_off + 28)
                loop_off  = cdata_off + 36
                if num_loops >= 1 and loop_off + 24 <= cdata_off + csz:
                    # 1つ目だけ読む（必要なら複数対応に拡張可）
                    # struct SampleLoop { cuePointID, type, start, end, fraction, playCount }
                    start = u32le(loop_off + 8)
                    end   = u32le(loop_off + 12)
                    wav["loop_start"] = int(start)
                    wav["loop_end"]   = int(end)
        # 偶数境界アライメント
        off = cdata_off + ((csz + 1) & ~1)

    if not all([wav["channels"], wav["samplerate"], wav["bits"], data_bytes is not None]):
        raise ValueError("fmt/data not found or incomplete")

    bytes_per_sample = (wav["bits"] // 8) * wav["channels"]
    total_samples = data_bytes // bytes_per_sample
    wav["total_samples"] = int(total_samples)
    wav["duration_ms"]   = int(total_samples * 1000 / wav["samplerate"])
    return wav

def write_txt(path: Path, info: dict):
    # 3桁区切りなしでそのまま出力
    out = []
    out.append(f"チャンネル数       : {info['channels']} ch")
    out.append(f"サンプリングレート : {info['samplerate']} Hz")
    out.append(f"サンプルビット数   : {info['bits']} bit")
    out.append("")
    out.append(f"総サンプル数   : {info['total_samples']} sample")
    out.append(f"総再生時間     : {info['duration_ms']} ms")
    out.append("")
    if info.get("loop_start") is not None and info.get("loop_end") is not None:
        out.append(f"ループ開始サンプル数 : {info['loop_start']} sample")
        out.append(f"ループ終了サンプル数 : {info['loop_end']} sample")
    else:
        out.append("ループ情報       : なし")
    txt = "\n".join(out) + "\n"

    outpath = path.with_suffix(path.suffix + ".txt")  # foo.wav.txt
    outpath.write_text(txt, encoding="utf-8")
    return outpath

import os, shutil

COMMON_FFMPEG_PATHS = [
    "/opt/homebrew/bin/ffmpeg",   # Apple Silicon Homebrew
    "/usr/local/bin/ffmpeg",      # Intel Homebrew
    "/opt/local/bin/ffmpeg",      # MacPorts
]

def find_ffmpeg() -> str | None:
    # Finder起動の.appはPATHが短いので、自前で拡張
    extra = ["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"]
    cur = os.environ.get("PATH", "")
    parts = cur.split(":") if cur else []
    for p in extra:
        if p not in parts:
            parts.append(p)
    os.environ["PATH"] = ":".join(parts)

    # まず which
    ff = shutil.which("ffmpeg")
    if ff:
        log(f"ffmpeg found via PATH: {ff}")
        return ff

    # 次に絶対パスの候補を総当たり
    for p in COMMON_FFMPEG_PATHS:
        if os.path.exists(p) and os.access(p, os.X_OK):
            log(f"ffmpeg found via fallback: {p}")
            return p
    log("ffmpeg not found in PATH or common locations")
    return None

def convert_to_ogg(wav_path: Path, info: dict, quality: float = 5.0, outdir: Path | None = None):
    ff = find_ffmpeg()
    if not ff:
        log("[warn] ffmpeg not found; skip ogg")
        return None
    outdir = outdir or wav_path.parent
    out = outdir / (wav_path.stem + ".ogg")

    meta = []
    if info.get("loop_start") is not None and info.get("loop_end") is not None:
        ls = int(info["loop_start"])
        le = int(info["loop_end"])
        ll = max(0, le - ls)  # 慣習的に length = end - start（サンプル数）
        # Vorbisコメントに書く（大小区別なし）：互換のため両系統を入れる
        meta += ["-metadata", f"LOOPSTART={ls}"]
        meta += ["-metadata", f"LOOPLENGTH={ll}"]
        meta += ["-metadata", f"LOOPEND={le}"]

    cmd = [
        ff, "-y", "-i", str(wav_path),
        "-acodec", "libvorbis", "-q:a", str(quality),
        *meta,
        str(out)
    ]
    subprocess.run(cmd, check=True)
    return out

def main():
    # 使い方：_main [--to-ogg] [--q 4.0] [--out outdir] <files_or_dirs...>
    log(f"argv={sys.argv!r}")

    args = sys.argv[1:]
    to_ogg = True
    q = 5.0
    outdir = None

    i = 0
    targets = []
    while i < len(args):
        a = args[i]
        if a == "--to-ogg":
            to_ogg = True; i += 1
        elif a in ("-q","--q","--quality"):
            q = float(args[i+1]); i += 2
        elif a in ("-o","--out"):
            outdir = Path(args[i+1]); outdir.mkdir(parents=True, exist_ok=True); i += 2
        else:
            targets.append(a); i += 1

    if not targets:
        print("使い方: ドラッグ&ドロップ、または `_main.py --to-ogg -q 5 <file_or_dir ...>`")
        sys.exit(0)

    wavs = find_wavs(targets)
    if not wavs:
        log("*.wav が見つからんかったよ")
        sys.exit(1)

    for w in wavs:
        try:
            info = read_wav_info(w)
            txt = write_txt(w, info)
            log(f"[ok] {w.name} -> {txt.name}")
            log(f"txt OK: {txt}")
            if to_ogg:
                ogg = convert_to_ogg(w, info, quality=q, outdir=outdir)
                if ogg:
                    log(f"[ok] 変換: {ogg.name}")
        except Exception as e:
            log(f"[err] {w}: {e}")

if __name__ == "__main__":
    main()
