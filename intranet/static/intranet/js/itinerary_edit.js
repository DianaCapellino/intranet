(function () {
    const csrfToken = () => document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';

    document.addEventListener('DOMContentLoaded', function () {
        const $days = $('#itinerary-days');

        // ── Copiar link público ────────────────────────────────────────────────
        $('#it-copy-link').on('click', function () {
            const $input = $('#it-public-url');
            $input.trigger('select');
            navigator.clipboard?.writeText($input.val()).then(() => {
                const $btn = $(this);
                const original = $btn.html();
                $btn.html('<i class="fa-solid fa-check"></i>');
                setTimeout(() => $btn.html(original), 1200);
            });
        });

        // ── Publicar / despublicar ─────────────────────────────────────────────
        $('#it-published').on('change', function () {
            const published = this.checked;
            fetch(window.ITINERARY_PUBLISH_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
                body: JSON.stringify({ published }),
            }).catch(() => {});
        });

        // ── Actualizar desde Tourplan (pisa lo editado a mano) ──────────────────
        // .off() antes de .on() por las dudas de que este script se ejecute más de una vez
        // en la página (evita que el modal/confirmación quede disparándose dos veces).
        const resyncModalEl = document.getElementById('resyncConfirmModal');
        const resyncModal = resyncModalEl ? new bootstrap.Modal(resyncModalEl) : null;

        $('#it-resync-btn').off('click').on('click', function () {
            resyncModal?.show();
        });

        $('#resync-confirm-btn').off('click').on('click', function () {
            resyncModal?.hide();
            const $btn = $('#it-resync-btn');
            const original = $btn.html();
            $btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm me-1"></span>Actualizando…');

            fetch(window.ITINERARY_RESYNC_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            })
                .then(r => r.json())
                .then(data => {
                    if (data.ok) {
                        location.reload();
                    } else {
                        alert(data.error || 'No se pudo actualizar desde Tourplan.');
                        $btn.prop('disabled', false).html(original);
                    }
                })
                .catch(() => {
                    alert('No se pudo actualizar desde Tourplan.');
                    $btn.prop('disabled', false).html(original);
                });
        });

        // ── Agregar / eliminar días ─────────────────────────────────────────────
        $('#add-day-btn').on('click', function () {
            const tpl = document.getElementById('day-template');
            $days.append(tpl.content.cloneNode(true));
        });

        $days.on('click', '.remove-day-btn', function () {
            $(this).closest('.itinerary-day').remove();
        });

        // ── Agregar / eliminar ítems ─────────────────────────────────────────────
        $days.on('click', '.add-line-btn', function () {
            const tpl = document.getElementById('line-template');
            $(this).closest('.card-body').find('.itinerary-lines').append(tpl.content.cloneNode(true));
        });

        $days.on('click', '.remove-line-btn', function () {
            $(this).closest('.itinerary-line').remove();
        });

        // ── Subida de fotos (portada / día / ítem) ──────────────────────────────
        $(document).on('change', '.itinerary-upload-input', function () {
            const file = this.files[0];
            if (!file) return;
            const $group = $(this).closest('.image-upload-group');
            const $urlInput = $group.find('.image-url-input');
            const $label = $(this).closest('label');
            const originalIcon = $label.html();
            $label.html('<span class="spinner-border spinner-border-sm"></span>');

            const formData = new FormData();
            formData.append('photo', file);
            fetch(window.ITINERARY_UPLOAD_URL, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken() },
                body: formData,
            })
                .then(r => r.json())
                .then(data => {
                    if (data.url) $urlInput.val(data.url);
                })
                .finally(() => {
                    $label.html(originalIcon);
                    $label.find('.itinerary-upload-input').val('');
                });
        });

        // ── Guardar ──────────────────────────────────────────────────────────────
        $('#save-itinerary-btn').on('click', function () {
            const $btn = $(this);
            const $feedback = $('#save-feedback');

            const days = $('.itinerary-day').map(function () {
                const $day = $(this);
                const lines = $day.find('.itinerary-line').map(function () {
                    const $line = $(this);
                    return {
                        service_code: $line.find('.line-service-code').val(),
                        supplier_code: $line.find('.line-supplier-code').val(),
                        option_code: $line.find('.line-option-code').val(),
                        location_code: $line.find('.line-location-code').val(),
                        location_name: $line.find('.line-location-name').val(),
                        supplier_name: $line.find('.line-supplier-name').val(),
                        title_note: $line.find('.line-title-note').val(),
                        option_description: $line.find('.line-option-description').val(),
                        room_summary: $line.find('.line-room-summary').val(),
                        nights: $line.find('.line-nights').val() || null,
                        conditions_note: $line.find('.line-conditions').val(),
                        is_optional: $line.find('.line-is-optional').is(':checked'),
                        custom_title: $line.find('.line-title').val(),
                        custom_description: $line.find('.line-description').val(),
                        image_url: $line.find('.line-image').val(),
                        image_url_2: $line.find('.line-image-2').val(),
                        image_url_3: $line.find('.line-image-3').val(),
                        amount: $line.find('.line-amount').val() || null,
                    };
                }).get();

                return {
                    date: $day.find('.day-date').val(),
                    title: $day.find('.day-title').val(),
                    description: $day.find('.day-description').val(),
                    image_url: $day.find('.day-image').val(),
                    lines,
                };
            }).get();

            const payload = {
                title: $('#it-title').val(),
                intro_text: $('#it-intro').val(),
                cover_image_url: $('#it-cover-image').val(),
                show_prices: $('#it-show-prices').is(':checked'),
                currency: $('#it-currency').val(),
                total_amount: $('#it-total-amount').val() || null,
                important_comments: $('#it-important-comments').val(),
                prepayments_required: $('#it-prepayments').val(),
                pax_count: $('#it-pax-count').val() || null,
                consultant_name: $('#it-consultant-name').val(),
                trip_style: $('#it-trip-style').val(),
                sustainability_note: $('#it-sustainability-note').val(),
                days,
            };

            $btn.prop('disabled', true);
            $feedback.text('Guardando…').removeClass('text-danger text-success');

            fetch(window.ITINERARY_SAVE_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
                body: JSON.stringify(payload),
            })
                .then(r => r.json())
                .then(data => {
                    if (data.ok) {
                        $feedback.text('Guardado ✓').addClass('text-success');
                        setTimeout(() => location.reload(), 600);
                    } else {
                        $feedback.text(data.error || 'Error al guardar').addClass('text-danger');
                        $btn.prop('disabled', false);
                    }
                })
                .catch(() => {
                    $feedback.text('Error al guardar').addClass('text-danger');
                    $btn.prop('disabled', false);
                });
        });
    });
})();
