from datetime import datetime, timedelta

from django.db import IntegrityError
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from availability.models import (
    DoctorLeave,
    DoctorSchedule,
)

from doctors.models import Doctor
from patients.models import Patient

from .models import Appointment

def doctor_availability(request, doctor_id):
    patient_id = request.session.get(
        "patient_id"
    )

    if not patient_id:
        return redirect(
            "patient_login"
        )

    doctor = get_object_or_404(
        Doctor,
        id=doctor_id
    )

    selected_date = request.GET.get(
        "date"
    )

    slots = []
    message = None

    if selected_date:
        try:
            selected_date_obj = datetime.strptime(
                selected_date,
                "%Y-%m-%d"
            ).date()

            day_name = selected_date_obj.strftime(
                "%A"
            )

            is_leave = DoctorLeave.objects.filter(
                doctor=doctor,
                leave_date=selected_date_obj
            ).exists()

            if is_leave:
                message = (
                    "Doctor is on leave on this date."
                )
            else:
                schedule = DoctorSchedule.objects.filter(
                    doctor=doctor,
                    day=day_name,
                    is_available=True
                ).first()

                if not schedule:
                    message = (
                        f"Doctor is not available on {day_name}."
                    )
                else:
                    current_time = datetime.combine(
                        selected_date_obj,
                        schedule.start_time
                    )

                    end_datetime = datetime.combine(
                        selected_date_obj,
                        schedule.end_time
                    )

                    slot_duration = timedelta(
                        minutes=schedule.slot_duration
                    )

                    booked_times = set(
                        Appointment.objects.filter(
                            doctor=doctor,
                            appointment_date=selected_date_obj
                        ).exclude(
                            status="cancelled"
                        ).values_list(
                            "appointment_time",
                            flat=True
                        )
                    )

                    while (
                        current_time + slot_duration
                        <= end_datetime
                    ):
                        slot_start = current_time.time()
                        slot_end = (
                            current_time + slot_duration
                        ).time()
                        is_break = False

                        for doctor_break in schedule.breaks.all():
                            if (
                                slot_start < doctor_break.break_end
                                and
                                slot_end > doctor_break.break_start
                            ):
                                is_break = True
                                break

                        if not is_break:
                            slots.append(
                                {
                                    "time": slot_start,
                                    "is_booked": (
                                        slot_start
                                        in booked_times
                                    )
                                }
                            )

                        current_time += slot_duration

                    if not slots:
                        message = (
                            "No slots available for this date."
                        )

        except ValueError:
            message = (
                "Please select a valid date."
            )

    return render(
        request,
        "booking/doctor_availability.html",
        {
            "doctor": doctor,
            "selected_date": selected_date,
            "slots": slots,
            "message": message
        }
    )

def book_appointment(request, doctor_id):
    patient_id = request.session.get(
        "patient_id"
    )

    if not patient_id:
        return redirect(
            "patient_login"
        )

    if request.method != "POST":

        return redirect(
            "doctor_availability",
            doctor_id=doctor_id
        )

    patient = get_object_or_404(
        Patient,
        id=patient_id
    )

    doctor = get_object_or_404(
        Doctor,
        id=doctor_id
    )

    appointment_date = request.POST.get(
        "appointment_date"
    )

    appointment_time = request.POST.get(
        "appointment_time"
    )

    already_booked = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=appointment_date,
        appointment_time=appointment_time
    ).exclude(
        status="cancelled"
    ).exists()

    if already_booked:

        return redirect(
            "doctor_availability",
            doctor_id=doctor.id
        )

    try:

        appointment = Appointment.objects.create(
            doctor=doctor,
            patient=patient,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status="pending"
        )

        return render(
            request,
            "booking/booking_success.html",
            {
                "appointment": appointment
            }
        )

    except IntegrityError:

        return redirect(
            "doctor_availability",
            doctor_id=doctor.id
        )