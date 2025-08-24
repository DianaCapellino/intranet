import django_filters
from .models import Trip

class TripFilter(django_filters.FilterSet):
    class Meta:
        model = Trip
        fields = {
            'name': ['icontains'],
            'travelling_date': ['lt','gt'],
            'status':['exact'],
            'difficulty':['exact'],
            'client_reference':['icontains'],
            'tourplanId':['exact'],
            'responsable_user':['exact'],
            'operations_user':['exact']
        }
