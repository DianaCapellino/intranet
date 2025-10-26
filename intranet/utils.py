from datetime import datetime, date, timedelta
from .models import Entry, Holidays, Trip

def update_entries():
    
    # All entries
    entries = Entry.objects.all()
    
    for entry in entries:
        update_timingStatus(entry)


def update_timingStatus(entry):

    # Today
    today = date.today()

    # Get the days between today and the day the entry was received
    n_holidays = Holidays.objects.filter(workable=False).filter(date_from__range=(entry.starting_date, today)).count()

    difference = (today - entry.starting_date.date()).days - n_holidays

    # Prepare the colors if it is quote
    if entry.status == "Quote":
        if difference == 0:
            entry.timingStatus = "light"
        elif difference == 1:
            entry.timingStatus = "warning"
        elif difference >= 2 and difference < 6:
            entry.timingStatus = "info"
        elif difference >= 6:
            entry.timingStatus = "danger"
    elif entry.status == "Booking" or entry.status == "Final Itinerary":
        if difference <= 2:
            entry.timingStatus = "light"
        elif difference == 3:
            entry.timingStatus = "warning"
        elif difference >= 4 and difference < 7:
            entry.timingStatus = "info"
        elif difference >= 8:
            entry.timingStatus = "danger"
    else:
        if difference <= 3:
            entry.timingStatus = "light"
        elif difference == 4:
            entry.timingStatus = "warning"
        elif difference >= 5 and difference < 10:
            entry.timingStatus = "info"
        elif difference >= 11:
            entry.timingStatus = "danger"

    entry.save()

def get_duplicate_trips():
    duplicated_files = []
    for trip in Trip.objects.all():
        for trip_compared in Trip.objects.all():
            if trip.tourplanId == trip_compared.tourplanId:
                duplicated_files.append((trip.id, trip_compared.id))