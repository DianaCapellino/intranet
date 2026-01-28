import math

def apply_client_margin(rate, client_category, service_type):
    sell = rate.sell

    if client_category == "C":
        return sell

    if service_type == "AC":
        if rate.margin == "Regular":
            if client_category == "B":
                sell *= 1.0366
            elif client_category == "A":
                sell *= 1.0625
        elif rate.margin == "High":
            if client_category in ("A", "B"):
                sell *= 1.025

    elif service_type == "NA":
        if rate.margin == "Regular":
            if client_category == "B":
                sell *= 1.03
            elif client_category == "A":
                sell *= 1.06

    return math.ceil(sell)