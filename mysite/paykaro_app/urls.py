from django.urls import path
from . import views

urlpatterns = [
    path('login/manager/', views.manager_login, name='manager_login'),
    path('login/employee/', views.employee_login, name='employee_login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/manager/', views.manager_dashboard, name='manager_dashboard'),
    path('dashboard/employee/', views.employee_dashboard, name='employee_dashboard'),
    path('signup/', views.signup, name='signup'),
]
