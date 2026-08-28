from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.contrib.auth.hashers import make_password, check_password
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from .models import Patient
from doctors.models import Doctor
from booking.models import Appointment
from availability.models import DoctorSchedule, DoctorLeave


# ============================================================
# HELPER — NO CACHE
# ============================================================

def no_cache(response):

    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"

    return response


# ============================================================
# PATIENT REGISTER
# ============================================================

def patient_register(request):

    patient_id = request.session.get("patient_id")

    if patient_id:

        if Patient.objects.filter(
            id=patient_id
        ).exists():

            return redirect(
                "department_list"
            )

        request.session.pop(
            "patient_id",
            None
        )

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        confirm_password = request.POST.get(
            "confirm_password",
            ""
        )

        if (
            not name
            or not email
            or not password
            or not confirm_password
        ):

            response = render(
                request,
                "patients/register.html",
                {
                    "error": "Please fill in all fields.",
                    "name": name,
                    "email": email,
                }
            )

            return no_cache(response)

        if password != confirm_password:

            response = render(
                request,
                "patients/register.html",
                {
                    "error": "Passwords do not match.",
                    "name": name,
                    "email": email,
                }
            )

            return no_cache(response)

        if len(password) < 6:

            response = render(
                request,
                "patients/register.html",
                {
                    "error": "Password must be at least 6 characters.",
                    "name": name,
                    "email": email,
                }
            )

            return no_cache(response)

        if Patient.objects.filter(
            email=email
        ).exists():

            response = render(
                request,
                "patients/register.html",
                {
                    "error": (
                        "An account with this email already exists. "
                        "Please login."
                    ),
                    "name": name,
                    "email": email,
                }
            )

            return no_cache(response)

        patient = Patient.objects.create(
            name=name,
            email=email,
            password=make_password(password)
        )

        request.session["patient_id"] = patient.id

        return redirect(
            "department_list"
        )

    response = render(
        request,
        "patients/register.html"
    )

    return no_cache(response)


# ============================================================
# HELPER — CHECK PARTICULAR DOCTOR AVAILABILITY
# ============================================================

def is_doctor_available(
    doctor,
    selected_date,
    selected_time
):

    # --------------------------------------------------------
    # CHECK LEAVE
    # --------------------------------------------------------

    if DoctorLeave.objects.filter(
        doctor=doctor,
        leave_date=selected_date
    ).exists():

        return False

    # --------------------------------------------------------
    # CHECK SCHEDULE
    # --------------------------------------------------------

    day_name = selected_date.strftime(
        "%A"
    )

    schedule = DoctorSchedule.objects.filter(
        doctor=doctor,
        day=day_name,
        is_available=True
    ).first()

    if not schedule:

        return False

    # --------------------------------------------------------
    # CHECK WORKING TIME
    # --------------------------------------------------------

    if not (
        schedule.start_time
        <= selected_time
        < schedule.end_time
    ):

        return False

    # --------------------------------------------------------
    # CHECK SLOT DURATION
    # --------------------------------------------------------

    slot_duration = timedelta(
        minutes=schedule.slot_duration
    )

    selected_start = datetime.combine(
        selected_date,
        selected_time
    )

    selected_end_datetime = (
        selected_start
        + slot_duration
    )

    selected_end = (
        selected_end_datetime.time()
    )

    if selected_end > schedule.end_time:

        return False

    # --------------------------------------------------------
    # CHECK BREAK
    # --------------------------------------------------------

    for doctor_break in schedule.breaks.all():

        if (
            selected_time < doctor_break.break_end
            and
            selected_end > doctor_break.break_start
        ):

            return False

    # --------------------------------------------------------
    # CHECK EXISTING ACTIVE BOOKING
    # --------------------------------------------------------

    already_booked = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=selected_date,
        appointment_time=selected_time
    ).exclude(
        status="cancelled"
    ).exists()

    if already_booked:

        return False

    return True


# ============================================================
# HELPER — CHECK WHETHER WHOLE SLOT IS BOOKED
# ============================================================

def is_slot_fully_booked(
    department,
    selected_date,
    selected_time
):

    doctors = Doctor.objects.filter(
        specialization=department
    )

    if not doctors.exists():

        return True

    for doctor in doctors:

        if is_doctor_available(
            doctor,
            selected_date,
            selected_time
        ):

            return False

    return True


# ============================================================
# PATIENT LOGIN
# ============================================================

