"""KisanLens – Flask application.

Run locally:   python app.py
Production:    gunicorn "app:create_app()"
"""
import io
import json
import os
import re
import secrets
import time
import uuid

from flask import Flask, jsonify, render_template, request, send_from_directory, session
from PIL import Image, ImageOps, UnidentifiedImageError

import database
from model.predict import ModelUnavailable, Predictor
from services import disease_advisory

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SUPPORTED_CROPS = ("tomato", "potato")
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024       # 8 MB
MAX_PIXELS = 40_000_000                  # reject decompression bombs
MIN_SIDE = 64                            # too small to show a leaf
MAX_STORED_SIDE = 1600
MAX_PENDING = 8                          # unsaved results kept per browser session
REF_RE = re.compile(r"^[a-f0-9]{32}\.jpg$")
XHR_HEADER = ("X-Requested-With", "KisanLens")


class ApiError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def create_app(test_config=None):
    app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.update(
        DB_PATH=os.path.join(app.instance_path, "kisanlens.db"),
        UPLOAD_DIR=os.path.join(app.instance_path, "uploads"),
        MODEL_DIR=os.environ.get("KISANLENS_MODEL_DIR") or os.path.join(BASE_DIR, "model"),
        MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES + 512 * 1024,   # multipart overhead
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("KISANLENS_SECURE_COOKIES") == "1",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)
    app.config["SECRET_KEY"] = app.config.get("SECRET_KEY") or _load_secret_key(app.instance_path)

    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    database.init_db(app.config["DB_PATH"])
    _cleanup_orphan_uploads(app)

    origins = os.environ.get("KISANLENS_CORS_ORIGINS")
    if origins:  # same-origin only unless explicitly configured
        from flask_cors import CORS
        CORS(app, resources={r"/api/*": {"origins": [o.strip() for o in origins.split(",")]}},
             supports_credentials=True)

    # tests may inject a stand-in predictor; production always uses the real one
    app.extensions["predictor"] = app.config.get("PREDICTOR") or Predictor(app.config["MODEL_DIR"])
    _register_hooks(app)
    _register_pages(app)
    _register_api(app)
    return app


# --------------------------------------------------------------------- setup
def _load_secret_key(instance_path):
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    path = os.path.join(instance_path, "secret_key")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:                      # another worker created it first
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(key)
    return key


def _cleanup_orphan_uploads(app, max_age_seconds=24 * 3600):
    """Delete unsaved uploads older than a day (saved ones are referenced in the DB)."""
    keep = database.all_image_refs(app.config["DB_PATH"])
    now = time.time()
    for name in os.listdir(app.config["UPLOAD_DIR"]):
        path = os.path.join(app.config["UPLOAD_DIR"], name)
        if name not in keep and REF_RE.match(name) and now - os.path.getmtime(path) > max_age_seconds:
            try:
                os.remove(path)
            except OSError:
                pass


def _register_hooks(app):
    @app.before_request
    def _csrf_guard():
        # State-changing API calls must carry a custom header. Browsers will not
        # add it on cross-site form posts, and cross-origin fetches need CORS preflight.
        if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get(XHR_HEADER[0]) != XHR_HEADER[1]:
                return _json_error("forbidden", "Missing required request header.", 403)

    @app.after_request
    def _security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(ApiError)
    def _api_error(err):
        return _json_error(err.code, err.message, err.status)

    @app.errorhandler(413)
    def _too_large(_):
        return _json_error("file_too_large", f"Image is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.", 413)

    @app.errorhandler(404)
    def _not_found(_):
        if request.path.startswith("/api/"):
            return _json_error("not_found", "Resource not found.", 404)
        return render_template("error.html", page="", code=404), 404

    @app.errorhandler(405)
    def _bad_method(_):
        return _json_error("method_not_allowed", "Method not allowed.", 405)

    @app.errorhandler(500)
    def _server_error(_):
        if request.path.startswith("/api/"):
            return _json_error("server_error", "Something went wrong on the server.", 500)
        return render_template("error.html", page="", code=500), 500


def _json_error(code, message, status):
    resp = jsonify({"ok": False, "error": {"code": code, "message": message}})
    resp.status_code = status
    return resp


