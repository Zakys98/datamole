import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated

import aiohttp
from fastapi import FastAPI, Depends, HTTPException, Response, status

from datamole.services.storage import Storage, EventType


def storage_dep() -> Storage:
    return Storage()


async def get_events(storage: Storage = storage_dep()) -> None:
    GITHUB_EVENTS_URL = "https://api.github.com/events"

    headers = {"Accept": "application/vnd.github+json", "User-Agent": "github-event-fetcher"}
    print("Fetching events from GitHub API...")
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(GITHUB_EVENTS_URL) as response:
            if response.status != 200:
                raise Exception(f"GitHub API returned status code {response.status}")
            raw_events = await response.json()

    events = [event for event in raw_events if event["type"] in EventType.to_set()]

    for event in events:
        storage.save(event["type"], event)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async def event_updater():
        while True:
            try:
                await get_events()
            except Exception as e:
                print("Failed to update events:", e)
            await asyncio.sleep(10)

    task = asyncio.create_task(event_updater())

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)


@app.get("/average")
def average_time(repository: str, storage: Annotated[Storage, Depends(storage_dep)]) -> Response:
    events = [
        event
        for event in storage.get(EventType.PULL_REQUEST_EVENT)
        if event["repo"]["name"] == repository
    ]

    if not events:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No repository found")

    if len(events) < 2:
        return Response(
            status_code=status.HTTP_200_OK,
            content=f"Cannot calculate average time for repository {repository} with less than 2 events",
        )

    times = [datetime.fromisoformat(event["created_at"].replace("Z", "+00:00")) for event in events]
    times.sort()
    intervals = [
        (times[i] - times[i-1]).total_seconds()
        for i in range(1, len(times))
    ]
    average_time = sum(intervals) / len(intervals)

    return Response(
        status_code=status.HTTP_200_OK,
        content=f"Average time: {average_time} seconds",
    )


@app.get("/total")
async def total_events(offset: int, storage: Annotated[Storage, Depends(storage_dep)]) -> Response:
    output = {}
    adjusted_time = datetime.now(timezone.utc) - timedelta(minutes=offset)

    for event_type in EventType.to_set():
        events = storage.get(event_type)
        output[event_type] = 0
        for event in events:
            event_time = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
            if event_time >= adjusted_time:
                output[event_type] += 1

    return Response(
        status_code=status.HTTP_200_OK,
        content=", ".join([f"{key}: {value}" for key, value in output.items()]),
    )
