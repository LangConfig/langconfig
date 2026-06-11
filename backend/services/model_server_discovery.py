"""
Model server discovery for local/OpenAI-compatible LLM servers.
"""
import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from models.local_model import LocalModel
from models.settings import Settings
from services.encryption import encryption_service

logger = logging.getLogger(__name__)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def sanitize_model_id(model_id: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", model_id.lower()).strip("-")


@dataclass
class DiscoveredModel:
    id: str
    name: str
    size: Optional[int] = None
    modified_at: Optional[str] = None


@dataclass
class SyncResult:
    added: int = 0
    updated: int = 0
    removed: int = 0
    errors: List[str] = field(default_factory=list)


class ServerUnreachableError(Exception):
    pass


class ModelServerDiscovery:
    async def discover_models(
        self,
        base_url: str,
        provider: str,
        api_key: Optional[str] = None,
    ) -> List[DiscoveredModel]:
        clean_url = base_url.rstrip("/")
        if clean_url.endswith("/v1"):
            clean_url = clean_url[:-3]

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        timeout = httpx.Timeout(10.0, connect=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if provider == "ollama":
                    return await self._discover_ollama(client, clean_url, headers)
                return await self._discover_openai_compatible(client, clean_url, headers)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise ServerUnreachableError(f"Cannot reach server at {clean_url}: {e}") from e
        except ServerUnreachableError:
            raise
        except Exception as e:
            raise ServerUnreachableError(f"Discovery failed for {clean_url}: {e}") from e

    async def _discover_ollama(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        headers: dict,
    ) -> List[DiscoveredModel]:
        try:
            response = await client.get(f"{base_url}/api/tags", headers=headers)
            if response.status_code == 200:
                data = response.json()
                return [
                    DiscoveredModel(
                        id=m.get("model", m.get("name", "")),
                        name=m.get("name", m.get("model", "")),
                        size=m.get("size"),
                        modified_at=m.get("modified_at"),
                    )
                    for m in data.get("models", [])
                    if m.get("model") or m.get("name")
                ]
        except (httpx.ConnectError, httpx.TimeoutException):
            raise
        except Exception as e:
            logger.debug("Ollama /api/tags failed, trying /v1/models: %s", e)

        return await self._discover_openai_compatible(client, base_url, headers)

    async def _discover_openai_compatible(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        headers: dict,
    ) -> List[DiscoveredModel]:
        response = await client.get(f"{base_url}/v1/models", headers=headers)
        if response.status_code != 200:
            raise ServerUnreachableError(
                f"Server returned {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        return [
            DiscoveredModel(id=m.get("id", ""), name=m.get("id", ""))
            for m in data.get("data", [])
            if m.get("id")
        ]

    def sync_server(self, server: dict, db: Session) -> SyncResult:
        result = SyncResult()
        server_id = server.get("id")
        server_name = server.get("name", "local-server")
        base_url = server.get("base_url", "")
        provider = server.get("provider", "custom")

        api_key = None
        if server.get("api_key"):
            try:
                api_key = encryption_service.decrypt(server["api_key"])
            except Exception as e:
                result.errors.append(f"Failed to decrypt API key for {server_name}: {e}")
                return result

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    discovered = pool.submit(
                        asyncio.run,
                        self.discover_models(base_url, provider, api_key),
                    ).result()
            else:
                discovered = asyncio.run(self.discover_models(base_url, provider, api_key))
        except ServerUnreachableError as e:
            result.errors.append(str(e))
            return result
        except Exception as e:
            result.errors.append(f"Discovery failed: {e}")
            return result

        existing = db.query(LocalModel).filter(
            LocalModel.server_id == server_id,
            LocalModel.auto_discovered == True,
        ).all()
        existing_by_model_id: Dict[str, LocalModel] = {m.model_name: m for m in existing}
        discovered_ids = set()

        server_slug = slugify(server_name) or "local-server"
        model_base_url = base_url.rstrip("/")
        if not model_base_url.endswith("/v1"):
            model_base_url = f"{model_base_url}/v1"

        for model in discovered:
            discovered_ids.add(model.id)
            local_name = f"{server_slug}-{sanitize_model_id(model.id)}"
            existing_model = existing_by_model_id.get(model.id)

            if existing_model:
                if not existing_model.is_active or not existing_model.is_validated:
                    existing_model.is_active = True
                    existing_model.is_validated = True
                    existing_model.validation_error = None
                    existing_model.updated_at = datetime.now(timezone.utc)
                    result.updated += 1
                continue

            if db.query(LocalModel).filter(LocalModel.name == local_name).first():
                logger.debug("Skipping discovered model with existing name: %s", local_name)
                continue

            db.add(LocalModel(
                name=local_name,
                display_name=model.name,
                description=f"Auto-discovered from {server_name}",
                provider=provider,
                base_url=model_base_url,
                model_name=model.id,
                api_key=server.get("api_key"),
                is_validated=True,
                last_validated_at=datetime.now(timezone.utc),
                server_id=server_id,
                auto_discovered=True,
                tags=["auto-discovered"],
            ))
            result.added += 1

        for model_id, existing_model in existing_by_model_id.items():
            if model_id not in discovered_ids and existing_model.is_active:
                existing_model.is_active = False
                existing_model.is_validated = False
                existing_model.validation_error = "Model no longer available on server"
                existing_model.updated_at = datetime.now(timezone.utc)
                result.removed += 1

        db.commit()
        return result


discovery_service = ModelServerDiscovery()


def get_model_servers(db: Session) -> List[dict]:
    settings = db.query(Settings).filter(Settings.id == 1).first()
    if not settings or not settings.model_servers:
        return []
    return settings.model_servers


def save_model_servers(db: Session, servers: List[dict]) -> None:
    settings = db.query(Settings).filter(Settings.id == 1).first()
    if not settings:
        settings = Settings(id=1, model_servers=servers)
        db.add(settings)
    else:
        settings.model_servers = servers
        settings.updated_at = datetime.now(timezone.utc)
    db.commit()


def create_model_server(db: Session, server_data: dict) -> dict:
    servers = get_model_servers(db)
    for server in servers:
        if server.get("name", "").lower() == server_data["name"].lower():
            raise ValueError(f"A server with name '{server_data['name']}' already exists")

    encrypted_api_key = None
    if server_data.get("api_key"):
        encrypted_api_key = encryption_service.encrypt(server_data["api_key"])

    server = {
        "id": str(uuid.uuid4()),
        "name": server_data["name"],
        "base_url": server_data["base_url"].rstrip("/"),
        "provider": server_data.get("provider", "custom"),
        "api_key": encrypted_api_key,
        "is_active": True,
        "auto_sync": server_data.get("auto_sync", False),
        "sync_interval_seconds": server_data.get("sync_interval_seconds", 300),
        "last_sync_at": None,
        "last_sync_error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    servers.append(server)
    save_model_servers(db, servers)
    return server


def delete_model_server(db: Session, server_id: str, hard_delete: bool = False) -> bool:
    servers = get_model_servers(db)
    remaining = [server for server in servers if server.get("id") != server_id]
    if len(remaining) == len(servers):
        return False

    save_model_servers(db, remaining)
    models = db.query(LocalModel).filter(LocalModel.server_id == server_id).all()
    for model in models:
        if hard_delete:
            db.delete(model)
        else:
            model.is_active = False
            model.is_validated = False
            model.validation_error = "Parent model server removed"
            model.updated_at = datetime.now(timezone.utc)
    db.commit()
    return True
