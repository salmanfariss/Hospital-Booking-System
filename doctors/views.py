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


# ============================================================
# DOCTOR LOGIN
# ============================================================

def doctor_login(request):

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        specialization = request.POST.get(
            "specialization",
            ""
        ).strip()

        doctor, created = Doctor.objects.get_or_create(
            email=email,
            defaults={
                "name": name,
                "specialization": specialization
            }
        )

        # If existing doctor logs in, update details if needed
        if not created:

            doctor.name = name
            doctor.specialization = specialization

            doctor.save(
                update_fields=[
                    "name",
                    "specialization"
                ]
            )

        request.session["doctor_id"] = doctor.id

        return redirect(
            "doctor_dashboard"
        )

    return render(
        request,
        "doctors/login.html"
    )


# ============================================================
# DOCTOR DASHBOARD
# ============================================================

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

    today_appointments = (
        Appointment.objects
        .filter(
            doctor=doctor,
            appointment_date=today
        )
        .exclude(
            status="cancelled"
        )
        .order_by(
            "appointment_time"
        )
    )

    pending_count = today_appointments.filter(
        status="pending"
    ).count()

    completed_count = today_appointments.filter(
        status="completed"
    ).count()

    total_appointments = today_appointments.count()

    upcoming_count = (
        today_appointments
        .exclude(
            status="completed"
        )
        .count()
    )

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


# ============================================================
# MANAGE AVAILABILITY
# ============================================================

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

    # ========================================================
    # POST
    # ========================================================

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

        # NEW
        max_patients_per_slot = request.POST.get(
            "max_patients_per_slot"
        )

        break_starts = request.POST.getlist(
            "break_start[]"
        )

        break_ends = request.POST.getlist(
            "break_end[]"
        )

        # ----------------------------------------------------
        # BASIC VALIDATION
        # ----------------------------------------------------

        if not days:
            return render(
                request,
                "doctors/manage_availability.html",
                {
                    "doctor": doctor,
                    "error": "Please select at least one day."
                }
            )

        if not start_time or not end_time:
            return render(
                request,
                "doctors/manage_availability.html",
                {
                    "doctor": doctor,
                    "error": "Please select start and end time."
                }
            )

        if not slot_duration:
            slot_duration = 30

        if not max_appointments:
            max_appointments = 20

        if not max_patients_per_slot:
            max_patients_per_slot = 1

        # ----------------------------------------------------
        # CONVERT TO INTEGER
        # ----------------------------------------------------

        try:

            slot_duration = int(
                slot_duration
            )

            max_appointments = int(
                max_appointments
            )

            max_patients_per_slot = int(
                max_patients_per_slot
            )

        except ValueError:

            return render(
                request,
                "doctors/manage_availability.html",
                {
                    "doctor": doctor,
                    "error": "Please enter valid numbers."
                }
            )

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if slot_duration <= 0:

            return render(
                request,
                "doctors/manage_availability.html",
                {
                    "doctor": doctor,
                    "error": (
                        "Slot duration must be greater than 0."
                    )
                }
            )

        if max_appointments <= 0:

            return render(
                request,
                "doctors/manage_availability.html",
                {
                    "doctor": doctor,
                    "error": (
                        "Maximum appointments per day "
                        "must be greater than 0."
                    )
                }
            )

        if max_patients_per_slot <= 0:

            return render(
                request,
                "doctors/manage_availability.html",
                {
                    "doctor": doctor,
                    "error": (
                        "Maximum patients per slot "
                        "must be greater than 0."
                    )
                }
            )

        # ----------------------------------------------------
        # DELETE OLD SCHEDULES
        # ----------------------------------------------------

        DoctorSchedule.objects.filter(
            doctor=doctor
        ).delete()

        # ----------------------------------------------------
        # CREATE NEW SCHEDULE
        # ----------------------------------------------------

        for day in days:

            schedule = DoctorSchedule.objects.create(

                doctor=doctor,

                day=day,

                start_time=start_time,

                end_time=end_time,

                slot_duration=slot_duration,

                max_appointments=max_appointments,

                max_patients_per_slot=(
                    max_patients_per_slot
                ),

                is_available=True
            )

            # ------------------------------------------------
            # CREATE BREAKS
            # ------------------------------------------------

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

    # ========================================================
    # GET
    # ========================================================

    return render(
        request,
        "doctors/manage_availability.html",
        {
            "doctor": doctor
        }
    )


# ============================================================
# DOCTOR LOGOUT
# ============================================================

def doctor_logout(request):

    request.session.flush()

    return redirect(
        "home"
    )


# ============================================================
# APPLY LEAVE
# ============================================================

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

    leaves = (
        DoctorLeave.objects
        .filter(
            doctor=doctor
        )
        .order_by(
            "leave_date"
        )
    )

    return render(
        request,
        "doctors/apply_leave.html",
        {
            "doctor": doctor,
            "leaves": leaves
        }
    )


# ============================================================
# DOCTOR APPOINTMENTS
# ============================================================

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

    appointments = (
        Appointment.objects
        .filter(
            doctor=doctor
        )
        .order_by(
            "-appointment_date",
            "appointment_time"
        )
    )

    return render(
        request,
        "doctors/appointments.html",
        {
            "doctor": doctor,
            "appointments": appointments
        }
    )


# ============================================================
# UPDATE APPOINTMENT STATUS
# ============================================================

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

            appointment.save(
                update_fields=[
                    "status"
                ]
            )

    return redirect(
        "doctor_appointments"
    )