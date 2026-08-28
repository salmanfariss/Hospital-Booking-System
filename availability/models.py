from django.db import models
from doctors.models import Doctor


class DoctorSchedule(models.Model):
    DAYS = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE
    )

    day = models.CharField(
        max_length=20,
        choices=DAYS
    )

    start_time = models.TimeField()
    end_time = models.TimeField()

    slot_duration = models.IntegerField(
        default=30
    )

    max_appointments = models.IntegerField(
        default=20
    )

    is_available = models.BooleanField(
        default=True
    )

    def __str__(self):
        return f"{self.doctor.name} - {self.day}"
    
class DoctorBreak(models.Model):
    schedule = models.ForeignKey(
        DoctorSchedule,
        on_delete=models.CASCADE,
        related_name='breaks'
    )

    break_start = models.TimeField()
    break_end = models.TimeField()

    def __str__(self):
        return f"{self.break_start} - {self.break_end}"

class DoctorLeave(models.Model):

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="leaves"
    )

    leave_date = models.DateField()

    reason = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = (
            "doctor",
            "leave_date"
        )

    def __str__(self):
        return f"{self.doctor.name} - {self.leave_date}"