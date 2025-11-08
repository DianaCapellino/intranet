from datetime import datetime, date, timedelta
from .models import Entry, Holidays, Trip, Absence

def update_entries():
    
    # All entries
    entries = Entry.objects.all()
    
    for entry in entries:
        update_timingStatus(entry)


def update_timingStatus(entry):

    # Today
    today = date.today()

    difference = get_working_days(entry.starting_date, today)

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


def get_working_days(from_date, to_date):
    
    # Normalize the dates
    if hasattr(from_date, "date"):
        from_date = from_date.date()
    if hasattr(to_date, "date"):
        to_date = to_date.date()

    # Check if the order is correct
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    # Get the quantity of holidays
    n_holidays = Holidays.objects.filter(
        workable=False,
        date_from__range=(from_date, to_date)
    ).count()

    working_days = (to_date - from_date).days - n_holidays
    return working_days


def get_working_days_worker(from_date, to_date, worker):

    working_days = get_working_days(from_date, to_date)

    holidays_worker = Holidays.objects.filter(working_user=worker).filter(date_from__range=(from_date, to_date)).count()

    absence_worker = Absence.objects.filter(absence_user=worker).filter(date_from__range=(from_date, to_date)).count()

    return working_days + holidays_worker - absence_worker
    

def check_duplicate_trips(date_from, date_to):
    duplicated_files = []

    filtered_trips = Trip.objects.filter(travelling_date__range=(date_from, date_to))
    for trip in filtered_trips:
        for trip_compared in filtered_trips:
            if trip.tourplanId:
                if trip.tourplanId == trip_compared.tourplanId and trip.id != trip_compared.id:
                    duplicated_files.append((trip, trip_compared))
    
    return duplicated_files


def check_missing_amounts(date_from, date_to):
    missing_amounts_entries = []

    for entry in Entry.objects.filter(starting_date__range=(date_from, date_to)):
        if (entry.amount == 0 or entry.amount is None) and (entry.status == "Quote" and entry.version_quote == "A" or entry.status == "Booking" and entry.version == "1"):
            missing_amounts_entries.append(entry)
    
    return missing_amounts_entries


def check_incongruent_trip_dates(date_from, date_to):
    incongruent_trips = []

    for trip in Trip.objects.filter(travelling_date__range=(date_from, date_to)):
        if trip.starting_date == trip.travelling_date or trip.travelling_date < trip.starting_date:
            incongruent_trips.append(trip)
    
    return incongruent_trips


def check_incongruent_entry_dates(date_from, date_to):
    incongruent_entries = []

    for entry in Entry.objects.filter(starting_date__range=(date_from, date_to)):
        difference = (entry.closing_date - entry.starting_date).days
        if entry.starting_date == entry.trip.travelling_date or entry.starting_date > entry.closing_date or difference < 0 or difference > 30:
            incongruent_entries.append(entry)
    
    return incongruent_entries