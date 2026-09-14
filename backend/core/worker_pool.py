"""File worker pool: queue management, concurrency control, and batch state.

Extracted from ``apps/desktop/src/ui/main_window.py`` so the UI layer no
longer owns threading. The pool communicates with the UI exclusively through
thread-safe callbacks (log/progress/stats/preview/batch-complete/finished);
callers must marshal any Tk widget access onto the main thread via ``after``.
"""

import os
import shutil
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

from backend.ai.provider_router import AIService
from backend.core.config_manager import (
    get_cached_metadata,
    get_file_hash,
    set_cached_metadata,
)
from backend.processors.exiftool_client import ExifToolClient
from backend.processors.media_converter import extract_preview_image
from packages.shared_utils.csv_exporter import generate_microstock_csvs
from packages.shared_utils.cost_tracker import cost_tracker
from packages.shared_utils.filter import PLATFORM_RULES, clean_metadata
from packages.shared_utils.logger import CSVLogger


def resolve_target_kw(options: dict) -> int:
    """Return the target keyword count for a batch run."""
    return int(options.get("target_kw", 49))


def find_companion_files(file_path):
    """Find files with same base name but different extensions in the same folder."""
    if not file_path or not os.path.exists(file_path):
        return []
    folder = os.path.dirname(file_path)
    base = os.path.splitext(os.path.basename(file_path))[0]
    companions = []
    for f in os.listdir(folder):
        f_base = os.path.splitext(f)[0]
        f_path = os.path.join(folder, f)
        if f_base == base and f_path != file_path and os.path.isfile(f_path):
            companions.append(f_path)
    return companions


def sync_companion_metadata(
    file_path, title, desc, kws, processor, copyright_text, author, is_ai_generated=False
):
    """Embed metadata to all companion files with the same base name. Returns count."""
    companions = find_companion_files(file_path)
    if not companions:
        return 0
    count = 0
    for comp in companions:
        comp_hash = get_file_hash(comp)
        meta = {"title": title, "description": desc, "keywords": kws}
        set_cached_metadata(comp_hash, meta)
        if processor.embed_metadata(
            comp, title, desc, kws, copyright_text, author, is_ai_generated
        ):
            count += 1
    return count


