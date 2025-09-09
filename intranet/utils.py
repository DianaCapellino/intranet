from datetime import datetime, date, timedelta
from .models import Entry, Holidays

def update_entries():
    # Today
    today = date.today()
    
    # Days to calculate the days shown
    days = 15

    # Date for filtering
    date_fil = today - timedelta(days=days)
    date_fil_to = today + timedelta(days=1)

    # Filter the entries for the last days
    filter_entries = Entry.objects.filter(starting_date__gte=date_fil, starting_date__lte=date_fil_to)
    
    for entry in filter_entries:
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