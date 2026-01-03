"""Entity extraction service for analyzing conversation content."""

from typing import List, Dict, Any, Tuple, Optional
import re
from collections import defaultdict


class EntityExtractionService:
    """Service for extracting entities from conversation text."""

    def __init__(self):
        """Initialize entity extraction service."""
        self.spacy_model = None
        self._init_spacy()

    def _init_spacy(self):
        """Initialize spaCy model if available."""
        try:
            import spacy
            # Try to load multilingual model first, then English model
            for model_name in ["zh_core_web_sm", "en_core_web_sm"]:
                try:
                    self.spacy_model = spacy.load(model_name)
                    print(f"Loaded spaCy model: {model_name}")
                    return
                except OSError:
                    continue

            print("No spaCy model found. Using fallback entity extraction.")
        except ImportError:
            print("spaCy not installed. Using fallback entity extraction.")

    def extract_entities(
        self,
        text: str,
        role: str = "user",
        extract_relationships: bool = True
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract entities and relationships from text.

        Args:
            text: Text to analyze
            role: Role of the speaker ('user' or 'assistant')
            extract_relationships: Whether to extract relationships

        Returns:
            Tuple of (entities, relationships)
        """
        if self.spacy_model:
            return self._extract_with_spacy(text, role, extract_relationships)
        else:
            return self._extract_with_fallback(text, role, extract_relationships)

    def _extract_with_spacy(
        self,
        text: str,
        role: str,
        extract_relationships: bool
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract entities using spaCy."""
        doc = self.spacy_model(text)

        entities = []
        entity_map = {}  # Map entity name to index

        # Extract named entities
        for ent in doc.ents:
            entity_type = self._map_spacy_entity_type(ent.label_)
            entity_name = ent.text.strip()

            if entity_name and len(entity_name) > 1:
                entity_dict = {
                    "entity_type": entity_type,
                    "entity_name": entity_name,
                    "description": f"{entity_type}: {entity_name} (mentioned in {role} message)"
                }
                entities.append(entity_dict)
                entity_map[entity_name.lower()] = len(entities) - 1

        # Extract key noun phrases as concepts
        for chunk in doc.noun_chunks:
            chunk_text = chunk.text.strip()
            # Only add if not already in entities and is meaningful
            if (chunk_text.lower() not in entity_map and
                len(chunk_text) > 2 and
                len(chunk_text.split()) <= 4):
                entities.append({
                    "entity_type": "concept",
                    "entity_name": chunk_text,
                    "description": f"Concept: {chunk_text}"
                })
                entity_map[chunk_text.lower()] = len(entities) - 1

        relationships = []
        if extract_relationships:
            relationships = self._extract_relationships_from_doc(doc, entities, entity_map)

        return entities, relationships

    def _extract_with_fallback(
        self,
        text: str,
        role: str,
        extract_relationships: bool
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Fallback entity extraction using patterns and keywords."""
        entities = []
        entity_map = {}

        # Extract technical terms (libraries, frameworks, tools)
        tech_keywords = [
            "Python", "Pandas", "NumPy", "Matplotlib", "Seaborn", "Scikit-learn",
            "TensorFlow", "PyTorch", "Django", "Flask", "FastAPI", "React", "Vue",
            "JavaScript", "TypeScript", "Java", "C++", "Go", "Rust", "SQL",
            "PostgreSQL", "MySQL", "MongoDB", "Redis", "Docker", "Kubernetes",
            "Git", "GitHub", "AWS", "Azure", "GCP", "Linux", "API", "REST",
            "GraphQL", "Machine Learning", "Deep Learning", "AI", "NLP", "CV"
        ]

        for keyword in tech_keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
                entity_name = keyword
                if entity_name.lower() not in entity_map:
                    entities.append({
                        "entity_type": "technology",
                        "entity_name": entity_name,
                        "description": f"Technology/Tool: {entity_name}"
                    })
                    entity_map[entity_name.lower()] = len(entities) - 1

        # Extract Chinese technical terms and concepts (common patterns)
        chinese_pattern = r'[\u4e00-\u9fff]{2,6}'
        chinese_matches = re.findall(chinese_pattern, text)

        # Common Chinese technical terms
        chinese_tech_terms = [
            "数据分析", "机器学习", "深度学习", "人工智能", "数据库",
            "前端", "后端", "全栈", "开发", "编程", "算法", "架构",
            "微服务", "容器化", "云计算", "大数据", "数据挖掘"
        ]

        for term in chinese_tech_terms:
            if term in text and term not in entity_map:
                entities.append({
                    "entity_type": "concept",
                    "entity_name": term,
                    "description": f"概念: {term}"
                })
                entity_map[term] = len(entities) - 1

        # Extract method/function names (camelCase or snake_case)
        methods = re.findall(r'\b([a-z_]+\([^\)]*\))', text)
        for method in methods:
            method_name = method.split('(')[0]
            if method_name and method_name not in entity_map:
                entities.append({
                    "entity_type": "method",
                    "entity_name": method_name,
                    "description": f"Method/Function: {method_name}"
                })
                entity_map[method_name] = len(entities) - 1

        relationships = []
        # Simple relationship extraction based on co-occurrence
        if extract_relationships and len(entities) > 1:
            for i in range(len(entities) - 1):
                for j in range(i + 1, min(i + 3, len(entities))):
                    relationships.append({
                        "source_entity_name": entities[i]["entity_name"],
                        "target_entity_name": entities[j]["entity_name"],
                        "relationship_type": "mentioned_with",
                        "weight": 1.0
                    })

        return entities, relationships

    def _map_spacy_entity_type(self, spacy_label: str) -> str:
        """Map spaCy entity labels to our entity types."""
        mapping = {
            "PERSON": "person",
            "ORG": "organization",
            "GPE": "location",
            "LOC": "location",
            "PRODUCT": "product",
            "EVENT": "event",
            "WORK_OF_ART": "work",
            "LAW": "law",
            "LANGUAGE": "language",
            "DATE": "date",
            "TIME": "time",
            "PERCENT": "metric",
            "MONEY": "metric",
            "QUANTITY": "metric",
            "ORDINAL": "metric",
            "CARDINAL": "metric",
        }
        return mapping.get(spacy_label, "concept")

    def _extract_relationships_from_doc(
        self,
        doc,
        entities: List[Dict[str, Any]],
        entity_map: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """Extract relationships from spaCy doc."""
        relationships = []

        # Extract relationships based on dependency parsing
        for token in doc:
            # Look for verb-based relationships
            if token.pos_ == "VERB":
                subjects = [child for child in token.children if child.dep_ in ("nsubj", "nsubjpass")]
                objects = [child for child in token.children if child.dep_ in ("dobj", "pobj", "attr")]

                for subj in subjects:
                    for obj in objects:
                        subj_text = subj.text.lower()
                        obj_text = obj.text.lower()

                        if subj_text in entity_map and obj_text in entity_map:
                            relationships.append({
                                "source_entity_name": entities[entity_map[subj_text]]["entity_name"],
                                "target_entity_name": entities[entity_map[obj_text]]["entity_name"],
                                "relationship_type": token.lemma_,
                                "weight": 1.5
                            })

        # Also add co-occurrence relationships for entities in same sentence
        for sent in doc.sents:
            sent_entities = []
            for ent in sent.ents:
                ent_text = ent.text.strip().lower()
                if ent_text in entity_map:
                    sent_entities.append(entities[entity_map[ent_text]]["entity_name"])

            # Create relationships between co-occurring entities
            for i in range(len(sent_entities) - 1):
                for j in range(i + 1, len(sent_entities)):
                    relationships.append({
                        "source_entity_name": sent_entities[i],
                        "target_entity_name": sent_entities[j],
                        "relationship_type": "co_occurs_with",
                        "weight": 1.0
                    })

        return relationships


# Singleton instance
_entity_extraction_service: Optional[EntityExtractionService] = None


def get_entity_extraction_service() -> EntityExtractionService:
    """Get entity extraction service singleton."""
    global _entity_extraction_service
    if _entity_extraction_service is None:
        _entity_extraction_service = EntityExtractionService()
    return _entity_extraction_service