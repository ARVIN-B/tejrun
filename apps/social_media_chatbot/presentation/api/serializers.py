from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(
        required=True,
        allow_blank=False,
    )


class ChatResponseSerializer(serializers.Serializer):
    response = serializers.CharField()