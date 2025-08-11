#!/usr/bin/env python3
# wav_loop_inspect_jp.py
import sys, struct, pathlib, math

def read_chunks(f):
    hdr = f.read(12)
    if len(hdr) < 12 or hdr[:4] not in (b'RIFF', b'RIFX') or hdr[8:12] != b'WAVE':
        raise ValueError("Not a RIFF/WAVE file")
    be = (hdr[:4] == b'RIFX')
    endian = '>' if be else '<'
    while True:
        head = f.read(8)
        if len(head) < 8:
            break
        cid, size = head[:4], struct.unpack(endian+'I', head[4:])[0]
        data = f.read(size)
        if size % 2 == 1:  # pad to WORD boundary
            f.read(1)
        yield cid, data, endian

def parse_fmt(data, endian):
    # WAVEFORMATEX minimum 16 bytes
    if len(data) < 16:
        return None
    (wFormatTag, nChannels, nSamplesPerSec, nAvgBytesPerSec,
     nBlockAlign, wBitsPerSample) = struct.unpack(endian+'HHIIHH', data[:16])
    return dict(format=wFormatTag, channels=nChannels, samplerate=nSamplesPerSec,
                blockalign=nBlockAlign, bits=wBitsPerSample)

def parse_smpl(data, endian):
    if len(data) < 36:
        return None
    # 9 * uint32 header
    vals = struct.unpack(endian+'9I', data[:36])
    num_loops = vals[7]
    offs = 36
    loops = []
    for _ in range(num_loops):
        if offs + 24 > len(data): break
        lid, ltype, start, end, frac, count = struct.unpack(endian+'6I', data[offs:offs+24])
        loops.append(dict(id=lid, type=ltype, start=start, end=end, fraction=frac, count=count))
        offs += 24
    return dict(num_loops=num_loops, loops=loops)

def main(path):
    p = pathlib.Path(path)
    fmt = None
    data_bytes = None
    smpl = None

    with p.open('rb') as f:
        for cid, chunk, endian in read_chunks(f):
            if cid == b'fmt ':
                fmt = parse_fmt(chunk, endian)
            elif cid == b'data':
                data_bytes = len(chunk)
            elif cid == b'smpl':
                smpl = parse_smpl(chunk, endian)

    if not fmt or data_bytes is None:
        raise RuntimeError("fmt もしくは data チャンクが見つかりませんでした")

    channels = fmt['channels']
    rate = fmt['samplerate']
    bits = fmt['bits'] or 8  # 8以上想定
    block = fmt['blockalign'] or max(1, channels * ((bits + 7)//8))
    total_samples = data_bytes // block
    total_ms = int(round((total_samples * 1000.0) / rate))

    # ループ（smplの先頭を表示）
    loop_start = None
    loop_end = None
    if smpl and smpl['loops']:
        lp = smpl['loops'][0]
        loop_start = lp['start']
        loop_end   = lp['end']   # 多くのツールで end は「含む」終端

    # 出力
    def fmt_int(n, width=7):  # 桁そろえ用
        return f"{n:>{width},}".replace(",", "")

    print(f"チャンネル数       : {channels} ch")
    print(f"サンプリングレート : {rate} Hz")
    print(f"サンプルビット数   : {bits} bit\n")
    print(f"総サンプル数   : {fmt_int(total_samples)} sample")
    print(f"総再生時間     : {fmt_int(total_ms)} ms\n")
    if loop_start is not None and loop_end is not None:
        print(f"ループ開始サンプル数 : {fmt_int(loop_start)} sample")
        print(f"ループ終了サンプル数 : {fmt_int(loop_end)} sample")
    else:
        print("ループ開始サンプル数 : なし")
        print("ループ終了サンプル数 : なし")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: python3 wav_loop_inspect_jp.py <path-to-wav>")
        sys.exit(1)
    main(sys.argv[1])
