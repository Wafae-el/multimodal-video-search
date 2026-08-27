from pathlib import Path
import subprocess


class FrameExtractor:

    def extract(
        self,
        video_path: Path,
        timestamp_ms: int,
        output_path: Path,
    ):

        seconds = timestamp_ms / 1000

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(seconds),
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )

        return output_path