def _ok(payload=None, status=200):
    body = {"ok": True}
    if payload:
        body.update(payload)
    resp = jsonify(body)
    resp.status_code = status
    return resp


# --------------------------------------------------------------------- pages
def _register_pages(app):
    pages = {
        "/": ("index.html", "home"),
        "/detect": ("detect.html", "detect"),
        "/results": ("results.html", "results"),
        "/diseases": ("diseases.html", "diseases"),
        "/history": ("history.html", "history"),
        "/about": ("about.html", "about"),
    }
    for path, (template, name) in pages.items():
        app.add_url_rule(
            path, endpoint=f"page_{name}",
            view_func=(lambda t=template, n=name: render_template(t, page=n, crops=SUPPORTED_CROPS)),
        )


# ----------------------------------------------------------------------- API
def _session_id():
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
        session.permanent = True
    return session["sid"]


def _upload_path(app, ref):
    if not REF_RE.match(ref or ""):
        raise ApiError("invalid_reference", "Invalid image reference.", 400)
    root = os.path.realpath(app.config["UPLOAD_DIR"])
    path = os.path.realpath(os.path.join(root, ref))
    if os.path.commonpath([root, path]) != root:       # path-traversal guard
        raise ApiError("invalid_reference", "Invalid image reference.", 400)
    return path


def _remove_upload(app, ref):
    try:
        os.remove(_upload_path(app, ref))
    except (OSError, ApiError):
        pass


def validate_image(data):
    """Decode and validate image bytes. Never trusts filename or MIME type."""
    if not data:
        raise ApiError("empty_file", "The uploaded file is empty.", 400)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError("file_too_large", f"Image is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.", 413)
    try:
        probe = Image.open(io.BytesIO(data))
        fmt = probe.format
        width, height = probe.size
        if fmt not in ALLOWED_FORMATS:
            raise ApiError("unsupported_format", "Only JPEG, PNG and WEBP images are supported.", 415)
        if width * height > MAX_PIXELS:
            raise ApiError("image_too_large", "Image dimensions are too large.", 413)
        if min(width, height) < MIN_SIDE:
            raise ApiError("image_too_small", f"Image is too small (minimum {MIN_SIDE}px on each side).", 400)
        probe.verify()                                    # structural check
        img = Image.open(io.BytesIO(data))
        img.load()                                        # full decode (catches truncation)
    except ApiError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise ApiError("invalid_image", "This file is not a readable image. Please upload a JPEG, PNG or WEBP photo.", 400)
    return ImageOps.exif_transpose(img).convert("RGB")


