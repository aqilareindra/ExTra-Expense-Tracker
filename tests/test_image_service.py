"""Unit test untuk validasi, orientasi EXIF, resize, dan kompresi gambar (M1.1)."""

import io

from PIL import Image, ImageDraw
import pytest

from backend.services import image_service
from backend.services.image_service import (
    ImageTooLargeError,
    InvalidImageError,
    MAX_IMAGE_WIDTH,
    MAX_UPLOAD_SIZE_BYTES,
    validate_and_compress_image,
)


def _create_receipt_like_image_bytes(
    width: int,
    height: int,
    fmt: str = "JPEG",
    mode: str = "RGB",
    exif_orientation: int | None = None,
) -> bytes:
    """Buat gambar sintetis menyerupai struk untuk pengujian kompresi dan konversi."""
    bg_color: tuple[int, ...] | int
    if mode == "RGBA":
        bg_color = (255, 255, 255, 0)
    elif mode == "LA":
        bg_color = (255, 0)
    elif mode in {"L", "P"}:
        bg_color = 255
    else:
        bg_color = (250, 250, 248)

    img = Image.new(mode if mode != "P" else "RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    line_color: tuple[int, ...] | int
    if img.mode == "RGBA":
        line_color = (25, 25, 25, 255)
    elif img.mode == "LA":
        line_color = (25, 255)
    elif img.mode == "L":
        line_color = 25
    else:
        line_color = (30, 30, 30)

    step = max(20, height // 40)
    for y in range(20, height - 20, step):
        draw.line([(20, y), (width - 20, y)], fill=line_color, width=3)

    if mode == "P":
        img = img.convert("P")

    buf = io.BytesIO()
    save_kwargs: dict[str, object] = {}
    if fmt.upper() == "JPEG":
        save_kwargs["quality"] = 100
        save_kwargs["subsampling"] = 0
    if exif_orientation is not None:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        save_kwargs["exif"] = exif.tobytes()

    img.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


class TestImageCompressionAndResize:
    """Pengujian resize proporsional, anti-upscale, orientasi EXIF, dan konversi RGBA."""

    def test_large_high_res_image_resized_to_1280_proportionally_and_shrunk(
        self,
    ) -> None:
        raw_bytes = _create_receipt_like_image_bytes(
            width=2560,
            height=3200,
            fmt="JPEG",
            mode="RGB",
        )

        compressed_bytes, target_mime = validate_and_compress_image(
            image_bytes=raw_bytes,
            filename="foto_struk_kamera.jpg",
            content_type="image/jpeg",
        )

        assert target_mime == "image/jpeg"
        assert len(compressed_bytes) < len(raw_bytes) * 0.6

        with Image.open(io.BytesIO(compressed_bytes)) as out_img:
            assert out_img.format == "JPEG"
            assert out_img.mode == "RGB"
            assert out_img.size == (MAX_IMAGE_WIDTH, 1600)

    @pytest.mark.parametrize(
        ("orig_width", "orig_height"),
        [
            (640, 960),
            (1280, 1600),
        ],
    )
    def test_small_or_exact_1280_image_is_not_upscaled(
        self,
        orig_width: int,
        orig_height: int,
    ) -> None:
        raw_bytes = _create_receipt_like_image_bytes(
            width=orig_width,
            height=orig_height,
            fmt="JPEG",
            mode="RGB",
        )

        compressed_bytes, target_mime = validate_and_compress_image(
            image_bytes=raw_bytes,
            filename="struk_kecil.jpeg",
            content_type="image/jpeg",
        )

        assert target_mime == "image/jpeg"
        with Image.open(io.BytesIO(compressed_bytes)) as out_img:
            assert out_img.format == "JPEG"
            assert out_img.mode == "RGB"
            assert out_img.size == (orig_width, orig_height)

    @pytest.mark.parametrize("png_mode", ["RGBA", "LA", "P"])
    def test_png_with_alpha_or_palette_converted_to_rgb_jpeg_safely(
        self,
        png_mode: str,
    ) -> None:
        raw_png = _create_receipt_like_image_bytes(
            width=500,
            height=700,
            fmt="PNG",
            mode=png_mode,
        )

        compressed_bytes, target_mime = validate_and_compress_image(
            image_bytes=raw_png,
            filename="struk_digital.png",
            content_type="image/png",
        )

        assert target_mime == "image/jpeg"
        assert compressed_bytes.startswith(image_service.JPEG_MAGIC_BYTES)

        with Image.open(io.BytesIO(compressed_bytes)) as out_img:
            assert out_img.format == "JPEG"
            assert out_img.mode == "RGB"
            assert out_img.size == (500, 700)
            # Area transparan di pojok kiri atas harus menjadi latar putih, bukan hitam
            r, g, b = out_img.getpixel((2, 2))
            assert r >= 245 and g >= 245 and b >= 245

    def test_exif_orientation_transposed_before_proportional_resize(self) -> None:
        # Gambar disimpan 3200x2560 dengan EXIF Orientation=6 (rotasi 90 CW -> 2560x3200)
        raw_rotated = _create_receipt_like_image_bytes(
            width=3200,
            height=2560,
            fmt="JPEG",
            mode="RGB",
            exif_orientation=6,
        )

        compressed_bytes, target_mime = validate_and_compress_image(
            image_bytes=raw_rotated,
            filename="kamera_portrait.jpg",
            content_type="image/jpeg",
        )

        assert target_mime == "image/jpeg"
        with Image.open(io.BytesIO(compressed_bytes)) as out_img:
            assert out_img.size == (1280, 1600)


class TestImageValidationErrors:
    """Pengujian penolakan file korup, non-gambar, ekstensi palsu, dan > 5 MB."""

    @pytest.mark.parametrize(
        ("filename", "content_type", "bad_bytes"),
        [
            ("catatan_palsu.jpg", "image/jpeg", b"Ini file .txt yang diganti jadi .jpg"),
            ("dokumen_palsu.png", "image/png", b"Bukan gambar PNG sama sekali"),
            (
                "korup_header.jpg",
                "image/jpeg",
                b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9",
            ),
            (
                "korup_terpotong.png",
                "image/png",
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02",
            ),
            ("kosong.jpg", "image/jpeg", b""),
        ],
    )
    def test_rejects_corrupt_or_renamed_non_image_files(
        self,
        filename: str,
        content_type: str,
        bad_bytes: bytes,
    ) -> None:
        with pytest.raises(InvalidImageError) as exc_info:
            validate_and_compress_image(
                image_bytes=bad_bytes,
                filename=filename,
                content_type=content_type,
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == "INVALID_FILE_TYPE"

    def test_rejects_mismatched_extension_or_mime_against_magic_bytes(self) -> None:
        valid_png = _create_receipt_like_image_bytes(100, 100, fmt="PNG", mode="RGB")

        with pytest.raises(InvalidImageError) as exc_info:
            validate_and_compress_image(
                image_bytes=valid_png,
                filename="salah_ekstensi.jpg",
                content_type="image/jpeg",
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == "INVALID_FILE_TYPE"

    def test_rejects_file_exceeding_5mb_with_413(self) -> None:
        oversized = b"\xff\xd8\xff" + (b"\x00" * MAX_UPLOAD_SIZE_BYTES)

        with pytest.raises(ImageTooLargeError) as exc_info:
            validate_and_compress_image(
                image_bytes=oversized,
                filename="terlalu_besar.jpg",
                content_type="image/jpeg",
            )

        assert exc_info.value.status_code == 413
        assert exc_info.value.error_code == "FILE_TOO_LARGE"
