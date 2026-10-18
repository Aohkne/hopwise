"""Helper dùng chung để truy vấn Wikidata / Wikimedia Commons.

Chỉ dùng thư viện chuẩn để không phải cài thêm dependency.
Mọi request đều khai báo User-Agent định danh theo yêu cầu của Wikimedia.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "JEV-KG-Research/0.1 (khoalh.dev@gmail.com)"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
ENTITY_DATA = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"

# Wikidata giới hạn độ dài URL cho GET; chia VALUES thành từng lô nhỏ.
BATCH_SIZE = 150


def _get(url: str, headers: dict[str, str], retries: int = 4, timeout: int = 120) -> bytes:
    """GET có retry + backoff. Ném lỗi nếu hết lượt thử — không nuốt lỗi âm thầm."""
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as err:
            last_err = err
            # 429/503 là tín hiệu bị rate-limit -> chờ lâu hơn
            wait = 2 ** attempt * 2
            print(f"    [retry {attempt + 1}/{retries}] {err} -> chờ {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"Request thất bại sau {retries} lần: {url[:120]}") from last_err


def sparql(query: str) -> list[dict]:
    """Chạy SPARQL, trả về list dict đã phẳng hoá (mỗi key -> giá trị chuỗi)."""
    url = SPARQL_ENDPOINT + "?" + urllib.parse.urlencode({"query": query})
    raw = _get(url, {"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT})
    data = json.loads(raw)
    rows = []
    for binding in data["results"]["bindings"]:
        rows.append({k: v["value"] for k, v in binding.items()})
    return rows


def sparql_batched(query_template: str, values: list[str], placeholder: str = "{VALUES}") -> list[dict]:
    """Chạy 1 query nhiều lần theo lô, ghép kết quả.

    query_template phải chứa placeholder để chèn khối `VALUES ?x { wd:Q1 wd:Q2 }`.
    """
    out: list[dict] = []
    for i in range(0, len(values), BATCH_SIZE):
        chunk = values[i : i + BATCH_SIZE]
        block = " ".join(f"wd:{q}" for q in chunk)
        out.extend(sparql(query_template.replace(placeholder, block)))
        print(f"    ...lô {i // BATCH_SIZE + 1}/{(len(values) - 1) // BATCH_SIZE + 1} -> tổng {len(out)} dòng")
        time.sleep(1)  # lịch sự với endpoint công cộng
    return out


def entity_json(qid: str) -> dict:
    """Lấy toàn bộ claim của một entity Wikidata."""
    raw = _get(ENTITY_DATA.format(qid=qid), {"User-Agent": USER_AGENT})
    return json.loads(raw)["entities"][qid]


def commons_url(name_or_url: str) -> str:
    """Chuẩn hoá về URL ảnh Commons (Special:FilePath redirect tới upload.wikimedia.org).

    Nhận cả tên file thuần ("Hoang Thinh.png") lẫn URL đầy đủ do SPARQL trả về
    (đã percent-encode sẵn). Phải unquote trước khi quote lại, nếu không sẽ bị
    double-encode ("%20" -> "%2520") và link chết.
    """
    filename = name_or_url.rsplit("/", 1)[-1]
    filename = urllib.parse.unquote(filename)
    return "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(filename.replace(" ", "_"))


def qid_of(uri: str) -> str:
    """http://www.wikidata.org/entity/Q123 -> Q123"""
    return uri.rsplit("/", 1)[-1]


def slug(qid: str, name: str) -> str:
    """id node: dùng QID làm khoá chính để MERGE idempotent, kèm tên cho dễ đọc."""
    base = "".join(c if c.isalnum() else "_" for c in (name or "").lower()).strip("_")
    base = "_".join(filter(None, base.split("_")))[:40]
    return f"{qid}_{base}" if base else qid


def check_url_alive(url: str, timeout: int = 20, retries: int = 3) -> bool:
    """Kiểm tra link ảnh còn sống. Có retry + fallback GET vì CDN Wikimedia
    đôi khi chặn/giới hạn HEAD request từ IP dùng chung (VD CI), gây dương
    tính giả — một lần fail không có nghĩa link thật sự chết.
    """
    for attempt in range(retries):
        for method in ("HEAD", "GET"):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method=method)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return 200 <= resp.status < 400
            except urllib.error.HTTPError as err:
                if err.code == 405 and method == "HEAD":
                    continue  # server không hỗ trợ HEAD -> thử GET ngay
                if err.code not in (429, 503):
                    return False  # 404/403... link thật sự hỏng, không cần retry
            except Exception:
                pass
        if attempt < retries - 1:
            time.sleep(2 ** attempt)
    return False