class FileWorkerPool:
    def __init__(self, callbacks: dict | None = None):
        self.callbacks = callbacks or {}
        self.is_running = False
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.cancel_flag = False
        self.cancel_event = threading.Event()
        self.stats = {"total": 0, "success": 0, "error": 0}
        self.session_stats = {
            "processed": 0,
            "skipped": 0,
            "cost": 0.0,
            "csvs": [],
            "tokens_est": 0,
        }
        self.processor = ExifToolClient()
        self._lock = threading.Lock()
        self._executor = None
        self._batch_thread = None

    def _emit(self, name: str, *args):
        cb = self.callbacks.get(name)
        if cb:
            cb(*args)

    def _inc_stat(self, key: str):
        with self._lock:
            self.stats[key] += 1
        self._emit("stats", self.stats_snapshot(), self.is_running)

    def stats_snapshot(self) -> dict:
        return dict(self.stats)

    def reap_stale(self) -> bool:
        """Clear a stale ``is_running`` flag left over from a batch thread that
        already exited (e.g. cancel drained and the thread finished). Returns
        True when a stale flag was cleared."""
        if self.is_running:
            bt = self._batch_thread
            if bt is None or not bt.is_alive():
                self.is_running = False
                self._batch_thread = None
                return True
        return False

    def start(self, paths, in_dir, options) -> bool:
        """Begin the batch in a background thread. Returns False if already running."""
        if self.is_running and not self.reap_stale():
            return False
        self.is_running = True
        self.cancel_flag = False
        self.cancel_event.clear()
        self.pause_event.set()
        self.stats = {"total": len(paths), "success": 0, "error": 0}
        self.session_stats = {
            "processed": 0,
            "skipped": options.get("skipped_count", 0),
            "cost": self.session_stats.get("cost", 0),
            "tokens_est": 0,
            "csvs": [],
        }
        self._emit("stats", self.stats_snapshot(), True)
        t = threading.Thread(
            target=self._run_batch, args=(paths, in_dir, options), daemon=True
        )
        self._batch_thread = t
        t.start()
        return True

    def toggle_pause(self) -> bool:
        """Return True if the pool is now paused."""
        if self.pause_event.is_set():
            self.pause_event.clear()
            return True
        self.pause_event.set()
        return False

    def cancel(self):
        self.cancel_flag = True
        self.cancel_event.set()
        self.pause_event.set()
        executor = self._executor
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    def _run_batch(self, paths, out_dir, options):
        try:
            self._run_batch_inner(paths, out_dir, options)
        except Exception as e:
            try:
                self._emit("log", f"Batch failed: {e}", "error")
            except Exception:
                pass
        finally:
            self.is_running = False
            self._batch_thread = None
            try:
                self._emit("stats", self.stats_snapshot(), False)
                self._emit("finished")
            except Exception:
                pass

    def _run_batch_inner(self, paths, out_dir, options):
        provider = options.get("provider", "Gemini")
        api_keys_dict = options.get("api_keys", {})
        api_key = api_keys_dict.get(provider, "")
        # Build failover dict from other configured providers
        failover_providers = {
            p: k for p, k in api_keys_dict.items() if p != provider and k
        }
        raw_model = options.get("model") or "Gemini"
        ai = AIService(
            provider,
            api_key,
            raw_model.split(" ")[0],
            options.get("temperature", 0.3),
            failover_providers=failover_providers,
            custom_base_url=options.get("custom_base_url", ""),
        )
        processed_dir = os.path.join(out_dir, "Processed Assets")
        csv_dir = os.path.join(out_dir, "Metadata CSV")
        os.makedirs(processed_dir, exist_ok=True)
        os.makedirs(csv_dir, exist_ok=True)

        csv_logger = CSVLogger(os.path.join(csv_dir, "metadata_output.csv"))

        max_w = max(1, int(options.get("workers", 2)))
        total = len(paths)
        cost_before = cost_tracker.estimated_cost_usd
        tokens_before = cost_tracker.estimated_tokens

        def submit(f):
            return self._executor.submit(
                self._process_file, f, processed_dir, ai, options, csv_logger
            )

        with ThreadPoolExecutor(max_workers=max_w) as executor:
            self._executor = executor
            futures = {submit(f): f for f in paths}
            for i, future in enumerate(as_completed(futures), 1):
                if future.cancelled():
                    continue
                try:
                    future.result()
                except Exception as e:
                    self._inc_stat("error")
                    self._emit(
                        "log",
                        f"Worker error on {os.path.basename(futures[future])}: {e}",
                        "error",
                    )
                if not self.cancel_flag:
                    self._emit("progress", i / total)
            self._executor = None

        if self.cancel_flag:
            self._emit("log", "Batch CANCELED.", "error")
        else:
            self._emit("log", "Batch complete. Generating exports...", "info")
            csv_platforms = set(options.get("csv_platforms", set()))
            selected = options.get("platform")
            if selected and selected != "Generic":
                csv_platforms.add(selected)
            generate_microstock_csvs(csv_dir, csv_platforms)

            # Collect generated CSV list
            csv_files = [
                f
                for f in os.listdir(csv_dir)
                if f.endswith("_export.csv") or f == "metadata_output.csv"
            ]
            cost_delta = cost_tracker.estimated_cost_usd - cost_before
            tokens_delta = cost_tracker.estimated_tokens - tokens_before
            summary = {
                "processed": self.stats["success"],
                "errors": self.stats["error"],
                "cost": self.session_stats.get("cost", 0) + cost_delta,
                "tokens_est": self.session_stats.get("tokens_est", 0) + tokens_delta,
                "csvs": csv_files,
                "out_dir": csv_dir,
                "skipped": self.session_stats.get("skipped", 0),
            }
            self.session_stats.update(summary)
            self._emit("batch_complete", summary)

    def _remove_preview(self, preview):
        try:
            os.remove(preview)
        except OSError:
            pass

    def _process_file(self, file_path, out_dir, ai, options, csv_logger):
        self.pause_event.wait()
        if self.cancel_flag:
            return

        name = os.path.basename(file_path)
        target_kw = resolve_target_kw(options)
        self._emit("file_status", name, "processing")
        self._emit("log", f"[{name}] Starting processing pipeline...", "processing")

        def log_cb(msg, lvl="info"):
            self._emit("log", msg, lvl)

        preview = extract_preview_image(file_path, progress_callback=log_cb)
        if not preview:
            self._emit("file_status", name, "failed")
            self._inc_stat("error")
            return
        if self.cancel_flag:
            self._remove_preview(preview)
            self._emit("file_status", name, "failed")
            self._emit("log", f"[{name}] Stopped after preview render.", "info")
            return

        file_hash = get_file_hash(preview)
        cached = get_cached_metadata(file_hash)

        if cached:
            self._emit("log", f"[{name}] [CACHE HIT] Metadata loaded from cache.", "cache")
            meta = cached
            status, tag = "CACHE", "cache"
        else:
            meta = ai.generate_metadata(
                preview,
                target_kw,
                options["style_preset"],
                options.get("extra_prompt", ""),
                log_callback=log_cb,
                cancel_check=lambda: self.cancel_flag,
                platform=options.get("platform", ""),
            )

            if meta.get("fail_reason") == "cancelled":
                self._remove_preview(preview)
                self._emit("file_status", name, "failed")
                self._emit("log", f"[{name}] Stopped: batch cancelled.", "info")
                return

            if meta.get("is_fallback") or meta.get("error"):
                err_detail = meta.get("error_details", "fallback rejected")
                fail_reason = meta.get("fail_reason")
                if fail_reason == "auth" and not self.cancel_flag:
                    self.cancel_flag = True
                    self.pause_event.set()
                    self._emit(
                        "log",
                        f"[{name}] Fatal AI error ({fail_reason}). Canceling batch...",
                        "error",
                    )
                self._emit(
                    "log",
                    f"[{name}] AI generation failed: {err_detail}",
                    "error",
                )
                self._emit("file_status", name, "failed")
                self._inc_stat("error")
                # Clean up preview since we're aborting
                self._remove_preview(preview)
                return

            set_cached_metadata(file_hash, meta)
            self._emit(
                "log",
                f"[{name}] Generated: Title='{meta.get('title', '')[:30]}...' | {len(meta.get('keywords', []))} Keywords",
                "success",
            )
            status, tag = "API", "api"

            # Inject mandatory custom keywords on first API generation
            custom_kws_raw = options.get("custom_kw", "")
            if custom_kws_raw.strip():
                custom_kws = [k.strip() for k in custom_kws_raw.split(",") if k.strip()]
                # remove any exact overlaps in AI response
                ai_kws = [
                    k
                    for k in meta.get("keywords", [])
                    if k.lower() not in [ck.lower() for ck in custom_kws]
                ]

                pos = options.get("custom_kw_pos", "Start (Priority)")
                if pos == "Start (Priority)":
                    merged_kws = custom_kws + ai_kws
                else:
                    merged_kws = ai_kws + custom_kws
                meta["keywords"] = merged_kws

        try:
            with Image.open(preview) as opened_img:
                img = opened_img.copy()
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
        except (OSError, ValueError):
            img = None

        try:
            os.remove(preview)
        except OSError:
            pass

        meta = clean_metadata(meta, target_kw)
        is_ai_generated = bool(
            options.get("is_ai_generated") or meta.get("is_ai_generated", False)
        )

        base_name = os.path.splitext(name)[0]
        final_path = os.path.join(out_dir, name)
        shutil.move(file_path, final_path)

        title, desc, keywords = (
            meta.get("title", ""),
            meta.get("description", ""),
            meta.get("keywords", []),
        )

        if img:
            self._emit(
                "preview", img, status, tag, meta, final_path, file_hash
            )

        if self.cancel_flag:
            self._emit("log", f"[{name}] Saved but batch stopped before embedding.", "info")
            self._emit("file_status", name, "done")
            return

        if self.processor.embed_metadata(
            final_path,
            title,
            desc,
            keywords,
            options.get("copyright", ""),
            options.get("author", ""),
            is_ai_generated=is_ai_generated,
        ):
            self._emit("log", f"[{name}] File completed and saved. ({len(keywords)} kw)", "success")
            self._emit("file_status", name, "done")
            self._inc_stat("success")

            if options.get("sync_companions"):
                synced = sync_companion_metadata(
                    final_path,
                    title,
                    desc,
                    keywords,
                    self.processor,
                    options.get("copyright", ""),
                    options.get("author", ""),
                    is_ai_generated=is_ai_generated,
                )
                if synced > 0:
                    self._emit(
                        "log",
                        f"  └─ Synced metadata to {synced} companion file(s)",
                        "info",
                    )

            csv_logger.log(name, title, desc, keywords, is_ai_generated=is_ai_generated)

            if (
                options.get("auto_zip")
                and name.lower().endswith((".svg", ".eps"))
            ):
                jpg_path = os.path.join(out_dir, base_name + ".jpg")
                if img:
                    try:
                        img.convert("RGB").save(jpg_path, "JPEG", quality=95)
                    except OSError:
                        pass
                zip_path = os.path.join(out_dir, base_name + ".zip")
                try:
                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        zf.write(final_path, arcname=name)
                        if os.path.exists(jpg_path):
                            zf.write(jpg_path, arcname=base_name + ".jpg")
                except OSError:
                    pass

            delay = float(options.get("delay") or 0)
            if delay > 0:
                self._emit(
                    "log",
                    f"[{name}] Cooldown {delay:.0f}s before next file...",
                    "info",
                )
                if self.cancel_event.wait(timeout=delay):
                    self._emit("log", f"[{name}] Cooldown interrupted by cancel.", "info")

        else:
            self._emit("log", f"[{name}] ExifTool metadata embedding failed.", "error")
            self._emit("file_status", name, "failed")
            self._inc_stat("error")