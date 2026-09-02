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

    response["Cache-Control"] = (
        "no-cache, no-store, must-revalidate"
    )

    response["Pragma"] = "no-cache"
    response["Expires"] = "0"

    return response


# ============================================================
# HELPER — MAKE LOCAL DATETIME
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
# HELPER — GET DOCTOR SCHEDULE
# ============================================================

def get_doctor_schedule(doctor, selected_date):

    day_name = selected_date.strftime("%A")

    return DoctorSchedule.objects.filter(
        doctor=doctor,
        day=day_name,
        is_available=True
    ).first()


# ============================================================
# HELPER — CHECK DOCTOR AVAILABILITY
# ============================================================

def is_doctor_available(
    doctor,
    selected_date,
    selected_time
):

    # CHECK LEAVE

    if DoctorLeave.objects.filter(
        doctor=doctor,
        leave_date=selected_date
    ).exists():

        return False


    # GET SCHEDULE

    schedule = get_doctor_schedule(
        doctor,
        selected_date
    )

    if not schedule:

        return False


    # CHECK WORKING TIME

    if not (
        schedule.start_time
        <= selected_time
        < schedule.end_time
    ):

        return False


    # SLOT DURATION

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


    # SLOT MUST END BEFORE WORKING TIME ENDS

    if selected_end > schedule.end_time:

        return False


    # CHECK BREAKS

    for doctor_break in schedule.breaks.all():

        if (
            selected_time < doctor_break.break_end
            and
            selected_end > doctor_break.break_start
        ):

            return False


    # ========================================================
    # COUNT PATIENTS ALREADY BOOKED IN THIS SLOT
    # ========================================================

    booked_count = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=selected_date,
        appointment_time=selected_time
    ).exclude(
        status="cancelled"
    ).count()


    # MAX PATIENTS PER SLOT

    if booked_count >= schedule.max_patients_per_slot:

        return False


    return True


# ============================================================
# HELPER — CHECK DEPARTMENT SLOT
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
# HELPER — GENERATE AVAILABLE SLOTS
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


    # ========================================================
    # LOOP THROUGH DOCTORS
    # ========================================================

    for doctor in doctors:


        # CHECK LEAVE

        if DoctorLeave.objects.filter(
            doctor=doctor,
            leave_date=selected_date
        ).exists():

            continue


        # GET SCHEDULE

        schedule = get_doctor_schedule(
            doctor,
            selected_date
        )

        if not schedule:

            continue


        # SLOT DURATION

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


        # GENERATE SLOTS

        while (
            current_datetime + slot_duration
            <= end_datetime
        ):

            current_slot = current_datetime.time()

            slot_end_datetime = (
                current_datetime
                + slot_duration
            )

            slot_end = slot_end_datetime.time()


            # CHECK BREAK

            is_break = False


            for doctor_break in schedule.breaks.all():

                if (
                    current_slot
                    < doctor_break.break_end

                    and

                    slot_end
                    > doctor_break.break_start
                ):

                    is_break = True

                    break


            if not is_break:

                possible_times.add(
                    current_slot
                )


            current_datetime += slot_duration


    # ========================================================
    # CREATE FINAL SLOT LIST
    # ========================================================

    slots = []


    for slot_time in sorted(
        possible_times
    ):


        # CHECK PAST SLOT

        is_past = False


        if selected_date == today:

            slot_datetime = make_local_datetime(
                selected_date,
                slot_time
            )


            if slot_datetime <= now:

                is_past = True


        # CHECK FULL

        fully_booked = is_slot_fully_booked(
            department,
            selected_date,
            slot_time
        )


        # FINAL AVAILABILITY

        available = (
            not is_past
            and
            not fully_booked
        )


        slots.append({

            "time": slot_time,

            "available": available,

            "booked": fully_booked,

            "past": is_past,

        })


    return slots


# ============================================================
# PATIENT REGISTER
# ============================================================

