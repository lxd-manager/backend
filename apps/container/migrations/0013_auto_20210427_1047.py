# Generated by Django 3.0.6 on 2021-04-27 10:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('container', '0012_container_custom_network'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ip',
            name='ip',
            field=models.GenericIPAddressField(unique=True),
        ),
    ]