from django.urls import path

from . import views

app_name = "teams"

urlpatterns = [
    path("", views.team_list, name="team-list"),
    path("<int:pk>/manage/", views.team_manage, name="team-manage"),
]