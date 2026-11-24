"""Skrip uji koneksi ke Google Gemini API menggunakan konfigurasi ExTra."""

import sys

try:
    from google import genai
    from google.genai import errors as genai_errors

    from backend.config import GEMINI_MODEL, ConfigurationError, get_gemini_api_key
except ImportError as exc:
    print(
        f"[ERROR] Dependensi belum terpasang ({exc}). "
        "Jalankan: pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> int:
    """Jalankan pengujian koneksi singkat ke Google Gemini API."""
    try:
        api_key = get_gemini_api_key()
    except ConfigurationError as exc:
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        return 1

    print(f"Menguji koneksi ke Google Gemini API (model: {GEMINI_MODEL})...")

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents='Balas hanya dengan kata "OK".',
        )
        reply_text = (response.text or "").strip()
        if not reply_text:
            print(
                f"[WARNING] Koneksi berhasil ke model '{GEMINI_MODEL}', "
                "tetapi respons teks kosong.",
                file=sys.stderr,
            )
            return 1

        print("Koneksi berhasil!")
        print(f"Model   : {GEMINI_MODEL}")
        print(f"Respons : {reply_text}")
        return 0
    except genai_errors.APIError as exc:
        print(
            f"[GEMINI API ERROR] Gagal memanggil model '{GEMINI_MODEL}': {exc}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # noqa: BLE001
        print(
            f"[CONNECTION ERROR] Gagal terhubung ke Google Gemini API: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
