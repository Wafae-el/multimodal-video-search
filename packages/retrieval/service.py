from packages.retrieval.embedder import TextEmbedder
from packages.retrieval.bm25 import BM25Index

from packages.retrieval.fusion import (
    reciprocal_rank_fusion,
    aggregate_neighboring_audio_hits,
    multimodal_reciprocal_rank_fusion,
)

from packages.retrieval.qdrant_store import QdrantStore
from packages.retrieval.audio_qdrant_store import AudioQdrantStore
from packages.retrieval.visual_qdrant_store import VisualQdrantStore

from packages.audio.clap_encoder import CLAPAudioEncoder
from packages.visual.openclip_encoder import OpenCLIPVisualEncoder


class HybridRetrievalService:

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
    ):

        # ==================================================
        # TEXT
        # ==================================================

        self.embedder = TextEmbedder()

        self.qdrant = QdrantStore(
            url=qdrant_url,
            vector_size=self.embedder.dimension,
        )

        self.bm25 = BM25Index()

        self._restore_bm25()

        # ==================================================
        # AUDIO
        # ==================================================

        self.audio_encoder = CLAPAudioEncoder(
            model_name="laion/clap-htsat-unfused",
            device="cpu",
        )

        self.audio_qdrant = AudioQdrantStore(
            url=qdrant_url,
            vector_size=self.audio_encoder.dimension,
        )

        # ==================================================
        # VISUAL
        # ==================================================

        self.visual_encoder = OpenCLIPVisualEncoder(
            model_name="ViT-B-32",
            pretrained="openai",
            device="cpu",
        )

        self.visual_qdrant = VisualQdrantStore(
            url=qdrant_url,
            vector_size=self.visual_encoder.dimension,
        )

    # ======================================================
    # TEXT INDEXING
    # ======================================================

    def index(
        self,
        chunks: list,
        video_id: int | None = None,
        language: str | None = None,
    ) -> None:

        if not chunks:
            return

        texts = [
            chunk.normalized_text
            for chunk in chunks
        ]

        embeddings = self.embedder.embed(
            texts
        )

        self.qdrant.create_collection()

        self.qdrant.upsert_chunks(
            chunks=chunks,
            embeddings=embeddings,
            video_id=video_id,
            language=language,
        )

        self.bm25.build(chunks)

    # ======================================================
    # TEXT SEARCH
    # ======================================================

    def search_text(
        self,
        query: str,
        limit: int = 5,
    ):

        if not query.strip():
            raise ValueError(
                "Query cannot be empty"
            )

        query_vector = (
            self.embedder.embed_one(
                query
            )
        )

        dense_results = self.qdrant.search(
            query_vector,
            limit=limit,
        )

        try:
            sparse_results = self.bm25.search(
                query,
                limit=limit,
            )
        except RuntimeError:
            sparse_results = []

        fused = reciprocal_rank_fusion(
            dense_results=dense_results,
            sparse_results=sparse_results,
            limit=limit,
        )

        return {
            "query": query,
            "dense": dense_results,
            "sparse": sparse_results,
            "fused": fused,
        }

    # ======================================================
    # MULTIMODAL SEARCH
    # ======================================================

    def search_multimodal(
        self,
        query: str,
        limit: int = 5,
    ):

        if not query.strip():
            raise ValueError(
                "Query cannot be empty"
            )

        # --------------------------------------------------
        # TEXT EMBEDDING
        # --------------------------------------------------

        text_vector = (
            self.embedder.embed_one(
                query
            )
        )

        # --------------------------------------------------
        # CLAP TEXT EMBEDDING
        # --------------------------------------------------

        audio_vector = (
            self.audio_encoder.encode_text(
                query
            )
        )

        # --------------------------------------------------
        # OPENCLIP TEXT EMBEDDING
        # --------------------------------------------------

        visual_vector = (
            self.visual_encoder.encode_text(
                query
            )
        )

        # --------------------------------------------------
        # TEXT DENSE
        # --------------------------------------------------

        text_dense = self.qdrant.search(
            text_vector,
            limit=limit,
        )

        # --------------------------------------------------
        # BM25
        # --------------------------------------------------

        try:
            text_sparse = self.bm25.search(
                query,
                limit=limit,
            )
        except RuntimeError:
            text_sparse = []

        # --------------------------------------------------
        # AUDIO
        # --------------------------------------------------

        audio_raw = self.audio_qdrant.search(
            audio_vector,
            limit=limit * 3,
        )

        # --------------------------------------------------
        # AUDIO NEIGHBOR AGGREGATION
        # --------------------------------------------------

        audio_results = (
            aggregate_neighboring_audio_hits(
                audio_results=audio_raw,
                max_gap_ms=2500,
                limit=limit,
            )
        )

        # --------------------------------------------------
        # VISUAL
        # --------------------------------------------------

        visual_results = (
            self.visual_qdrant.search(
                visual_vector,
                limit=limit,
            )
        )

        # --------------------------------------------------
        # TEXT INTERNAL FUSION
        # --------------------------------------------------

        text_fused = reciprocal_rank_fusion(
            dense_results=text_dense,
            sparse_results=text_sparse,
            limit=limit,
        )

        # --------------------------------------------------
        # MULTIMODAL FUSION
        # --------------------------------------------------

        multimodal = (
            multimodal_reciprocal_rank_fusion(
                text_results=text_dense,
                audio_results=audio_results,
                visual_results=visual_results,
                limit=limit,
            )
        )

        # --------------------------------------------------
        # RETURN
        # --------------------------------------------------

        return {
            "query": query,

            "text": {
                "dense": text_dense,
                "sparse": text_sparse,
                "fused": text_fused,
            },

            "audio": audio_results,

            "audio_raw": audio_raw,

            "visual": visual_results,

            "multimodal": multimodal,
        }

    # ======================================================
    # ALIAS
    # ======================================================

    def search(
        self,
        query: str,
        limit: int = 5,
    ):

        return self.search_multimodal(
            query=query,
            limit=limit,
        )

    # ======================================================
    # RESTORE BM25
    # ======================================================

    def _restore_bm25(self) -> None:
        """
        Rebuild the in-memory BM25 index from
        transcript payloads stored in Qdrant.
        """

        try:

            payloads = (
                self.qdrant.get_all_payloads()
            )

            if not payloads:
                return

            self.bm25.build_from_payloads(
                payloads
            )

            print(
                f"BM25 restored: "
                f"{len(payloads)} chunks"
            )

        except Exception as exc:

            print(
                f"BM25 restore skipped: {exc}"
            )