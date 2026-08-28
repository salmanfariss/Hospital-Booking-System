from django.db import models
from doctors.models import Doctor


# ============================================================
# DOCTOR SCHEDULE
# ============================================================

class DoctorSchedule(models.Model):

    DAYS = [
        ("Monday", "Monday"),
        ("Tuesday", "Tuesday"),
        ("Wednesday", "Wednesday"),
        ("Thursday", "Thursday"),
        ("Friday", "Friday"),
        ("Saturday", "Saturday"),
        ("Sunday", "Sunday"),
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

    # --------------------------------------------------------
    # SLOT DURATION
    # Example:
    # 15 = 15 minutes
    # 30 = 30 minutes
    # --------------------------------------------------------

    slot_duration = models.IntegerField(
        default=30
    )

    # --------------------------------------------------------
    # MAXIMUM APPOINTMENTS PER DAY
    #
    # Example:
    # max_appointments = 10
    #
    # Doctor can have maximum 10 appointments
    # on that particular day.
    # --------------------------------------------------------

    max_appointments = models.IntegerField(
        default=20
    )

    # --------------------------------------------------------
    # MAXIMUM PATIENTS PER SLOT
    #
    # Example:
    # slot_duration = 15
    # max_patients_per_slot = 2
    #
    # 4:00 PM -> 2 patients
    # 4:15 PM -> 2 patients
    # 4:30 PM -> 2 patients
    # --------------------------------------------------------

    max_patients_per_slot = models.IntegerField(
        default=1
    )

    # --------------------------------------------------------
    # AVAILABILITY
    # --------------------------------------------------------

    is_available = models.BooleanField(
        default=True
    )

    def __str__(self):

        return (
            f"{self.doctor.name} - "
            f"{self.day}"
        )


# ============================================================
# DOCTOR BREAK
# ============================================================

class DoctorBreak(models.Model):

    schedule = models.ForeignKey(
        DoctorSchedule,
        on_delete=models.CASCADE,
        related_name="breaks"
    )

    break_start = models.TimeField()

    break_end = models.TimeField()

    def __str__(self):

        return (
            f"{self.break_start} - "
            f"{self.break_end}"
        )


# ============================================================
# DOCTOR LEAVE
# ============================================================

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

        return (
            f"{self.doctor.name} - "
            f"{self.leave_date}"
        )