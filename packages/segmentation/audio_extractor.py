import hashlib
import subprocess
from pathlib import Path

from packages.storage.minio_service import (
    upload_audio,
)


FFMPEG_TIMEOUT = 120


class AudioExtractionError(Exception):
    pass


def calculate_checksum(file_path: Path) -> str:
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)

    return sha256.hexdigest()


def extract_audio(
    asset_id: str,
    video_path: Path,
    workspace: Path,
):
    workspace.mkdir(
        parents=True,
        exist_ok=True,
    )

    audio_path = workspace / "source.wav"

    if audio_path.exists():
        checksum = calculate_checksum(audio_path)

        upload = upload_audio(
            asset_id,
            audio_path,
        )

        return {
            "path": audio_path,
            "checksum": checksum,
            **upload,
        }

    command = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(audio_path),
    ]

    try:
        subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=FFMPEG_TIMEOUT,
            check=True,
        )

    except subprocess.TimeoutExpired:
        raise AudioExtractionError(
            "FFMPEG_TIMEOUT"
        )

    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()[-500:]
        raise AudioExtractionError(
            f"AUDIO_EXTRACTION_FAILED: {stderr}"
        )

    if not audio_path.exists():
        raise AudioExtractionError(
            "AUDIO_NOT_CREATED"
        )

    checksum = calculate_checksum(audio_path)

    upload = upload_audio(
        asset_id,
        audio_path,
    )

    return {
        "path": audio_path,
        "checksum": checksum,
        **upload,
    }
