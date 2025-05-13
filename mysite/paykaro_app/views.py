from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.cache import never_cache
from .forms import EmployeeSignupForm

# Make sure the path to your models is correct
from .models import Employee, Department

def manager_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            emp = Employee.objects.get(emp_email=email, emp_pass=password)

            if Department.objects.filter(man_id=emp).exists():
                request.session['emp_id'] = emp.emp_id
                request.session['role'] = 'manager'
                return redirect('manager_dashboard')
            else:
                messages.error(request, 'This user is not a manager.')
        except Employee.DoesNotExist:
            messages.error(request, 'Invalid credentials.')
    return render(request, 'paykaro_app/manager_login2.html')


def employee_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            emp = Employee.objects.get(emp_email=email, emp_pass=password)

            if not Department.objects.filter(man_id=emp).exists():
                request.session['emp_id'] = emp.emp_id
                request.session['role'] = 'employee'
                return redirect('employee_dashboard')
            else:
                messages.error(request, 'This user is a manager, not an employee.')
        except Employee.DoesNotExist:
            messages.error(request, 'Invalid credentials.')
    return render(request, 'paykaro_app/employee_login2.html')

# paykaro_app/views.py
@never_cache
def manager_dashboard(request):
    if request.session.get('role') == 'manager':
        return render(request, 'paykaro_app/manager_dashboard.html')
    return redirect('manager_login')

@never_cache
def employee_dashboard(request):
    if request.session.get('role') == 'employee':
        return render(request, 'paykaro_app/employee_dashboard.html')
    return redirect('employee_login')


def logout_view(request):
    role = request.session.get('role')  # Check the user's role before logout
    request.session.flush()  # Clear session (logs the user out)

    if role == 'manager':
        return redirect('manager_login')  # Use your named URL
    else:
        return redirect('employee_login')  # Default to employee if not manager

def signup(request):
    if request.method == 'POST':
        form = EmployeeSignupForm(request.POST)
        if form.is_valid():
            employee = form.save()
            role = form.cleaned_data['role']

            # Store session
            request.session['emp_id'] = employee.emp_id
            request.session['role'] = role

            # Redirect based on role
            if role == 'manager':
                return redirect('manager_dashboard')
            else:
                return redirect('employee_dashboard')
    else:
        form = EmployeeSignupForm()

    return render(request, 'paykaro_app/signup2.html', {'form': form})