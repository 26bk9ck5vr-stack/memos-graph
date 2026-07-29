"""FAISS Acceleration - 向量搜索加速"""

import numpy as np
import logging
from typing import List, Tuple, Any

logger = logging.getLogger(__name__)

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS not available")


class FAISSAccelerator:
    """FAISS 向量搜索加速器"""
    
    def __init__(self, dimension: int = 1024, index_type: str = "IVF", nlist: int = 100):
        self.dimension = dimension
        self.index_type = index_type
        self.nlist = nlist
        self.index = None
        self.id_map = {}
        self._size = 0
        
        if FAISS_AVAILABLE:
            self._init_index()
            logger.info(f"FAISSAccelerator initialized (dim={dimension})")
    
    def _init_index(self):
        """Initialize FAISS index"""
        if not FAISS_AVAILABLE:
            return
        
        if self.index_type == "IVF":
            quantizer = faiss.IndexFlatL2(self.dimension)
            self.index = faiss.IndexIVFFlat(quantizer, self.dimension, self.nlist, faiss.METRIC_INNER_PRODUCT)
        else:
            self.index = faiss.IndexFlatIP(self.dimension)
    
    def add(self, vectors: np.ndarray, ids: List[Any]):
        """Add vectors to index"""
        if not FAISS_AVAILABLE or self.index is None:
            return
        
        if not self.index.is_trained:
            self.index.train(vectors)
        
        n = len(vectors)
        faiss_ids = np.arange(self._size, self._size + n, dtype=np.int64)
        self.index.add(vectors)
        
        for fid, oid in zip(faiss_ids, ids):
            self.id_map[int(fid)] = oid
        
        self._size += n
        logger.info(f"Added {n} vectors, total {self._size}")
    
    def search(self, query_vector: np.ndarray, top_k: int = 10) -> List[Tuple[Any, float]]:
        """Search similar vectors"""
        if not FAISS_AVAILABLE or self.index is None:
            return []
        
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)
        
        distances, indices = self.index.search(query_vector, top_k)
        
        results = []
        for fid, dist in zip(indices[0], distances[0]):
            if fid >= 0 and fid in self.id_map:
                results.append((self.id_map[fid], float(dist)))
        
        return results
    
    @property
    def size(self) -> int:
        return self._size


if __name__ == "__main__":
    print("FAISS Accelerator loaded")
    print(f"FAISS available: {FAISS_AVAILABLE}")
