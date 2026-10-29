import os
import time
import math
import hashlib
import threading
from typing import Dict, Any, Optional, List, Tuple
import numpy as np

from app.core.logging_config import SafeLogger
from app.db.database import db
from app.ingestion.catalogue_loader import catalogue_loader
from app.retrieval.semantic_search import local_vector_index
from app.retrieval.adaptive_embeddings import embedding_manager, DocumentBuilder

DEFAULT_BATCH_SIZE = int(os.getenv("ACTIVATION_BATCH_SIZE", "100"))
MAX_RETRIES = int(os.getenv("ACTIVATION_MAX_RETRIES", "3"))

class ActivationWorker:
    """
    Handles asynchronous and bounded batch activation for product datasets.
    Prevents HTTP timeouts, memory spikes, and lock contention on 5,000+ record datasets.
    Provides real-time persisted progress tracking, SHA-256 embedding caching,
    dimension verification, and atomic database activation.
    """

    def __init__(self):
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._threads: Dict[str, threading.Thread] = {}

    def _get_dataset_lock(self, dataset_id: str) -> threading.Lock:
        with self._global_lock:
            if dataset_id not in self._locks:
                self._locks[dataset_id] = threading.Lock()
            return self._locks[dataset_id]

    def start_activation_async(
        self,
        cat_id: str,
        actor_id: str,
        batch_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Validates dataset and launches background worker thread.
        Returns job metadata immediately to caller.
        """
        b_size = batch_size or DEFAULT_BATCH_SIZE
        cat = db.get_catalogue_by_id(cat_id)
        if not cat:
            raise ValueError(f"Catalogue with ID '{cat_id}' not found.")

        # Check if dataset is already active
        if cat.get("is_active"):
            latest_job = db.get_latest_activation_job_for_dataset(cat["id"])
            if latest_job and latest_job.get("status") == "ACTIVE":
                return latest_job
            return {
                "id": str(cat["id"]),
                "dataset_id": cat["id"],
                "version": cat["version"],
                "status": "ACTIVE",
                "stage": "COMPLETED",
                "total_records": cat.get("record_count", 0),
                "processed_records": cat.get("record_count", 0),
                "embedded_records": cat.get("record_count", 0),
                "indexed_records": cat.get("record_count", 0),
                "failed_records": 0,
                "skipped_records": 0,
                "current_batch": 1,
                "total_batches": 1,
                "batch_size": b_size,
                "progress_percent": 100.0,
                "is_active": True,
                "message": f"Catalogue {cat['version']} is already active."
            }

        # Check for active running job for this dataset to prevent duplicate jobs
        existing_job = db.get_latest_activation_job_for_dataset(cat["id"])
        if existing_job and existing_job.get("status") in ("PENDING", "ACTIVATING", "PROCESSING_EMBEDDINGS", "INDEXING"):
            SafeLogger.info(f"Activation job {existing_job['id']} already running for dataset {cat_id}. Returning existing job.")
            return existing_job

        # Count total records in database for this catalogue
        with db.get_connection() as conn:
            cnt_row = conn.execute("SELECT COUNT(*) as cnt FROM products WHERE catalogue_id = ?", (cat["id"],)).fetchone()
            total_records = cnt_row["cnt"] if cnt_row else cat.get("valid_count", 0)

        if total_records == 0:
            raise ValueError(f"Catalogue '{cat['version']}' contains 0 valid product records to activate.")

        # Create activation job in database
        job = db.create_activation_job(
            dataset_id=cat["id"],
            version=cat["version"],
            total_records=total_records,
            batch_size=b_size
        )

        # Update catalogue status to INDEX_BUILDING
        with db.get_connection() as conn:
            conn.execute("UPDATE catalogues SET status = 'INDEX_BUILDING' WHERE id = ?", (cat["id"],))
            conn.execute("UPDATE dataset_metadata SET status = 'INDEX_BUILDING', embedding_status = 'EMBEDDING' WHERE id = ?", (cat["id"],))

        # Launch background thread
        thread = threading.Thread(
            target=self._process_activation,
            args=(job["id"], cat["id"], actor_id, b_size, total_records),
            daemon=True,
            name=f"activation-worker-{job['id'][:8]}"
        )
        with self._global_lock:
            self._threads[job["id"]] = thread
        thread.start()

        SafeLogger.info(f"Launched asynchronous activation worker for {cat['version']} ({total_records} records, batch_size={b_size}, job_id={job['id']}).")
        return job

    def execute_activation_sync(
        self,
        cat_id: str,
        actor_id: str,
        batch_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes activation synchronously (used for small datasets or direct tests).
        """
        b_size = batch_size or DEFAULT_BATCH_SIZE
        cat = db.get_catalogue_by_id(cat_id)
        if not cat:
            raise ValueError(f"Catalogue with ID '{cat_id}' not found.")

        with db.get_connection() as conn:
            cnt_row = conn.execute("SELECT COUNT(*) as cnt FROM products WHERE catalogue_id = ?", (cat["id"],)).fetchone()
            total_records = cnt_row["cnt"] if cnt_row else cat.get("valid_count", 0)

        job = db.create_activation_job(
            dataset_id=cat["id"],
            version=cat["version"],
            total_records=total_records,
            batch_size=b_size
        )

        self._process_activation(
            job_id=job["id"],
            cat_id=cat["id"],
            actor_id=actor_id,
            batch_size=b_size,
            total_records=total_records
        )
        return db.get_activation_job(job["id"]) or job

    def _process_activation(
        self,
        job_id: str,
        cat_id: str,
        actor_id: str,
        batch_size: int,
        total_records: int
    ) -> None:
        """Core batch processing loop executed in worker thread."""
        lock = self._get_dataset_lock(cat_id)
        if not lock.acquire(blocking=False):
            SafeLogger.warning(f"Dataset {cat_id} is already being processed by another worker. Skipping duplicate run.")
            return

        try:
            cat = db.get_catalogue_by_id(cat_id)
            if not cat:
                raise ValueError(f"Dataset {cat_id} not found.")

            target_category = cat.get("category", "PRODUCT_CATALOGUE")
            total_batches = max(1, math.ceil(total_records / batch_size))

            processed_count = 0
            embedded_count = 0
            failed_count = 0

            # ---------------- STAGE 1: BATCH PROCESSING & EMBEDDINGS ----------------
            SafeLogger.info(f"[Activation Job {job_id[:8]}] Stage 1: Batch embedding {total_records} records in {total_batches} batches.")
            
            for b_idx in range(total_batches):
                offset = b_idx * batch_size
                batch_records = db.get_dataset_records_paginated(
                    catalogue_id=cat_id,
                    limit=batch_size,
                    offset=offset
                )

                if not batch_records:
                    break

                # Generate domain-aware text and vectors with bounded retry
                retries = 0
                success = False
                batch_error: Optional[Exception] = None

                while retries <= MAX_RETRIES and not success:
                    try:
                        # Extract and check embedding cache
                        eligible, matrix = embedding_manager.embed_records(
                            records=batch_records,
                            category=target_category
                        )
                        success = True
                    except Exception as e:
                        retries += 1
                        batch_error = e
                        if retries <= MAX_RETRIES:
                            backoff = 0.25 * (2 ** retries)
                            SafeLogger.warning(f"[Job {job_id[:8]}] Batch {b_idx+1}/{total_batches} embedding error: {str(e)}. Retrying in {backoff:.2f}s...")
                            time.sleep(backoff)
                        else:
                            SafeLogger.error(f"[Job {job_id[:8]}] Batch {b_idx+1}/{total_batches} failed after {MAX_RETRIES} retries: {str(e)}")

                if not success:
                    failed_count += len(batch_records)
                    raise RuntimeError(f"Embedding generation failed for batch {b_idx+1}/{total_batches}: {str(batch_error)}")

                processed_count += len(batch_records)
                embedded_count += len(batch_records)

                # Persist progress after each batch
                db.update_activation_job_progress(
                    job_id=job_id,
                    processed_records=processed_count,
                    embedded_records=embedded_count,
                    current_batch=b_idx + 1,
                    stage="BATCHING_EMBEDDINGS",
                    status="ACTIVATING",
                    failed_records=failed_count
                )

            # ---------------- STAGE 2: VECTOR INDEXING ----------------
            SafeLogger.info(f"[Activation Job {job_id[:8]}] Stage 2: Rebuilding local vector search index.")
            db.update_activation_job_progress(
                job_id=job_id,
                processed_records=processed_count,
                embedded_records=embedded_count,
                current_batch=total_batches,
                stage="INDEXING",
                status="INDEXING"
            )

            # Load active products into memory loader and build index
            is_product_cat = target_category in ("PRODUCT_CATALOGUE", "MARKETPLACE_LISTINGS", "PRODUCT_SPECIFICATIONS", "GENERIC_DATASET")
            if is_product_cat:
                all_products = db.get_dataset_records_paginated(catalogue_id=cat_id, limit=max(total_records, 10000), offset=0)
                catalogue_loader.load_from_records(
                    records=all_products,
                    is_official=True,
                    is_synthetic=False,
                    source_name=f"{cat['name']} ({cat['version']})"
                )
            indexed_ok = local_vector_index.build_index(force_rebuild=True)
            if not indexed_ok and total_records > 0 and is_product_cat:
                raise RuntimeError("Vector index rebuild returned false after loading products.")

            # ---------------- STAGE 3: ATOMIC ACTIVATION ----------------
            SafeLogger.info(f"[Activation Job {job_id[:8]}] Stage 3: Atomic database activation.")
            db.update_activation_job_progress(
                job_id=job_id,
                processed_records=processed_count,
                embedded_records=embedded_count,
                current_batch=total_batches,
                stage="ATOMIC_ACTIVATION",
                status="ACTIVATING"
            )

            # Atomically switch active catalogue in database
            db.activate_catalogue(cat_id=cat_id, actor_id=actor_id)
            if is_product_cat:
                catalogue_loader.load_from_database()
            local_vector_index.build_index(force_rebuild=True)

            # Mark job complete
            db.complete_activation_job(
                job_id=job_id,
                status="ACTIVE",
                stage="COMPLETED",
                indexed_records=processed_count
            )
            SafeLogger.info(f"Activation Job {job_id[:8]} completed successfully for {cat['version']} ({processed_count} records).")

        except Exception as e:
            SafeLogger.error(f"Activation Job {job_id[:8]} failed: {str(e)}")
            err_category = "EMBEDDING_FAILURE" if "embedding" in str(e).lower() else "DATABASE_FAILURE"
            try:
                db.complete_activation_job(
                    job_id=job_id,
                    status="FAILED",
                    stage="FAILED",
                    error_message=str(e),
                    error_category=err_category
                )
                with db.get_connection() as conn:
                    conn.execute("UPDATE catalogues SET status = 'READY_FOR_ACTIVATION' WHERE id = ?", (cat_id,))
                    conn.execute("UPDATE dataset_metadata SET status = 'READY_FOR_ACTIVATION', embedding_status = 'EMBEDDING_FAILED' WHERE id = ?", (cat_id,))
            except Exception as inner_e:
                SafeLogger.error(f"Failed to record job failure state: {str(inner_e)}")
        finally:
            lock.release()
            with self._global_lock:
                self._threads.pop(job_id, None)

    def retry_job(self, job_id: str, actor_id: str) -> Dict[str, Any]:
        """Resumes or retries a failed activation job."""
        job = db.get_activation_job(job_id)
        if not job:
            raise ValueError(f"Activation job '{job_id}' not found.")

        if job.get("status") == "ACTIVE":
            return job

        return self.start_activation_async(cat_id=job["dataset_id"], actor_id=actor_id)


activation_worker = ActivationWorker()

