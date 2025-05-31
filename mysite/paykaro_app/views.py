from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import EmployeeSignupForm
'''from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json'''

# Make sure the path to your models is correct
from .models import Employee, Department, Leave, Salary, Payroll
from decimal import Decimal
from django.utils import timezone
'''import os
from django.conf import settings'''
import csv
from django.http import HttpResponse
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from functools import wraps
from django.shortcuts import redirect

def manager_login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.session.get('emp_id') or request.session.get('role') != 'manager':
            return redirect('manager_login')
        return view_func(request, *args, **kwargs)
    return wrapped

def manager_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            emp = Employee.objects.get(emp_email=email, emp_pass=password)
            # Check if this employee is a manager by seeing if any employees report to them
            if Employee.objects.filter(man_id=emp).exists():
                request.session['emp_id'] = emp.emp_id
                request.session['role'] = 'manager'
                return redirect('manager_dashboard')
            else:
                messages.error(request, 'This user is not a manager.')
        except Employee.DoesNotExist:
            messages.error(request, 'Invalid credentials.')
    return render(request, 'paykaro_app/manager_login.html')


def employee_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            emp = Employee.objects.get(emp_email=email, emp_pass=password)
            
            # Check if this employee is a manager (has employees reporting to them)
            is_manager = Employee.objects.filter(man_id=emp).exists()
            
            if not is_manager:
                request.session['emp_id'] = emp.emp_id
                request.session['role'] = 'employee'
                return redirect('employee_dashboard')
            else:
                messages.error(request, 'This user is a manager. Please use manager login.')
                
        except Employee.DoesNotExist:
            messages.error(request, 'Invalid credentials.')
    return render(request, 'paykaro_app/employee_login.html')

def employee_login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.session.get('emp_id') or request.session.get('role') != 'employee':
            return redirect('employee_login')
        return view_func(request, *args, **kwargs)
    return wrapped

# paykaro_app/views.py
@manager_login_required
def view_department_employees(request):
    if request.session.get('role') != 'manager':
        return redirect('manager_login')
    
    manager_id = request.session.get('emp_id')
    try:
        # Get the manager's employee record
        manager = Employee.objects.get(emp_id=manager_id)
        # Get the department the manager belongs to
        department = manager.dept_id
        # Get all employees in this department
        employees = Employee.objects.filter(dept_id=department)
        
        return render(request, 'paykaro_app/department_employees.html', {
            'department': department,
            'employees': employees
        })
    except Employee.DoesNotExist:
        messages.error(request, 'Manager not found.')
        return redirect('manager_login')

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
import json

@manager_login_required
def manage_employees(request):
    manager_id = request.session.get('emp_id')
    try:
        # Get the manager's employee record
        manager = Employee.objects.get(emp_id=manager_id)
        # Get the department the manager belongs to
        department = manager.dept_id
        # Get all employees in this department except the manager
        employees = Employee.objects.filter(dept_id=department).exclude(emp_id=manager_id)
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'add':
                try:
                    # Handle adding new employee
                    new_employee = Employee(
                        f_name=request.POST.get('f_name'),
                        l_name=request.POST.get('l_name'),
                        emp_pass=request.POST.get('emp_pass'),
                        emp_email=request.POST.get('emp_email'),
                        age=int(request.POST.get('age')),
                        gender=request.POST.get('gender'),
                        city=request.POST.get('city'),
                        sal=float(request.POST.get('sal')),
                        dept_id=department,
                        man_id=manager
                    )
                    new_employee.save()
                    messages.success(request, 'Employee added successfully!')
                except Exception as e:
                    messages.error(request, f'Error adding employee: {str(e)}')
            
            return redirect('manage_employees')
        
        return render(request, 'paykaro_app/manage_employees.html', {
            'employees': employees,
            'department': department,
            'manager': manager
        })
        
    except Employee.DoesNotExist:
        messages.error(request, 'Manager not found.')
        return redirect('manager_dashboard')

