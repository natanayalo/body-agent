from sentence_transformers import SentenceTransformer
import os

MODEL = os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

if MODEL != "__stub__":
    print(f"Downloading model {MODEL}...")
    SentenceTransformer(MODEL)
    print("Model downloaded.")
else:
    print("Skipping model download for __stub__ model.")
