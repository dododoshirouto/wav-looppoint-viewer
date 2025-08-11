# _create_icns.py
# 1枚の入力画像から macOS 用 .icns を生成（優先: ImageMagick、失敗時: iconutil）
# 使い方: python _create_icns.py icons/icon.png icon.icns
from PIL import Image
import os, sys, tempfile, subprocess, shutil, platform

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p

def have(cmd):
    try:
        subprocess.run([cmd, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return True
    except FileNotFoundError:
        return False

def make_resized_pngs(src_path, out_dir):
    # Appleの推奨セット：1x/2x（=Retina）サイズ
    base_sizes = [16, 32, 128, 256, 512]
    retina_sizes = [s * 2 for s in base_sizes]  # 32, 64, 256, 512, 1024
    sizes = sorted(set(base_sizes + retina_sizes))
    img = Image.open(src_path).convert("RGBA")
    paths = []
    for s in sizes:
        out_path = os.path.join(out_dir, f"{s}x{s}.png")
        img.resize((s, s), resample=Image.LANCZOS).save(out_path)
        paths.append(out_path)
    return paths

def build_icns_with_imagemagick(png_paths, out_icns):
    # ImageMagick の 'magick' コマンドで PNG 群→ICNS
    # 例: magick 16.png 32.png 64.png ... icon.icns
    # （ICNSはICOと同様に複数解像度を内包する形式） :contentReference[oaicite:1]{index=1}
    cmd = ["magick"] + png_paths + [out_icns]
    subprocess.run(cmd, check=True)

def build_icns_with_iconutil(png_dir, out_icns):
    # macOSの標準ツール iconutil で .iconset → .icns 生成 :contentReference[oaicite:2]{index=2}
    iconset = os.path.join(png_dir, "icon.iconset")
    ensure_dir(iconset)

    # iconutil が期待するファイル名でコピー
    name_map = {
        16:  ["icon_16x16.png", "icon_16x16@2x.png"],
        32:  ["icon_32x32.png", "icon_32x32@2x.png"],
        128: ["icon_128x128.png", "icon_128x128@2x.png"],
        256: ["icon_256x256.png", "icon_256x256@2x.png"],
        512: ["icon_512x512.png", "icon_512x512@2x.png"],
    }
    for base, names in name_map.items():
        src1 = os.path.join(png_dir, f"{base}x{base}.png")
        src2 = os.path.join(png_dir, f"{base*2}x{base*2}.png")
        shutil.copy(src1, os.path.join(iconset, names[0]))
        shutil.copy(src2, os.path.join(iconset, names[1]))

    # iconutil 実行
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out_icns], check=True)

def main():
    if len(sys.argv) < 3:
        print("Usage: python _create_icns.py <input_png> <output.icns>")
        sys.exit(1)
    input_png = sys.argv[1]
    output_icns = sys.argv[2]

    with tempfile.TemporaryDirectory() as tmp:
        png_dir = ensure_dir(os.path.join(tmp, "pngs"))
        pngs = make_resized_pngs(input_png, png_dir)

        # 1) ImageMagick 優先（Windows対応のため）
        try:
            if not have("magick"):
                raise FileNotFoundError("ImageMagick 'magick' not found")
            # 並びは小さい順が無難
            pngs_sorted = sorted(pngs, key=lambda p: int(os.path.basename(p).split('x')[0]))
            build_icns_with_imagemagick(pngs_sorted, output_icns)
            print(f"ICNS created with ImageMagick: {output_icns}")
            return
        except Exception as im_err:
            # 2) macOSなら iconutil にフォールバック
            if platform.system() == "Darwin" and have("iconutil"):
                try:
                    build_icns_with_iconutil(png_dir, output_icns)
                    print(f"ICNS created with iconutil: {output_icns}")
                    return
                except subprocess.CalledProcessError as e:
                    print("iconutil failed:", e)
            # 3) 失敗の詳細を出す
            print("Failed to build .icns with ImageMagick.", im_err)
            if platform.system() == "Darwin":
                print("Tip: install Xcode Command Line Tools to get 'iconutil'.")
            sys.exit(2)

if __name__ == "__main__":
    main()
