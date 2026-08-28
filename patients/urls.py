from django.urls import path

from . import views


urlpatterns = [

    path(
        "register/",
        views.patient_register,
        name="patient_register"
    ),

    path(
        "login/",
        views.patient_login,
        name="patient_login"
    ),

    path(
        "departments/",
        views.department_list,
        name="department_list"
    ),

    path(
        "select-datetime/",
        views.select_datetime,
        name="select_datetime"
    ),

    path(
        "doctors/",
        views.doctor_list,
        name="doctor_list"
    ),

    path(
        "my-appointments/",
        views.my_appointments,
        name="my_appointments"
    ),

    path(
        "cancel/<int:appointment_id>/",
        views.cancel_appointment,
        name="cancel_appointment"
    ),

    path(
        "logout/",
        views.patient_logout,
        name="patient_logout"
    ),
]