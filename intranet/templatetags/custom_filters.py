from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return None
    
@register.filter
def add(value, arg):
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return None

@register.filter
def divided(value, arg):
    try:
        return int(value) / int(arg)
    except (ValueError, TypeError):
        return None

@register.filter
def dict_get(d, key):
    try:
        return d[key]
    except (KeyError, TypeError):
        return None

@register.filter
def split(value, sep):
    return value.split(sep)