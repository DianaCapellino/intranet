from django import template

register = template.Library()

@register.filter
def contrast_color(hex_color):
    try:
        h = str(hex_color).lstrip('#')
        r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return '#333333' if luminance > 0.45 else '#ffffff'
    except (ValueError, TypeError):
        return '#333333'

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

@register.filter
def has_key(d, key):
    try:
        return key in d
    except TypeError:
        return False