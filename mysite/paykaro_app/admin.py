from django.contrib import admin

# Register your models here.
from .models import Employee,Department,Job,Leave,Salary,Payroll

admin.site.register(Employee)
admin.site.register(Department)
admin.site.register(Job)
admin.site.register(Leave)
admin.site.register(Salary)
admin.site.register(Payroll)

