from django.contrib import admin
from django.urls import path, include

urlpatterns = [

    path("admin/", admin.site.urls),

    path("", include("accounts.urls")),

    path("doctor/", include("doctors.urls")),

    path("patient/", include("patients.urls")),

    path("booking/", include("booking.urls")),

]