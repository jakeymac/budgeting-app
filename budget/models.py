import calendar
from datetime import date
from django.db import models


def period_start():
    return date.today().replace(day=1)


def period_end():
    today = date.today()
    return today.replace(day=calendar.monthrange(today.year, today.month)[1])


class Budget(models.Model):
    owner = models.CharField(max_length=80, default='Teresa')
    title = models.CharField(max_length=120, default='Everyday budget')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reserve = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    start = models.DateField(default=period_start)
    end = models.DateField(default=period_end)


class SpendingEvent(models.Model):
    description = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=40, default='Other')
    date = models.DateField(default=date.today)
    note = models.TextField(blank=True, max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']


class MonthlyPlan(models.Model):
    # Exactly two named slots; saving replaces a slot rather than creating versions.
    kind = models.CharField(max_length=11, primary_key=True, choices=[('actual', 'Actual'), ('theoretical', 'Theoretical')])
    data = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(kind__in=['actual', 'theoretical']), name='only_two_plan_slots')]
