# teacher_app_fixed.py
import streamlit as st
from PIL import Image
import numpy as np
import io
import hashlib

st.set_page_config(page_title="👩‍🏫 教員用アプリ（学生ごとシェア生成）", layout="centered")
st.title("👩‍🏫 教員用アプリ（学生ごとシェア生成）")

uploaded = st.file_uploader("QRコード画像をアップロード（PNG/JPG）", type=["png", "jpg", "jpeg"])
student_text = st.text_area("学生IDリストを改行区切りで入力（例: s001）", height=200)
student_list = [s.strip() for s in student_text.splitlines() if s.strip()]

threshold = st.slider("閾値（画像→2値化）", min_value=1, max_value=254, value=128)

def stable_seed_from_str(s: str) -> int:
    # sha256 を使って安定な 32bit 整数を作る
    h = hashlib.sha256(s.encode("utf-8")).digest()
    # 上位4バイトを取り出して整数化
    return int.from_bytes(h[:4], "big")

if uploaded and student_list:
    try:
        # 画像を読み込んでグレースケールにし、閾値で0/1の配列に変換
        img = Image.open(uploaded).convert("L")
        arr = np.array(img)  # 0-255
        bin_base = (arr < threshold).astype(np.uint8)  # QR の「黒」を 1 にする（閾値以下を黒扱い）
        # bin_base は 0/1（uint8）
        st.success(f"入力画像サイズ: {img.size[0]} x {img.size[1]}、学生数: {len(student_list)}")

        for student in student_list:
            seed = stable_seed_from_str(student)
            rng = np.random.default_rng(seed=seed)
            # shareA: 0/1 のランダム配列
            shareA = rng.integers(0, 2, size=bin_base.shape, dtype=np.uint8)
            # shareB = base XOR shareA  (0/1 同士)
            shareB = bin_base ^ shareA

            # 画像化: 0->255 (白), 1->0 (黒) に戻す（視覚復号と合わせる）
            imgA = Image.fromarray((255 * (1 - shareA)).astype(np.uint8))  # 教員保存用（白=背景）
            imgB = Image.fromarray((255 * (1 - shareB)).astype(np.uint8))  # 配布用

            # バッファに入れる
            bufA = io.BytesIO()
            bufB = io.BytesIO()
            imgA.save(bufA, format="PNG")
            imgB.save(bufB, format="PNG")

            col1, col2 = st.columns([1,1])
            with col1:
                st.image(imgA, caption=f"{student} 用 ShareA (教員保管)", width=120)
            with col2:
                st.image(imgB, caption=f"{student} 用 ShareB (配布用)", width=120)

            st.download_button(f"📥 {student}用シェアA（教員保管）", data=bufA.getvalue(), file_name=f"shareA_{student}.png", mime="image/png")
            st.download_button(f"📤 {student}用シェアB（配布用）", data=bufB.getvalue(), file_name=f"shareB_{student}.png", mime="image/png")

    except Exception as e:
        st.error(f"処理中にエラーが発生しました: {e}")
else:
    st.info("右上から QR 画像をアップロードし、学生IDリストを入力してください。")
