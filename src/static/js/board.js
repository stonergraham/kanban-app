// Board.js - Kanban Board Functionality

// Create Card Modal
function showCreateCardModal(column) {
    const modal = document.getElementById('createCardModal');
    const columnInput = document.getElementById('cardColumn');
    const titleInput = document.getElementById('cardTitle');
    
    columnInput.value = column;
    titleInput.value = '';
    modal.classList.add('active');
    titleInput.focus();
}

function closeCreateCardModal() {
    const modal = document.getElementById('createCardModal');
    modal.classList.remove('active');
}

// Close modal when clicking outside
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('createCardModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeCreateCardModal();
            }
        });
    }
    
    // Close modal with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeCreateCardModal();
        }
    });
});

// Move Card Function
function moveCard(cardId, newColumn) {
    const formData = new FormData();
    formData.append('column', newColumn);
    
    fetch(`/card/${cardId}/move`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Reload the page to show updated card positions
            window.location.reload();
        } else {
            alert('Error moving card: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error moving card');
    });
}

// Drag and Drop (Basic - will enhance in Phase 3C)
document.addEventListener('DOMContentLoaded', function() {
    const cards = document.querySelectorAll('.card-item[draggable="true"]');
    const columns = document.querySelectorAll('.cards-list');
    
    cards.forEach(card => {
        card.addEventListener('dragstart', handleDragStart);
        card.addEventListener('dragend', handleDragEnd);
    });
    
    columns.forEach(column => {
        column.addEventListener('dragover', handleDragOver);
        column.addEventListener('drop', handleDrop);
        column.addEventListener('dragenter', handleDragEnter);
        column.addEventListener('dragleave', handleDragLeave);
    });
});

let draggedCard = null;

function handleDragStart(e) {
    draggedCard = this;
    this.style.opacity = '0.5';
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
}

function handleDragEnd(e) {
    this.style.opacity = '1';
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDragEnter(e) {
    this.classList.add('drag-over');
}

function handleDragLeave(e) {
    this.classList.remove('drag-over');
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }
    
    this.classList.remove('drag-over');
    
    if (draggedCard) {
        const cardId = draggedCard.dataset.cardId;
        const newColumn = this.id;
        
        if (newColumn && ['assigned', 'in_progress', 'complete'].includes(newColumn)) {
            moveCard(cardId, newColumn);
        }
    }
    
    return false;
}

console.log('Board.js loaded');