def patient_register(request):

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

        confirm_password = request.POST.get(
            "confirm_password",
            ""
        )


        context = {

            "name": name,

            "email": email,

        }


        if (
            not name
            or not email
            or not password
            or not confirm_password
        ):

            context["error"] = (
                "Please fill in all fields."
            )

            return no_cache(
                render(
                    request,
                    "patients/register.html",
                    context
                )
            )


        if password != confirm_password:

            context["error"] = (
                "Passwords do not match."
            )

            return no_cache(
                render(
                    request,
                    "patients/register.html",
                    context
                )
            )


        if len(password) < 6:

            context["error"] = (
                "Password must be at least 6 characters."
            )

            return no_cache(
                render(
                    request,
                    "patients/register.html",
                    context
                )
            )


        if Patient.objects.filter(
            email=email
        ).exists():

            context["error"] = (
                "An account with this email already exists."
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

            password=make_password(
                password
            ),

        )


        request.session[
            "patient_id"
        ] = patient.id


        return redirect(
            "department_list"
        )


    return no_cache(
        render(
            request,
            "patients/register.html"
        )
    )


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


        context = {

            "name": name,

            "email": email,

        }


        if (
            not name
            or not email
            or not password
        ):

            context["error"] = (
                "Please fill in all fields."
            )

            return render(
                request,
                "patients/login.html",
                context
            )


        try:

            patient = Patient.objects.get(
                email=email
            )

        except Patient.DoesNotExist:

            context["error"] = (
                "Invalid email or password."
            )

            return render(
                request,
                "patients/login.html",
                context
            )


        if not check_password(
            password,
            patient.password
        ):

            context["error"] = (
                "Invalid email or password."
            )

            return render(
                request,
                "patients/login.html",
                context
            )


        request.session[
            "patient_id"
        ] = patient.id


        return redirect(
            "department_list"
        )


    return no_cache(
        render(
            request,
            "patients/login.html"
        )
    )


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
# SELECT DATE AND TIME
# ============================================================

