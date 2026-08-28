from django.urls import path
from . import views

urlpatterns = [
    path(
        "doctor/<int:doctor_id>/",
        views.doctor_availability,
        name="doctor_availability"
    ),

    path(
        "book/<int:doctor_id>/",
        views.book_appointment,
        name="book_appointment"
    ),
]