from collections import defaultdict
from enum import StrEnum


class EventType(StrEnum):
    WATCH_EVENT = "WatchEvent"
    PULL_REQUEST_EVENT = "PullRequestEvent"
    ISSUES_EVENT = "IssuesEvent"

    @classmethod
    def to_set(cls) -> set[str]:
        return {cls.WATCH_EVENT, cls.PULL_REQUEST_EVENT, cls.ISSUES_EVENT}


class Storage:
    storage: defaultdict[EventType, list[any]] = defaultdict(list)

    def save(self, key: EventType, value: any) -> None:
        self.storage[key].append(value)

    def get(self, key: EventType) -> list[any]:
        return self.storage[key]
