from django.urls import path
from . import views


urlpatterns = [

    path(
        "login/",
        views.doctor_login,
        name="doctor_login"
    ),

    path(
        "dashboard/",
        views.doctor_dashboard,
        name="doctor_dashboard"
    ),

    path(
        "availability/",
        views.manage_availability,
        name="manage_availability"
    ),

    path(
        "leave/",
        views.apply_leave,
        name="apply_leave"
    ),

    path(
        "appointments/",
        views.doctor_appointments,
        name="doctor_appointments"
    ),

    path(
        "appointment/<int:appointment_id>/<str:status>/",
        views.update_appointment_status,
        name="update_appointment_status"
    ),

    path(
        "logout/",
        views.doctor_logout,
        name="doctor_logout"
    ),

]