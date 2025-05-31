from django.urls import path
from . import views

urlpatterns = [
    # Login/Logout paths
    path('login/manager/', views.manager_login, name='manager_login'),
    path('login/employee/', views.employee_login, name='employee_login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard paths
    path('dashboard/manager/', views.manager_dashboard, name='manager_dashboard'),
    path('dashboard/employee/', views.employee_dashboard, name='employee_dashboard'),
    
    # Manager functions
    path('manager/department/', views.view_department_employees, name='view_department'),
    path('manager/manage/', views.manage_employees, name='manage_employees'),
    path('manager/leaves/', views.approve_leaves, name='approve_leaves'),
    path('manager/payroll/', views.generate_payroll, name='generate_payroll'),
    
    # API endpoints for employee management
    path('api/employees/<int:employee_id>/update/', views.update_employee, name='update_employee'),
    path('api/employees/<int:employee_id>/delete/', views.delete_employee, name='delete_employee'),
    
    # Registration
    path('signup/', views.signup, name='signup'),
    # Add these to your existing urlpatterns
    path('employee/apply-leave/', views.apply_leave, name='apply_leave'),
    path('employee/salary/', views.view_salary, name='view_salary'),
    path('update-profile-photo/', views.update_profile_photo, name='update_profile_photo'),
]