"""
Vector Store Manager
Handles embeddings and vector search using Qdrant
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import uuid
import hashlib


class VectorStore:
    """Manages vector embeddings and semantic search"""
    
    def __init__(self, path: str = "./qdrant_data", collection_name: str = "neighborhood_knowledge"):
        self.client = QdrantClient(path=path)
        self.collection_name = collection_name
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')  # 384 dimensions
        self.vector_size = 384
        
        # Create collection if it doesn't exist
        self._ensure_collection_exists()
    
    def _ensure_collection_exists(self):
        """Create collection if it doesn't exist"""
        try:
            self.client.get_collection(self.collection_name)
        except:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )
            print(f"Created collection: {self.collection_name}")
    
    def generate_id(self, text: str, metadata: Dict) -> str:
        """Generate consistent ID for a document"""
        # Use URL or source as unique identifier
        unique_string = metadata.get('url', '') + text[:100]
        return hashlib.md5(unique_string.encode()).hexdigest()
    
    def add_document(self, text: str, metadata: Dict) -> str:
        """Add a single document to the vector store"""
        # Generate embedding
        vector = self.encoder.encode(text).tolist()
        
        # Generate ID
        doc_id = self.generate_id(text, metadata)
        
        # Create point
        point = PointStruct(
            id=doc_id,
            vector=vector,
            payload={
                'text': text,
                'source': metadata.get('source', 'unknown'),
                'source_type': metadata.get('source_type', 'unknown'),
                'url': metadata.get('url', ''),
                'date': metadata.get('date', ''),
                'title': metadata.get('title', ''),
                'word_count': len(text.split()),
                **metadata
            }
        )
        
        # Upsert point
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        
        return doc_id
    
    def add_documents_batch(self, documents: List[Dict], progress_callback=None) -> List[str]:
        """Add multiple documents in batch"""
        points = []
        doc_ids = []
        
        for i, doc in enumerate(documents):
            text = doc['text']
            metadata = doc.get('metadata', {})
            
            # Generate embedding
            vector = self.encoder.encode(text).tolist()
            
            # Generate ID
            doc_id = self.generate_id(text, metadata)
            doc_ids.append(doc_id)
            
            # Create point
            point = PointStruct(
                id=doc_id,
                vector=vector,
                payload={
                    'text': text,
                    'source': metadata.get('source', 'unknown'),
                    'source_type': metadata.get('source_type', 'unknown'),
                    'url': metadata.get('url', ''),
                    'date': metadata.get('date', ''),
                    'title': metadata.get('title', ''),
                    'word_count': len(text.split()),
                    **metadata
                }
            )
            points.append(point)
            
            if progress_callback:
                progress_callback(i + 1, len(documents))
        
        # Batch upsert
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        return doc_ids
    
    def search(self, query: str, top_k: int = 5, filter_dict: Optional[Dict] = None) -> List[Dict]:
        """Search for relevant documents"""
        # Generate query embedding
        query_vector = self.encoder.encode(query).tolist()
        
        # Search
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=filter_dict
        )
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                'id': result.id,
                'score': result.score,
                'text': result.payload.get('text', ''),
                'source': result.payload.get('source', ''),
                'source_type': result.payload.get('source_type', ''),
                'url': result.payload.get('url', ''),
                'title': result.payload.get('title', ''),
                'date': result.payload.get('date', ''),
                'metadata': result.payload
            })
        
        return formatted_results
    
    def get_stats(self) -> Dict:
        """Get collection statistics"""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                'total_documents': info.points_count,
                'vector_size': info.config.params.vectors.size,
                'distance_metric': info.config.params.vectors.distance
            }
        except:
            return {'total_documents': 0}
    
    def delete_by_source(self, source: str):
        """Delete all documents from a specific source"""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="source",
                        match=MatchValue(value=source)
                    )
                ]
            )
        )
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if len(chunk.split()) > 50:  # Only keep substantial chunks
                chunks.append(chunk)
        
        return chunks


# Example usage
if __name__ == "__main__":
    store = VectorStore()
    
    # Add a document
    doc_id = store.add_document(
        text="The Select Board meeting discussed the new bike lane proposal on Beacon Street.",
        metadata={
            'source': 'Town Meeting',
            'source_type': 'youtube',
            'url': 'https://youtube.com/watch?v=example',
            'date': '2024-01-15',
            'title': 'Select Board Meeting - January 15, 2024'
        }
    )
    
    # Search
    results = store.search("bike lanes", top_k=3)
    for r in results:
        print(f"Score: {r['score']:.3f} - {r['title']}")
        print(f"Text: {r['text'][:100]}...")
