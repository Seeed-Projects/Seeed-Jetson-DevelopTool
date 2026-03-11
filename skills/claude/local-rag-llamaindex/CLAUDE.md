---
name: local-rag-llamaindex
description: Deploy a local RAG chatbot on Jetson using LlamaIndex + ChromaDB + quantized Llama2-7b (MLC). Uses jetson-containers Docker environment. Requires Jetson with ≥16GB RAM and JetPack 5.1+.
---

# Local RAG with LlamaIndex

A local Retrieval-Augmented Generation chatbot running entirely on Jetson. Uses the
jetson-containers Docker environment, ChromaDB as the vector store, and a quantized
Llama2-7b (MLC q4f16) model for inference.

Hardware: reComputer Jetson with ≥16GB RAM
Prerequisites: JetPack 5.1+, Docker installed and running

---

## Execution model

Run one phase at a time. After each phase:
- Relay all output lines to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Phase 1 — setup  (~2 min)

Clone jetson-containers and install its Python tooling.

```bash
git clone --depth=1 https://github.com/dusty-nv/jetson-containers
cd jetson-containers
pip install -r requirements.txt
```

Expected: pip install completes without errors. `[OK]`

---

## Phase 2 — clone  (~1 min)

Clone the RAG project into the jetson-containers data directory.

```bash
cd jetson-containers/data
git clone https://github.com/Seeed-Projects/RAG_based_on_Jetson.git
```

Expected: `RAG_based_on_Jetson/` directory created. `[OK]`

---

## Phase 3 — model  (varies, depends on network)

Install git-lfs and clone the quantized Llama2-7b model weights.

```bash
sudo apt-get install git-lfs
git lfs install
cd jetson-containers/data/RAG_based_on_Jetson
git clone https://huggingface.co/JiahaoLi/llama2-7b-MLC-q4f16-jetson-containers
```

Expected: model directory `llama2-7b-MLC-q4f16-jetson-containers/` populated with weight files. `[OK]`

---

## Phase 4 — run  (inside Docker container)

Launch the MLC container, install dependencies inside it, then start the RAG app.

```bash
# From the jetson-containers root:
cd jetson-containers
./run.sh $(./autotag mlc)
```

Once inside the container shell:

```bash
cd data/RAG_based_on_Jetson/
pip install -r requirements.txt
pip install chromadb==0.3.29
python3 RAG.py
```

> Note: `pip install chromadb==0.3.29` may print dependency conflict warnings — these are
> ignorable as long as the install completes and `RAG.py` starts successfully.

Expected: RAG chatbot starts and accepts queries in the terminal. `[OK]`

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| git clone fails (jetson-containers or RAG repo) | Check network connectivity. Re-run the clone command — it is safe to retry. |
| Docker not found / `./run.sh` permission denied | Confirm Docker is installed: `docker --version`. Add user to docker group: `sudo usermod -aG docker $USER` then log out/in. |
| `./autotag mlc` returns no image | Run `./autotag mlc` standalone to see available tags. Pull manually: `docker pull dustynv/mlc:r35.x.x` matching your L4T version. |
| model clone fails — git-lfs not initialised | Run `git lfs install` after `sudo apt-get install git-lfs`, then retry the clone. |
| model clone fails — network/HuggingFace timeout | Retry. For slow connections add `GIT_LFS_SKIP_SMUDGE=1` to clone first, then `git lfs pull`. |
| chromadb install errors (inside container) | Dependency conflict warnings from chromadb==0.3.29 are ignorable. Only stop if `import chromadb` fails when running `RAG.py`. |
| `RAG.py` crashes — CUDA OOM | Confirm board has ≥16GB RAM. Close other GPU workloads and retry. |

---

## Reference files

- `references/source.body.md` — original tutorial article (background reading, not required for execution)
