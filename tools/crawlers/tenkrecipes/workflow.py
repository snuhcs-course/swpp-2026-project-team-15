# AI-assisted with Codex, 2026-11-11; human review pending.
"""Persist source snapshots and resume recorded work without allocating quotas."""

import copy
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from .config import validate_output_dir
from .fetching import NetworkDisabled
from .images import ImageDownloader
from .parsing import ParseError, parse_list_page, parse_recipe
from .storage import IntegrityError, RunStorage, digest, plain

PARSER_VERSION = "tenkrecipes-dom-1"
SCHEMA_VERSION = "2"


class ResumeMismatch(ValueError):
    """A saved run uses a different plan, network policy, or parser/schema version."""


class CollectionRun:
    """Own an immutable run identity and atomically checkpoint successful operations.

    Snapshot publication follows raw/derived file publication. Raw provenance
    sidecars allow reuse if interruption occurs before the manifest is published.
    One operator must own a run directory; concurrent writers are not supported.
    """

    def __init__(self, storage, metadata, manifest, client, utcnow, image_downloader):
        self.storage, self.metadata, self._manifest = storage, metadata, manifest
        self.client, self.utcnow = client, utcnow
        self.image_downloader = image_downloader

    @classmethod
    def create(
        cls,
        *,
        plan,
        client,
        parser_version,
        schema_version,
        utcnow=lambda: datetime.now(UTC),
        image_downloader=None,
    ):
        """Create a new run, rejecting missing live opt-in before any directories."""
        if not client.live:
            raise NetworkDisabled("Collection requires --live")
        image_downloader = image_downloader or ImageDownloader(client)
        if image_downloader.client is not client:
            raise ValueError("Source and image I/O must share one pacing client")
        frozen_plan = plain(plan)
        root = validate_output_dir(Path(frozen_plan["output_dir"]))
        root.mkdir(parents=True, exist_ok=False)
        storage = RunStorage(root)
        metadata = dict(
            run_id=uuid4().hex,
            started_at=utcnow().isoformat(),
            plan=frozen_plan,
            parser_version=parser_version,
            schema_version=schema_version,
            network_policy=plain(client.policy),
            image_policy=plain(image_downloader.policy),
        )
        manifest = cls._empty_manifest(metadata)
        storage.write_json("run.json", metadata, immutable=True)
        storage.write_json("manifest.json", manifest)
        return cls(storage, metadata, manifest, client, utcnow, image_downloader)

    @staticmethod
    def _empty_manifest(metadata):
        return dict(
            run_id=metadata["run_id"],
            state="running",
            reason=None,
            network_policy=copy.deepcopy(metadata["network_policy"]),
            lists=[],
            candidates=[],
            details={},
            images={},
            responses=[],
            attempts=[],
            pending_lists=[],
            retry_not_before=None,
        )

    @classmethod
    def resume(
        cls,
        *,
        plan,
        client,
        parser_version,
        schema_version,
        utcnow=lambda: datetime.now(UTC),
        image_downloader=None,
    ):
        """Verify configuration and saved bytes before network calls or repair writes."""
        if not client.live:
            raise NetworkDisabled("Resume requires --live")
        image_downloader = image_downloader or ImageDownloader(client)
        if image_downloader.client is not client:
            raise ValueError("Source and image I/O must share one pacing client")
        frozen_plan = plain(plan)
        storage = RunStorage(validate_output_dir(Path(frozen_plan["output_dir"])))
        metadata = storage.read_json("run.json")
        if (
            metadata["plan"] != frozen_plan
            or metadata["parser_version"] != parser_version
            or metadata["schema_version"] != schema_version
            or metadata["network_policy"] != plain(client.policy)
            or metadata.get("image_policy") != plain(image_downloader.policy)
        ):
            raise ResumeMismatch("Run configuration or parser/schema version changed")
        manifest_path = storage.path("manifest.json")
        manifest = (
            storage.read_json("manifest.json")
            if manifest_path.exists()
            else cls._empty_manifest(metadata)
        )
        if manifest["run_id"] != metadata["run_id"]:
            raise IntegrityError("Manifest does not belong to this run")
        for entry in manifest["responses"]:
            storage.verify(entry)
        for detail in manifest["details"].values():
            record = detail.get("record")
            # A missing derived record is recoverable from verified raw HTML.
            if record and storage.path(record["path"]).exists():
                storage.verify(record)
        for image in manifest["images"].values():
            if image["state"] == "image_validated" and storage.path(image["path"]).exists():
                storage.verify(image)
        run = cls(storage, metadata, manifest, client, utcnow, image_downloader)
        # A raw list may have been published just before a failed manifest replace.
        # Replay only complete, hash-verified local lists; never fetch during open.
        sidecars = []
        for path in storage.root.glob("lists/*/*.html.meta.json"):
            if re.fullmatch(r"[0-9]+\.html\.meta\.json", path.name):
                relative = path.relative_to(storage.root).as_posix()
                entry = storage.read_json(relative)
                if storage.path(entry["path"]).exists():
                    storage.verify(entry)
                    sidecars.append(
                        (entry["fetched_at"], path.parent.name, int(path.name.split(".")[0]))
                    )
        for _, category, page in sorted(sidecars):
            if not any(
                row["category_code"] == category and row["page"] == page
                for row in run._manifest["lists"]
            ):
                run.fetch_list(category, page)
        return run

    def snapshot(self):
        """Return an independent copy of the latest committed manifest."""
        return copy.deepcopy(self._manifest)

    def _commit(self, manifest):
        self.storage.write_json("manifest.json", manifest)
        self._manifest = manifest

    def _source(self, relative, url):
        """Reuse a verified raw snapshot, including a publish-before-checkpoint orphan."""
        path = self.storage.path(relative)
        if not path.exists():
            deferred = self._deferred()
            if deferred:
                return dict(deferred, body=None, attempts=[], responses=[])
            return self.client.get(url)
        provenance = self.storage.read_json(relative + ".meta.json")
        if provenance["run_id"] != self.metadata["run_id"] or provenance["source_url"] != url:
            raise IntegrityError("Raw snapshot provenance differs from this run/source")
        body = self.storage.verify(provenance)
        return dict(
            status="ok", reason=None, body=body, attempts=provenance["attempts"], responses=[]
        )

    def _retain(self, manifest, result, relative, url):
        """Preserve each response and final snapshot before advancing the checkpoint."""
        known = {item["attempt_id"] for item in manifest["attempts"]}
        for response in result["responses"]:
            attempt = response["attempt"]
            path = f"attempts/{attempt['attempt_id']}.html"
            self.storage.write(path, response["body"], immutable=True)
            entry = dict(path=path, **attempt)
            if not any(row["path"] == path for row in manifest["responses"]):
                manifest["responses"].append(entry)
        for attempt in result["attempts"]:
            if attempt["attempt_id"] not in known:
                manifest["attempts"].append(copy.deepcopy(attempt))
                known.add(attempt["attempt_id"])
        if result["body"] is None:
            return None
        # Failed snapshots get unique names so a later retry never rewrites them.
        if result["status"] != "ok":
            path = Path(relative)
            relative = str(path.with_name(f"{path.stem}.failed-{uuid4().hex}.html")).replace(
                "\\", "/"
            )
        last_response = next((row for row in reversed(result["attempts"]) if "sha256" in row), {})
        entry = dict(
            last_response,
            path=relative,
            source_url=url,
            sha256=digest(result["body"]),
            run_id=self.metadata["run_id"],
            attempts=copy.deepcopy(result["attempts"]),
        )
        # Sidecars precede bodies, so an orphan body always has verifiable provenance.
        if not self.storage.path(relative).exists():
            self.storage.write_json(relative + ".meta.json", entry)
        self.storage.write(relative, result["body"], immutable=True)
        if not any(row["path"] == relative for row in manifest["responses"]):
            manifest["responses"].append(entry)
        return entry

    def _failure(self, manifest, result):
        manifest.update(state=result["status"], reason=result["reason"])
        manifest["retry_not_before"] = result.get("retry_not_before")
        self._commit(manifest)
        return dict(status=result["status"], reason=result["reason"])

    def _deferred(self):
        """Carry server retry deadlines across process restarts without sleeping early."""
        deadline = self._manifest.get("retry_not_before")
        if deadline and datetime.fromisoformat(deadline) > self.utcnow():
            return dict(
                status="deferred", reason=self._manifest["reason"], retry_not_before=deadline
            )
        return None

    def fetch_list(self, category_code, page):
        """Fetch one approved list page; retain every observation without allocating it."""
        category_code = str(category_code)
        category = next(
            (row for row in self.metadata["plan"]["categories"] if row["cat4"] == category_code),
            None,
        )
        if category is None or type(page) is not int or page < 1:
            raise ValueError("Expected a configured category and positive page")
        parts = urlsplit(category["list_url"])
        query = parse_qs(parts.query)
        query["page"] = [str(page)]
        url = urlunsplit(parts._replace(query=urlencode(query, doseq=True)))
        cached = next(
            (
                entry
                for entry in self._manifest["lists"]
                if entry["category_code"] == category_code and entry["page"] == page
            ),
            None,
        )
        if cached:
            return parse_list_page(self.storage.verify(cached).decode("utf-8-sig"), source_url=url)
        relative = f"lists/{category_code}/{page}.html"
        result = self._source(relative, url)
        parsed = None
        if result["status"] == "ok":
            try:
                parsed = parse_list_page(result["body"].decode("utf-8-sig"), source_url=url)
            except (ParseError, UnicodeError):
                result = dict(result, status="blocked", reason="structure_mismatch")
        manifest = self.snapshot()
        entry = self._retain(manifest, result, relative, url)
        if parsed is None:
            pending = dict(category_code=category_code, page=page)
            if pending not in manifest["pending_lists"]:
                manifest["pending_lists"].append(pending)
            return self._failure(manifest, result)
        entry.update(category_code=category_code, page=page)
        manifest["lists"].append(entry)
        for item in parsed["items"]:
            state = manifest["details"].get(item["source_id"], {}).get("state", "discovered")
            manifest["candidates"].append(
                dict(item, category_code=category_code, page=page, state=state)
            )
        manifest["pending_lists"] = [
            row
            for row in manifest["pending_lists"]
            if row != dict(category_code=category_code, page=page)
        ]
        manifest.update(state="running", reason=None, retry_not_before=None)
        self._commit(manifest)
        return parsed

    def fetch_detail(self, source_id):
        """Reuse verified details or save raw HTML and its DOM-derived record."""
        source_id = str(source_id)
        if not re.fullmatch(r"[0-9]+", source_id):
            raise ValueError("Expected numeric source recipe ID")
        url = f"https://www.10000recipe.com/recipe/{source_id}"
        cached = self._manifest["details"].get(source_id)
        if (
            cached
            and cached["state"] == "parsed"
            and self.storage.path(cached["record"]["path"]).exists()
        ):
            return dict(status="parsed", record=json.loads(self.storage.verify(cached["record"])))
        relative = f"details/{source_id}.html"
        result = self._source(relative, url)
        record = None
        if result["status"] == "ok":
            try:
                record = parse_recipe(result["body"].decode("utf-8-sig"), source_url=url)
            except (ParseError, UnicodeError):
                result = dict(result, status="blocked", reason="structure_mismatch")
        manifest = self.snapshot()
        entry = self._retain(manifest, result, relative, url)
        state = result["status"]
        if record is not None:
            record_path = f"recipes/{source_id}.json"
            self.storage.write_json(record_path, record, immutable=True)
            entry["record"] = dict(
                path=record_path, sha256=digest(self.storage.path(record_path).read_bytes())
            )
            state = "parsed"
        manifest["details"][source_id] = dict(
            state=state, reason=result["reason"], source_url=url, raw=entry
        )
        if record is not None:
            manifest["details"][source_id]["record"] = entry["record"]
        for candidate in manifest["candidates"]:
            if candidate["source_id"] == source_id:
                candidate["state"] = state
        if record is None:
            return self._failure(manifest, result)
        manifest.update(state="running", reason=None, retry_not_before=None)
        self._commit(manifest)
        return dict(status="parsed", record=record)

    def fetch_thumbnail(self, source_id):
        """Save only the list-selected thumbnail; never infer full/step image URLs.

        Validated originals are reused by source ID. A verified provenance sidecar
        recovers publication interrupted before checkpoint replacement.
        """
        source_id = str(source_id)
        candidate = next(
            (row for row in self._manifest["candidates"] if row["source_id"] == source_id), None
        )
        if (
            candidate is None
            or self._manifest["details"].get(source_id, {}).get("state") != "parsed"
        ):
            raise ValueError("Thumbnail requires a recorded list candidate and parsed detail")
        cached = self._manifest["images"].get(source_id)
        if (
            cached
            and cached["state"] == "image_validated"
            and self.storage.path(cached["path"]).exists()
        ):
            self.storage.verify(cached)
            if any(
                row["state"] != "image_validated"
                for row in self._manifest["candidates"]
                if row["source_id"] == source_id
            ):
                manifest = self.snapshot()
                for row in manifest["candidates"]:
                    if row["source_id"] == source_id:
                        row["state"] = "image_validated"
                self._commit(manifest)
            return dict(cached, status="image_validated")
        entry = None
        for path in self.storage.root.glob(f"images/{source_id}.*.meta.json"):
            provenance = self.storage.read_json(path.relative_to(self.storage.root).as_posix())
            if (
                provenance["run_id"] != self.metadata["run_id"]
                or provenance["source_url"] != candidate["thumbnail_url"]
            ):
                raise IntegrityError("Thumbnail provenance differs from this run/source")
            if self.storage.path(provenance["path"]).exists():
                body = self.storage.verify(provenance)
                self.image_downloader.validate(body)
                entry = provenance
                break
        manifest = self.snapshot()
        if entry is None:
            if deferred := self._deferred():
                return deferred
            result = self.image_downloader.get(candidate["thumbnail_url"])
            known = {row["attempt_id"] for row in manifest["attempts"]}
            manifest["attempts"].extend(
                dict(row, kind="thumbnail")
                for row in result["attempts"]
                if row["attempt_id"] not in known
            )
            if result["status"] != "image_validated":
                manifest["images"][source_id] = dict(
                    state=result["status"],
                    reason=result["reason"],
                    source_url=candidate["thumbnail_url"],
                    source_id=source_id,
                )
                return self._failure(manifest, result)
            extension = "jpg" if result["format"] == "JPEG" else result["format"].lower()
            relative = f"images/{source_id}.{extension}"
            entry = {
                key: value
                for key, value in result.items()
                if key not in ("body", "responses", "status")
            }
            entry.update(
                path=relative,
                state="image_validated",
                source_id=source_id,
                run_id=self.metadata["run_id"],
                recipe_source_url=candidate["source_url"],
            )
            self.storage.write_json(relative + ".meta.json", entry)
            self.storage.write(relative, result["body"], immutable=True)
        # Sidecar replay restores attempt history without performing a download.
        known = {row["attempt_id"] for row in manifest["attempts"]}
        manifest["attempts"].extend(
            dict(row, kind="thumbnail")
            for row in entry["attempts"]
            if row["attempt_id"] not in known
        )
        manifest["images"][source_id] = entry
        for row in manifest["candidates"]:
            if row["source_id"] == source_id:
                row["state"] = "image_validated"
        manifest.update(state="running", reason=None, retry_not_before=None)
        self._commit(manifest)
        return dict(entry, status="image_validated")

    def resume_pending(self, *, include_images=False):
        """Drain saved candidates; optionally acquire their selected thumbnails."""
        if deferred := self._deferred():
            return [deferred]
        results, seen = [], set()
        for candidate in self.snapshot()["candidates"]:
            source_id = candidate["source_id"]
            if source_id in seen:
                continue
            seen.add(source_id)
            result = self.fetch_detail(source_id)
            results.append(result)
            if result["status"] in ("blocked", "deferred", "failed"):
                return results
            if include_images:
                image = self.fetch_thumbnail(source_id)
                results.append(image)
                if image["status"] in ("blocked", "deferred", "failed"):
                    return results
        for pending in self.snapshot()["pending_lists"]:
            result = self.fetch_list(pending["category_code"], pending["page"])
            results.append(result)
            if result["status"] in ("blocked", "deferred", "failed"):
                return results
        if self._manifest["candidates"] and any(
            row["source_id"] not in seen for row in self._manifest["candidates"]
        ):
            results.extend(self.resume_pending(include_images=include_images))
        return results
