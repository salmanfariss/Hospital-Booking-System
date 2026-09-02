from django.db import models
from django.db.models import Q, Max

from doctors.models import Doctor
from patients.models import Patient


class Appointment(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="appointments"
    )

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="appointments"
    )

    appointment_date = models.DateField()

    appointment_time = models.TimeField()

    token_number = models.IntegerField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        ordering = [
            "appointment_date",
            "appointment_time"
        ]

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "doctor",
                    "appointment_date",
                    "appointment_time"
                ],
                condition=~Q(status="cancelled"),
                name="unique_active_doctor_appointment_slot"
            )

        ]

    def save(self, *args, **kwargs):

        if self.token_number is None:

            last_token = Appointment.objects.filter(
                doctor=self.doctor,
                appointment_date=self.appointment_date
            ).aggregate(
                Max("token_number")
            )["token_number__max"]

            if last_token is None:
                self.token_number = 1
            else:
                self.token_number = last_token + 1

        super().save(*args, **kwargs)


    def __str__(self):

        return (
            f"Token #{self.token_number} - "
            f"{self.patient.name} - "
            f"Dr. {self.doctor.name}"
        )