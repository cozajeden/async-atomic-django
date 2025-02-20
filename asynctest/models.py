from django.db import models

class MyModel(models.Model):
    name = models.CharField(max_length=255)
    saved = models.IntegerField(default=0)
    
    def save(self, *args, **kwargs):
        self.saved += 1
        super().save(*args, **kwargs)
