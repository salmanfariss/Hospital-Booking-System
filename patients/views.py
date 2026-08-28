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

        if Patient.objects.filter(id=patient_id).exists():
            return redirect("department_list")

        request.session.pop("patient_id", None)

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        context = {
            "name": name,
            "email": email,
        }

        if not name or not email or not password or not confirm_password:

            context["error"] = "Please fill in all fields."

            return no_cache(
                render(
                    request,
                    "patients/register.html",
                    context
                )
            )

        if password != confirm_password:

            context["error"] = "Passwords do not match."

            return no_cache(
                render(
                    request,
                    "patients/register.html",
                    context
                )
            )

        if len(password) < 6:

            context["error"] = "Password must be at least 6 characters."

            return no_cache(
                render(
                    request,
                    "patients/register.html",
                    context
                )
            )

        if Patient.objects.filter(email=email).exists():

            context["error"] = (
                "An account with this email already exists. "
                "Please login."
            )

            return no_cache(
                render(
                    request,
                    "patients/register.html",
                    context
                )
            )

        patient = Patient.objects.create(
            name=name,
            email=email,
            password=make_password(password),
        )

        request.session["patient_id"] = patient.id

        return redirect("department_list")

    response = render(
        request,
        "patients/register.html"
    )

    return no_cache(response)


# ============================================================
# HELPER — MAKE AWARE DATETIME
# ============================================================

def make_local_datetime(selected_date, selected_time):

    naive_datetime = datetime.combine(
        selected_date,
        selected_time
    )

    return timezone.make_aware(
        naive_datetime,
        timezone.get_current_timezone()
    )


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

    day_name = selected_date.strftime("%A")

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
        schedule.start_time <= selected_time < schedule.end_time
    ):
        return False

    # --------------------------------------------------------
    # SLOT DURATION
    # --------------------------------------------------------

    slot_duration = timedelta(
        minutes=schedule.slot_duration
    )

    selected_start = datetime.combine(
        selected_date,
        selected_time
    )

    selected_end_datetime = (
        selected_start + slot_duration
    )

    selected_end = selected_end_datetime.time()

    # --------------------------------------------------------
    # SLOT MUST FINISH INSIDE WORKING TIME
    # --------------------------------------------------------

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
    # CHECK DOCTOR EXISTING BOOKING
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
# HELPER — CHECK PATIENT SAME DATE + SAME TIME
#
# IMPORTANT:
# One patient can have ONLY ONE doctor appointment
# for the EXACT same date and time.
# ============================================================

def is_patient_slot_booked(
    patient,
    selected_date,
    selected_time
):

    return Appointment.objects.filter(
        patient=patient,
        appointment_date=selected_date,
        appointment_time=selected_time
    ).exclude(
        status="cancelled"
    ).exists()


# ============================================================
# HELPER — CHECK WHOLE DEPARTMENT SLOT
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
# HELPER — GENERATE AVAILABLE TIME SLOTS
# ============================================================