@manager_login_required
def approve_leaves(request):
    if request.session.get('role') != 'manager':
        return redirect('manager_login')
    
    manager_id = request.session.get('emp_id')
    try:
        # Get the manager's employee record
        manager = Employee.objects.get(emp_id=manager_id)
        # Get the department the manager belongs to
        department = manager.dept_id
        
        # Get pending leaves for employees in manager's department
        pending_leaves = Leave.objects.filter(
            emp_id__dept_id=department,  # Using dept_id directly from Employee model
            status='P'
        ).select_related('emp_id')  # Optimize by pre-fetching employee data
        
        if request.method == 'POST':
            leave_id = request.POST.get('leave_id')
            action = request.POST.get('action')
            
            leave = get_object_or_404(Leave, leave_id=leave_id)
            # Verify the leave belongs to an employee in manager's department
            if leave.emp_id.dept_id != department:
                messages.error(request, 'Unauthorized: Leave belongs to employee from different department')
                return redirect('approve_leaves')
            
            if action == 'approve':
                leave.status = 'A'
                # If approved, create a Payroll entry if needed
                if not leave.payroll_id:
                    try:
                        salary = Salary.objects.get(emp_id=leave.emp_id)
                        payroll = Payroll.objects.create(
                            tot_amt=0,  # This should be calculated based on your business logic
                            date=timezone.now(),
                            salary_id=salary
                        )
                        leave.payroll_id = payroll
                    except Salary.DoesNotExist:
                        messages.warning(request, 'Leave approved but no salary record found for payroll creation')
            elif action == 'reject':
                leave.status = 'R'
            
            leave.save()
            messages.success(request, f'Leave {action}d successfully')
            return redirect('approve_leaves')
        
        return render(request, 'paykaro_app/approve_leaves.html', {
            'pending_leaves': pending_leaves
        })
        
    except Employee.DoesNotExist:
        messages.error(request, 'Manager not found.')
        return redirect('manager_login')

@manager_login_required
def generate_payroll(request):
    if request.session.get('role') != 'manager':
        return redirect('manager_login')
    
    manager_id = request.session.get('emp_id')
    department = Department.objects.get(man_id_id=manager_id)
    employees = Employee.objects.filter(dept_id_id=department)
    
    if request.method == 'POST':
        # Generate payroll for selected employees
        selected_employees = request.POST.getlist('employees')
        
        # Create CSV file
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="payroll_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Employee ID', 'Name', 'Basic Salary', 'DA', 'HRA', 'Bonus', 
                        'PF', 'Income Tax', 'Health Insurance', 'Net Salary'])
        
        for emp_id in selected_employees:
            employee = Employee.objects.get(emp_id=emp_id)
            salary = Salary.objects.get(emp_id=employee)
            
            net_salary = (salary.basic + salary.DA + salary.HRA + salary.bonus - 
                         salary.PF - salary.income_tax - salary.health_ins)
            
            writer.writerow([
                employee.emp_id,
                f"{employee.f_name} {employee.l_name}",
                salary.basic,
                salary.DA,
                salary.HRA,
                salary.bonus,
                salary.PF,
                salary.income_tax,
                salary.health_ins,
                net_salary
            ])
            
            # Create Payroll record
            Payroll.objects.create(
                tot_amt=net_salary,
                date=timezone.now(),
                salary_id=salary
            )
        
        return response

    return render(request, 'paykaro_app/generate_payroll.html', {
        'employees': employees
    })
from django.views.decorators.cache import never_cache
@never_cache
def manager_dashboard(request):
    if request.session.get('role') == 'manager':
        manager_id = request.session.get('emp_id')
        try:
            manager = Employee.objects.get(emp_id=manager_id)
            department = manager.dept_id
            employee_count = Employee.objects.filter(dept_id=department).count()
            
            # Get additional statistics
            active_leaves = Leave.objects.filter(
                emp_id__dept_id=department,
                status='A',
                end_date__gte=timezone.now().date()
            ).count()
            
            pending_requests = Leave.objects.filter(
                emp_id__dept_id=department,
                status='P'
            ).count()

            context = {
                'manager': manager,
                'department': department,
                'employee_count': employee_count,
                'active_leaves': active_leaves,
                'pending_requests': pending_requests
            }
            return render(request, 'paykaro_app/manager_dashboard.html', context)
            
        except Employee.DoesNotExist:
            messages.error(request, 'Manager not found.')

    return redirect('manager_login')


@never_cache
@employee_login_required
def employee_dashboard(request):
    if request.session.get('role') != 'employee':
        return redirect('employee_login')
    
    try:
        # Get employee details
        emp_id = request.session.get('emp_id')
        employee = Employee.objects.get(emp_id=emp_id)
        
        # Get leave statistics
        current_year = timezone.now().year
        all_leaves = Leave.objects.filter(
            emp_id=employee,
            start_date__year=current_year
        )
        
        leaves_taken = all_leaves.filter(status='A').count()
        leaves_remaining = 12 - leaves_taken  # Assuming 12 leaves per year
        
        # Get recent leave applications
        recent_leaves = Leave.objects.filter(
            emp_id=employee
        ).order_by('-start_date')[:5]  # Get last 5 leaves
        
        context = {
            'employee': employee,
            'leaves_taken': leaves_taken,
            'leaves_remaining': leaves_remaining,
            'recent_leaves': recent_leaves,
        }
        
        return render(request, 'paykaro_app/employee_dashboard.html', context)
    
    except Employee.DoesNotExist:
        messages.error(request, 'Employee not found.')
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

    return render(request, 'paykaro_app/signup.html', {'form': form})

