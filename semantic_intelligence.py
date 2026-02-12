# import numpy as np
# import shutil
# from pathlib import Path
# from sklearn.cluster import AgglomerativeClustering
# from sklearn.feature_extraction.text import TfidfVectorizer

# # Global state
# FILES = {}  # path -> {hash, embedding, text, cluster}

# # -----------------------------
# # Domain detection (top level)
# # -----------------------------
# DOMAIN_KEYWORDS = {
#     "StudyMaterial": ["ai", "machine learning", "ml", "deep learning", "neural"],
#     "Programming": ["code", "algorithm", "function", "class"],
#     "Finance": ["invoice", "tax", "bank", "account"],
#     "Legal": ["contract", "agreement", "law"]
# }

# def detect_domain(text):
#     text = text.lower()
#     for domain, words in DOMAIN_KEYWORDS.items():
#         if any(w in text for w in words):
#             return domain
#     return "General"

# # -----------------------------
# # Cluster naming
# # -----------------------------
# def name_cluster(file_paths):
#     texts = [FILES[p]["text"] for p in file_paths if p in FILES]
#     if not texts:
#         return "Misc"

#     tfidf = TfidfVectorizer(stop_words="english", max_features=5)
#     tfidf.fit(texts)
#     keywords = tfidf.get_feature_names_out()

#     return "_".join(keywords[:2]).title()

# # -----------------------------
# # Hierarchical clustering
# # -----------------------------
# def reorganize_files(root_dir):
#     file_paths = list(FILES.keys())

#     if len(file_paths) < 2:
#         print("[Semantic] Not enough files to cluster.")
#         return

#     embeddings = np.array([FILES[p]["embedding"] for p in file_paths])

#     clustering = AgglomerativeClustering(
#         n_clusters=None,
#         metric="cosine",
#         linkage="average",
#         distance_threshold=0.35
#     )

#     labels = clustering.fit_predict(embeddings)

#     # Assign clusters
#     clusters = {}
#     for path, label in zip(file_paths, labels):
#         FILES[path]["cluster"] = label
#         clusters.setdefault(label, []).append(path)

#     # Apply hierarchy + moves
#     for cluster_id, paths in clusters.items():
#         cluster_name = name_cluster(paths)
#         combined_text = " ".join(FILES[p]["text"] for p in paths)
#         domain = detect_domain(combined_text)

#         target_dir = Path(root_dir) / domain / cluster_name
#         target_dir.mkdir(parents=True, exist_ok=True)

#         for old_path in paths:
#             src = Path(old_path)
#             dst = target_dir / src.name

#             if src != dst:
#                 try:
#                     print(f"[Move] {src.name} → {domain}/{cluster_name}")
#                     shutil.move(str(src), str(dst))

#                     FILES[str(dst)] = FILES.pop(old_path)
#                     FILES[str(dst)]["cluster"] = cluster_id
#                 except Exception as e:
#                     print(f"[Move Error] {e}")

#     print("[Semantic] Hierarchical reorganization complete.")

# from pathlib import Path
# from collections import defaultdict

# def build_semantic_tree(root_dir):
#     """
#     Converts FILES dict into a tree structure for UI.
#     """
#     tree = {
#         "name": Path(root_dir).name,
#         "type": "root",
#         "children": []
#     }

#     domain_map = defaultdict(list)

#     for path, meta in FILES.items():
#         p = Path(path)
#         parts = p.relative_to(root_dir).parts

#         if len(parts) >= 3:
#             domain, cluster = parts[0], parts[1]
#         else:
#             domain, cluster = "Unsorted", "Files"

#         domain_map[(domain, cluster)].append(p.name)

#     domains = defaultdict(dict)
#     for (domain, cluster), files in domain_map.items():
#         domains[domain][cluster] = files

#     for domain, clusters in domains.items():
#         domain_node = {"name": domain, "type": "domain", "children": []}
#         for cluster, files in clusters.items():
#             cluster_node = {"name": cluster, "type": "cluster", "children": []}
#             for f in files:
#                 cluster_node["children"].append({
#                     "name": f,
#                     "type": "file"
#                 })
#             domain_node["children"].append(cluster_node)
#         tree["children"].append(domain_node)

#     return tree


import numpy as np
import shutil
import re
import requests
from pathlib import Path
from collections import defaultdict
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

# =============================
# Global state
# =============================
FILES = {}  # path -> {hash, embedding, text, cluster}

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:latest"