def generate_available_slots(
    department,
    selected_date
):

    doctors = Doctor.objects.filter(
        specialization=department
    )

    possible_times = set()

    now = timezone.localtime()
    today = now.date()

    # --------------------------------------------------------
    # LOOP THROUGH DOCTORS
    # --------------------------------------------------------

    for doctor in doctors:

        # ----------------------------------------------------
        # CHECK LEAVE
        # ----------------------------------------------------

        if DoctorLeave.objects.filter(
            doctor=doctor,
            leave_date=selected_date
        ).exists():

            continue

        # ----------------------------------------------------
        # GET SCHEDULE
        # ----------------------------------------------------

        day_name = selected_date.strftime("%A")

        schedule = DoctorSchedule.objects.filter(
            doctor=doctor,
            day=day_name,
            is_available=True
        ).first()

        if not schedule:
            continue

        # ----------------------------------------------------
        # SLOT DURATION
        # ----------------------------------------------------

        slot_duration = timedelta(
            minutes=schedule.slot_duration
        )

        current_datetime = datetime.combine(
            selected_date,
            schedule.start_time
        )

        end_datetime = datetime.combine(
            selected_date,
            schedule.end_time
        )

        # ----------------------------------------------------
        # GENERATE ALL SLOTS
        # ----------------------------------------------------

        while (
            current_datetime + slot_duration
            <= end_datetime
        ):

            current_slot = current_datetime.time()

            slot_end_datetime = (
                current_datetime + slot_duration
            )

            slot_end = slot_end_datetime.time()

            # ------------------------------------------------
            # CHECK BREAK
            # ------------------------------------------------

            is_break = False

            for doctor_break in schedule.breaks.all():

                if (
                    current_slot < doctor_break.break_end
                    and
                    slot_end > doctor_break.break_start
                ):

                    is_break = True
                    break

            # ------------------------------------------------
            # ADD SLOT
            # ------------------------------------------------

            if not is_break:

                possible_times.add(
                    current_slot
                )

            current_datetime += slot_duration

    # --------------------------------------------------------
    # CREATE FINAL SLOT LIST
    # --------------------------------------------------------

    slots = []

    for slot_time in sorted(possible_times):

        # ----------------------------------------------------
        # CHECK WHETHER SLOT IS PAST
        # ----------------------------------------------------

        is_past = False

        if selected_date == today:

            slot_datetime = make_local_datetime(
                selected_date,
                slot_time
            )

            if slot_datetime <= now:
                is_past = True

        # ----------------------------------------------------
        # CHECK WHETHER SLOT IS FULLY BOOKED
        # ----------------------------------------------------

        fully_booked = is_slot_fully_booked(
            department,
            selected_date,
            slot_time
        )

        # ----------------------------------------------------
        # FINAL AVAILABILITY
        # ----------------------------------------------------

        if is_past:

            available = False

        else:

            available = not fully_booked

        slots.append({

            "time": slot_time,

            "available": available,

            "booked": fully_booked,

            "past": is_past,

        })

    return slots


# ============================================================
# PATIENT LOGIN
# ============================================================

def patient_login(request):

    patient_id = request.session.get("patient_id")

    if patient_id:

        if Patient.objects.filter(id=patient_id).exists():
            return redirect("department_list")

        request.session.pop("patient_id", None)

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        context = {
            "name": name,
            "email": email,
        }

        if not name or not email or not password:

            context["error"] = "Please fill in all fields."

            return no_cache(
                render(
                    request,
                    "patients/login.html",
                    context
                )
            )

        try:

            patient = Patient.objects.get(
                email=email
            )

        except Patient.DoesNotExist:

            context["error"] = "Invalid email or password."

            return no_cache(
                render(
                    request,
                    "patients/login.html",
                    context
                )
            )

        if not patient.password:

            context["error"] = (
                "This account does not have a password. "
                "Please register again."
            )

            return no_cache(
                render(
                    request,
                    "patients/login.html",
                    context
                )
            )

        if not check_password(
            password,
            patient.password
        ):

            context["error"] = "Invalid email or password."

            return no_cache(
                render(
                    request,
                    "patients/login.html",
                    context
                )
            )

        if patient.name != name:

            patient.name = name

            patient.save(
                update_fields=["name"]
            )

        request.session["patient_id"] = patient.id

        return redirect("department_list")

    response = render(
        request,
        "patients/login.html"
    )

    return no_cache(response)


# ============================================================
# DEPARTMENT LIST
# ============================================================