@manager_login_required
@csrf_exempt  # Add this decorator
@require_http_methods(["POST"])
def update_employee(request, employee_id):
    if request.session.get('role') != 'manager':
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)
    
    try:
        # Get the manager's department
        manager = Employee.objects.get(emp_id=request.session.get('emp_id'))
        department = manager.dept_id
        
        # Get the employee and verify they belong to the manager's department
        employee = get_object_or_404(Employee, emp_id=employee_id, dept_id=department)
        
        try:
            # Parse the JSON data from request
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            }, status=400)
        
        # Update allowed fields
        allowed_fields = ['f_name', 'l_name', 'emp_email', 'age', 'gender', 'city', 'sal']
        
        for field in allowed_fields:
            if field in data:
                try:
                    if field == 'age':
                        setattr(employee, field, int(data[field]))
                    elif field == 'sal':
                        setattr(employee, field, Decimal(data[field]))
                    else:
                        setattr(employee, field, data[field])
                except (ValueError, TypeError) as e:
                    return JsonResponse({
                        'success': False,
                        'message': f'Invalid value for field {field}: {str(e)}'
                    }, status=400)
        
        try:
            employee.full_clean()  # Validate the model
            employee.save()
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'message': 'Employee updated successfully',
            'data': {
                'emp_id': employee.emp_id,
                'f_name': employee.f_name,
                'l_name': employee.l_name,
                'emp_email': employee.emp_email,
                'age': employee.age,
                'gender': employee.get_gender_display(),
                'city': employee.city,
                'sal': str(employee.sal)
            }
        })
        
    except Employee.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Employee or manager not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred while updating the employee: {str(e)}'
        }, status=500)

@manager_login_required
@require_http_methods(["POST"])
def delete_employee(request, employee_id):
    if request.session.get('role') != 'manager':
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)
    
    try:
        # Get the manager's department
        manager = Employee.objects.get(emp_id=request.session.get('emp_id'))
        department = manager.dept_id
        
        # Get the employee and verify they belong to the manager's department
        employee = get_object_or_404(Employee, emp_id=employee_id, dept_id=department)
        employee.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Employee deleted successfully'
        })
        
    except Employee.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Employee or manager not found'
        }, status=404)

@employee_login_required
def apply_leave(request):
    if request.method == 'POST':
        emp_id = request.session.get('emp_id')
        try:
            employee = Employee.objects.get(emp_id=emp_id)
            
            # Get form data
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            reason = request.POST.get('reason')
            
            # Handle 'Other' reason
            if reason == 'Other':
                reason = request.POST.get('other_reason')
            
            # Validate dates
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
            
            # Check for overlapping leaves
            overlapping_leaves = Leave.objects.filter(
                emp_id=employee,
                start_date__lte=end_date,
                end_date__gte=start_date,
                status__in=['P', 'A']  # Pending or Approved
            ).exists()
            
            if overlapping_leaves:
                messages.error(request, 'You already have a leave request for these dates')
                return redirect('employee_dashboard')
            
            # Calculate number of days
            leave_days = (end_date - start_date).days + 1
            
            # Get leave statistics
            current_year = timezone.now().year
            approved_leaves = Leave.objects.filter(
                emp_id=employee,
                status='A',
                start_date__year=current_year
            ).count()
            
            if approved_leaves + leave_days > 12:  # Assuming 12 leaves per year
                messages.error(request, 'Insufficient leave balance')
                return redirect('employee_dashboard')
            
            # Create leave request
            Leave.objects.create(
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                emp_id=employee,
                status='P'  # Set as Pending
            )
            
            messages.success(request, 'Leave application submitted successfully!')
            
        except Employee.DoesNotExist:
            messages.error(request, 'Employee not found.')
        except ValueError as e:
            messages.error(request, f'Invalid date format: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error applying for leave: {str(e)}')
            
    return redirect('employee_dashboard')

@employee_login_required
def view_salary(request):
    if request.session.get('role') != 'employee':
        return redirect('employee_login')
    
    emp_id = request.session.get('emp_id')
    try:
        employee = Employee.objects.get(emp_id=emp_id)
        salary = Salary.objects.get(emp_id=employee)
        
        context = {
            'employee': employee,
            'salary': salary
        }
        
        return render(request, 'paykaro_app/view_salary.html', context)
        
    except Employee.DoesNotExist:
        messages.error(request, 'Employee not found.')
        return redirect('employee_login')
    except Salary.DoesNotExist:
        messages.error(request, 'Salary information not found.')
        return redirect('employee_dashboard')