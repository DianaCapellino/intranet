


document.addEventListener('DOMContentLoaded', () => {

    // Get the datatable style
    new DataTable('#trips', {
        language: {
            url: 'https://cdn.datatables.net/plug-ins/2.2.2/i18n/es-AR.json',
        },
    });

    // Display form when clicking plus sign
    const new_trip_btn = document.querySelector('#new_trip_btn');
    new_trip_btn.addEventListener("click", () => {
        document.querySelector('#new_trip').className = 'd-block';
        document.querySelector('#trip_list').className = 'd-none';
        document.querySelector('#new_trip_btn').className = 'd-none';

    });

})