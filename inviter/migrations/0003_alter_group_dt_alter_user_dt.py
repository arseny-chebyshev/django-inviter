# Generated by Django 4.1.2 on 2022-10-12 17:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inviter', '0002_alter_group_dt_alter_user_dt'),
    ]

    operations = [
        migrations.AlterField(
            model_name='group',
            name='dt',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Creation datetime'),
        ),
        migrations.AlterField(
            model_name='user',
            name='dt',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Creation datetime'),
        ),
    ]
