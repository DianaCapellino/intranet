/*
 * Cajas de "arrastrar o cliquear" para subir fotos (Location/Supplier/Product) — reemplaza
 * los campos de texto donde antes había que tipear el nombre del archivo a mano.
 *
 * Markup esperado (ver tariff/_photo_drop_field.html): un contenedor .tariff-photo-drop con
 * adentro un .tariff-photo-dropzone (clickeable/soltable), una <img class="tariff-photo-preview">
 * y un <span class="tariff-photo-placeholder">, más un <input type="file" class="tariff-photo-input">
 * oculto. El input real es el que viaja con el <form> normal al hacer submit — no hay AJAX
 * acá, es solo la interacción visual de arrastrar/cliquear + la vista previa.
 */
(function () {
  function showPreview(zone, src) {
    const img = zone.querySelector('.tariff-photo-preview');
    const placeholder = zone.querySelector('.tariff-photo-placeholder');
    if (src) {
      img.src = src;
      img.style.display = '';
      placeholder.style.display = 'none';
    } else {
      img.src = '';
      img.style.display = 'none';
      placeholder.style.display = '';
    }
  }

  function handleFiles(drop, files) {
    if (!files || !files.length) return;
    const file = files[0];
    if (!file.type || !file.type.startsWith('image/')) return;
    const input = drop.querySelector('.tariff-photo-input');
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;

    const reader = new FileReader();
    reader.onload = e => showPreview(drop, e.target.result);
    reader.readAsDataURL(file);
  }

  function initDrop(drop) {
    const zone = drop.querySelector('.tariff-photo-dropzone');
    const input = drop.querySelector('.tariff-photo-input');

    zone.addEventListener('click', () => input.click());
    zone.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
    });
    input.addEventListener('change', () => handleFiles(drop, input.files));

    ['dragenter', 'dragover'].forEach(evt => {
      zone.addEventListener(evt, e => {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.add('drag-over');
      });
    });
    ['dragleave', 'drop'].forEach(evt => {
      zone.addEventListener(evt, e => {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.remove('drag-over');
      });
    });
    zone.addEventListener('drop', e => handleFiles(drop, e.dataTransfer.files));
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.tariff-photo-drop').forEach(initDrop);
  });
})();
