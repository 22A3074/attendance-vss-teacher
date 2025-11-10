# attendance_vss_teacher.py
import streamlit as st
from PIL import Image, ImageOps
import numpy as np
import io, os, csv, hashlib, hmac, threading, time, json
from flask import Flask, request, jsonify
import pandas as pd

st.set_page_config(page_title="👩‍🏫 教員用アプリ（出席管理）", layout="wide")

# --- 設定ファイル / 保存パス ---
DATA_DIR = "teacher_data"
os.makedirs(DATA_DIR, exist_ok=True)
SHAREB_DIR = os.path.join(DATA_DIR, "shareb")
os.makedirs(SHAREB_DIR, exist_ok=True)
SHAREB_HASH_FILE = os.path.join(DATA_DIR, "shareb_hashes.csv")
ATTEND_FILE = os.path.join(DATA_DIR, "attendance.csv")

# helper
def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def save_shareb_hashes(mapping):
    # mapping: dict student_id -> sha256 hex
    with open(SHAREB_HASH_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["student_id","sha256"])
        for k,v in mapping.items():
            writer.writerow([k,v])

def load_shareb_hashes():
    if not os.path.exists(SHAREB_HASH_FILE):
        return {}
    df = pd.read_csv(SHAREB_HASH_FILE, dtype=str)
    return dict(zip(df["student_id"].astype(str), df["sha256"].astype(str)))

