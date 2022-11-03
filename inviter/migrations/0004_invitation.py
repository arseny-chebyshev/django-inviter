# Generated by Django 4.1.2 on 2022-10-12 17:08

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inviter', '0003_alter_group_dt_alter_user_dt'),
    ]

    operations = [
        migrations.CreateModel(
            name='Invitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_added', models.BooleanField(default=False)),
                ('error_message', models.CharField(blank=True, max_length=255, null=True, verbose_name='Error message')),
                ('dt', models.DateTimeField(auto_now_add=True, verbose_name='Creation datetime')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inviter.group')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inviter.user')),
            ],
        ),
    ]
