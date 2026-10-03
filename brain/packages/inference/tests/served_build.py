"""Read the engine build a llama-server names on ``GET /props``, for a live run to print."""

import httpx


async def served_build(client: httpx.AsyncClient, endpoint: str, role: str) -> str:
    """Print ``build_info`` off ``GET /props`` at ``endpoint`` under ``role``, and return it."""
    response = await client.get(f"{endpoint.rstrip('/')}/props")
    response.raise_for_status()
    props: dict[str, object] = response.json()
    build = props.get("build_info")
    assert isinstance(build, str), (
        f"GET /props at {endpoint} names no build_info, so this run cannot say which engine "
        f"build served it: {sorted(props)}"
    )
    print(f"\n{role}  {build} at {endpoint}")  # noqa: T201 -- the build is part of the run's output
    return build
