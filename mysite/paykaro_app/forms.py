from django import forms
from .models import Employee

class EmployeeSignupForm(forms.ModelForm):
    ROLE_CHOICES = [('manager', 'Manager'), ('employee', 'Employee')]
    emp_pass = forms.CharField(widget=forms.PasswordInput)
    role = forms.ChoiceField(choices=ROLE_CHOICES)

    class Meta:
        model = Employee
        fields = ['f_name', 'l_name', 'emp_email', 'emp_pass', 'age', 'gender', 'city']
