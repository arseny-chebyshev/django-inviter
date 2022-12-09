from datetime import datetime
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

class TelethonSession(models.Model):

    session_string = models.TextField(verbose_name="Session string identifier", unique=True)
    is_active = models.BooleanField(default=True)
    is_on_rehab = models.BooleanField(default=False)
    rehab_start_time = models.DateTimeField(null=True, auto_now=True) # Телетон опять напился и в рехаб
    in_use = models.BooleanField(default=False)

    @property
    def is_finished_rehab(self) -> bool: # Вся семья ждет когда он либо откинется либо закодируется
        return (datetime.now() - self.rehab_start_time).total_seconds >= 100000

    def send_to_rehab(self):
        self.is_active, self.is_on_rehab = False, True
        self.rehab_start_time = datetime.now()
        self.in_use = False
        self.save()
