from django.contrib import admin
from .models import (
    DoctorSchedule,
    DoctorBreak,
    DoctorLeave
)


class DoctorBreakInline(admin.TabularInline):
    model = DoctorBreak
    extra = 1


@admin.register(DoctorSchedule)
class DoctorScheduleAdmin(admin.ModelAdmin):

    list_display = (
        "doctor",
        "day",
        "start_time",
        "end_time",
        "slot_duration",
        "max_appointments",
        "is_available",
    )

    list_filter = (
        "doctor",
        "day",
        "is_available",
    )

    search_fields = (
        "doctor__name",
        "doctor__email",
    )

    inlines = [
        DoctorBreakInline
    ]


@admin.register(DoctorLeave)
class DoctorLeaveAdmin(admin.ModelAdmin):

    list_display = (
        "doctor",
        "leave_date",
        "reason",
        "created_at",
    )

    list_filter = (
        "leave_date",
    )

    search_fields = (
        "doctor__name",
        "doctor__email",
    )