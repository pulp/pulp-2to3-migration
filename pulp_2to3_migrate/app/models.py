from django.db import models

class Pulp2To3Map(models.Model):
    pulp2_id = models.UUIDField(primary_key=True)
    pulp3_id = models.UUIDField()
    type = models.CharField(max_length=255)
