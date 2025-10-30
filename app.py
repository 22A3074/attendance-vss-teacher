import streamlit as st
from PIL import Image, ImageOps
import numpy as np
import io

st.title("👩‍🏫 教員用アプリ（シェア画像生成）")

st.write("授業出席用QRコードなどを秘密分散化します。")

uploaded = st.file_uploader("出席用QRコード画像をアップロードしてください", type=["png", "jpg"])

if uploaded:
    base = Image.open(uploaded).convert("1")  # 白黒化
    base = ImageOps.invert(base)
    np_base = np.array(base)

    # ランダムなシェアAを生成
    shareA = np.random.randint(0, 2, np_base.shape, dtype=np.uint8)
    shareB = np_base ^ shareA

    imgA = Image.fromarray((1 - shareA) * 255)
    imgB = Image.fromarray((1 - shareB) * 255)

    st.image([imgA, imgB], caption=["シェアA（教員保管）", "シェアB（学生配布用）"], width=250)

    # ダウンロードボタン
    bufA = io.BytesIO()
    bufB = io.BytesIO()
    imgA.save(bufA, format="PNG")
    imgB.save(bufB, format="PNG")

    st.download_button("📥 シェアAをダウンロード（教員保管用）", bufA.getvalue(), "shareA.png")
    st.download_button("📤 シェアBをダウンロード（学生へ配布）", bufB.getvalue(), "shareB.png")
