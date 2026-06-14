from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reportFake', '0006_alter_fakereport_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='fakereport',
            name='bluesky_url',
            field=models.URLField(blank=True, default=None, null=True),
        ),
    ]
