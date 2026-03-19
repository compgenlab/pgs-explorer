/**
 * PGS ID Autocomplete Widget
 * Replaces a <select> with a text input that autocompletes on PGS ID and trait name.
 *
 * Usage:
 *   const ac = initPgsAutocomplete({
 *       inputId:   'pgsIdSearch',   // visible text input id
 *       hiddenId:  'pgsId',         // hidden input id (holds the selected PGS ID value)
 *       dropdownId:'pgsIdDropdown', // dropdown container id
 *   });
 *   ac.refresh();  // reload data from API (e.g. after DB switch)
 */
function initPgsAutocomplete(options) {
    const inputId    = options.inputId    || 'pgsIdSearch';
    const hiddenId   = options.hiddenId   || 'pgsId';
    const dropdownId = options.dropdownId || 'pgsIdDropdown';

    let pgsData = [];

    // ---- Data loading ----
    function loadData(callback) {
        $.get('/api/pgs_and_trait_list', function(data) {
            pgsData = data.pgs || [];
            if (callback) callback();
        }).fail(function() {
            console.error('PGS autocomplete: failed to load PGS list');
        });
    }

    // ---- Filtering ----
    function filterData(query) {
        if (!query || !query.trim()) {
            return pgsData.slice(0, 30);
        }
        const q = query.trim().toLowerCase();
        return pgsData.filter(function(pgs) {
            return pgs.id.toLowerCase().includes(q) ||
                   (pgs.trait && pgs.trait.toLowerCase().includes(q));
        }).slice(0, 50);
    }

    // ---- Dropdown rendering ----
    function renderDropdown(items) {
        const $dd = $('#' + dropdownId);
        $dd.empty();
        if (items.length === 0) {
            $dd.append('<div class="pgs-item pgs-no-match">No matches found</div>');
        } else {
            items.forEach(function(pgs) {
                const trait = pgs.trait || '';
                $dd.append(
                    $('<div class="pgs-item">')
                        .attr('data-pgs-id', pgs.id)
                        .attr('data-pgs-trait', trait)
                        .append($('<span class="pgs-id">').text(pgs.id))
                        .append(trait ? $('<span class="pgs-trait">').text(' \u2013 ' + trait) : '')
                );
            });
        }
        $dd.show();
    }

    function hideDropdown() {
        $('#' + dropdownId).hide();
    }

    // ---- Selection ----
    function selectPgs(pgsId, pgsTrait) {
        const display = pgsTrait ? pgsId + ' \u2013 ' + pgsTrait : pgsId;
        $('#' + inputId).val(display);
        const $hidden = $('#' + hiddenId);
        $hidden.val(pgsId);
        $hidden.trigger('change');
        hideDropdown();
    }

    // ---- Keyboard navigation helpers ----
    function getItems() {
        return $('#' + dropdownId + ' .pgs-item:not(.pgs-no-match)');
    }

    function getActive() {
        return getItems().filter('.active');
    }

    // ---- Event bindings ----

    // Text input: filter on typing
    $(document).on('input', '#' + inputId, function() {
        const query = $(this).val();
        // Clear hidden value when user edits the text
        $('#' + hiddenId).val('');
        if (!query.trim()) {
            hideDropdown();
            return;
        }
        renderDropdown(filterData(query));
    });

    // Text input: show dropdown on focus
    $(document).on('focus', '#' + inputId, function() {
        const query = $(this).val();
        if (!$('#' + hiddenId).val()) {
            renderDropdown(filterData(query));
        }
    });

    // Item click: select
    $(document).on('click', '#' + dropdownId + ' .pgs-item', function() {
        const pgsId = $(this).data('pgs-id');
        const pgsTrait = $(this).data('pgs-trait');
        if (pgsId) {
            selectPgs(pgsId, pgsTrait);
        }
    });

    // Click outside: hide dropdown
    $(document).on('click.pgsAc', function(e) {
        if (!$(e.target).closest('#' + inputId).length &&
            !$(e.target).closest('#' + dropdownId).length) {
            hideDropdown();
        }
    });

    // Keyboard navigation
    $(document).on('keydown', '#' + inputId, function(e) {
        const $dd = $('#' + dropdownId);
        if (!$dd.is(':visible')) return;

        const $items = getItems();
        const $active = getActive();

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if ($active.length === 0) {
                $items.first().addClass('active');
            } else {
                const $next = $active.next('.pgs-item');
                $active.removeClass('active');
                ($next.length ? $next : $items.first()).addClass('active');
            }
            scrollActiveIntoView();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if ($active.length === 0) {
                $items.last().addClass('active');
            } else {
                const $prev = $active.prev('.pgs-item');
                $active.removeClass('active');
                ($prev.length ? $prev : $items.last()).addClass('active');
            }
            scrollActiveIntoView();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if ($active.length > 0) {
                selectPgs($active.data('pgs-id'), $active.data('pgs-trait'));
            }
        } else if (e.key === 'Escape') {
            hideDropdown();
        }
    });

    function scrollActiveIntoView() {
        const $active = getActive();
        if ($active.length) {
            const $dd = $('#' + dropdownId);
            const itemTop = $active.position().top + $dd.scrollTop();
            const itemBottom = itemTop + $active.outerHeight();
            const ddHeight = $dd.outerHeight();
            if (itemBottom > $dd.scrollTop() + ddHeight) {
                $dd.scrollTop(itemBottom - ddHeight);
            } else if (itemTop < $dd.scrollTop()) {
                $dd.scrollTop(itemTop);
            }
        }
    }

    // ---- Public API ----
    const api = {
        refresh: function() {
            loadData(function() {
                // Re-render if dropdown is open
                const $dd = $('#' + dropdownId);
                if ($dd.is(':visible')) {
                    renderDropdown(filterData($('#' + inputId).val()));
                }
            });
            // Clear selection
            $('#' + inputId).val('');
            $('#' + hiddenId).val('');
        },
        getValue: function() {
            return $('#' + hiddenId).val();
        }
    };

    // Initial load
    loadData();

    return api;
}
