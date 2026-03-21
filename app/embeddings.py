import httpx

from . import config


async def embed(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{config.get_ollama_url()}/api/embeddings",
            json={"model": config.get_embed_model(), "prompt": text},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    return [await embed(t) for t in texts]
