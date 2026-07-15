from pathlib import Path
import subprocess


def extract_audio(
    video_path: Path,
    output_dir: Path,
) -> Path:
    """
    Extract audio as PCM mono 16 kHz WAV.
    """

    output_dir.mkdir(exist_ok=True)

    audio_path = output_dir / f"{video_path.stem}.wav"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(audio_path),
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return audio_path