def department_list(request):

    patient_id = request.session.get("patient_id")

    if not patient_id:
        return redirect("patient_login")

    if not Patient.objects.filter(
        id=patient_id
    ).exists():

        request.session.pop(
            "patient_id",
            None
        )

        return redirect("patient_login")

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

    department = request.GET.get("department")

    if not department:
        return redirect("department_list")

    # ========================================================
    # POST — SELECT TIME SLOT
    # ========================================================

    if request.method == "POST":

        selected_date = request.POST.get("date")
        selected_time = request.POST.get("time")

        if not selected_date or not selected_time:

            response = render(
                request,
                "patients/select_datetime.html",
                {
                    "department": department,
                    "selected_date": selected_date,
                    "slots": [],
                    "message": (
                        "Please select a date and time slot."
                    ),
                }
            )

            return no_cache(response)

        # ----------------------------------------------------
        # CONVERT DATE + TIME
        # ----------------------------------------------------

        try:

            selected_date_obj = datetime.strptime(
                selected_date,
                "%Y-%m-%d"
            ).date()

            selected_time_obj = datetime.strptime(
                selected_time,
                "%H:%M"
            ).time()

        except ValueError:

            response = render(
                request,
                "patients/select_datetime.html",
                {
                    "department": department,
                    "selected_date": selected_date,
                    "slots": [],
                    "message": "Invalid date or time.",
                }
            )

            return no_cache(response)

        now = timezone.localtime()
        today = now.date()

        # ----------------------------------------------------
        # PAST DATE
        # ----------------------------------------------------

        if selected_date_obj < today:

            response = render(
                request,
                "patients/select_datetime.html",
                {
                    "department": department,
                    "selected_date": selected_date,
                    "slots": [],
                    "message": (
                        "You cannot book an appointment "
                        "for a past date."
                    ),
                }
            )

            return no_cache(response)

        # ----------------------------------------------------
        # PAST TIME
        # ----------------------------------------------------

        if selected_date_obj == today:

            selected_datetime = make_local_datetime(
                selected_date_obj,
                selected_time_obj
            )

            if selected_datetime <= now:

                slots = generate_available_slots(
                    department,
                    selected_date_obj
                )

                response = render(
                    request,
                    "patients/select_datetime.html",
                    {
                        "department": department,
                        "selected_date": selected_date,
                        "slots": slots,
                        "message": (
                            "You cannot book an appointment "
                            "for a past time."
                        ),
                    }
                )

                return no_cache(response)

        # ----------------------------------------------------
        # FINAL AVAILABILITY CHECK
        # ----------------------------------------------------

        if is_slot_fully_booked(
            department,
            selected_date_obj,
            selected_time_obj
        ):

            return redirect(
                reverse("select_datetime")
                + "?"
                + urlencode({
                    "department": department,
                    "date": selected_date,
                })
            )

        # ----------------------------------------------------
        # GO TO DOCTOR LIST
        # ----------------------------------------------------

        query_string = urlencode({
            "department": department,
            "date": selected_date,
            "time": selected_time,
        })

        return HttpResponseRedirect(
            reverse("doctor_list")
            + "?"
            + query_string
        )

    # ========================================================
    # GET — SHOW DATE + TIME SLOTS
    # ========================================================

    selected_date = request.GET.get("date")

    slots = []
    message = None

    if selected_date:

        try:

            selected_date_obj = datetime.strptime(
                selected_date,
                "%Y-%m-%d"
            ).date()

            today = timezone.localtime().date()

            if selected_date_obj < today:

                message = (
                    "You cannot book an appointment "
                    "for a past date."
                )

            else:

                slots = generate_available_slots(
                    department,
                    selected_date_obj
                )

                if not slots:

                    message = (
                        "No time slots are available "
                        "for this date."
                    )

        except ValueError:

            selected_date = None
            slots = []
            message = "Please select a valid date."

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
            "message": message,
        }
    )

    return no_cache(response)


# ============================================================
# DOCTOR LIST + BOOK APPOINTMENT
# ============================================================

