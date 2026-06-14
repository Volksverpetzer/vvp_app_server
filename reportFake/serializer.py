# Write Serializer for ReportFake Model
from rest_framework import serializers

from .models import FakeReport


class FakeReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = FakeReport
        fields = "__all__"