def _register_api(app):
    predictor = app.extensions["predictor"]

    @app.get("/api/health")
    def health():
        return _ok({"app": "KisanLens", "version": "1.0.0", "crops": list(SUPPORTED_CROPS),
                    "model": predictor.status() | {"classes": predictor.classes}})

    @app.post("/api/predict")
    def predict():
        sid = _session_id()
        crop = (request.form.get("crop") or "").strip().lower()
        if crop not in SUPPORTED_CROPS:
            raise ApiError("invalid_crop", f"Please choose a crop: {', '.join(SUPPORTED_CROPS)}.", 400)
        upload = request.files.get("image")
        if upload is None:
            raise ApiError("missing_image", "No image was uploaded (field name: image).", 400)

        data = upload.read(MAX_UPLOAD_BYTES + 1)
        img = validate_image(data)

        if not predictor.available:
            raise ApiError("model_unavailable",
                           "The AI model is not installed on this server, so no analysis was done. "
                           "No result is shown because it would not be real.", 503)
        try:
            result = predictor.predict(img, selected_crop=crop)
        except ModelUnavailable as exc:
            raise ApiError("model_unavailable", str(exc), 503)
        except Exception:  # noqa: BLE001
            app.logger.exception("Inference failed")
            raise ApiError("inference_failed", "The model could not analyse this image. Please try another photo.", 500)

        # Store a sanitised copy (re-encoded JPEG, no metadata) under a random name.
        img.thumbnail((MAX_STORED_SIDE, MAX_STORED_SIDE))
        ref = f"{uuid.uuid4().hex}.jpg"
        img.save(_upload_path(app, ref), "JPEG", quality=90)

        pending = session.get("pending", {})
        pending[ref] = [crop, result["class_key"], round(result["confidence"], 6)]
        while len(pending) > MAX_PENDING:
            old = next(iter(pending))
            pending.pop(old)
            _remove_upload(app, old)
        session["pending"] = pending

        top3 = [{**t, "label": disease_advisory.class_label(t["class_key"])} for t in result["top3"]]
        return _ok({"result": {
            **result,
            "top3": top3,
            "crop": crop,
            "label": disease_advisory.class_label(result["class_key"]),
            "advisory": disease_advisory.get_advisory(result["class_key"]),
            "image_ref": ref,
            "image_url": f"/api/image/{ref}",
        }})

    @app.get("/api/image/<ref>")
    def image(ref):
        sid = _session_id()
        if not REF_RE.match(ref):
            raise ApiError("not_found", "Image not found.", 404)
        if ref not in session.get("pending", {}) and not database.ref_owned(ref, sid, app.config["DB_PATH"]):
            raise ApiError("not_found", "Image not found.", 404)
        path = _upload_path(app, ref)
        if not os.path.isfile(path):
            raise ApiError("not_found", "Image not found.", 404)
        resp = send_from_directory(app.config["UPLOAD_DIR"], ref, mimetype="image/jpeg", max_age=0)
        resp.headers["Cache-Control"] = "private, no-store"
        return resp

    @app.get("/api/history")
    def history_list():
        sid = _session_id()
        scans = database.get_scans(sid, app.config["DB_PATH"])
        for s in scans:
            s["label"] = disease_advisory.class_label(s["predicted_class"])
            s["image_url"] = f"/api/image/{s['image_ref']}"
        return _ok({"scans": scans, "count": len(scans)})

    @app.post("/api/history")
    def history_save():
        sid = _session_id()
        body = request.get_json(silent=True) or {}
        ref = body.get("image_ref")
        pending = session.get("pending", {})
        if not isinstance(ref, str) or ref not in pending:
            raise ApiError("not_found", "No unsaved result found for this image. Scan it again.", 404)
        crop, predicted_class, confidence = pending[ref]
        scan_id = database.add_scan(sid, crop, predicted_class, confidence, ref, app.config["DB_PATH"])
        pending.pop(ref)
        session["pending"] = pending
        return _ok({"id": scan_id}, 201)

    @app.delete("/api/history/<int:scan_id>")
    def history_delete(scan_id):
        sid = _session_id()
        ref = database.delete_scan(scan_id, sid, app.config["DB_PATH"])
        if ref is None:
            raise ApiError("not_found", "Scan not found.", 404)
        _remove_upload(app, ref)
        return _ok({"deleted": scan_id})

    @app.delete("/api/history")
    def history_clear():
        sid = _session_id()
        refs = database.delete_all_scans(sid, app.config["DB_PATH"])
        for ref in refs:
            _remove_upload(app, ref)
        return _ok({"deleted_count": len(refs)})

    @app.get("/api/model-metrics")
    def model_metrics():
        """Measured evaluation results written by train_model.py (None if never trained)."""
        path = os.path.join(app.config["MODEL_DIR"], "artifacts", "metrics.json")
        if not predictor.available or not os.path.isfile(path):
            return _ok({"metrics": None})
        with open(path, encoding="utf-8") as f:
            return _ok({"metrics": json.load(f)})

    @app.get("/api/diseases")
    def diseases():
        crop = (request.args.get("crop") or "").strip().lower() or None
        if crop and crop not in SUPPORTED_CROPS:
            raise ApiError("invalid_crop", "Unknown crop.", 400)
        if predictor.available:
            keys, source = predictor.classes, "model"
        else:
            keys, source = None, "dataset_config"      # documented classes, model not installed
        items = disease_advisory.list_advisories(keys, crop)
        return _ok({
            "source": source,
            "model_available": predictor.available,
            "diseases": items,
            "references": disease_advisory.REFERENCE_SOURCES,
        })


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)),
                     debug=os.environ.get("FLASK_DEBUG") == "1")
