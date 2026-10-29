# Persisted Indexes Directory

This directory stores persisted local vector embeddings, TF-IDF matrices, and structured inverted indexes built from the ingested catalogue.

Index files cached here allow fast CPU cold starts without rebuilding embeddings on every server restart.
