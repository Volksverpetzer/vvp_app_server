from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("proxycache", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="instatoken",
            name="account",
            field=models.CharField(
                db_index=True, default="volksverpetzer", max_length=100
            ),
        ),
    ]
