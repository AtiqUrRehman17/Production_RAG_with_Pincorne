"""Pinecone vector store, accessed through LangChain's PineconeVectorStore.

Each user gets their own Pinecone namespace. A search in one namespace can only
return that namespace's vectors, so users can never see each other's documents.

Chunk IDs look like "<document_id>:<chunk_index>", so all vectors of a document
can be found by ID prefix and deleted together.
"""

from functools import lru_cache

from langchain_core.documents import Document
from langchain_pinecone import PineconeVectorStore
from pinecone import NotFoundException, Pinecone, ServerlessSpec

from embeddings.gemini import get_embeddings
from utils.config import Settings, get_settings
from utils.exceptions import EmbeddingError, VectorStoreError
from utils.logger import get_logger

logger = get_logger(__name__)

TEXT_KEY = "text"  # metadata field where Pinecone keeps the chunk text
_UPSERT_BATCH_SIZE = 100
_DELETE_BATCH_SIZE = 1000  # Pinecone's limit for deleting by ID


class PineconeStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = Pinecone(api_key=settings.pinecone_api_key.get_secret_value())
        self._ensure_index()
        self.index = self._client.Index(settings.pinecone_index_name)
        self.vector_store = PineconeVectorStore(
            index=self.index, embedding=get_embeddings(), text_key=TEXT_KEY
        )

    def _ensure_index(self) -> None:
        """Create the index if it doesn't exist, and check its settings if it does."""
        name = self.settings.pinecone_index_name
        try:
            try:
                # One API call in the normal case where the index already exists
                description = self._client.describe_index(name)
            except NotFoundException:
                logger.info("Creating Pinecone index '%s'", name)
                self._client.create_index(
                    name=name,
                    dimension=self.settings.embedding_dimension,
                    metric=self.settings.pinecone_metric,
                    spec=ServerlessSpec(
                        cloud=self.settings.pinecone_cloud, region=self.settings.pinecone_region
                    ),
                )
                description = self._client.describe_index(name)
        except Exception as exc:
            raise VectorStoreError(
                "Could not connect to Pinecone. Check PINECONE_API_KEY and your internet connection."
            ) from exc

        if description.dimension != self.settings.embedding_dimension:
            raise VectorStoreError(
                f"Pinecone index '{name}' has dimension {description.dimension} but "
                f"EMBEDDING_DIMENSION is {self.settings.embedding_dimension}. They must match."
            )
        if description.metric != self.settings.pinecone_metric:
            raise VectorStoreError(
                f"Pinecone index '{name}' uses metric '{description.metric}' but "
                f"PINECONE_METRIC is '{self.settings.pinecone_metric}'."
            )

    def add_chunks(self, chunks: list[Document], namespace: str) -> int:
        ids = [chunk.metadata["chunk_id"] for chunk in chunks]
        try:
            self.vector_store.add_documents(
                chunks, ids=ids, namespace=namespace, batch_size=_UPSERT_BATCH_SIZE
            )
        except EmbeddingError:
            raise  # already has a clear message
        except Exception as exc:
            raise VectorStoreError("Could not save the document's chunks to Pinecone.") from exc
        logger.info("Stored %d chunks in namespace '%s'", len(ids), namespace)
        return len(ids)

    def list_chunk_ids(self, document_id: str, namespace: str) -> list[str]:
        ids: list[str] = []
        # list() pages through all IDs that start with the prefix
        for page in self.index.list(prefix=f"{document_id}:", namespace=namespace):
            ids.extend(page)
        return ids

    def delete_document(
        self, document_id: str, namespace: str, known_ids: list[str] | None = None
    ) -> int:
        """Delete all vectors of a document.

        Pinecone's ID listing can lag a few seconds behind recent writes, so pass
        `known_ids` (e.g. the IDs just written) to be sure those are deleted too.
        """
        try:
            ids = sorted(set(known_ids or []) | set(self.list_chunk_ids(document_id, namespace)))
            for start in range(0, len(ids), _DELETE_BATCH_SIZE):
                self.index.delete(ids=ids[start : start + _DELETE_BATCH_SIZE], namespace=namespace)
        except NotFoundException:
            # The namespace doesn't exist (yet): nothing of this user is stored, so nothing to delete
            logger.info("Nothing to delete for %s: namespace '%s' doesn't exist", document_id, namespace)
            return 0
        except Exception as exc:
            raise VectorStoreError(f"Could not delete document {document_id} from Pinecone.") from exc
        logger.info("Deleted %d chunks of %s from namespace '%s'", len(ids), document_id, namespace)
        return len(ids)

    def move_document(self, document_id: str, from_namespace: str, to_namespace: str, user_id: str) -> int:
        """Move a document's vectors to another user's namespace (nothing is embedded again).
        They are copied first and deleted after, so running it again after a failure is safe."""
        try:
            ids = self.list_chunk_ids(document_id, from_namespace)
            for start in range(0, len(ids), _UPSERT_BATCH_SIZE):
                fetched = self.index.fetch(ids=ids[start : start + _UPSERT_BATCH_SIZE], namespace=from_namespace)
                vectors = [(vector.id, vector.values, {**vector.metadata, "user_id": user_id})
                           for vector in fetched.vectors.values()]
                self.index.upsert(vectors=vectors, namespace=to_namespace, show_progress=False)
            for start in range(0, len(ids), _DELETE_BATCH_SIZE):
                self.index.delete(ids=ids[start : start + _DELETE_BATCH_SIZE], namespace=from_namespace)
        except Exception as exc:
            raise VectorStoreError(f"Could not move document {document_id} in Pinecone.") from exc
        logger.info("Moved %d chunks of %s from namespace '%s' to '%s'", len(ids), document_id,
                    from_namespace, to_namespace)
        return len(ids)

    def delete_namespace(self, namespace: str) -> None:
        """Delete every vector of a user (used when an account is deleted)."""
        try:
            self.index.delete(delete_all=True, namespace=namespace)
        except NotFoundException:
            pass  # the user never stored anything
        except Exception as exc:
            raise VectorStoreError(f"Could not delete namespace '{namespace}' from Pinecone.") from exc
        logger.info("Deleted namespace '%s'", namespace)

    def namespace_vector_count(self, namespace: str) -> int:
        stats = self.index.describe_index_stats()
        summary = stats.namespaces.get(namespace)
        return summary.vector_count if summary else 0


@lru_cache
def get_store() -> PineconeStore:
    return PineconeStore(get_settings())
