import streamlit as st
from PIL import Image
import numpy as np
import io
import random

st.title("👩‍🏫 教員用アプリ（視覚復号型シェア生成）")

uploaded = st.file_uploader("出席用QRコードをアップロード", type=["png", "jpg"])

def binarize(img, threshold=128):
    return img.convert("L").point(lambda x: 0 if x < threshold else 255, '1')

def visual_secret_sharing(img):
    width, height = img.size
    pixels = np.array(img, dtype=np.uint8)
    share1 = np.zeros((height*2, width*2), dtype=np.uint8)
    share2 = np.zeros((height*2, width*2), dtype=np.uint8)

    patterns = [
        (np.array([[0,255],[255,0]]), np.array([[255,0],[0,255]])),
        (np.array([[255,0],[0,255]]), np.array([[0,255],[255,0]]))
    ]

    for y in range(height):
        for x in range(width):
            pixel = pixels[y,x]
            pattern = random.choice(patterns)
            if pixel == 0:  # 黒
                s1, s2 = pattern
            else:  # 白
                s1, s2 = pattern
                s2 = s1.copy()
            share1[y*2:y*2+2, x*2:x*2+2] = s1
            share2[y*2:y*2+2, x*2:x*2+2] = s2
    return Image.fromarray(share1), Image.fromarray(share2)

if uploaded:
    img = Image.open(uploaded)
    img = img.resize((128,128))
    img_bin = binarize(img)

    shareA, shareB = visual_secret_sharing(img_bin)

    st.image([shareA, shareB], caption=["シェアA（教員用）","シェアB（学生用）"], width=250)

    bufA, bufB = io.BytesIO(), io.BytesIO()
    shareA.save(bufA, format="PNG")
    shareB.save(bufB, format="PNG")

    st.download_button("📥 シェアAダウンロード", bufA.getvalue(), "shareA.png")
    st.download_button("📤 シェアBダウンロード", bufB.getvalue(), "shareB.png")
