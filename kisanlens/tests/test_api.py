import io
import os

import pytest

from conftest import H, StubPredictor, make_image, upload


# ------------------------------------------------------------- health / model
def test_health_reports_missing_model(client_nomodel):
    r = client_nomodel.get("/api/health")
    assert r.status_code == 200
    m = r.get_json()["model"]
    assert m["available"] is False and m["error"]


def test_predict_without_model_never_fabricates(client_nomodel):
    r = upload(client_nomodel, make_image())
    assert r.status_code == 503
    body = r.get_json()
    assert body["ok"] is False and body["error"]["code"] == "model_unavailable"
    assert "result" not in body


# -------------------------------------------------------------- validation
def test_valid_upload_all_formats(client):
    for fmt, name in (("JPEG", "a.jpg"), ("PNG", "a.png"), ("WEBP", "a.webp")):
        r = upload(client, make_image(fmt), name)
        assert r.status_code == 200, (fmt, r.get_json())
        res = r.get_json()["result"]
        assert res["crop"] == "tomato" and 0 <= res["confidence"] <= 1
        assert len(res["top3"]) == 3 and res["advisory"]["symptoms"]["en"]


@pytest.mark.parametrize("fmt,name", [("GIF", "a.gif"), ("BMP", "a.bmp"), ("TIFF", "a.tiff")])
def test_unsupported_formats_rejected_even_if_named_jpg(client, fmt, name):
    r = upload(client, make_image(fmt), "leaf.jpg")
    assert r.status_code == 415 and r.get_json()["error"]["code"] == "unsupported_format"


def test_text_file_disguised_as_image(client):
    r = upload(client, io.BytesIO(b"this is not an image at all" * 50), "leaf.jpg")
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "invalid_image"


