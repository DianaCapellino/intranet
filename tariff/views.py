from django.shortcuts import render

# Create your views here.
def tariff(request):
    return render(request, "tariff/tariff.html")