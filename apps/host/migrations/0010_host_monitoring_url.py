# Generated by Django 3.0.6 on 2020-08-19 10:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('host', '0009_image_protocol'),
    ]

    operations = [
        migrations.AddField(
            model_name='host',
            name='monitoring_url',
            field=models.CharField(max_length=1000, null=True),
        ),
    ]
