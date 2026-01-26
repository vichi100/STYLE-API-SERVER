import os
import json
import glob
import logging
from typing import List, Dict, Any, Optional
import typing_extensions as typing

from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorScoreComponent(typing.TypedDict):
    criterion: str
    score: int
    rule_citation: str
    similarity: float

class VectorScoreResult(typing.TypedDict):
    total_score: int
    breakdown: List[VectorScoreComponent]
    critique: str

class VectorScoringService:
    def __init__(self, rules_dir: str = "rules_json", collection_name: str = "fashion_rules"):
        self.rules_dir = rules_dir
        self.collection_name = collection_name
        
        # Delayed Init
        self.client = None
        self.model = None

    def initialize(self):
        """
        Explicitly initializes the collection and ingests rules if needed.
        Should be called on server startup.
        """
        if not self.client:
             logger.info("Initializing Qdrant Client...")
             self.client = QdrantClient(path="qdrant_db")
        
        if not self.model:
             logger.info("Loading embedding model...")
             self.model = SentenceTransformer('all-MiniLM-L6-v2')
             
        self.init_collection()

    def init_collection(self):
        # Check if collection exists
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            logger.info(f"Creating collection '{self.collection_name}'...")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=384, # all-MiniLM-L6-v2 size
                    distance=models.Distance.COSINE
                )
            )
            # Auto-ingest on create
            self.ingest_rules()

    def ingest_rules(self):
        """
        Reads JSON rules, chunks them, and stores in Qdrant.
        """
        logger.info("Ingesting rules into Vector DB...")
        json_files = glob.glob(os.path.join(self.rules_dir, "*.json"))
        
        points = []
        point_id = 0
        
        for file_path in json_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    filename = os.path.basename(file_path)
                    
                    # Recursive chunking of JSON
                    chunks = self._flatten_json(data)
                    
                    for chunk in chunks:
                        text = f"Rule from {filename}: {chunk}"
                        vector = self.model.encode(text).tolist()
                        
                        points.append(models.PointStruct(
                            id=point_id,
                            vector=vector,
                            payload={"source": filename, "text": chunk}
                        ))
                        point_id += 1
                        
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")

        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            logger.info(f"Ingested {len(points)} rule chunks.")

    def _flatten_json(self, y: Any) -> List[str]:
        """
        Flattens JSON into meaningful text chunks.
        """
        out = []
        
        def flatten(x: Any, name: str = ''):
            if type(x) is dict:
                for a in x:
                    flatten(x[a], name + a + ': ')
            elif type(x) is list:
                for i, a in enumerate(x):
                     if type(a) is str:
                         out.append(name + a)
                     else:
                        flatten(a, name + str(i) + ': ')
            elif type(x) is str:
                 out.append(name + x)
            else:
                 out.append(name + str(x))

        flatten(y)
        return out

    def score_outfit_semantic(self, top: dict, bottom: dict, mood: str = None) -> VectorScoreResult:
        """
        Scores outfit based on semantic similarity to rules.
        """
        # 1. Construct Query
        outfit_desc = []
        if top:
            outfit_desc.append(f"Top: {top.get('custom_category')} ({top.get('specific_category')}) {top.get('tags')}")
        if bottom:
             outfit_desc.append(f"Bottom: {bottom.get('custom_category')} ({bottom.get('specific_category')}) {bottom.get('tags')}")
        if mood:
            outfit_desc.append(f"Target Occasion: {mood}")
            
        query_text = " ".join(outfit_desc)
        query_text = " ".join(outfit_desc)
        query_vector = self.model.encode(query_text).tolist()

        # Update: Calculate Mood-Outfit Similarity directly
        mood_penalty_multiplier = 1.0
        mood_similarity = 0.0
        
        if mood:
            from sentence_transformers import util
            # Vector for outfit items ONLY
            items_text = " ".join([d for d in outfit_desc if not d.startswith("Target Occasion")])
            items_vector = self.model.encode(items_text)
            
            # Vector for Mood
            mood_vector = self.model.encode(mood)
            
            # Cosine Similarity
            sim = util.cos_sim(items_vector, mood_vector).item()
            mood_similarity = sim
            
            # Penalty Logic
            # Similarity < 0.15 is typically a mismatch (e.g. "Gym" vs "Party")
            if sim < 0.15:
                mood_penalty_multiplier = 0.4 # Severe penalty (60% reduction)
                print(f"Severe Mood Mismatch detected. Sim: {sim}")
            elif sim < 0.25:
                mood_penalty_multiplier = 0.7 # Moderate penalty
            elif sim > 0.4:
                mood_penalty_multiplier = 1.1 # Small boost for good match
        
        # 2. Search Rules
        # Use query_points for newer client versions
        hits = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=5
        ).points
        
        # 3. Calculate Score based on Similarity
        # High similarity to "Good" rules = Good? 
        # Actually rules are neutral usually ("Do X"). 
        # If we find relevant rules, we assume compliance if text matches?
        # A simple proximity score: The more relevant rules we find, the more "principled" the outfit is?
        # Use a dynamic score based on cosine similarity
        
        total_score = 60 # Base
        breakdown = []
        
        for hit in hits:
            # Score contribution: 0.0 to 1.0 similarity mapped to points
            # 0.5+ is usually relevant
            relevance = hit.score
            points = 0
            
            # Simple heuristic: If relevance > 0.4, it's a relevant rule application
            if relevance > 0.3: 
                points = int(relevance * 10)
                total_score += points
                
            breakdown.append({
                "criterion": "Rule Relevance",
                "score": points,
                "rule_citation": hit.payload['text'],
                "similarity": relevance
            })
            
        final_score = min(100, total_score)
        
        # Apply Mood Penalty/Boost
        if mood_penalty_multiplier != 1.0:
            final_score = int(final_score * mood_penalty_multiplier)
            final_score = min(100, max(1, final_score))
            
        critique = f"Analyzed against semantically relevant rules. Top match: {hits[0].payload.get('text') if hits else 'None'}."
        
        if mood_penalty_multiplier < 0.8:
            critique += f" WARNING: Significant mismatch detected with occasion '{mood}' (Sim: {mood_similarity:.2f})."
        elif mood_penalty_multiplier > 1.0:
            critique += f" Great fit for occasion '{mood}'!"

        return {
            "total_score": final_score,
            "breakdown": breakdown,
            "critique": critique
        }

    def retrieve_relevant_rules(self, query_text: str, limit: int = 5) -> str:
        """
        Retrieves relevant rule text for RAG usage.
        Returns a formatted string of rules.
        """
        if not self.client:
             logger.warning("Vector Retrieval skipped: Client not initialized.")
             return ""

        target_vector = self.model.encode(query_text).tolist()
        
        try:
            hits = self.client.query_points(
                collection_name=self.collection_name,
                query=target_vector,
                limit=limit
            ).points
            
            context = ""
            for i, hit in enumerate(hits):
                context += f"Rule {i+1} (Source: {hit.payload.get('source')}): {hit.payload.get('text')}\\n"
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to retrieve rules: {e}")
            return "No specific rules retrieved."

    def retrieve_from_source(self, query_text: str, source_filename: str, limit: int = 3) -> str:
        """
        Retrieves rules ONLY from a specific source file (e.g. detailed color dict).
        """
        if not self.client: return ""
        
        target_vector = self.model.encode(query_text).tolist()
        
        try:
            # Qdrant Filter for source
            from qdrant_client.http import models as qmodels
            
            source_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="source",
                        match=qmodels.MatchValue(value=source_filename)
                    )
                ]
            )
            
            hits = self.client.query_points(
                collection_name=self.collection_name,
                query=target_vector,
                query_filter=source_filter,
                limit=limit
            ).points
            
            context = ""
            for i, hit in enumerate(hits):
                context += f"- {hit.payload.get('text')}\\n"
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to retrieve from source {source_filename}: {e}")
            return ""

# Singleton Instance
_vector_service_instance = None

def get_vector_service() -> VectorScoringService:
    global _vector_service_instance
    if _vector_service_instance is None:
        _vector_service_instance = VectorScoringService()
    return _vector_service_instance
