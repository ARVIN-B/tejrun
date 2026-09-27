from abc import ABC, abstractmethod


class ChatMemoryRepository(ABC):

    @abstractmethod
    async def get_or_create_user(
        self,
        source: str,
        external_id: str,
    ):
        raise NotImplementedError

    @abstractmethod
    async def get_or_create_conversation(
        self,
        user,
    ):
        raise NotImplementedError

    @abstractmethod
    async def get_history(
        self,
        conversation,
        limit: int = 20,
    ):
        raise NotImplementedError

    @abstractmethod
    async def save_message(
        self,
        conversation,
        role: str,
        content: str,
    ):
        raise NotImplementedError