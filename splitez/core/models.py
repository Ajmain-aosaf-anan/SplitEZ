'''core/models.py'''

from django.db import models
from django.contrib.auth.models import User

class Group(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    members = models.ManyToManyField(User, related_name='group_memberships')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    def total_expenses(self):
        return self.expense_set.aggregate(total=models.Sum('amount'))['total'] or 0
    
    class Meta:
        indexes = [
            models.Index(fields=['created_by']),
        ]

class Expense(models.Model):
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_by = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    category = models.CharField(
        max_length=50,
        choices=[('food', 'Food'), ('rent', 'Rent'), ('travel', 'Travel'), ('other', 'Other')],
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.description} (${self.amount})"
    
    class Meta:
        indexes = [
            models.Index(fields=['group']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gte=0), name='expense_amount_gte_0'),
        ]

class Debt(models.Model):
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='debts_owed')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='debts_due')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('paid', 'Paid'), ('disputed', 'Disputed')],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.from_user} owes {self.to_user} ${self.amount}"
    
    class Meta:
        indexes = [
            models.Index(fields=['group']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gte=0), name='debt_amount_gte_0'),
        ]

class Split(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    share = models.DecimalField(max_digits=10, decimal_places=2)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} owes ${self.share} for {self.expense}"
    
    class Meta:
        indexes = [
            models.Index(fields=['group']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(share__gte=0), name='split_share_gte_0'),
        ]