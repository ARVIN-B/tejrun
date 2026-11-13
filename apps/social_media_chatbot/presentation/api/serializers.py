from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    bot_id = serializers.IntegerField(min_value=1)
    external_id = serializers.CharField(max_length=255)
    message = serializers.CharField(
        required=True,
        allow_blank=False,
    )


class ChatResponseSerializer(serializers.Serializer):
    response = serializers.CharField()