def patient_login(request):

    patient_id = request.session.get(
        "patient_id"
    )

    if patient_id:

        if Patient.objects.filter(
            id=patient_id
        ).exists():

            return redirect(
                "department_list"
            )

        request.session.pop(
            "patient_id",
            None
        )

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        if (
            not name
            or not email
            or not password
        ):

            response = render(
                request,
                "patients/login.html",
                {
                    "error": "Please fill in all fields.",
                    "name": name,
                    "email": email,
                }
            )

            return no_cache(response)

        try:

            patient = Patient.objects.get(
                email=email
            )

        except Patient.DoesNotExist:

            response = render(
                request,
                "patients/login.html",
                {
                    "error": "Invalid email or password.",
                    "name": name,
                    "email": email,
                }
            )

            return no_cache(response)

        if not patient.password:

            response = render(
                request,
                "patients/login.html",
                {
                    "error": (
                        "This account does not have a password. "
                        "Please register again."
                    ),
                    "name": name,
                    "email": email,
                }
            )

            return no_cache(response)

        if not check_password(
            password,
            patient.password
        ):

            response = render(
                request,
                "patients/login.html",
                {
                    "error": "Invalid email or password.",
                    "name": name,
                    "email": email,
                }
            )

            return no_cache(response)

        if patient.name != name:

            patient.name = name

            patient.save(
                update_fields=["name"]
            )

        request.session["patient_id"] = patient.id

        return redirect(
            "department_list"
        )

    response = render(
        request,
        "patients/login.html"
    )

    return no_cache(response)


# ============================================================
# DEPARTMENT LIST
# ============================================================

def department_list(request):

    patient_id = request.session.get(
        "patient_id"
    )

    if not patient_id:

        return redirect(
            "patient_login"
        )

    if not Patient.objects.filter(
        id=patient_id
    ).exists():

        request.session.pop(
            "patient_id",
            None
        )

        return redirect(
            "patient_login"
        )

    departments = (
        Doctor.objects
        .values_list(
            "specialization",
            flat=True
        )
        .distinct()
    )

    return render(
        request,
        "patients/department_list.html",
        {
            "departments": departments
        }
    )


# ============================================================
# SELECT DATE + TIME SLOT
# ============================================================

