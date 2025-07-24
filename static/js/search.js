$(document).ready(function() {

    // Hiding the navigation buttons on load
    $('#previous_button').hide();
    $('#next_button').hide();

    $('#searchInput').on('keypress', function (e) {
        if (e.which === 32 && this.value.trim() !== '') { //basing it on Space is only good for single word queries
            const queryText = this.value.trim();

            const $pill = $('<div/>').addClass('pill');

            // Add the query text as the pill content
            $pill.append(document.createTextNode(queryText));

            // Remove pill button
            const $remove = $('<span/>').addClass('remove').html('&times;');
            $remove.on('click', () => {
                $pill.remove();
                $(`.hit-item-${queryText}`).remove();
                search();
                setTimeout(() => {

                    if ($('#hit-list .hit-item').length === 0) {

                        $('#totalHits').empty();
                        $('#next_button').hide();
                        $('#previous_button').hide();
                        $('#display-pageNumber').empty();
                    }
                }, 10)

            });
            $pill.append($remove);

            $('#pillboxes').append($pill);

            this.value = '';
            e.preventDefault();           
            $('.pagination').data('pageNumber', 0);
            search();   
        }
    });

    //Form submission
    $("#searchForm").on("submit", function(event){
        event.preventDefault();

        // To keep track of the page number for the btns
        $('.pagination').data('pageNumber', 0);
        search();
    })

    // Update the page btns
    function updatePageNumber(elem) {
        const directionBtn = elem.id

            // Get the page number stored in pagination element
            let pageNumber = parseInt($('.pagination').data('pageNumber'));

            // Update page number based on the btn clicked
            if (directionBtn === 'previous_button') {
                if(pageNumber >= 1){
                    pageNumber = pageNumber - 1;
                    $('#display-pageNumber').empty();
                    $('#display-pageNumber').append(`Page ${pageNumber + 1}`);

                    if(pageNumber === 0 ){
                        $('#previous_button').hide();
                    }
                }else{
                    $('#previous_button').hide();
                    $('#display-pageNumber').append(`Page ${pageNumber - 1}`);
                }
            } else if (directionBtn === 'next_button') {
                pageNumber = pageNumber + 1
                $('#previous_button').show();
                $('#display-pageNumber').empty();
                $('#display-pageNumber').append(`Page ${pageNumber+1}`);
            }

            // Store the new page number in the pagination element
            $('.pagination').data('pageNumber', pageNumber);
            search();

    }

    $('.pagination').data('pageNumber', 0);

    // Update page num on click of a button
    $('#previous_button').on('click', function () {
        updatePageNumber(this);
    });
    $('#next_button').on('click', function () {
        updatePageNumber(this);
    });


///// Search function //////
    function search(){
        // FOR SINGLE SEARCH // 
        // const search_term = $("#searchInput").val();

        const pageNumber = $('.pagination').data('pageNumber');
        const offset = pageNumber * 15;

        const multiQueries = [];

        $('#pillboxes .pill').each(function () {
            const term = $(this).contents().get(0).textContent.trim();

            multiQueries.push({
                indexUid: 'PGS',
                query: term,
                "limit": 15,
                "offset": offset
            });
        });

        const requestData = {
            multi_queries: multiQueries
        }
        
        // Send to backend
        $.ajax({
            url: '/api/submit_search',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(requestData),

            success: function (response) {      
                $('#hit-list').empty(); // Empty the previous list

                let totalHitsCount = 0;

                // Put the response, aka the PGS, into a list on the html
                $(response.results).each(function(index, result) {
                    const term = result.query;
                    totalHitsCount += result.estimatedTotalHits;


                    $(result.hits).each(function(hitIndex, hit) {
                        const $li = $('<li/>').addClass(`hit-item hit-item-${term}`);

                        let fieldIndex = 0;
                        $.each(hit, function(key, value) {
                            if (key === '_federation') return;

                            if (fieldIndex === 0) {
                                $li.data('field0', value);
                            }


                            $li.append(
                                $('<div/>')
                                .addClass(`hit-field hit-field-${fieldIndex}`)
                                .html(`<strong class="hit-key">${key}:</strong> <span class="hit-value">${value}</span>`)
                            );
                            fieldIndex++;
                        });
                        $('#hit-list').append($li);
                    });
                });

                // Trying to handle different cases for the page buttons
                if(totalHitsCount < multiQueries[0].limit){
                    $('#next_button').hide();
                    $('#display-pageNumber').empty();
                }else{
                    $('#next_button').show();
                    $('#display-pageNumber').empty();
                    $('#display-pageNumber').append(`Page ${pageNumber +1}`);
                }

                if(totalHitsCount > 0){    
                    $('#totalHits').empty();
                    $('#totalHits').append( 
                        $('<div/>').html(`<strong id="hit-num">Total results:</strong> ${totalHitsCount}`)
                    );

                }else if($('#pillboxes .pill').length === 0){
                    $('#totalHits').empty();
                    $('#display-pageNumber').empty();
                    $('#next_button').hide();
                
                }else{
                    $('#totalHits').append("No results found");
                    $('#display-pageNumber').empty();
                    $('#next_button').hide();
                }


                // add the ID pills
                $(document).on('click', '.hit-item', function () {
                    const value = $(this).find('.hit-field-0 .hit-value').text();
                    
                    if ($(`#selectedIDs [data-id="${value}"]`).length === 0) {
                        const $IDs = $('<div/>')
                            .addClass('selected-id')
                            .attr('data-id', value)
                            .text(value);

                        const $removeID = $('<span/>')
                            .addClass('removeID')
                            .html('&times;')
                            .on('click', function () {
                                $IDs.remove();
                                $('.hit-item').each(function () {
                                    const itemValue = $(this).find('.hit-field-0 .hit-value').text();
                                    if (itemValue === value) {
                                        $(this).css('pointer-events', 'auto');
                                    }
                                });
                            });

                        
                        $IDs.append($removeID);
                        $('#selectedIDs').append($IDs);
                        $(this).css('pointer-events', 'none'); //disable clicking it once added

                    } else {
                        console.log(`ID "${value}" already added.`);
                    }
                });
            },
                error: function(errorThrown){
                console.log(errorThrown.responseText)
            }
        });
    }
});