def doctor_list(request):

    patient_id = request.session.get("patient_id")

    if not patient_id:
        return redirect("patient_login")

    department = request.GET.get("department")
    selected_date = request.GET.get("date")
    selected_time = request.GET.get("time")

    doctors = Doctor.objects.none()

    error_message = None

    # ========================================================
    # POST — SELECT DOCTOR
    # ========================================================

    if request.method == "POST":

        doctor_id = request.POST.get("doctor_id")

        selected_date = (
            request.POST.get("date")
            or selected_date
        )

        selected_time = (
            request.POST.get("time")
            or selected_time
        )

        if not doctor_id:

            error_message = "Please select a doctor."

        elif not selected_date or not selected_time:

            error_message = "Date and time are missing."

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

            except ValueError:

                error_message = "Invalid date or time."

            else:

                now = timezone.localtime()
                today = now.date()

                # ------------------------------------------------
                # PAST DATE
                # ------------------------------------------------

                if selected_date_obj < today:

                    error_message = (
                        "You cannot book an appointment "
                        "for a past date."
                    )

                # ------------------------------------------------
                # PAST TIME
                # ------------------------------------------------

                elif selected_date_obj == today:

                    selected_datetime = make_local_datetime(
                        selected_date_obj,
                        selected_time_obj
                    )

                    if selected_datetime <= now:

                        error_message = (
                            "You cannot book an appointment "
                            "for a past time."
                        )

                # ------------------------------------------------
                # CONTINUE
                # ------------------------------------------------

                if not error_message:

                    try:

                        doctor = Doctor.objects.get(
                            id=doctor_id
                        )

                        patient = Patient.objects.get(
                            id=patient_id
                        )

                    except Doctor.DoesNotExist:

                        error_message = (
                            "Selected doctor was not found."
                        )

                    except Patient.DoesNotExist:

                        request.session.pop(
                            "patient_id",
                            None
                        )

                        return redirect("patient_login")

                    else:

                        # ----------------------------------------
                        # VERIFY DEPARTMENT
                        # ----------------------------------------

                        if doctor.specialization != department:

                            error_message = (
                                "Invalid doctor selection."
                            )

                        else:

                            # ====================================
                            # IMPORTANT PATIENT SLOT CHECK
                            #
                            # Same patient
                            # +
                            # Same date
                            # +
                            # Same time
                            #
                            # = ONLY ONE DOCTOR ALLOWED
                            # ====================================

                            if is_patient_slot_booked(
                                patient,
                                selected_date_obj,
                                selected_time_obj
                            ):

                                error_message = (
                                    "You already have an appointment "
                                    "at this date and time. "
                                    "You cannot book another doctor "
                                    "for the same time slot."
                                )

                            # ------------------------------------
                            # CHECK DOCTOR AVAILABILITY
                            # ------------------------------------

                            elif not is_doctor_available(
                                doctor,
                                selected_date_obj,
                                selected_time_obj
                            ):

                                error_message = (
                                    "This doctor is already booked "
                                    "or unavailable for this slot."
                                )

                            # ------------------------------------
                            # BOOK APPOINTMENT
                            # ------------------------------------

                            else:

                                try:

                                    with transaction.atomic():

                                        # ==================================
                                        # LOCK PATIENT
                                        #
                                        # This prevents the same patient
                                        # from creating two appointments
                                        # at exactly the same date/time
                                        # through simultaneous requests.
                                        # ==================================

                                        locked_patient = (
                                            Patient.objects
                                            .select_for_update()
                                            .get(
                                                id=patient.id
                                            )
                                        )

                                        # ==================================
                                        # CHECK PATIENT AGAIN INSIDE
                                        # TRANSACTION
                                        # ==================================

                                        patient_already_booked = (
                                            Appointment.objects
                                            .filter(
                                                patient=locked_patient,
                                                appointment_date=selected_date_obj,
                                                appointment_time=selected_time_obj
                                            )
                                            .exclude(
                                                status="cancelled"
                                            )
                                            .exists()
                                        )

                                        if patient_already_booked:

                                            raise ValueError(
                                                "PATIENT_ALREADY_BOOKED"
                                            )

                                        # ==================================
                                        # LOCK DOCTOR
                                        # ==================================

                                        locked_doctor = (
                                            Doctor.objects
                                            .select_for_update()
                                            .get(
                                                id=doctor.id
                                            )
                                        )

                                        # ==================================
                                        # CHECK DOCTOR SLOT AGAIN
                                        # ==================================

                                        existing_appointment = (
                                            Appointment.objects
                                            .select_for_update()
                                            .filter(
                                                doctor=locked_doctor,
                                                appointment_date=selected_date_obj,
                                                appointment_time=selected_time_obj
                                            )
                                            .first()
                                        )

                                        # ==================================
                                        # DOCTOR SLOT ALREADY BOOKED
                                        # ==================================

                                        if (
                                            existing_appointment
                                            and
                                            existing_appointment.status
                                            != "cancelled"
                                        ):

                                            raise IntegrityError(
                                                "DOCTOR_SLOT_BOOKED"
                                            )

                                        # ==================================
                                        # PATIENT CHECK AGAIN
                                        #
                                        # Extra safety check.
                                        # ==================================

                                        patient_already_booked = (
                                            Appointment.objects
                                            .filter(
                                                patient=locked_patient,
                                                appointment_date=selected_date_obj,
                                                appointment_time=selected_time_obj
                                            )
                                            .exclude(
                                                status="cancelled"
                                            )
                                            .exists()
                                        )

                                        if patient_already_booked:

                                            raise ValueError(
                                                "PATIENT_ALREADY_BOOKED"
                                            )

                                        # ==================================
                                        # REUSE CANCELLED APPOINTMENT
                                        # ==================================

                                        if existing_appointment:

                                            existing_appointment.patient = (
                                                locked_patient
                                            )

                                            existing_appointment.status = (
                                                "confirmed"
                                            )

                                            existing_appointment.save(
                                                update_fields=[
                                                    "patient",
                                                    "status",
                                                ]
                                            )

                                        # ==================================
                                        # CREATE NEW APPOINTMENT
                                        # ==================================

                                        else:

                                            Appointment.objects.create(
                                                patient=locked_patient,
                                                doctor=locked_doctor,
                                                appointment_date=selected_date_obj,
                                                appointment_time=selected_time_obj,
                                                status="confirmed"
                                            )

                                        # Use locked objects after
                                        # successful transaction.

                                        doctor = locked_doctor
                                        patient = locked_patient

                                except ValueError as e:

                                    if str(e) == "PATIENT_ALREADY_BOOKED":

                                        error_message = (
                                            "You already have an appointment "
                                            "at this date and time. "
                                            "You cannot book another doctor "
                                            "for the same time slot."
                                        )

                                    else:

                                        error_message = (
                                            "Unable to book appointment."
                                        )

                                except IntegrityError:

                                    error_message = (
                                        "This doctor's time slot "
                                        "is already booked."
                                    )

                                else:

                                    request.session[
                                        "appointment_success"
                                    ] = True

                                    return render(
                                        request,
                                        "patients/doctor_list.html",
                                        {
                                            "doctors": Doctor.objects.none(),
                                            "department": department,
                                            "selected_date": selected_date,
                                            "selected_time": selected_time,
                                            "error_message": None,
                                            "booked": True,
                                            "booked_doctor": doctor,
                                        }
                                    )

    # ========================================================
    # GET — SHOW AVAILABLE DOCTORS
    # ========================================================

    if (
        request.method == "GET"
        and department
        and selected_date
        and selected_time
    ):

        try:

            selected_date_obj = datetime.strptime(
                selected_date,
                "%Y-%m-%d"
            ).date()

            selected_time_obj = datetime.strptime(
                selected_time,
                "%H:%M"
            ).time()

        except ValueError:

            doctors = Doctor.objects.none()

        else:

            now = timezone.localtime()
            today = now.date()

            # ------------------------------------------------
            # PAST DATE
            # ------------------------------------------------

            if selected_date_obj < today:

                return render(
                    request,
                    "patients/doctor_list.html",
                    {
                        "doctors": Doctor.objects.none(),
                        "department": department,
                        "selected_date": selected_date,
                        "selected_time": selected_time,
                        "error_message": (
                            "You cannot book an appointment "
                            "for a past date."
                        ),
                        "booked": False,
                        "booked_doctor": None,
                    }
                )

            # ------------------------------------------------
            # PAST TIME
            # ------------------------------------------------

            if selected_date_obj == today:

                selected_datetime = make_local_datetime(
                    selected_date_obj,
                    selected_time_obj
                )

                if selected_datetime <= now:

                    return render(
                        request,
                        "patients/doctor_list.html",
                        {
                            "doctors": Doctor.objects.none(),
                            "department": department,
                            "selected_date": selected_date,
                            "selected_time": selected_time,
                            "error_message": (
                                "You cannot book an appointment "
                                "for a past time."
                            ),
                            "booked": False,
                            "booked_doctor": None,
                        }
                    )

            # ------------------------------------------------
            # CHECK PATIENT SAME DATE + TIME
            #
            # If patient already booked another doctor
            # at this exact date/time, don't show doctors.
            # ------------------------------------------------

            try:

                patient = Patient.objects.get(
                    id=patient_id
                )

            except Patient.DoesNotExist:

                request.session.pop(
                    "patient_id",
                    None
                )

                return redirect("patient_login")

            if is_patient_slot_booked(
                patient,
                selected_date_obj,
                selected_time_obj
            ):

                return render(
                    request,
                    "patients/doctor_list.html",
                    {
                        "doctors": Doctor.objects.none(),
                        "department": department,
                        "selected_date": selected_date,
                        "selected_time": selected_time,
                        "error_message": (
                            "You already have an appointment "
                            "at this date and time. "
                            "You cannot book another doctor "
                            "for the same time slot."
                        ),
                        "booked": False,
                        "booked_doctor": None,
                    }
                )

            # ------------------------------------------------
            # GET DEPARTMENT DOCTORS
            # ------------------------------------------------

            department_doctors = Doctor.objects.filter(
                specialization=department
            )

            available_doctor_ids = []

            for doctor in department_doctors:

                if is_doctor_available(
                    doctor,
                    selected_date_obj,
                    selected_time_obj
                ):

                    available_doctor_ids.append(
                        doctor.id
                    )

            doctors = Doctor.objects.filter(
                id__in=available_doctor_ids
            )

            # ------------------------------------------------
            # ALL DOCTORS BOOKED
            # ------------------------------------------------

            if not doctors.exists():

                return render(
                    request,
                    "patients/doctor_list.html",
                    {
                        "doctors": Doctor.objects.none(),
                        "department": department,
                        "selected_date": selected_date,
                        "selected_time": selected_time,
                        "error_message": None,
                        "booked": False,
                        "slot_fully_booked": True,
                        "booked_doctor": None,
                    }
                )

    # ========================================================
    # RENDER DOCTOR PAGE
    # ========================================================

    return render(
        request,
        "patients/doctor_list.html",
        {
            "doctors": doctors,
            "department": department,
            "selected_date": selected_date,
            "selected_time": selected_time,
            "error_message": error_message,
            "booked": False,
            "booked_doctor": None,
        }
    )


# ============================================================
# MY APPOINTMENTS
# ============================================================

def my_appointments(request):

    patient_id = request.session.get("patient_id")

    if not patient_id:
        return redirect("patient_login")

    patient = get_object_or_404(
        Patient,
        id=patient_id
    )

    appointments = (
        Appointment.objects
        .filter(patient=patient)
        .order_by(
            "-appointment_date",
            "-appointment_time"
        )
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
            "success": success,
        }
    )


# ============================================================
# CANCEL APPOINTMENT
# ============================================================

def cancel_appointment(
    request,
    appointment_id
):

    patient_id = request.session.get("patient_id")

    if not patient_id:
        return redirect("patient_login")

    if request.method != "POST":
        return redirect("my_appointments")

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

    return redirect("home")