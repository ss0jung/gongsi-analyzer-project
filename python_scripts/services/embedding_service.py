import chromadb
from chromadb.config import Settings
from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from models.schemas import DocumentChunk, EmbeddedChunk
from config import settings
import uuid
import json


class EmbeddingService:
    """Embedding and Vector Search Services"""

    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = settings.EMBEDDING_MODEL
        self.batch_size = settings.EMBEDDING_BATCH_SIZE

        # ChromaDB 초기화
        self.chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False),
        )

        # 컬렉션 생성 또는 가져오기
        try:
            self.collection = self.chroma_client.get_collection(
                name=settings.COLLECTION_NAME
            )
        except:
            self.collection = self.chroma_client.create_collection(
                name=settings.COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
            )

    async def embed_chunks(self, chunks: List[DocumentChunk]) -> List[EmbeddedChunk]:
        """청크들을 임베딩하여 벡터 DB에 저장"""
        embedded_chunks = []

        # 배치 단위로 처리
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            batch_embeddings = await self._create_embeddings(
                [chunk.content for chunk in batch]
            )

            for chunk, embedding in zip(batch, batch_embeddings):
                embedded_chunk = EmbeddedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    embedding=embedding,
                    metadata={
                        "chunk_type": chunk.chunk_type,
                        "section": chunk.section,
                        "page": chunk.page,
                        **chunk.metadata,
                    },
                )
                embedded_chunks.append(embedded_chunk)

        # ChromaDB에 저장
        await self._store_embeddings(embedded_chunks)

        return embedded_chunks

    async def _create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """OpenAI API로 임베딩 생성"""
        try:
            response = await self.openai_client.embeddings.create(
                input=texts, model=self.embedding_model
            )

            embeddings = [data.embedding for data in response.data]
            return embeddings

        except Exception as e:
            print(f"Error creating embeddings: {e}")
            # 실패 시 빈 벡터 반환
            return [[0.0] * 1536] * len(texts)  # text-embedding-3-small 차원수

    async def _store_embeddings(self, embedded_chunks: List[EmbeddedChunk]):
        """ChromaDB에 임베딩 저장"""
        try:
            ids = [chunk.chunk_id for chunk in embedded_chunks]
            embeddings = [chunk.embedding for chunk in embedded_chunks]
            documents = [chunk.content for chunk in embedded_chunks]
            metadatas = [chunk.metadata for chunk in embedded_chunks]

            # 배치로 저장
            self.collection.add(
                ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
            )

        except Exception as e:
            print(f"Error storing embeddings: {e}")

    async def search_similar_chunks(
        self,
        query: str,
        document_id: Optional[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.8,
    ) -> List[Tuple[DocumentChunk, float]]:
        """유사한 청크 검색"""
        try:
            # 쿼리 임베딩 생성
            query_embedding = await self._create_embeddings([query])

            # 검색 필터 설정
            where_filter = {}
            if document_id:
                where_filter["document_id"] = document_id

            # ChromaDB에서 검색
            results = self.collection.query(
                query_embeddings=query_embedding,
                where=where_filter if where_filter else None,
                n_results=top_k,
            )

            # 결과 파싱
            similar_chunks = []
            if results["documents"] and results["documents"][0]:
                for i, (doc, metadata, distance) in enumerate(
                    zip(
                        results["documents"][0],
                        results["metadatas"][0],
                        results["distances"][0],
                    )
                ):
                    # 거리를 유사도로 변환 (코사인 거리 -> 유사도)
                    similarity = 1 - distance

                    if similarity >= min_similarity:
                        chunk = DocumentChunk(
                            chunk_id=results["ids"][0][i],
                            document_id=metadata.get("document_id", ""),
                            content=doc,
                            chunk_type=metadata.get("chunk_type", "text"),
                            section=metadata.get("section", ""),
                            page=metadata.get("page"),
                            metadata=metadata,
                        )
                        similar_chunks.append((chunk, similarity))

            return similar_chunks

        except Exception as e:
            print(f"Error searching similar chunks: {e}")
            return []

    async def get_document_chunks(self, document_id: str) -> List[DocumentChunk]:
        """특정 문서의 모든 청크 조회"""
        try:
            results = self.collection.get(where={"document_id": document_id})

            chunks = []
            if results["documents"]:
                for i, (doc, metadata) in enumerate(
                    zip(results["documents"], results["metadatas"])
                ):
                    chunk = DocumentChunk(
                        chunk_id=results["ids"][i],
                        document_id=metadata.get("document_id", ""),
                        content=doc,
                        chunk_type=metadata.get("chunk_type", "text"),
                        section=metadata.get("section", ""),
                        page=metadata.get("page"),
                        metadata=metadata,
                    )
                    chunks.append(chunk)

            return chunks

        except Exception as e:
            print(f"Error getting document chunks: {e}")
            return []

    def delete_document(self, document_id: str):
        """문서 삭제"""
        try:
            # 해당 문서의 모든 청크 삭제
            results = self.collection.get(where={"document_id": document_id})

            if results["ids"]:
                self.collection.delete(ids=results["ids"])

        except Exception as e:
            print(f"Error deleting document: {e}")

    def get_collection_stats(self) -> Dict[str, Any]:
        """컬렉션 통계 정보"""
        try:
            count = self.collection.count()
            return {
                "total_chunks": count,
                "collection_name": settings.COLLECTION_NAME,
                "embedding_model": self.embedding_model,
            }
        except Exception as e:
            print(f"Error getting collection stats: {e}")
            return {}

    async def semantic_search_with_rerank(
        self, query: str, document_id: str, top_k: int = 10, rerank_top_k: int = 5
    ) -> List[Tuple[DocumentChunk, float]]:
        """의미 검색 + 리랭킹"""
        # 1차: 벡터 유사도 검색
        candidates = await self.search_similar_chunks(
            query=query, document_id=document_id, top_k=top_k, min_similarity=0.3
        )

        if not candidates:
            return []

        # 2차: 키워드 기반 리랭킹
        reranked = self._rerank_by_keywords(query, candidates)

        return reranked[:rerank_top_k]

    def _rerank_by_keywords(
        self, query: str, candidates: List[Tuple[DocumentChunk, float]]
    ) -> List[Tuple[DocumentChunk, float]]:
        """키워드 기반 리랭킹"""
        query_words = set(query.lower().split())

        scored_candidates = []
        for chunk, similarity in candidates:
            content_words = set(chunk.content.lower().split())

            # 키워드 매칭 점수
            keyword_score = len(query_words.intersection(content_words)) / len(
                query_words
            )

            # 최종 점수 = 벡터 유사도 * 0.7 + 키워드 점수 * 0.3
            final_score = similarity * 0.7 + keyword_score * 0.3

            scored_candidates.append((chunk, final_score))

        # 점수 순으로 정렬
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        return scored_candidates
