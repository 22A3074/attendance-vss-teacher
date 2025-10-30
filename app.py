import streamlit as st
from PIL import Image, ImageOps
import numpy as np
import io

st.title("👩‍🏫 教員用アプリ（学生ごとシェア生成）")

uploaded = st.file_uploader("QRコード画像をアップロード", type=["png", "jpg"])

student_list = st.text_area("学生IDリストを改行区切りで入力").splitlines()

if uploaded and student_list:
    base = Image.open(uploaded).convert("1")
    base = ImageOps.invert(base)
    np_base = np.array(base)

    for student in student_list:
        # 学生ごとの乱数シードで shareA を生成
        rng = np.random.default_rng(seed=hash(student) & 0xFFFFFFFF)
        shareA = rng.integers(0, 2, np_base.shape, dtype=np.uint8)
        shareB = np_base ^ shareA

        imgA = Image.fromarray((1 - shareA) * 255)
        imgB = Image.fromarray((1 - shareB) * 255)

        bufA, bufB = io.BytesIO(), io.BytesIO()
        imgA.save(bufA, format="PNG")
        imgB.save(bufB, format="PNG")

        st.download_button(f"📥 {student}用シェアA（教員保管）", bufA.getvalue(), f"shareA_{student}.png")
        st.download_button(f"📤 {student}用シェアB（配布用）", bufB.getvalue(), f"shareB_{student}.png")
