from pathlib import Path

import packages.workflow.activities as activities
from packages.media.ffprobe_service import VideoMetadata
from packages.workflow.activities import AssetInfo


def _asset() -> AssetInfo:
    return AssetInfo(
        id=1,
        asset_id="asset-1",
        source_checksum="checksum",
        pipeline_version="v1",
        minio_bucket="media",
        minio_object_key="media-original/asset-1/original.mp4",
    )


def test_segment_media_manifest_is_time_aligned(monkeypatch, tmp_path):
    monkeypatch.setattr(
        activities,
        "download_original_video",
        lambda info, workdir: Path(workdir) / "original.mp4",
    )
    monkeypatch.setattr(
        activities,
        "analyze_video",
        lambda path: VideoMetadata(6.0, 10, "h264", 640, 360, has_audio=True),
    )
    monkeypatch.setattr(
        activities,
        "upload_json_manifest",
        lambda asset_id, name, path: {"bucket": "media", "object_key": f"manifests/{name}.json"},
    )

    result = activities._do_segment_media(_asset(), tmp_path)

    assert result["file_type"] == "segments_manifest"
    assert result["output_key"] == "manifests/segments.json"
    assert (tmp_path / "segments.json").read_text().count("start_ms") >= 2


def test_index_and_audio_quality_manifests_are_uploadable(monkeypatch, tmp_path):
    monkeypatch.setattr(
        activities,
        "upload_json_manifest",
        lambda asset_id, name, path: {"bucket": "media", "object_key": f"manifests/{name}.json"},
    )

    speech = activities._do_index_speech(_asset(), tmp_path)
    visual = activities._do_index_visual(_asset(), tmp_path)
    audio = activities._do_score_audio_quality(_asset(), tmp_path)

    assert speech["file_type"] == "speech_index_manifest"
    assert visual["file_type"] == "visual_index_manifest"
    assert audio["file_type"] == "audio_quality_manifest"
    assert "zero audio quality" in (tmp_path / "audio-quality.json").read_text()
