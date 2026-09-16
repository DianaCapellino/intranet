from django import template

from tariff.utils import resolve_pic_url

register = template.Library()


@register.filter
def pic_url(filename):
    """Resuelve pic1_url/pic2_url/pic3_url de Location/Supplier/Product a una URL real,
    sea el nombre de archivo suelto viejo (relativo a static/tariff/) o la URL completa nueva
    (subida real vía save_pic_upload) — ver tariff/utils.py:resolve_pic_url."""
    return resolve_pic_url(filename)
