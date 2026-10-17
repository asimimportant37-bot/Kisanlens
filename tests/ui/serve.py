import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from app import create_app
port, model_dir = int(sys.argv[1]), sys.argv[2]
tmp = tempfile.mkdtemp()
app = create_app({"SECRET_KEY": "ui", "DB_PATH": tmp + "/d.db", "UPLOAD_DIR": tmp + "/u", "MODEL_DIR": model_dir})
app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
