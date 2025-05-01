'''core/urls.py'''
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from io import BytesIO
from django.db.models import Sum
from .models import Group, Expense, Debt, Split
from django.contrib.auth.forms import UserCreationForm
from django.db import IntegrityError
import json
import qrcode


def index(request):
    groups = Group.objects.filter(members=request.user) if request.user.is_authenticated else []
    return render(request, 'core/index.html', {'groups': groups})


@login_required
@csrf_exempt
def create_group(request):
    if request.method == 'POST':
        print("Request body:", request.body)
        try:
            data = json.loads(request.body)
            print("Parsed data:", data)
            if not data.get('name'):
                return JsonResponse({'error': 'Group name is required'}, status=400)
            try:
                group = Group.objects.create(name=data['name'], created_by=request.user)
                print("Group Created:", group)
                group.members.add(request.user)
                return JsonResponse({'group_id': group.id})
            except IntegrityError:
                print("Integrity error:", str(e))
                return JsonResponse({'error': 'A group with this name already exists for you'}, status=400)
            except Exception as e:
                print("Error creating group:", str(e))
                return JsonResponse({'error': str(e)}, status=500)
        except json.JSONDecodeError:
            print("JSON decode error:", str(e))
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def group_detail(request, group_id):
    try:
        group = Group.objects.get(id=group_id)
        expenses = Expense.objects.filter(group=group)
        debts = Debt.objects.filter(group=group)
        splits = Split.objects.filter(group=group)
        return render(request, 'core/group.html', {
            'group': group,
            'expenses': expenses,
            'debts': debts,
            'splits': splits
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found'}, status=404)


@login_required
@csrf_exempt
def add_expense(request, group_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        try:
            group = Group.objects.get(id=group_id)
            Expense.objects.create(
                description=data['description'],
                amount=data['amount'],
                paid_by=request.user,
                group=group, 
                category=data.get('category', '') 
            )
            calculate_debts(group)
            return JsonResponse({'success': True})
        except Group.DoesNotExist:
            return JsonResponse({'error': 'Group not found'}, status=404)
        except KeyError as e:
            return JsonResponse({'error': f'Missing field: {e}'}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
@csrf_exempt
def join_group(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            group_name = data.get('group_name')
            if not group_name:
                return JsonResponse({'error': 'Group name is required'}, status=400)
            try:
                group = Group.objects.get(name=group_name)
                if request.user in group.members.all():
                    return JsonResponse({'error': 'You are already a member of this group'}, status=400)
                group.members.add(request.user)
                return JsonResponse({'success': True, 'group_id': group.id})
            except Group.DoesNotExist:
                return JsonResponse({'error': 'Group not found'}, status=404)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)


def group_qr(request, group_id):
    try:
        url = request.build_absolute_uri(f"/group/{group_id}/")
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return HttpResponse(buffer.getvalue(), content_type='image/png')
    except Exception as e:  
        return HttpResponse(status=500)


@login_required
@csrf_exempt
def join_group_by_id(request, group_id):
    if request.method == 'POST':
        try:
            group = Group.objects.get(id=group_id)
            if request.user in group.members.all():
                return JsonResponse({'success': True, 'group_id': group.id})
            group.members.add(request.user)
            return JsonResponse({'success': True, 'group_id': group.id})
        except Group.DoesNotExist:
            return JsonResponse({'error': 'Group not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def pay_debt(request, debt_id):
    if request.method == 'POST':
        try:
            debt = Debt.objects.get(id=debt_id, from_user=request.user)
            if debt.status != 'pending':
                return JsonResponse({'error': 'Debt is not pending'}, status=400)
            debt.status = 'paid'
            debt.save()
            return JsonResponse({'success': True})
        except Debt.DoesNotExist:
            return JsonResponse({'error': 'Debt not found or you are not the debtor'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)

def calculate_debts(group):
    Debt.objects.filter(group=group, status='pending').delete()
    Split.objects.filter(group=group).delete()
    expenses = Expense.objects.filter(group=group)
    members = group.members.all()
    if not members:
        return []
    balances = {member.id: 0 for member in members}
    paid_debts = Debt.objects.filter(group=group, status='paid')
    for debt in paid_debts:
        balances[debt.from_user.id] += debt.amount
        balances[debt.to_user.id] -= debt.amount
    for expense in expenses:
        share = expense.amount / len(members)
        for member in members:
            Split.objects.create(
                expense=expense,
                user=member,
                share=share,
                group=group
            )
            if member == expense.paid_by:
                balances[member.id] += expense.amount - share
            else:
                balances[member.id] -= share
    debts = []
    for from_id, balance in balances.items():
        for to_id, to_balance in balances.items():
            if from_id < to_id and balance < 0 and to_balance > 0:
                amount = min(-balance, to_balance)
                if amount > 0:
                    Debt.objects.create(
                        from_user_id=from_id,
                        to_user_id=to_id,
                        amount=amount,
                        group=group
                    )
                    balances[from_id] += amount
                    balances[to_id] -= amount
                    debts.append({'from': from_id, 'to': to_id, 'amount': amount})
    return debts

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'core/register.html', {'form': form})