def select_datetime(request):

    patient_id = request.session.get(
        "patient_id"
    )


    if not patient_id:

        return redirect(
            "patient_login"
        )


    department = request.GET.get(
        "department"
    )


    if not department:

        return redirect(
            "department_list"
        )


    # ========================================================
    # POST
    # ========================================================

    if request.method == "POST":

        selected_date = request.POST.get(
            "date"
        )

        selected_time = request.POST.get(
            "time"
        )


        if not selected_date or not selected_time:

            return render(
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


        try:

            selected_date_obj = (
                datetime.strptime(
                    selected_date,
                    "%Y-%m-%d"
                ).date()
            )


            selected_time_obj = (
                datetime.strptime(
                    selected_time,
                    "%H:%M"
                ).time()
            )


        except ValueError:

            return render(
                request,
                "patients/select_datetime.html",
                {
                    "department": department,

                    "selected_date": selected_date,

                    "slots": [],

                    "message": (
                        "Invalid date or time."
                    ),
                }
            )


        today = timezone.localdate()


        if selected_date_obj < today:

            return redirect(
                reverse(
                    "select_datetime"
                )
                + "?"
                + urlencode({
                    "department": department
                })
            )


        # CHECK SLOT

        if is_slot_fully_booked(
            department,
            selected_date_obj,
            selected_time_obj
        ):

            return redirect(
                reverse(
                    "select_datetime"
                )
                + "?"
                + urlencode({
                    "department": department,

                    "date": selected_date,
                })
            )


        query_string = urlencode({

            "department": department,

            "date": selected_date,

            "time": selected_time,

        })


        return HttpResponseRedirect(

            reverse(
                "doctor_list"
            )

            + "?"

            + query_string

        )


    # ========================================================
    # GET
    # ========================================================

    selected_date = request.GET.get(
        "date"
    )


    slots = []

    message = None


    if selected_date:

        try:

            selected_date_obj = (
                datetime.strptime(
                    selected_date,
                    "%Y-%m-%d"
                ).date()
            )


            if (
                selected_date_obj
                >= timezone.localdate()
            ):

                slots = generate_available_slots(
                    department,
                    selected_date_obj
                )

            else:

                message = (
                    "You cannot select a past date."
                )


        except ValueError:

            message = (
                "Please select a valid date."
            )


    return no_cache(
        render(
            request,
            "patients/select_datetime.html",
            {

                "department": department,

                "selected_date": selected_date,

                "slots": slots,

                "message": message,

            }
        )
    )


# ============================================================
# DOCTOR LIST + BOOK APPOINTMENT
# ============================================================

def doctor_list(request):

    patient_id = request.session.get(
        "patient_id"
    )


    if not patient_id:

        return redirect(
            "patient_login"
        )


    department = request.GET.get(
        "department"
    )

    selected_date = request.GET.get(
        "date"
    )

    selected_time = request.GET.get(
        "time"
    )


    doctors = Doctor.objects.none()

    error_message = None


    # ========================================================
    # POST — BOOK APPOINTMENT
    # ========================================================

    if request.method == "POST":

        doctor_id = request.POST.get(
            "doctor_id"
        )


        selected_date = request.POST.get(
            "date"
        )


        selected_time = request.POST.get(
            "time"
        )


        if (
            not doctor_id
            or not selected_date
            or not selected_time
        ):

            error_message = (
                "Please select doctor, date and time."
            )


        else:

            try:

                doctor = Doctor.objects.get(
                    id=doctor_id
                )


                patient = Patient.objects.get(
                    id=patient_id
                )


                selected_date_obj = (
                    datetime.strptime(
                        selected_date,
                        "%Y-%m-%d"
                    ).date()
                )


                selected_time_obj = (
                    datetime.strptime(
                        selected_time,
                        "%H:%M"
                    ).time()
                )


            except (
                Doctor.DoesNotExist,
                Patient.DoesNotExist,
                ValueError
            ):

                error_message = (
                    "Invalid appointment details."
                )


            else:

                # VERIFY DEPARTMENT

                if doctor.specialization != department:

                    error_message = (
                        "Invalid doctor selection."
                    )


                # PATIENT ALREADY HAS APPOINTMENT
                # SAME DATE + TIME

                elif Appointment.objects.filter(

                    patient=patient,

                    appointment_date=selected_date_obj,

                    appointment_time=selected_time_obj

                ).exclude(

                    status="cancelled"

                ).exists():

                    error_message = (
                        "You already have an appointment "
                        "at this date and time."
                    )


                # CHECK DOCTOR SLOT

                elif not is_doctor_available(

                    doctor,

                    selected_date_obj,

                    selected_time_obj

                ):

                    error_message = (
                        "This doctor is unavailable "
                        "for this time slot."
                    )


                else:

                    try:

                        with transaction.atomic():


                            # CHECK AGAIN INSIDE TRANSACTION

                            booked_count = (
                                Appointment.objects
                                .select_for_update()
                                .filter(

                                    doctor=doctor,

                                    appointment_date=
                                    selected_date_obj,

                                    appointment_time=
                                    selected_time_obj

                                )
                                .exclude(
                                    status="cancelled"
                                )
                                .count()
                            )


                            schedule = get_doctor_schedule(

                                doctor,

                                selected_date_obj

                            )


                            if (
                                not schedule
                                or
                                booked_count
                                >=
                                schedule.max_patients_per_slot
                            ):

                                raise IntegrityError(
                                    "SLOT_FULL"
                                )


                            # PATIENT CHECK AGAIN

                            patient_booked = (
                                Appointment.objects
                                .filter(

                                    patient=patient,

                                    appointment_date=
                                    selected_date_obj,

                                    appointment_time=
                                    selected_time_obj

                                )
                                .exclude(

                                    status="cancelled"

                                )
                                .exists()
                            )


                            if patient_booked:

                                raise ValueError(
                                    "PATIENT_BOOKED"
                                )


                            # CREATE APPOINTMENT

                            appointment = (
                                Appointment.objects.create(

                                    patient=patient,

                                    doctor=doctor,

                                    appointment_date=
                                    selected_date_obj,

                                    appointment_time=
                                    selected_time_obj,

                                    status="confirmed"

                                )
                            )


                    except ValueError:

                        error_message = (
                            "You already have an appointment "
                            "at this date and time."
                        )


                    except IntegrityError:

                        error_message = (
                            "This time slot is already full."
                        )


                    else:

                        # ====================================
                        # SUCCESS PAGE
                        # ====================================

                        return render(

                            request,

                            "patients/booked.html",

                            {

                                "appointment":
                                appointment,

                                "doctor":
                                doctor,

                            }

                        )


    # ========================================================
    # GET — AVAILABLE DOCTORS
    # ========================================================

    if (
        department
        and selected_date
        and selected_time
    ):

        try:

            selected_date_obj = (
                datetime.strptime(
                    selected_date,
                    "%Y-%m-%d"
                ).date()
            )


            selected_time_obj = (
                datetime.strptime(
                    selected_time,
                    "%H:%M"
                ).time()
            )


            department_doctors = (
                Doctor.objects.filter(
                    specialization=department
                )
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


        except ValueError:

            error_message = (
                "Invalid date or time."
            )


    # ========================================================
    # RENDER DOCTOR LIST
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

        }

    )


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


    appointments = (
        Appointment.objects
        .filter(
            patient=patient
        )
        .order_by(

            "-appointment_date",

            "-appointment_time"

        )
    )


    return render(

        request,

        "patients/my_appointments.html",

        {

            "appointments": appointments,

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