# =============================
# Helpers
# =============================
def clean_name(name, max_len=40):
    name = name.strip()
    name = re.sub(r'[^a-zA-Z0-9 _-]', '', name)
    name = name.replace(" ", "_")
    return name[:max_len] or "Misc"


def ollama_generate(prompt, max_chars=2000):
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt[:max_chars],
                "stream": False
            },
            timeout=60
        )
        return r.json()["response"].strip()
    except Exception as e:
        print("[Ollama Error]", e)
        return None

# =============================
# LLM Naming — Cluster
# =============================
def name_cluster_llm(file_paths):
    texts = [FILES[p]["text"] for p in file_paths if p in FILES]
    if not texts:
        return "Misc"

    combined = "\n".join(texts)[:2000]

    prompt = f"""
Create a short folder name describing the topic of these documents.

Rules:
- 3 to 6 words
- No punctuation
- Title Case
- Only output the name

Documents:
{combined}
"""

    out = ollama_generate(prompt)
    if out:
        return clean_name(out)

    return name_cluster_tfidf(file_paths)

# =============================
# LLM Naming — Domain (Top Level)
# =============================
def name_domain_llm(file_paths):
    texts = [FILES[p]["text"] for p in file_paths if p in FILES]
    if not texts:
        return "General"

    combined = "\n".join(texts)[:2000]

    prompt = f"""
Create a broad category name for these documents.

Rules:
- 1 to 3 words
- No punctuation
- Title Case
- Very general grouping label
- Only output the name

Documents:
{combined}
"""

    out = ollama_generate(prompt)
    if out:
        return clean_name(out)

    return "General"

# =============================
# TF-IDF fallback
# =============================
def name_cluster_tfidf(file_paths):
    texts = [FILES[p]["text"] for p in file_paths if p in FILES]
    if not texts:
        return "Misc"

    tfidf = TfidfVectorizer(stop_words="english", max_features=5)
    tfidf.fit(texts)
    keywords = tfidf.get_feature_names_out()
    return "_".join(keywords[:2]).title()

# =============================
# Hierarchical clustering
# =============================
def reorganize_files(root_dir):

    file_paths = list(FILES.keys())

    if len(file_paths) < 2:
        print("[Semantic] Not enough files to cluster.")
        return

    embeddings = np.array([FILES[p]["embedding"] for p in file_paths])

    clustering = AgglomerativeClustering(
        n_clusters=None,
        metric="cosine",
        linkage="average",
        distance_threshold=0.35
    )

    labels = clustering.fit_predict(embeddings)

    clusters = defaultdict(list)
    for path, label in zip(file_paths, labels):
        FILES[path]["cluster"] = label
        clusters[label].append(path)

    # ---------- LLM naming ----------
    for cluster_id, paths in clusters.items():

        cluster_name = name_cluster_llm(paths)
        domain_name = name_domain_llm(paths)

        target_dir = Path(root_dir) / domain_name / cluster_name
        target_dir.mkdir(parents=True, exist_ok=True)

        for old_path in paths:
            src = Path(old_path)
            dst = target_dir / src.name

            if src != dst:
                try:
                    print(f"[Move] {src.name} → {domain_name}/{cluster_name}")
                    shutil.move(str(src), str(dst))

                    FILES[str(dst)] = FILES.pop(old_path)
                    FILES[str(dst)]["cluster"] = cluster_id

                except Exception as e:
                    print("[Move Error]", e)

    print("[Semantic] LLM hierarchical reorganization complete.")

# =============================
# Semantic tree builder
# =============================
def build_semantic_tree(root_dir):

    tree = {
        "name": Path(root_dir).name,
        "type": "root",
        "children": []
    }

    domain_map = defaultdict(list)

    for path, meta in FILES.items():
        p = Path(path)
        parts = p.relative_to(root_dir).parts

        if len(parts) >= 3:
            domain, cluster = parts[0], parts[1]
        else:
            domain, cluster = "Unsorted", "Files"

        domain_map[(domain, cluster)].append(p.name)

    domains = defaultdict(dict)
    for (domain, cluster), files in domain_map.items():
        domains[domain][cluster] = files

    for domain, clusters in domains.items():
        domain_node = {"name": domain, "type": "domain", "children": []}

        for cluster, files in clusters.items():
            cluster_node = {"name": cluster, "type": "cluster", "children": []}

            for f in files:
                cluster_node["children"].append({
                    "name": f,
                    "type": "file"
                })

            domain_node["children"].append(cluster_node)

        tree["children"].append(domain_node)

    return tree
