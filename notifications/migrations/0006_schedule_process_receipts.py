from django.db import migrations

SCHEDULE_NAME = "Check Expo push receipts"


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.update_or_create(
        name=SCHEDULE_NAME,
        defaults={
            "func": "notifications.helper.process_receipts",
            "schedule_type": "I",  # minutes
            "minutes": 30,
            "repeats": -1,
        },
    )


def delete_schedule(apps, schema_editor):
    apps.get_model("django_q", "Schedule").objects.filter(name=SCHEDULE_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0005_notificationdevice_notification_new_pruefpunkt"),
        ("django_q", "0019_alter_task_options_alter_ormq_key_alter_ormq_lock_and_more"),
    ]

    operations = [migrations.RunPython(create_schedule, delete_schedule)]
