#!/usr/bin/env python3
# _main.py  (WindowsでPyInstaller --onefile予定)
# 使い方: exeにWAVをドラッグ&ドロップ → 同じ場所に "<元ファイル名>.wav.txt" を出力
import sys, struct, pathlib, math, traceback

# ---- RIFF/WAVEの基本（偶数境界パディングあり） ----
def _iter_chunks(f):
    hdr = f.read(12)
    if len(hdr) < 12 or hdr[0:4] not in (b'RIFF', b'RIFX') or hdr[8:12] != b'WAVE':
        raise ValueError("WAVE(RIFF)ではありません")
    be = (hdr[0:4] == b'RIFX')
    endian = '>' if be else '<'
    while True:
        head = f.read(8)
        if len(head) < 8:
            break
        cid = head[0:4]
        size = struct.unpack(endian + 'I', head[4:8])[0]
        data = f.read(size)
        if size & 1:  # 偶数境界にパディング
            f.read(1)
        yield cid, data, endian

def _parse_fmt(data, endian):
    if len(data) < 16:
        return None
    wFormatTag, nChannels, nSamplesPerSec, nAvgBytesPerSec, nBlockAlign, wBitsPerSample = \
        struct.unpack(endian + 'HHIIHH', data[:16])
    return {
        'format': wFormatTag, 'channels': nChannels, 'samplerate': nSamplesPerSec,
        'blockalign': nBlockAlign, 'bits': wBitsPerSample
    }

def _parse_smpl(data, endian):
    if len(data) < 36:  # 9 * uint32
        return None
    (manufacturer, product, sample_period_ns, midi_unity, midi_frac,
     smpte_format, smpte_offset, num_loops, sampler_data_size) = struct.unpack(endian+'9I', data[:36])
    loops = []
    off = 36
    for _ in range(num_loops):
        if off + 24 > len(data): break
        lid, ltype, start, end, frac, count = struct.unpack(endian+'6I', data[off:off+24])
        loops.append({'id': lid, 'type': ltype, 'start': start, 'end': end, 'fraction': frac, 'count': count})
        off += 24
    return {
        'num_loops': num_loops,
        'loops': loops,
        'midi_unity_note': midi_unity,
        'midi_pitch_fraction': midi_frac,
        'sample_period_ns': sample_period_ns
    }

def _parse_cue(data, endian):
    if len(data) < 4:
        return None
    num = struct.unpack(endian+'I', data[:4])[0]
    points = []
    off = 4
    for _ in range(num):
        if off + 24 > len(data): break
        id_, position, dataChunkID, chunkStart, blockStart, sampleOffset = struct.unpack(endian+'II4sIII', data[off:off+24])
        points.append({
            'id': id_, 'position': position,
            'data_chunk_id': dataChunkID.decode('ascii', errors='replace'),
            'sample_offset': sampleOffset
        })
        off += 24
    return {'num_points': num, 'points': points}

def _analyze(path: pathlib.Path) -> str:
    fmt = None
    data_bytes = None
    smpl = None
    cue  = None
    other = []

    with path.open('rb') as f:
        for cid, chunk, endian in _iter_chunks(f):
            if cid == b'fmt ':
                fmt = _parse_fmt(chunk, endian)
            elif cid == b'data':
                data_bytes = len(chunk)
            elif cid == b'smpl':
                smpl = _parse_smpl(chunk, endian)
            elif cid == b'cue ':
                cue = _parse_cue(chunk, endian)
            else:
                try:
                    other.append(cid.decode('ascii', errors='replace'))
                except Exception:
                    other.append(str(cid))

    if not fmt or data_bytes is None:
        raise RuntimeError("fmt または data チャンクが見つかりません")

    channels = fmt['channels']
    rate = fmt['samplerate']
    bits = fmt['bits'] or 8
    block = fmt['blockalign'] or max(1, channels * ((bits + 7)//8))
    total_samples = data_bytes // block
    total_ms = int(round(total_samples * 1000.0 / rate))

    # ループ表示（smplの先頭ループを優先）
    loop_start = None
    loop_end = None
    if smpl and smpl.get('loops'):
        lp = smpl['loops'][0]
        loop_start = lp['start']
        loop_end   = lp['end']
    elif cue and cue.get('points') and len(cue['points']) >= 2:
        # フォールバック：cueの最初の2点を開始/終了に解釈（互換目的のヒューリスティック）
        pts = sorted(cue['points'], key=lambda x: x['sample_offset'])
        loop_start = pts[0]['sample_offset']
        loop_end   = pts[1]['sample_offset']

    def fmt_int(n, width=7):
        return f"{n:>{width},}".replace(",", " ")

    lines = []
    lines.append(f"チャンネル数       : {channels} ch")
    lines.append(f"サンプリングレート : {rate} Hz")
    lines.append(f"サンプルビット数   : {bits} bit")
    lines.append("")
    lines.append(f"総サンプル数   : {fmt_int(total_samples)} sample")
    lines.append(f"総再生時間     : {fmt_int(total_ms)} ms")
    lines.append("")
    if loop_start is not None and loop_end is not None:
        lines.append(f"ループ開始サンプル数 : {fmt_int(loop_start)} sample")
        lines.append(f"ループ終了サンプル数 : {fmt_int(loop_end)} sample")
    else:
        lines.append("ループ開始サンプル数 : なし")
        lines.append("ループ終了サンプル数 : なし")

    return "\n".join(lines) + "\n"

def main(argv):
    # D&Dやコマンド引数で複数ファイル対応
    paths = [p for p in argv[1:] if not p.startswith('-')]
    if not paths:
        print("WAVファイルをこの実行ファイルにドラッグ＆ドロップしてください。")
        return 0

    exit_code = 0
    for p in paths:
        try:
            src = pathlib.Path(p)
            if not src.exists():
                print(f"[SKIP] 見つからない: {src}")
                continue
            if src.suffix.lower() not in ('.wav', '.wave'):
                print(f"[SKIP] WAVではない: {src.name}")
                continue

            report = _analyze(src)
            out_path = src.with_name(src.name + ".txt")  # 例: hoge.wav.txt
            # Windowsメモ帳対策でUTF-8 BOM
            out_path.write_text(report, encoding='utf-8-sig')
            print(f"[OK] {src.name} -> {out_path.name}")
        except Exception as e:
            print(f"[ERR] {p}: {e}")
            # デバッグ用スタック（配布時はコメントアウト可）
            traceback.print_exc()
            exit_code = 1
    return exit_code

if __name__ == "__main__":
    sys.exit(main(sys.argv))
