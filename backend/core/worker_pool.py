"""File worker pool: queue management, concurrency control, and batch state.

Extracted from ``apps/desktop/src/ui/main_window.py`` so the UI layer no
longer owns threading. The pool communicates with the UI exclusively through
thread-safe callbacks (log/progress/stats/preview/batch-complete/finished);
callers must marshal any Tk widget access onto the main thread via ``after``.
"""

import os
import shutil
import threading
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
from packages.shared_utils.csv_exporter import (
    build_editorial_caption,
    generate_microstock_csvs,
)
from packages.shared_utils.cost_tracker import cost_tracker
from packages.shared_utils.filter import clean_metadata
from packages.shared_utils.logger import CSVLogger
import random

# ponytail: Adaptive Cooldown replaces static 10s delay with 429 backoff
class AdaptiveCooldown:
    def __init__(self, base_min=2.5, base_max=3.5):
        self.base_min = base_min
        self.base_max = base_max
        self.multiplier = 1.0
        self._lock = threading.Lock()

    def update(self, is_429: bool):
        with self._lock:
            if is_429:
                self.multiplier = min(16.0, self.multiplier * 2.0)
            else:
                self.multiplier = max(1.0, self.multiplier * 0.5)

    def wait(self, log_cb, cancel_event):
        with self._lock:
            mult = self.multiplier
        delay = random.uniform(self.base_min, self.base_max) * mult
        log_cb(f"[INFO] Adaptive cooldown: {delay:.1f}s before next item...", "info")
        return cancel_event.wait(timeout=delay)



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
    file_path,
    title,
    desc,
    kws,
    processor,
    copyright_text,
    author,
    is_ai_generated=False,
    is_editorial=False,
    city="",
    country="",
    country_code="",
    date_created="",
    ai_system_name="",
    ai_system_version="",
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
            comp,
            title,
            desc,
            kws,
            copyright_text,
            author,
            is_ai_generated,
            is_editorial,
            city,
            country,
            country_code,
            date_created,
            ai_system_name,
            ai_system_version,
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
        self.cooldown = AdaptiveCooldown()
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
            if bt is not None and bt.is_alive():
                bt.join(timeout=2.0)
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
        base_delay = float(options.get("delay") or 2.5)
        self.cooldown = AdaptiveCooldown(base_min=base_delay, base_max=base_delay + 1.0)
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

        import queue
        import threading
        
        q_stage1 = queue.Queue()
        q_stage2 = queue.Queue(maxsize=max_w * 2)
        q_stage3 = queue.Queue(maxsize=max_w * 2)

        for p in paths:
            q_stage1.put(p)

        target_kw = resolve_target_kw(options)
        is_editorial = bool(options.get("is_editorial"))
        editorial_fields = {
            "city": options.get("editorial_city", ""),
            "country": options.get("editorial_country", ""),
            "country_code": options.get("editorial_country_code", ""),
            "date_created": options.get("editorial_date", ""),
        }

        processed_count = [0]
        count_lock = threading.Lock()

        def step_progress():
            with count_lock:
                processed_count[0] += 1
                curr = processed_count[0]
            if not self.cancel_flag:
                self._emit("progress", curr / total)

        def worker_stage1():
            while not self.cancel_flag:
                try:
                    p = q_stage1.get(timeout=0.2)
                except queue.Empty:
                    break
                
                self.pause_event.wait()
                if self.cancel_flag:
                    self._emit("file_status", os.path.basename(p), "cancelled")
                    step_progress()
                    continue

                name = os.path.basename(p)
                self._emit("file_status", name, "processing")
                self._emit("log", f"[{name}] Starting rasterization...", "processing")

                def log_cb(msg, lvl="info"):
                    self._emit("log", msg, lvl)

                from backend.core.worker_pool import extract_preview_image, get_file_hash
                preview = extract_preview_image(p, progress_callback=log_cb)
                if not preview:
                    self._inc_stat("error")
                    self._emit("file_status", name, "failed")
                    step_progress()
                    continue
                
                if self.cancel_flag:
                    self._remove_preview(preview)
                    self._emit("log", f"[{name}] Stopped after preview render.", "info")
                    self._emit("file_status", name, "cancelled")
                    step_progress()
                    continue

                f_hash = get_file_hash(preview)
                while not self.cancel_flag:
                    try:
                        q_stage2.put((p, preview, f_hash, name), timeout=0.2)
                        break
                    except queue.Full:
                        pass
                
                if self.cancel_flag:
                    self._remove_preview(preview)
                    self._emit("file_status", name, "cancelled")
                    step_progress()

        def worker_stage2():
            from backend.core.worker_pool import get_cached_metadata, set_cached_metadata
            while True:
                if self.cancel_flag:
                    try:
                        while True:
                            _, prev, _, n = q_stage2.get_nowait()
                            self._remove_preview(prev)
                            self._emit("file_status", n, "cancelled")
                            step_progress()
                    except queue.Empty:
                        break
                try:
                    item = q_stage2.get(timeout=0.2)
                except queue.Empty:
                    if stage1_done.is_set() and q_stage2.empty():
                        break
                    continue

                p, preview, f_hash, name = item
                self.pause_event.wait()
                if self.cancel_flag:
                    self._remove_preview(preview)
                    self._emit("file_status", name, "cancelled")
                    step_progress()
                    continue

                def log_cb(msg, lvl="info"):
                    self._emit("log", msg, lvl)

                cached = get_cached_metadata(f_hash)
                meta = None
                status = "failed"
                tag = "error"

                if cached:
                    self._emit("log", f"[{name}] [CACHE HIT] Metadata loaded from cache.", "cache")
                    meta = cached
                    old_len = len(meta.get("keywords", []))
                    if old_len < target_kw:
                        from packages.shared_utils.filter import expand_keywords
                        meta["keywords"] = expand_keywords(
                            meta.get("keywords", []), 
                            target_kw, 
                            title=meta.get("title", ""),
                            description=meta.get("description", ""),
                            asset_style=options.get("style_preset", "")
                        )
                        new_len = len(meta.get("keywords", []))
                        self._emit("log", f"[{name}] [DEBUG] Cache keywords expanded from {old_len} to {new_len} kw.", "info")
                        set_cached_metadata(f_hash, meta)
                    else:
                        self._emit("log", f"[{name}] [DEBUG] [CACHE HIT] Proceeding to embed_metadata...", "info")
                    status, tag = "CACHE", "cache"
                else:
                    self.cooldown.wait(log_cb, self.pause_event)
                    if self.cancel_flag:
                        self._remove_preview(preview)
                        self._emit("log", f"[{name}] Stopped before AI generation.", "info")
                        self._emit("file_status", name, "cancelled")
                        step_progress()
                        continue

                    meta = ai.generate_metadata(
                        preview,
                        target_kw,
                        options.get("style_preset", ""),
                        options.get("extra_prompt", ""),
                        log_callback=log_cb,
                        cancel_check=lambda: self.cancel_flag,
                        platform=options.get("platform", ""),
                        editorial=is_editorial,
                    )

                    if meta.get("fail_reason") == "cancelled":
                        self._remove_preview(preview)
                        self._emit("log", f"[{name}] Stopped: batch cancelled.", "info")
                        self._emit("file_status", name, "cancelled")
                        step_progress()
                        continue

                    if meta.get("is_fallback") or meta.get("error"):
                        err_detail = meta.get("error_details", "fallback rejected")
                        fail_reason = meta.get("fail_reason")
                        if fail_reason == "rate_limit" or "429" in err_detail or "503" in err_detail:
                            self.cooldown.update(True)
                        else:
                            self.cooldown.update(False)
                        if fail_reason == "auth" and not self.cancel_flag:
                            self.cancel_flag = True
                            self.pause_event.set()
                            self._emit("log", f"[{name}] Fatal AI error ({fail_reason}). Canceling batch...", "error")
                        self._emit("log", f"[{name}] AI generation failed: {err_detail}", "error")
                        self._inc_stat("error")
                        self._remove_preview(preview)
                        self._emit("file_status", name, "failed")
                        step_progress()
                        continue

                    set_cached_metadata(f_hash, meta)
                    self.cooldown.update(False)
                    self._emit("log", f"[{name}] Generated: Title='{str(meta.get('title', ''))[:30]}...' | {len(meta.get('keywords', []))} Keywords", "success")
                    status, tag = "API", "api"

                    _usage = meta.get("_usage")
                    if _usage:
                        self._emit(
                            "token_usage",
                            {
                                "tokens": _usage.get("total_tokens", 0),
                                "model": _usage.get("model", ""),
                            },
                        )

                    custom_kws_raw = options.get("custom_kw", "")
                    if custom_kws_raw.strip():
                        custom_kws = [k.strip() for k in custom_kws_raw.split(",") if k.strip()]
                        ai_kws = [k for k in meta.get("keywords", []) if k.lower() not in [ck.lower() for ck in custom_kws]]
                        pos = options.get("custom_kw_pos", "Start (Priority)")
                        if pos == "Start (Priority)":
                            meta["keywords"] = custom_kws + ai_kws
                        else:
                            meta["keywords"] = ai_kws + custom_kws

                while not self.cancel_flag:
                    try:
                        q_stage3.put((p, preview, f_hash, name, meta, status, tag), timeout=0.2)
                        break
                    except queue.Full:
                        pass
                
                if self.cancel_flag:
                    self._remove_preview(preview)
                    self._emit("file_status", name, "cancelled")
                    step_progress()

        def worker_stage3():
            from packages.shared_utils.filter import clean_metadata
            from packages.shared_utils.csv_exporter import build_editorial_caption
            from PIL import Image
            import shutil
            while True:
                if self.cancel_flag:
                    try:
                        while True:
                            _, prev, _, n, _, _, _ = q_stage3.get_nowait()
                            self._remove_preview(prev)
                            self._emit("file_status", n, "cancelled")
                            step_progress()
                    except queue.Empty:
                        break
                try:
                    item = q_stage3.get(timeout=0.2)
                except queue.Empty:
                    if stage2_done.is_set() and q_stage3.empty():
                        break
                    continue

                p, preview, f_hash, name, meta, status, tag = item
                self.pause_event.wait()
                if self.cancel_flag:
                    self._remove_preview(preview)
                    self._emit("file_status", name, "cancelled")
                    step_progress()
                    continue

                try:
                    with Image.open(preview) as opened_img:
                        img = opened_img.copy()
                        img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                except (OSError, ValueError):
                    img = None

                self._remove_preview(preview)

                meta = clean_metadata(meta, target_kw)
                if len(meta.get("keywords", [])) < target_kw:
                    from packages.shared_utils.filter import expand_keywords
                    meta["keywords"] = expand_keywords(
                        meta.get("keywords", []), 
                        target_kw, 
                        title=meta.get("title", ""),
                        description=meta.get("description", ""),
                        asset_style=options.get("style_preset", "")
                    )
                is_ai_generated = bool(options.get("is_ai_generated") or meta.get("is_ai_generated", False))
                final_path = os.path.join(processed_dir, name)
                shutil.move(p, final_path)

                title, desc, keywords = (meta.get("title", ""), meta.get("description", ""), meta.get("keywords", []))
                ai_system_name = str(options.get("ai_model") or options.get("model") or meta.get("ai_model") or "Gemini").split(" ")[0].strip()

                if is_editorial:
                    desc = build_editorial_caption(desc, editorial_fields["city"], editorial_fields["country"], editorial_fields["date_created"])

                if img:
                    self._emit("preview", img, status, tag, meta, final_path, f_hash)

                if self.cancel_flag:
                    self._emit("log", f"[{name}] Saved but batch stopped before embedding.", "info")
                    self._emit("file_status", name, "cancelled")
                    step_progress()
                    continue

                if self.processor.embed_metadata(
                    final_path, title, desc, keywords,
                    options.get("copyright", ""), options.get("author", ""),
                    is_ai_generated=is_ai_generated, is_editorial=is_editorial,
                    city=editorial_fields["city"], country=editorial_fields["country"],
                    country_code=editorial_fields["country_code"], date_created=editorial_fields["date_created"],
                    ai_system_name=ai_system_name,
                ):
                    self._emit("log", f"[{name}] [DEBUG] Metadata embedded. Proceeding to CSV export...", "info")
                    if options.get("sync_companions"):
                        from backend.core.worker_pool import sync_companion_metadata
                        synced = sync_companion_metadata(
                            final_path, title, desc, keywords, self.processor,
                            options.get("copyright", ""), options.get("author", ""),
                            is_ai_generated=is_ai_generated, is_editorial=is_editorial,
                            city=editorial_fields["city"], country=editorial_fields["country"],
                            country_code=editorial_fields["country_code"], date_created=editorial_fields["date_created"],
                            ai_system_name=ai_system_name,
                        )
                        if synced > 0:
                            self._emit("log", f"  └─ Synced metadata to {synced} companion file(s)", "info")

                    csv_logger.log(
                        name, title, desc, keywords,
                        category=meta.get("category", ""), primary_category=meta.get("primary_category", ""),
                        secondary_category=meta.get("secondary_category", ""),
                        is_ai_generated=is_ai_generated, is_editorial=is_editorial,
                        city=editorial_fields["city"], country=editorial_fields["country"],
                        date_created=editorial_fields["date_created"], country_code=editorial_fields["country_code"],
                    )
                    self._inc_stat("success")
                    self._emit("file_status", name, "done")
                else:
                    self._inc_stat("error")
                    self._emit("file_status", name, "failed")
                
                step_progress()

        stage1_done = threading.Event()
        stage2_done = threading.Event()

        t_stage1 = [threading.Thread(target=worker_stage1, name=f"Stage1-{i}") for i in range(max_w)]
        t_stage2 = [threading.Thread(target=worker_stage2, name=f"Stage2-{i}") for i in range(max(1, min(max_w, 2)))]
        t_stage3 = [threading.Thread(target=worker_stage3, name=f"Stage3-{i}") for i in range(max_w)]

        self._threads = t_stage1 + t_stage2 + t_stage3

        for t in self._threads:
            t.start()

        for t in t_stage1: t.join()
        stage1_done.set()

        for t in t_stage2: t.join()
        stage2_done.set()

        for t in t_stage3: t.join()
        self._threads.clear()


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
            self._emit("file_status", os.path.basename(file_path), "cancelled")
            return

        name = os.path.basename(file_path)
        target_kw = resolve_target_kw(options)
        is_editorial = bool(options.get("is_editorial"))
        editorial_fields = {
            "city": options.get("editorial_city", ""),
            "country": options.get("editorial_country", ""),
            "country_code": options.get("editorial_country_code", ""),
            "date_created": options.get("editorial_date", ""),
        }
        self._emit("file_status", name, "processing")
        self._emit("log", f"[{name}] Starting processing pipeline...", "processing")

        final_status = "failed"
        try:
            res = self._process_file_inner(file_path, out_dir, ai, options, csv_logger, name, target_kw, is_editorial, editorial_fields)
            if res == "cancelled":
                final_status = "cancelled"
            elif res is not False:
                final_status = "done"
        except Exception as e:
            self._emit("log", f"[{name}] Error: {str(e)}", "error")
            self._inc_stat("error")
        finally:
            self._emit("file_status", name, final_status)

    def _process_file_inner(self, file_path, out_dir, ai, options, csv_logger, name, target_kw, is_editorial, editorial_fields):
        def log_cb(msg, lvl="info"):
            self._emit("log", msg, lvl)

        preview = extract_preview_image(file_path, progress_callback=log_cb)
        if not preview:
            self._inc_stat("error")
            return False
        if self.cancel_flag:
            self._remove_preview(preview)
            self._emit("log", f"[{name}] Stopped after preview render.", "info")
            return "cancelled"

        file_hash = get_file_hash(preview)
        cached = get_cached_metadata(file_hash)

        if cached:
            self._emit("log", f"[{name}] [CACHE HIT] Metadata loaded from cache.", "cache")
            meta = cached
            old_len = len(meta.get("keywords", []))
            if old_len < target_kw:
                from packages.shared_utils.filter import expand_keywords
                meta["keywords"] = expand_keywords(
                    meta.get("keywords", []), 
                    target_kw, 
                    title=meta.get("title", ""),
                    description=meta.get("description", ""),
                    asset_style=options.get("style_preset", "")
                )
                new_len = len(meta.get("keywords", []))
                self._emit("log", f"[{name}] [DEBUG] Cache keywords expanded from {old_len} to {new_len} kw.", "info")
                set_cached_metadata(file_hash, meta)
            else:
                self._emit("log", f"[{name}] [DEBUG] [CACHE HIT] Proceeding to embed_metadata...", "info")
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
                editorial=is_editorial,
            )

            if meta.get("fail_reason") == "cancelled":
                self._remove_preview(preview)
                self._emit("log", f"[{name}] Stopped: batch cancelled.", "info")
                return "cancelled"

            if meta.get("is_fallback") or meta.get("error"):
                err_detail = meta.get("error_details", "fallback rejected")
                fail_reason = meta.get("fail_reason")
                
                # ponytail: dynamic backoff on 429/503
                if fail_reason == "rate_limit" or "429" in err_detail or "503" in err_detail:
                    self.cooldown.update(True)
                else:
                    self.cooldown.update(False)

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
                self._inc_stat("error")
                # Clean up preview since we're aborting
                self._remove_preview(preview)
                return False

            set_cached_metadata(file_hash, meta)
            self.cooldown.update(False)
            self._emit(
                "log",
                f"[{name}] Generated: Title='{meta.get('title', '')[:30]}...' | {len(meta.get('keywords', []))} Keywords",
                "success",
            )
            status, tag = "API", "api"

            _usage = meta.get("_usage")
            if _usage:
                self._emit(
                    "token_usage",
                    {
                        "tokens": _usage.get("total_tokens", 0),
                        "model": _usage.get("model", ""),
                    },
                )

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
        
        # Ensure exact count for fresh AI output as well, just like cache hit
        if len(meta.get("keywords", [])) < target_kw:
            from packages.shared_utils.filter import expand_keywords
            meta["keywords"] = expand_keywords(
                meta.get("keywords", []), 
                target_kw, 
                title=meta.get("title", ""),
                description=meta.get("description", ""),
                asset_style=options.get("style_preset", "")
            )
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

        # Record which AI system produced the metadata/asset for IPTC 2025.1.
        ai_system_name = (
            options.get("ai_model")
            or options.get("model")
            or meta.get("ai_model")
            or "Gemini"
        )
        ai_system_name = str(ai_system_name).split(" ")[0].strip()

        if is_editorial:
            desc = build_editorial_caption(
                desc,
                editorial_fields["city"],
                editorial_fields["country"],
                editorial_fields["date_created"],
            )

        if img:
            self._emit(
                "preview", img, status, tag, meta, final_path, file_hash
            )

        if self.cancel_flag:
            self._emit("log", f"[{name}] Saved but batch stopped before embedding.", "info")
            return "cancelled"

        if self.processor.embed_metadata(
            final_path,
            title,
            desc,
            keywords,
            options.get("copyright", ""),
            options.get("author", ""),
            is_ai_generated=is_ai_generated,
            is_editorial=is_editorial,
            city=editorial_fields["city"],
            country=editorial_fields["country"],
            country_code=editorial_fields["country_code"],
            date_created=editorial_fields["date_created"],
            ai_system_name=ai_system_name,
        ):
            self._emit("log", f"[{name}] [DEBUG] Metadata embedded. Proceeding to CSV export...", "info")

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
                    is_editorial=is_editorial,
                    city=editorial_fields["city"],
                    country=editorial_fields["country"],
                    country_code=editorial_fields["country_code"],
                    date_created=editorial_fields["date_created"],
                    ai_system_name=ai_system_name,
                )
                if synced > 0:
                    self._emit(
                        "log",
                        f"  └─ Synced metadata to {synced} companion file(s)",
                        "info",
                    )

            csv_logger.log(
                name,
                title,
                desc,
                keywords,
                category=meta.get("category", ""),
                primary_category=meta.get("primary_category", ""),
                secondary_category=meta.get("secondary_category", ""),
                is_ai_generated=is_ai_generated,
                is_editorial=is_editorial,
                city=editorial_fields["city"],
                country=editorial_fields["country"],
                country_code=editorial_fields["country_code"],
                date_created=editorial_fields["date_created"],
            )

            self._emit("log", f"[{name}] [DEBUG] CSV exported.", "info")
            self._emit("log", f"[{name}] File completed and saved. ({len(keywords)} kw)", "success")
            self._inc_stat("success")

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

            if self.cooldown.wait(log_cb, self.cancel_event):
                self._emit("log", f"[{name}] Cooldown interrupted by cancel.", "info")
            return True

        else:
            self._emit("log", f"[{name}] ExifTool metadata embedding failed.", "error")
            self._inc_stat("error")
            return False