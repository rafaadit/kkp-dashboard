"""Downloader TradeMap (ITC) — unduh file data + catat lineage + panggil pipeline.

Pembagian tugas:
  * Downloader  : mengambil file TradeMap (HTTP/API ITC atau fixture lokal),
                  menyimpannya ke TRADEMAP_DOWNLOAD_DIR, dan mencatat lineage
                  (automation_jobs 'trademap_download' + automation_download_logs).
  * Processor   : pipeline parsing -> mapping -> validasi -> trademap_trade
                  (TradeMapProcessor). Downloader TIDAK menulis data pasar
                  sendiri — ia menyerahkan file ke processor untuk diproses.

Mode fixture (--fixture path) memungkinkan pengujian tanpa API key nyata;
tanpa API key dan tanpa fixture, job ditandai FAILED (tidak crash).

Directori tujuan dibaca dari env TRADEMAP_DOWNLOAD_DIR (default ./data/trademap).
URL API dibaca dari env TRADEMAP_API_URL (default https://www.trademap.org).
"""
import hashlib
import json
import os
import shutil
import uuid
import urllib.error
import urllib.request

from backend.db import get_connection


class DownloadError(RuntimeError):
    """Error unduhan/validasi yang harus ditandai FAILED di lineage."""


def _sha256(path, chunk=1 << 16):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


