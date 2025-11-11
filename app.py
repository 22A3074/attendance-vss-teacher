# teacher_app.py
import streamlit as st
from PIL import Image
import numpy as np
import io, os, hashlib, datetime, json, pandas as pd

# --- 設定 ---
st.set_page_config(page_title="👩‍🏫 教員用：出席システム管理", layout="wide")
st.title("👩‍🏫 教員用アプリ（学生ごと固定 ShareB を生成、授業ごとに ShareA を作成）")

DATA_DIR = "data"
SHAREB_DIR = os.path.join(DATA_DIR, "shareB")
CLASS_DIR = os.path.join(DATA_DIR, "classes")
os.makedirs(SHAREB_DIR, exist_ok=True)
os.makedirs(CLASS_DIR, exist_ok=True)
ATT_CSV = os.path.join(DATA_DIR, "attendance_records.csv")
CLASSES_JSON = os.path.join(DATA_DIR, "classes_index.json")

# --- ユーティリティ ---
def stable_seed_from_str(s: str) -> int:
    h = hashlib.sha256(s.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big")

def img_to_binarr(img: Image.Image, threshold: int):
    g = img.convert("L")
    arr = np.array(g)
    return (arr < threshold).astype(np.uint8)  # 0/1

def binarr_to_image(binarr: np.ndarray):
    return Image.fromarray((255 * (1 - binarr)).astype(np.uint8))

def save_image_buf(img: Image.Image):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- 1) 学生ごとの固定 ShareB を生成（初回セットアップ） ---
st.header("① 学生ごとの固定 ShareB を作成（最初に一度だけ）")
student_text = st.text_area("学生IDを改行区切りで入力（例: s001）", height=150)
threshold = st.slider("閾値（2値化）", 1, 254, 128)
if st.button("固定 ShareB を生成してダウンロード可能にする"):
    students = [s.strip() for s in student_text.splitlines() if s.strip()]
    if not students:
        st.error("学生ID を入力してください。")
    else:
        for sid in students:
            seed = stable_seed_from_str("B:"+sid)  # B 用にプレフィックスを付け、固定化
            rng = np.random.default_rng(seed=seed)
            # 例えば 300x300 の既定サイズで作るので、実際には教師の base と同じサイズで使うことを推奨
            w = st.number_input(f"{sid} の ShareB 幅（px）", min_value=50, max_value=2000, value=300, key=f"w_{sid}")
            h = st.number_input(f"{sid} の ShareB 高さ（px）", min_value=50, max_value=2000, value=300, key=f"h_{sid}")
            shareB = rng.integers(0,2,size=(h,w), dtype=np.uint8)
            imgB = binarr_to_image(shareB)
            p = os.path.join(SHAREB_DIR, f"shareB_{sid}.png")
            imgB.save(p)
            st.success(f"{sid} の固定 shareB を保存しました: {p}")
            st.download_button(f"Download shareB_{sid}.png", data=save_image_buf(imgB), file_name=f"shareB_{sid}.png", mime="image/png")

st.info("※推奨ワークフロー: 初回に教員がここで各学生の固定 shareB を作り配布（ファイル配布または学籍管理システムへ）。")

# --- 2) 授業ごとに base(QR) をアップして、各学生用の ShareA を生成 ---
st.header("② 授業（base画像→shareA生成） - 毎授業行う")
with st.form("class_gen"):
    col1, col2 = st.columns(2)
    with col1:
        base_upload = st.file_uploader("授業で使う base(QR) 画像をアップロード（PNG/JPG）", type=["png","jpg","jpeg"])
        class_name = st.text_input("授業名 / クラス識別子（例: 2025-11-11_Lec1）", value=datetime.datetime.now().strftime("%Y%m%d_%H%M"))
    with col2:
        class_date = st.date_input("授業日", value=datetime.date.today())
        generate_btn = st.form_submit_button("この授業用に ShareA を生成")
if generate_btn:
    if not base_upload:
        st.error("base となる画像をアップしてください。")
    else:
        base_img = Image.open(base_upload).convert("L")
        base_arr = img_to_binarr(base_img, threshold)
        st.success(f"base サイズ: {base_img.size[0]} x {base_img.size[1]}")
        # load existing shareB files and verify sizes
        shareb_files = sorted([f for f in os.listdir(SHAREB_DIR) if f.startswith("shareB_") and f.endswith(".png")])
        if not shareb_files:
            st.error("固定 ShareB が存在しません。まず①で生成してください。")
        else:
            # save class folder
            class_id = f"{class_name}_{class_date.isoformat()}"
            folder = os.path.join(CLASS_DIR, class_id)
            os.makedirs(folder, exist_ok=True)
            # store base image and metadata
            base_img.save(os.path.join(folder, "base.png"))
            metadata = {"class_id": class_id, "class_name": class_name, "date": class_date.isoformat(), "threshold": int(threshold)}
            # generate shareA per student: shareA = base XOR shareB (expand/crop if sizes mismatch)
            st.write("生成された ShareA（一部を表示）")
            for f in shareb_files:
                sid = f.replace("shareB_","").replace(".png","")
                shareB_img = Image.open(os.path.join(SHAREB_DIR,f)).convert("L")
                shareB_arr = img_to_binarr(shareB_img, threshold)
                # If sizes differ, resize shareB to base size (deterministic nearest) — important
                if shareB_arr.shape != base_arr.shape:
                    shareB_img = shareB_img.resize(base_img.size)
                    shareB_arr = img_to_binarr(shareB_img, threshold)
                shareA_arr = base_arr ^ shareB_arr
                imgA = binarr_to_image(shareA_arr)
                imgA.save(os.path.join(folder, f"shareA_{sid}.png"))
                buf = save_image_buf(imgA)
                col1, col2 = st.columns([1,3])
                with col1:
                    st.image(imgA, width=120, caption=f"shareA_{sid}")
                with col2:
                    st.download_button(f"Download shareA_{sid}.png", data=buf, file_name=f"shareA_{sid}.png", mime="image/png")
            # save metadata and index
            metadata["base_hash"] = hashlib.sha256(open(os.path.join(folder,"base.png"),"rb").read()).hexdigest()
            with open(os.path.join(folder,"metadata.json"), "w", encoding="utf-8") as fp:
                json.dump(metadata, fp, ensure_ascii=False, indent=2)
            # update classes index
            idx = {}
            if os.path.exists(CLASSES_JSON):
                idx = json.load(open(CLASSES_JSON, "r", encoding="utf-8"))
            idx[class_id] = metadata
            json.dump(idx, open(CLASSES_JSON,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
            st.success(f"クラス {class_id} の ShareA を生成・保存しました（フォルダ: {folder}）。")

# --- 3) 出席記録の確認・ダウンロード ---
st.header("③ 出席記録の確認")
if os.path.exists(ATT_CSV):
    df = pd.read_csv(ATT_CSV)
    st.dataframe(df.sort_values(["class_id","timestamp"], ascending=[False,False]))
    st.download_button("出席記録 CSV をダウンロード", data=open(ATT_CSV,"rb").read(), file_name="attendance_records.csv", mime="text/csv")
else:
    st.info("まだ出席記録はありません。学生が学生アプリから出席を送信するとここに記録されます。")

st.info("注意: 今回の仕組みは教育目的のデモ実装です。実運用では ID 認証や TLS/サーバ保存などの追加対策を推奨します。")