def append_attendance(record):
    header = ["timestamp","class_id","student_id","shareb_hash","source_url"]
    exists = os.path.exists(ATTEND_FILE)
    with open(ATTEND_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(header)
        w.writerow([record.get(h,"") for h in header])

def read_attendance():
    if not os.path.exists(ATTEND_FILE):
        return pd.DataFrame(columns=["timestamp","class_id","student_id","shareb_hash","source_url"])
    return pd.read_csv(ATTEND_FILE, dtype=str)

# --- Flask API (スレッドで起動) ---
app = Flask(__name__)

@app.route("/api/record_attendance", methods=["POST"])
def api_record_attendance():
    """
    expecting JSON:
    {
      "student_id": "...",
      "shareb_hash": "...",
      "class_id": "...",
      "source_url": "..."  # optional, decoded from QR
    }
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"ok": False, "error":"no json"}), 400
    student_id = data.get("student_id")
    shareb_hash = data.get("shareb_hash")
    class_id = data.get("class_id")
    source_url = data.get("source_url","")
    if not (student_id and shareb_hash and class_id):
        return jsonify({"ok": False, "error":"missing fields"}), 400

    known = load_shareb_hashes()
    expected = known.get(student_id)
    if expected is None:
        return jsonify({"ok": False, "error":"unknown student_id"}), 403
    if expected != shareb_hash:
        return jsonify({"ok": False, "error":"shareb hash mismatch"}), 403

    rec = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "class_id": class_id,
        "student_id": student_id,
        "shareb_hash": shareb_hash,
        "source_url": source_url
    }
    append_attendance(rec)
    return jsonify({"ok": True, "message":"attendance recorded"}), 200

def run_flask(port):
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# --- UI ---
st.title("👩‍🏫 教員用アプリ（学生ごとシェア生成・出席確認）")

with st.expander("1) 初期：学生ごとの固定 ShareB を生成して配布（一度だけ実行）", expanded=True):
    st.write("student_id を改行区切りで入力し、'master secret' を設定してください。master secret は教員だけが知る値にします。")
    master_secret = st.text_input("Master secret（教員のみ知る）", type="password", key="master_secret")
    students_text = st.text_area("学生IDリスト（改行区切り）", height=150)
    if st.button("🔧 Generate ShareB for students"):
        if not master_secret or not students_text.strip():
            st.error("master secret と学生リストを入力してください。")
        else:
            students = [s.strip() for s in students_text.splitlines() if s.strip()]
            mapping = load_shareb_hashes()
            for sid in students:
                # deterministic RNG seed via HMAC(master_secret, sid)
                key = master_secret.encode("utf-8")
                msg = sid.encode("utf-8")
                digest = hmac.new(key, msg, hashlib.sha256).digest()
                seed_int = int.from_bytes(digest[:8],"big")
                rng = np.random.default_rng(seed=seed_int)
                # we choose a fixed size for share images (e.g., 300x300) OR produce from a template later.
                # Here we produce a 1-channel random matrix 300x300 bits (0/1) and save PNG
                h,w = 300,300
                shareb = rng.integers(0,2,(h,w), dtype=np.uint8)
                imgB = Image.fromarray((1 - shareb) * 255)  # invert for visual black/white
                outbuf = io.BytesIO()
                imgB.save(outbuf, format="PNG")
                data_bytes = outbuf.getvalue()
                file_path = os.path.join(SHAREB_DIR, f"shareB_{sid}.png")
                with open(file_path,"wb") as f:
                    f.write(data_bytes)
                sha = sha256_bytes(data_bytes)
                mapping[sid] = sha
                st.download_button(f"🔽 {sid} の ShareB をダウンロード", data_bytes, file_name=f"shareB_{sid}.png")
            save_shareb_hashes(mapping)
            st.success("ShareB を生成してハッシュを保存しました。shareb_hashes.csv を teacher_data に保存しました。")

with st.expander("2) 授業ごとの ShareA を生成（教員保管／学生には配らない）", expanded=False):
    st.write("授業用の秘密画像（QR等）をアップし、クラスID を入れて生成します。学生ごとに ShareA = class_base XOR shareB(student) を作成します。")
    class_img_file = st.file_uploader("授業用 QR（PNG/JPG）をアップロード", type=["png","jpg","jpeg"])
    class_id = st.text_input("Class ID（例: 2025-09-30-ALGEBRA）")
    if st.button("🔧 Generate ShareA for this class"):
        if not class_img_file or not class_id:
            st.error("class image と class_id を入力してください。")
        else:
            base_img = Image.open(class_img_file).convert("1")
            base_img = ImageOps.invert(base_img)
            np_base = np.array(base_img, dtype=np.uint8)
            # load existing shareb files and mapping
            mapping = load_shareb_hashes()
            if not mapping:
                st.error("先に ShareB を生成しておいてください（Step 1）。")
            else:
                for sid, sha in mapping.items():
                    # load shareb file
                    file_path = os.path.join(SHAREB_DIR, f"shareB_{sid}.png")
                    if not os.path.exists(file_path):
                        st.warning(f"{sid} の shareB ファイルが見つかりません（{file_path}）。")
                        continue
                    imgB = Image.open(file_path).convert("1").resize(base_img.size, Image.NEAREST)
                    arrB = np.array(imgB, dtype=np.uint8)
                    arrB = 1 - (arrB // 255)
                    shareA = np_base ^ arrB  # binary XOR -> teacher keeps shareA
                    imgA = Image.fromarray((1 - shareA) * 255)
                    buf = io.BytesIO()
                    imgA.save(buf, format="PNG")
                    data_bytes = buf.getvalue()
                    st.download_button(f"📥 {sid} 用 ShareA（教員保管）", data_bytes, file_name=f"shareA_{class_id}_{sid}.png")
                st.success("全学生分の ShareA を生成・ダウンロード可能にしました。各 shareA は教員側で管理してください。")

with st.expander("3) 出席記録の表示 / エクスポート", expanded=False):
    df = read_attendance()
    st.write("現在の出席レコード（attendance.csv）:")
    st.dataframe(df)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button("CSV をダウンロード", csv_bytes, "attendance.csv")

with st.expander("4) API サーバー（学生からのPOSTを受ける）", expanded=False):
    st.write("このアプリで簡易 API を立ち上げます（ローカル/デプロイ先で公開可能）。学生側は /api/record_attendance に JSON POST してください。")
    port = st.number_input("Flask サーバーポート", min_value=1000, max_value=65535, value=8501)
    if st.button("▶️ Flask API を起動（バックグラウンド）"):
        # start thread
        t = threading.Thread(target=run_flask, args=(int(port),), daemon=True)
        t.start()
        st.info(f"Flask API をポート {port} で起動しました。学生側は teacher_app_url = 'https://<あなたのデプロイ先>: {port}/api/record_attendance' を使ってください。")

st.markdown("---")
st.info("実運用の際は HTTPS とアクセス制御を忘れずに。master secret は安全に管理してください。")