class TradeMapDownloader:
    """Unduh file TradeMap dan catat automation_jobs + automation_download_logs."""

    def __init__(self, conn=None):
        self._conn = conn
        self._owns_conn = conn is None

    def _connect(self):
        if self._conn is None:
            self._conn = get_connection()
        return self._conn

    def close(self):
        if self._conn is not None and self._owns_conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    @staticmethod
    def download_dir():
        return os.environ.get("TRADEMAP_DOWNLOAD_DIR", "./data/trademap")

    @staticmethod
    def api_base():
        return os.environ.get("TRADEMAP_API_URL", "https://www.trademap.org").rstrip("/")

    @staticmethod
    def target_name(flow, year, partner=None):
        return "trademap_%s_%s_%s.csv" % (flow.lower(), year, (partner or "world").lower())

    def target_path(self, flow, year, partner=None):
        d = self.download_dir()
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        return os.path.join(d, self.target_name(flow, year, partner))

    @staticmethod
    def build_url(base, api_key, flow, year, partner=None):
        """Bangun URL unduhan API ITC (token + reporter Indonesia).

        Catatan: jalur endpoint persis mengikuti dokumentasi API TradeMap yang
        berlaku saat API key diprovisi (base tetap dari TRADEMAP_API_URL).
        """
        import urllib.parse

        qs = urllib.parse.urlencode({
            "token": api_key,
            "reporter": "ID",
            "flow": flow,
            "year": year,
            "partner": partner or "",
            "output": "csv",
        })
        return f"{base}/trademap_download?{qs}"

    def fetch(self, url, out_path):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                data = resp.read()
        except urllib.error.URLError as e:
            raise DownloadError(f"unduh gagal: {e}") from e
        with open(out_path, "wb") as fh:
            fh.write(data)
        return out_path

    # ------------------------------------------------------------------
    def run(self, flow="Export", year=None, partner=None, source="TradeMap ITC",
            fixture=None, process=True, commit=False, job_id=None):
        """
        Jalankan satu sesi unduhan (+ opsional proses).

        Return: dict {ok, job_id, download_log_id, file_path, file_hash,
                      file_size, message}.
        """
        cur = self._connect().cursor()
        job_id = self._begin_job(cur, job_id, flow, year, partner, source, fixture, process)
        dl_id = self._insert_download_log(cur, job_id, flow, year, partner, source)
        try:
            if fixture:
                out = self.target_path(flow, year, partner)
                shutil.copyfile(fixture, out)
                url = os.path.abspath(fixture)
            else:
                api_key = os.environ.get("TRADEMAP_API_KEY", "")
                if not api_key:
                    raise DownloadError("TRADEMAP_API_KEY kosong (isi di .env atau gunakan --fixture)")
                out = self.target_path(flow, year, partner)
                url = self.build_url(self.api_base(), api_key, flow, year, partner)
                self.fetch(url, out)
            size = os.path.getsize(out)
            fhash = _sha256(out)
            self._mark_downloaded(cur, dl_id, out, size, fhash)

            summary = {
                "ok": True,
                "job_id": job_id,
                "download_log_id": dl_id,
                "file_path": out,
                "file_hash": fhash,
                "file_size": size,
            }
            if process:
                from backend.trademap.processor import TradeMapProcessor

                proc = TradeMapProcessor()
                try:
                    res = proc.process(out, source=source, commit=commit,
                                       download_log_id=dl_id)
                finally:
                    proc.close()
                if not res.ok:
                    raise DownloadError(res.error or "proses gagal")
                summary["process_ok"] = True
                summary["raw_id"] = res.raw_id
                summary["process_job_id"] = res.job_id
                sqlv = self._connect().cursor()
                sqlv.execute(
                    "UPDATE automation_download_logs SET status='VALIDATED' WHERE id=%s",
                    (dl_id,))
                self._connect().commit()
            self._finish_job(cur, job_id, True, None)
            summary["message"] = "unduh sukses" + (" + proses selesai" if process else "")
            return summary
        except DownloadError as e:
            self._mark_failed(cur, job_id, dl_id, str(e))
            return {"ok": False, "job_id": job_id, "download_log_id": dl_id,
                    "error": str(e)}

    # --- lineage helpers -------------------------------------------------
    def _begin_job(self, cur, job_id, flow, year, partner, source, fixture, process):
        params = {"flow": flow, "year": year, "partner": partner, "source": source,
                  "fixture": os.path.basename(fixture) if fixture else None,
                  "process": process}
        if job_id is None:
            cur.execute(
                "INSERT INTO automation_jobs (job_type, status, params_json, "
                "correlation_id, started_at, attempts) "
                "VALUES ('trademap_download','RUNNING',%s,%s,NOW(),1)",
                (json.dumps(params, ensure_ascii=False), uuid.uuid4().hex))
            job_id = cur.lastrowid
            cur.execute(
                "INSERT INTO automation_job_logs (id_job, level, message) "
                "VALUES (%s,'info',%s)",
                (job_id, "mulai unduhan flow=%s year=%s partner=%s" % (flow, year, partner or "-")))
        else:
            cur.execute(
                "UPDATE automation_jobs SET status='RUNNING', started_at=NOW(), "
                "attempts=COALESCE(attempts,0)+1 WHERE id=%s", (job_id,))
            cur.execute(
                "INSERT INTO automation_job_logs (id_job, level, message) "
                "VALUES (%s,'info',%s)", (job_id, "resume unduhan dari antrian"))
        self._connect().commit()
        return job_id

    def _insert_download_log(self, cur, job_id, flow, year, partner, source):
        cur.execute(
            "INSERT INTO automation_download_logs (id_job, sumber, status) "
            "VALUES (%s,%s,'PENDING')",
            (job_id, "%s %s" % (source, year)))
        dl_id = cur.lastrowid
        self._connect().commit()
        return dl_id

    def _mark_downloaded(self, cur, dl_id, out, size, fhash):
        cur.execute(
            "UPDATE automation_download_logs SET status='DOWNLOADED', file_path=%s, "
            "file_name=%s, file_size=%s, file_hash=%s, downloaded_at=NOW() WHERE id=%s",
            (out, os.path.basename(out), size, fhash, dl_id))
        self._connect().commit()

    def _finish_job(self, cur, job_id, ok, error):
        if ok:
            cur.execute("UPDATE automation_jobs SET status='SUCCESS', finished_at=NOW() "
                        "WHERE id=%s", (job_id,))
            cur.execute(
                "INSERT INTO automation_job_logs (id_job, level, message) "
                "VALUES (%s,'info','unduhan selesai')", (job_id,))
        else:
            cur.execute("UPDATE automation_jobs SET status='FAILED', finished_at=NOW(), "
                        "error_message=%s WHERE id=%s", (error, job_id))
            cur.execute(
                "INSERT INTO automation_job_logs (id_job, level, message) "
                "VALUES (%s,'error',%s)", (job_id, error))
        self._connect().commit()

    def _mark_failed(self, cur, job_id, dl_id, error):
        cur.execute(
            "UPDATE automation_download_logs SET status='FAILED', error_message=%s "
            "WHERE id=%s", (error[:1000], dl_id))
        self._finish_job(cur, job_id, False, error)