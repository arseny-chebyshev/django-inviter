from django.db import models
from bulk_update_or_create import BulkUpdateOrCreateQuerySet

# Create your models here.
class User(models.Model):
    
    objects = BulkUpdateOrCreateQuerySet.as_manager()

    id = models.PositiveBigIntegerField(primary_key=True, unique=True, blank=False, null=False, verbose_name="User ID")
    first_name = models.CharField(verbose_name='Fisrt Name', max_length=255, blank=True, null=True)
    last_name = models.CharField(verbose_name='Last Name', max_length=255, blank=True, null=True)
    access_hash = models.BigIntegerField(verbose_name="Access Hash")
    dt = models.DateTimeField(verbose_name="Creation datetime", auto_now_add=True)

class Group(models.Model):

    objects = BulkUpdateOrCreateQuerySet.as_manager()

    id = models.PositiveBigIntegerField(primary_key=True, unique=True, blank=False, null=False, verbose_name="Group ID")
    link = models.CharField(verbose_name="Link to group", max_length=255)
    access_hash = models.BigIntegerField(verbose_name="Access Hash")
    dt = models.DateTimeField(verbose_name="Creation datetime", auto_now_add=True)
    user = models.ManyToManyField(to="User", related_name="groups_with_user")

class Invitation(models.Model):

    objects = BulkUpdateOrCreateQuerySet.as_manager()

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    is_added = models.BooleanField(default=False)
    error_message = models.CharField(verbose_name="Error message", max_length=2048, null=True, blank=True)
    dt = models.DateTimeField(verbose_name="Creation datetime", auto_now_add=True)
