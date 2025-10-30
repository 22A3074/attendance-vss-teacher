import streamlit as st
from PIL import Image, ImageOps
import numpy as np
import io

st.title("👩‍🏫 教員用アプリ（授業ごと shareA生成）")

uploaded_qr = st.file_uploader("QRコード画像をアップロード", type=["png", "jpg"])
uploaded_shareB = st.file_uploader("学生用固定シェアB画像をアップロード", type=["png", "jpg"])

if uploaded_qr and uploaded_shareB:
    # QRコード
    qr = Image.open(uploaded_qr).convert("1")
    qr = ImageOps.invert(qr)
    np_qr = np.array(qr)

    # 学生用 shareB
    shareB_img = Image.open(uploaded_shareB).convert("1")
    shareB_img = ImageOps.invert(shareB_img)
    np_shareB = np.array(shareB_img)

    # shareA を毎授業生成
    shareA = np.random.randint(0, 2, np_qr.shape, dtype=np.uint8)

    # 復号チェック用
    recovered = shareA ^ np_shareB
    imgA = Image.fromarray((1 - shareA) * 255)
    imgRec = Image.fromarray((1 - recovered) * 255)

    st.image([imgA, imgRec], caption=["shareA（教員用）", "復号確認"], width=250)

    # ダウンロードボタン
    bufA = io.BytesIO()
    imgA.save(bufA, format="PNG")
    st.download_button("📥 shareAをダウンロード（教員保管用）", bufA.getvalue(), "shareA.png")
