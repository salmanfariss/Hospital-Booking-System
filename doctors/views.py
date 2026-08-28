from django.shortcuts import (
    render,
    redirect,
    get_object_or_404
)

from django.utils import timezone

from .models import Doctor

from availability.models import (
    DoctorSchedule,
    DoctorBreak,
    DoctorLeave
)

from booking.models import Appointment


def doctor_login(request):

    if request.method == "POST":

        name = request.POST.get("name")
        email = request.POST.get("email")
        specialization = request.POST.get("specialization")

        doctor, created = Doctor.objects.get_or_create(
            email=email,
            defaults={
                "name": name,
                "specialization": specialization
            }
        )

        request.session["doctor_id"] = doctor.id

        return redirect("doctor_dashboard")

    return render(
        request,
        "doctors/login.html"
    )


def doctor_dashboard(request):

    doctor_id = request.session.get(
        "doctor_id"
    )

    if not doctor_id:
        return redirect(
            "doctor_login"
        )

    doctor = get_object_or_404(
        Doctor,
        id=doctor_id
    )

    today = timezone.localdate()

    today_appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=today
    ).exclude(
        status="cancelled"
    ).order_by(
        "appointment_time"
    )

    pending_count = today_appointments.filter(
        status="pending"
    ).count()

    completed_count = today_appointments.filter(
        status="completed"
    ).count()

    total_appointments = today_appointments.count()

    upcoming_count = today_appointments.exclude(
        status="completed"
    ).count()

    return render(
        request,
        "doctors/dashboard.html",
        {
            "doctor": doctor,
            "today_appointments": today_appointments,
            "total_appointments": total_appointments,
            "pending_count": pending_count,
            "completed_count": completed_count,
            "upcoming_count": upcoming_count,
            "today": today,
        }
    )


def manage_availability(request):

    doctor_id = request.session.get(
        "doctor_id"
    )

    if not doctor_id:
        return redirect(
            "doctor_login"
        )

    doctor = get_object_or_404(
        Doctor,
        id=doctor_id
    )

    if request.method == "POST":

        days = request.POST.getlist(
            "days"
        )

        start_time = request.POST.get(
            "start_time"
        )

        end_time = request.POST.get(
            "end_time"
        )

        slot_duration = request.POST.get(
            "slot_duration"
        )

        max_appointments = request.POST.get(
            "max_appointments"
        )

        break_starts = request.POST.getlist(
            "break_start[]"
        )

        break_ends = request.POST.getlist(
            "break_end[]"
        )

        DoctorSchedule.objects.filter(
            doctor=doctor
        ).delete()

        for day in days:

            schedule = DoctorSchedule.objects.create(
                doctor=doctor,
                day=day,
                start_time=start_time,
                end_time=end_time,
                slot_duration=slot_duration,
                max_appointments=max_appointments,
                is_available=True
            )

            for start, end in zip(
                break_starts,
                break_ends
            ):

                if start and end:

                    DoctorBreak.objects.create(
                        schedule=schedule,
                        break_start=start,
                        break_end=end
                    )

        return redirect(
            "doctor_dashboard"
        )

    return render(
        request,
        "doctors/manage_availability.html",
        {
            "doctor": doctor
        }
    )


def doctor_logout(request):

    request.session.flush()

    return redirect(
        "home"
    )


def apply_leave(request):

    doctor_id = request.session.get(
        "doctor_id"
    )

    if not doctor_id:
        return redirect(
            "doctor_login"
        )

    doctor = get_object_or_404(
        Doctor,
        id=doctor_id
    )

    if request.method == "POST":

        leave_date = request.POST.get(
            "leave_date"
        )

        reason = request.POST.get(
            "reason"
        )

        if leave_date:

            DoctorLeave.objects.get_or_create(
                doctor=doctor,
                leave_date=leave_date,
                defaults={
                    "reason": reason
                }
            )

        return redirect(
            "doctor_dashboard"
        )

    leaves = DoctorLeave.objects.filter(
        doctor=doctor
    ).order_by(
        "leave_date"
    )

    return render(
        request,
        "doctors/apply_leave.html",
        {
            "doctor": doctor,
            "leaves": leaves
        }
    )


def doctor_appointments(request):

    doctor_id = request.session.get(
        "doctor_id"
    )

    if not doctor_id:
        return redirect(
            "doctor_login"
        )

    doctor = get_object_or_404(
        Doctor,
        id=doctor_id
    )

    appointments = Appointment.objects.filter(
        doctor=doctor
    ).order_by(
        "-appointment_date",
        "appointment_time"
    )

    return render(
        request,
        "doctors/appointments.html",
        {
            "doctor": doctor,
            "appointments": appointments
        }
    )


def update_appointment_status(
    request,
    appointment_id,
    status
):

    doctor_id = request.session.get(
        "doctor_id"
    )

    if not doctor_id:
        return redirect(
            "doctor_login"
        )

    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        doctor_id=doctor_id
    )

    if request.method == "POST":

        allowed_statuses = [
            "confirmed",
            "completed",
            "cancelled"
        ]

        if status in allowed_statuses:

            appointment.status = status

            appointment.save()

    return redirect(
        "doctor_appointments"
    )
