from asgiref.sync import async_to_sync
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.social_media_chatbot.application.use_cases.chat import ChatUseCase
from apps.social_media_chatbot.infrastructure.ai.autogen_chatbot import (
    AutoGenChatbot,
)

from .serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
)


class ChatView(APIView):

    @extend_schema(
        request=ChatRequestSerializer,
        responses=ChatResponseSerializer,
    )
    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.validated_data["message"]

        chatbot = AutoGenChatbot()
        use_case = ChatUseCase(chatbot)

        response = async_to_sync(use_case.execute)(message)

        return Response(
            {"response": response},
            status=status.HTTP_200_OK,
        )
