# Local MiniLM for unmet needs

The gap analysis first maps explicit customer requests to the frozen aspect and attribute dictionaries. It clusters remaining phrases with the official quantized ONNX export of `sentence-transformers/all-MiniLM-L6-v2`, pinned to revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. The CPU encoder uses the published attention-masked mean pooling and vector normalization. [Official model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/blob/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/README.md)

From the project checkout, install the optional runtime in its virtual environment and fetch the two checksum-verified files once.

```sh
.venv/bin/python -m pip install -r requirements-minilm.txt
.venv/bin/python -m market_intel.minilm
```

The files occupy about 23.5 MB in `data/models/all-MiniLM-L6-v2/`. Set `MARKET_INTEL_MINILM_PATH` to use another local directory with those same two files. The setup command can resume an incomplete installation.

Offline reports use KMeans with seed 42, ten initializations and a maximum of five clusters. A recurring free-text need requires two distinct reviews and pairwise cosine similarity of at least 0.60. Phrases without a sufficiently similar partner remain singletons. With fewer than two unresolved phrases, no semantic clustering is necessary. If the optional runtime or files are unavailable, a deterministic token-overlap method groups text at Jaccard similarity ≥0.50. The category report records the method used in `gaps.clustering_method`.