def test_corrupted_image(client):
    raw = make_image("JPEG", (400, 400)).getvalue()
    r = upload(client, io.BytesIO(raw[: len(raw) // 2]), "leaf.jpg")
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "invalid_image"


def test_oversized_upload(client):
    r = upload(client, io.BytesIO(b"\xff\xd8\xff" + os.urandom(9 * 1024 * 1024)), "big.jpg")
    assert r.status_code == 413 and r.get_json()["error"]["code"] == "file_too_large"


def test_tiny_image_rejected(client):
    r = upload(client, make_image("PNG", (20, 20)), "t.png")
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "image_too_small"


def test_bad_inputs(client):
    assert upload(client, make_image(), crop="wheat").get_json()["error"]["code"] == "invalid_crop"
    assert upload(client, make_image(), crop="").status_code == 400
    r = client.post("/api/predict", data={"crop": "tomato"}, headers=H)
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "missing_image"
    r = upload(client, io.BytesIO(b""), "e.jpg")
    assert r.status_code == 400


def test_missing_csrf_header_blocked(client):
    r = upload(client, make_image(), headers={})
    assert r.status_code == 403
    assert client.delete("/api/history").status_code == 403


def test_low_confidence_flags_result(app_factory):
    c = app_factory(StubPredictor(warnings=["low_confidence"], confidence=0.41)).test_client()
    res = upload(c, make_image()).get_json()["result"]
    assert res["reliable"] is False and "low_confidence" in res["warnings"]


def test_unknown_routes_return_json(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.get_json()["error"]["code"] == "not_found"
    assert client.put("/api/health", headers=H).status_code == 405


# ------------------------------------------------------- images & privacy
def test_image_only_visible_to_owner_session(app_factory):
    app = app_factory(StubPredictor())
    owner, other = app.test_client(), app.test_client()
    ref = upload(owner, make_image()).get_json()["result"]["image_ref"]
    assert owner.get(f"/api/image/{ref}").status_code == 200
    assert owner.get(f"/api/image/{ref}").mimetype == "image/jpeg"
    assert other.get(f"/api/image/{ref}").status_code == 404


@pytest.mark.parametrize("ref", ["..%2f..%2fetc%2fpasswd", "../app.py", "%2e%2e%2fapp.py", "abc.jpg", "x" * 32 + ".jpg"])
def test_path_traversal_blocked(client, ref):
    assert client.get(f"/api/image/{ref}").status_code == 404


def test_stored_image_is_reencoded_without_metadata(client, app_factory):
    app = app_factory(StubPredictor())
    c = app.test_client()
    ref = upload(c, make_image("PNG")).get_json()["result"]["image_ref"]
    path = os.path.join(app.config["UPLOAD_DIR"], ref)
    assert open(path, "rb").read(3) == b"\xff\xd8\xff"          # JPEG magic: always re-encoded
    assert ref.endswith(".jpg") and "leaf" not in ref


# ----------------------------------------------------------------- history
def test_history_save_list_delete_persist(app_factory):
    app = app_factory(StubPredictor())
    c = app.test_client()
    ref = upload(c, make_image()).get_json()["result"]["image_ref"]
    assert c.get("/api/history").get_json()["count"] == 0          # not saved until asked
    r = c.post("/api/history", json={"image_ref": ref}, headers=H)
    assert r.status_code == 201
    scan_id = r.get_json()["id"]
    scans = c.get("/api/history").get_json()["scans"]
    assert len(scans) == 1 and scans[0]["predicted_class"] == "tomato_early_blight"
    assert scans[0]["crop"] == "tomato" and 0 < scans[0]["confidence"] <= 1
    # saving twice is refused (pending entry consumed)
    assert c.post("/api/history", json={"image_ref": ref}, headers=H).status_code == 404
    # persists across app instances using the same database
    app2 = app_factory(StubPredictor())
    assert len(app2.test_client().get("/api/history").get_json()["scans"]) == 0   # other session: isolated
    # delete removes row and file
    path = os.path.join(app.config["UPLOAD_DIR"], ref)
    assert os.path.isfile(path)
    assert c.delete(f"/api/history/{scan_id}", headers=H).status_code == 200
    assert not os.path.exists(path)
    assert c.delete(f"/api/history/{scan_id}", headers=H).status_code == 404
    assert c.get("/api/history").get_json()["count"] == 0


def test_cannot_save_or_delete_other_sessions_scans(app_factory):
    app = app_factory(StubPredictor())
    a, b = app.test_client(), app.test_client()
    ref = upload(a, make_image()).get_json()["result"]["image_ref"]
    assert b.post("/api/history", json={"image_ref": ref}, headers=H).status_code == 404
    sid = a.post("/api/history", json={"image_ref": ref}, headers=H).get_json()["id"]
    assert b.delete(f"/api/history/{sid}", headers=H).status_code == 404
    assert a.get("/api/history").get_json()["count"] == 1


def test_clear_all_history(client):
    for _ in range(3):
        ref = upload(client, make_image()).get_json()["result"]["image_ref"]
        client.post("/api/history", json={"image_ref": ref}, headers=H)
    assert client.get("/api/history").get_json()["count"] == 3
    assert client.delete("/api/history", headers=H).get_json()["deleted_count"] == 3
    assert client.get("/api/history").get_json()["count"] == 0


def test_sql_injection_attempt_is_harmless(client):
    assert client.post("/api/history", json={"image_ref": "'; DROP TABLE scans;--"}, headers=H).status_code == 404
    assert client.get("/api/history").status_code == 200


# --------------------------------------------------------------- diseases
def test_diseases_without_model_marked_as_dataset_config(client_nomodel):
    d = client_nomodel.get("/api/diseases").get_json()
    assert d["model_available"] is False and d["source"] == "dataset_config"
    assert {x["crop"] for x in d["diseases"]} == {"tomato", "potato"}


def test_diseases_follow_model_classes(client):
    d = client.get("/api/diseases").get_json()
    assert d["source"] == "model"
    assert {x["class_key"] for x in d["diseases"]} == set(StubPredictor.classes)
    assert [x["crop"] for x in client.get("/api/diseases?crop=potato").get_json()["diseases"]] == ["potato"]
    assert client.get("/api/diseases?crop=wheat").status_code == 400


# ------------------------------------------------------------------- pages
@pytest.mark.parametrize("path", ["/", "/detect", "/results", "/diseases", "/history", "/about"])
def test_pages_render(client, path):
    r = client.get(path)
    assert r.status_code == 200 and b"KisanLens" in r.data
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]


def test_404_page(client):
    assert client.get("/nope").status_code == 404


def test_session_cookie_flags(client):
    client.get("/api/history")
    cookie = client.get_cookie("session")
    assert cookie is not None and cookie.http_only and cookie.same_site == "Lax"