def select_datetime(request):

    patient_id = request.session.get("patient_id")

    if not patient_id:
        return redirect("patient_login")

    if not Patient.objects.filter(id=patient_id).exists():
        request.session.pop("patient_id", None)
        return redirect("patient_login")

    department = request.GET.get("department")

    if not department:
        return redirect("department_list")

    selected_date = request.GET.get("date")

    slots = []
    message = None

    # ========================================================
    # GENERATE ALL TIME SLOTS
    # ========================================================

    def generate_slots(selected_date_obj):

        doctors = Doctor.objects.filter(
            specialization=department
        )

        day_name = selected_date_obj.strftime("%A")

        possible_times = set()

        # ----------------------------------------------------
        # GET ALL POSSIBLE SLOTS FROM DOCTORS
        # ----------------------------------------------------

        for doctor in doctors:

            # ------------------------------------------------
            # DOCTOR LEAVE
            # ------------------------------------------------

            if DoctorLeave.objects.filter(
                doctor=doctor,
                leave_date=selected_date_obj
            ).exists():

                continue

            # ------------------------------------------------
            # DOCTOR SCHEDULE
            # ------------------------------------------------

            schedule = DoctorSchedule.objects.filter(
                doctor=doctor,
                day=day_name,
                is_available=True
            ).first()

            if not schedule:
                continue

            slot_duration = timedelta(
                minutes=schedule.slot_duration
            )

            current_datetime = datetime.combine(
                selected_date_obj,
                schedule.start_time
            )

            end_datetime = datetime.combine(
                selected_date_obj,
                schedule.end_time
            )

            # ------------------------------------------------
            # GENERATE SLOTS
            # ------------------------------------------------

            while (
                current_datetime + slot_duration
                <= end_datetime
            ):

                current_slot = current_datetime.time()

                slot_end = (
                    current_datetime + slot_duration
                ).time()

                is_break = False

                # --------------------------------------------
                # CHECK BREAK
                # --------------------------------------------

                for doctor_break in schedule.breaks.all():

                    if (
                        current_slot < doctor_break.break_end
                        and
                        slot_end > doctor_break.break_start
                    ):

                        is_break = True
                        break

                if not is_break:

                    possible_times.add(
                        current_slot
                    )

                current_datetime += slot_duration

        # ====================================================
        # CURRENT DATE / TIME
        # ====================================================

        now = timezone.localtime()

        today = now.date()
        current_time = now.time()

        result = []

        # ====================================================
        # CHECK EVERY SLOT
        # ====================================================

        for slot_time in sorted(possible_times):

            # ------------------------------------------------
            # CHECK PAST
            # ------------------------------------------------

            past = False

            if selected_date_obj < today:

                past = True

            elif (
                selected_date_obj == today
                and
                slot_time <= current_time
            ):

                past = True

            # ------------------------------------------------
            # CHECK WHETHER ALL DOCTORS ARE BOOKED
            # ------------------------------------------------

            fully_booked = is_slot_fully_booked(
                department,
                selected_date_obj,
                slot_time
            )

            # =================================================
            # PAST SLOT
            # =================================================

            if past:

                result.append({
                    "time": slot_time,
                    "available": False,
                    "booked": False,
                    "past": True
                })

            # =================================================
            # BOOKED SLOT
            # =================================================

            elif fully_booked:

                result.append({
                    "time": slot_time,
                    "available": False,
                    "booked": True,
                    "past": False
                })

            # =================================================
            # AVAILABLE SLOT
            # =================================================

            else:

                result.append({
                    "time": slot_time,
                    "available": True,
                    "booked": False,
                    "past": False
                })

        return result

    # ========================================================
    # GET — SELECT DATE
    # ========================================================

    if selected_date:

        try:

            selected_date_obj = datetime.strptime(
                selected_date,
                "%Y-%m-%d"
            ).date()

            now = timezone.localtime()

            today = now.date()

            # ------------------------------------------------
            # PAST DATE
            # ------------------------------------------------

            if selected_date_obj < today:

                message = (
                    "You cannot book an appointment "
                    "for a past date."
                )

            # ------------------------------------------------
            # GENERATE ALL SLOTS
            # ------------------------------------------------

            slots = generate_slots(
                selected_date_obj
            )

            if not slots and not message:

                message = (
                    "No time slots are available "
                    "for this date."
                )

        except ValueError:

            selected_date = None
            slots = []

            message = (
                "Please select a valid date."
            )

    # ========================================================
    # POST — SELECT TIME SLOT
    # ========================================================

    if request.method == "POST":

        selected_date = request.POST.get("date")
        selected_time = request.POST.get("time")

        if (
            not selected_date
            or
            not selected_time
        ):

            message = (
                "Please select a date and time slot."
            )

        else:

            try:

                selected_date_obj = datetime.strptime(
                    selected_date,
                    "%Y-%m-%d"
                ).date()

                selected_time_obj = datetime.strptime(
                    selected_time,
                    "%H:%M"
                ).time()

                # =================================================
                # CURRENT DATE / TIME
                # =================================================

                now = timezone.localtime()

                today = now.date()
                current_time = now.time()

                # =================================================
                # PAST DATE
                # =================================================

                if selected_date_obj < today:

                    message = (
                        "You cannot book an appointment "
                        "for a past date."
                    )

                # =================================================
                # PAST TIME
                # =================================================

                elif (
                    selected_date_obj == today
                    and
                    selected_time_obj <= current_time
                ):

                    message = (
                        "This time slot is not available."
                    )

                # =================================================
                # CHECK BOOKING
                # =================================================

                elif is_slot_fully_booked(
                    department,
                    selected_date_obj,
                    selected_time_obj
                ):

                    message = (
                        "This time slot is not available."
                    )

                # =================================================
                # VALID FUTURE SLOT
                # =================================================

                else:

                    query_string = urlencode({
                        "department": department,
                        "date": selected_date,
                        "time": selected_time
                    })

                    return HttpResponseRedirect(
                        reverse("doctor_list")
                        + "?"
                        + query_string
                    )

            except ValueError:

                message = (
                    "Invalid date or time."
                )

        # ----------------------------------------------------
        # REBUILD SLOTS AFTER ERROR
        # ----------------------------------------------------

        if selected_date:

            try:

                selected_date_obj = datetime.strptime(
                    selected_date,
                    "%Y-%m-%d"
                ).date()

                slots = generate_slots(
                    selected_date_obj
                )

            except ValueError:

                slots = []

    # ========================================================
    # RENDER
    # ========================================================

    response = render(
        request,
        "patients/select_datetime.html",
        {
            "department": department,
            "selected_date": selected_date,
            "slots": slots,
            "message": message
        }
    )

    return no_cache(response)

# ============================================================
# MY APPOINTMENTS
# ============================================================

def my_appointments(request):

    patient_id = request.session.get(
        "patient_id"
    )

    if not patient_id:

        return redirect(
            "patient_login"
        )

    patient = get_object_or_404(
        Patient,
        id=patient_id
    )

    appointments = Appointment.objects.filter(
        patient=patient
    ).order_by(
        "-appointment_date",
        "-appointment_time"
    )

    success = request.session.pop(
        "appointment_success",
        False
    )

    return render(
        request,
        "patients/my_appointments.html",
        {
            "appointments": appointments,
            "success": success
        }
    )


# ============================================================
# CANCEL APPOINTMENT
# ============================================================

def cancel_appointment(
    request,
    appointment_id
):

    patient_id = request.session.get(
        "patient_id"
    )

    if not patient_id:

        return redirect(
            "patient_login"
        )

    if request.method != "POST":

        return redirect(
            "my_appointments"
        )

    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        patient_id=patient_id
    )

    if appointment.status == "cancelled":

        return redirect(
            "my_appointments"
        )

    appointment.status = "cancelled"

    appointment.save(
        update_fields=["status"]
    )

    return redirect(
        "my_appointments"
    )


# ============================================================
# PATIENT LOGOUT
# ============================================================

def patient_logout(request):

    request.session.flush()

    return redirect(
        "home"
    )