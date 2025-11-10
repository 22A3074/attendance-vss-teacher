import streamlit as st
from PIL import Image, ImageOps
import numpy as np
import io, os, csv, hashlib
import pandas as pd

st.set_page_config(page_title="👩‍🏫 教員用アプリ（安定版）", layout="wide")

DATA_DIR = "teacher_data"
os.makedirs(DATA_DIR, exist_ok=True)
SHAREB_DIR = os.path.join(DATA_DIR, "shareb")
os.makedirs(SHAREB_DIR, exist_ok=True)
SHAREB_HASH_FILE = os.path.join(DATA_DIR, "shareb_hashes.csv")
ATTEND_FILE = os.path.join(DATA_DIR, "attendance.csv")

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def save_shareb_hashes(mapping):
    with open(SHAREB_HASH_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["student_id","sha256"])
        for sid,sha in mapping.items():
            writer.writerow([sid,sha])

def load_shareb_hashes():
    if not os.path.exists(SHAREB_HASH_FILE):
        return {}
    df = pd.read_csv(SHAREB_HASH_FILE, dtype=str)
    return dict(zip(df["student_id"], df["sha256"]))

st.title("👩‍🏫 教員用アプリ（ShareB固定 / ShareA授業ごと）")

with st.expander("1) ShareBを学生ごとに生成（初回のみ）", expanded=True):
    secret = st.text_input("Master Secret（教員専用）", type="password")
    text = st.text_area("学生IDを改行で入力")
    if st.button("生成"):
        ids = [s.strip() for s in text.splitlines() if s.strip()]
        mapping = load_shareb_hashes()
        for sid in ids:
            seed = int(hashlib.sha256((secret+sid).encode()).hexdigest(),16) % (2**32)
            rng = np.random.default_rng(seed=seed)
            arr = rng.integers(0,2,(300,300),dtype=np.uint8)
            img = Image.fromarray((1-arr)*255)
            buf = io.BytesIO()
            img.save(buf,format="PNG")
            data = buf.getvalue()
            with open(os.path.join(SHAREB_DIR,f"shareB_{sid}.png"),"wb") as f: f.write(data)
            mapping[sid] = sha256_bytes(data)
            st.download_button(f"{sid} 用 ShareB ダウンロード", data, file_name=f"shareB_{sid}.png")
        save_shareb_hashes(mapping)
        st.success("ShareB生成およびハッシュ記録が完了しました。")

with st.expander("2) 授業用 ShareA を学生ごと生成（毎授業）", expanded=False):
    imgfile = st.file_uploader("授業用QR画像", type=["png","jpg"])
    class_id = st.text_input("Class ID")
    if st.button("生成（ShareA）"):
        if imgfile and class_id:
            base = Image.open(imgfile).convert("L")
            base = ImageOps.invert(base)
            np_base = (np.array(base)//255).astype(np.uint8)
            mapping = load_shareb_hashes()
            for sid in mapping:
                shareb_img_path = os.path.join(SHAREB_DIR,f"shareB_{sid}.png")
                imgB = Image.open(shareb_img_path).convert("L").resize(base.size,Image.NEAREST)
                np_B = 1-(np.array(imgB)//255)
                np_A = np_base ^ np_B
                imgA = Image.fromarray((1-np_A)*255)
                buf = io.BytesIO()
                imgA.save(buf,format="PNG")
                st.download_button(f"{sid} 用 ShareA", buf.getvalue(), file_name=f"shareA_{class_id}_{sid}.png")
        else:
            st.error("QR画像とClass IDを入力してください。")

with st.expander("3) 出席記録を確認", expanded=False):
    if os.path.exists(ATTEND_FILE):
        df = pd.read_csv(ATTEND_FILE)
        st.dataframe(df)
        st.download_button("CSVダウンロード", df.to_csv(index=False).encode(), "attendance.csv")
    else:
        st.info("まだ出席記録はありません。")
