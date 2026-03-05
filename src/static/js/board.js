// Board.js - Enhanced Kanban Board Functionality

// Undo functionality
let lastMove = null;
let undoTimeout = null;

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

document.addEventListener('DOMContentLoaded', function() {
    // Initialize empty states
    updateEmptyStates();

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

    // Set up card content click-to-navigate
    document.querySelectorAll('.card-content[data-href]').forEach(el => {
        el.addEventListener('click', function() {
            window.location.href = this.dataset.href;
        });
    });

    // Set up move buttons
    document.querySelectorAll('.move-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const cardEl = this.closest('[data-card-id]');
            moveCard(cardEl.dataset.cardId, this.dataset.moveTo);
        });
    });

    // Set up drag and drop
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

// Move Card Function with Undo and Immediate Visual Update
function moveCard(cardId, newColumn) {
    const cardElement = document.querySelector(`[data-card-id="${cardId}"]`);
    const oldColumnElement = cardElement.closest('.cards-list');
    const oldColumn = oldColumnElement.id;

    // Store original parent for undo
    const originalParent = cardElement.parentElement;
    const originalNextSibling = cardElement.nextSibling;

    // Get target column
    const newColumnElement = document.getElementById(newColumn);
    if (!newColumnElement) {
        showToast('Error: Column not found', false);
        return;
    }

    // Remove card from old column
    cardElement.remove();

    // Hide empty state in new column if it exists
    const newEmptyState = newColumnElement.querySelector('.empty-column');
    if (newEmptyState) {
        newEmptyState.style.display = 'none';
    }

    // Add card to new column (at the top)
    newColumnElement.insertBefore(cardElement, newColumnElement.firstChild);

    // Update quick action buttons for the new column
    updateCardQuickActions(cardElement, newColumn);

    // Show empty state in old column if now empty
    const oldColumnCards = oldColumnElement.querySelectorAll('.card-item');
    if (oldColumnCards.length === 0) {
        const oldEmptyState = oldColumnElement.querySelector('.empty-column');
        if (oldEmptyState) {
            oldEmptyState.style.display = 'block';
        }
    }

    // Add animation
    cardElement.classList.add('card-moving');
    setTimeout(() => {
        cardElement.classList.remove('card-moving');
    }, 300);

    // Update server
    const formData = new FormData();
    formData.append('column', newColumn);

    fetch(`/card/${cardId}/move`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Store move for undo
            lastMove = {
                cardId: cardId,
                oldColumn: oldColumn,
                newColumn: newColumn,
                timestamp: Date.now(),
                cardElement: cardElement,
                originalParent: originalParent,
                originalNextSibling: originalNextSibling,
                oldColumnElement: oldColumnElement,
                newColumnElement: newColumnElement
            };

            // Show toast with undo option
            showToast(`Card moved to ${newColumn.replace('_', ' ')}`, true);

            // Set timeout to clear undo after 10 seconds
            if (undoTimeout) clearTimeout(undoTimeout);
            undoTimeout = setTimeout(() => {
                lastMove = null;
            }, 10000);

            // Update card counts
            updateCardCounts();

        } else {
            // Server rejected - move card back
            cardElement.remove();
            if (originalNextSibling) {
                originalParent.insertBefore(cardElement, originalNextSibling);
            } else {
                originalParent.appendChild(cardElement);
            }
            // Restore button state and empty states
            updateCardQuickActions(cardElement, oldColumn);
            updateEmptyStates();
            showToast('Error moving card: ' + (data.error || 'Unknown error'), false);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        // Move card back on error
        cardElement.remove();
        if (originalNextSibling) {
            originalParent.insertBefore(cardElement, originalNextSibling);
        } else {
            originalParent.appendChild(cardElement);
        }
        // Restore button state and empty states
        updateCardQuickActions(cardElement, oldColumn);
        updateEmptyStates();
        showToast('Error moving card', false);
    });
}

// Undo last move
function undoLastMove() {
    if (!lastMove) {
        showToast('Nothing to undo', false);
        return;
    }

    const timeSinceMove = Date.now() - lastMove.timestamp;
    if (timeSinceMove > 10000) {
        showToast('Undo expired (10 seconds)', false);
        lastMove = null;
        return;
    }

    // Remove card from current location
    const cardElement = lastMove.cardElement;
    cardElement.remove();

    // Hide empty state in old column
    const oldEmptyState = lastMove.oldColumnElement.querySelector('.empty-column');
    if (oldEmptyState) {
        oldEmptyState.style.display = 'none';
    }

    // Move card back to original location
    if (lastMove.originalNextSibling && lastMove.originalNextSibling.parentNode) {
        lastMove.originalParent.insertBefore(cardElement, lastMove.originalNextSibling);
    } else {
        lastMove.originalParent.appendChild(cardElement);
    }

    // Update quick action buttons for the old column
    updateCardQuickActions(cardElement, lastMove.oldColumn);

    // Show empty state in new column if now empty
    const newColumnCards = lastMove.newColumnElement.querySelectorAll('.card-item');
    if (newColumnCards.length === 0) {
        const newEmptyState = lastMove.newColumnElement.querySelector('.empty-column');
        if (newEmptyState) {
            newEmptyState.style.display = 'block';
        }
    }

    // Add animation
    cardElement.classList.add('card-moving');
    setTimeout(() => {
        cardElement.classList.remove('card-moving');
    }, 300);

    // Update server
    const formData = new FormData();
    formData.append('column', lastMove.oldColumn);

    fetch(`/card/${lastMove.cardId}/move`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Move undone', false);
            lastMove = null;

            // Update card counts
            updateCardCounts();

            // Remove toast
            const toast = document.querySelector('.toast');
            if (toast) {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }
        } else {
            // Server rejected undo - safest to reload
            showToast('Error undoing move', false);
            setTimeout(() => window.location.reload(), 1000);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Error undoing move', false);
        setTimeout(() => window.location.reload(), 1000);
    });
}

// Update card counts in column headers
function updateCardCounts() {
    const columns = document.querySelectorAll('.kanban-column');
    columns.forEach(column => {
        const cardsList = column.querySelector('.cards-list');
        const countBadge = column.querySelector('.card-count');
        if (cardsList && countBadge) {
            const cardCount = cardsList.querySelectorAll('.card-item').length;
            countBadge.textContent = cardCount;
        }
    });
}

// Update card quick action buttons based on column
function updateCardQuickActions(cardElement, columnId) {
    const quickActions = cardElement.querySelector('.card-quick-actions');
    if (!quickActions) return;

    quickActions.innerHTML = '';

    if (columnId === 'assigned') {
        const rightBtn = document.createElement('button');
        rightBtn.className = 'btn-icon';
        rightBtn.title = 'Move to In Progress';
        rightBtn.textContent = '→';
        rightBtn.onclick = function(e) {
            e.stopPropagation();
            moveCard(cardElement.dataset.cardId, 'in_progress');
        };
        quickActions.appendChild(rightBtn);

    } else if (columnId === 'in_progress') {
        const leftBtn = document.createElement('button');
        leftBtn.className = 'btn-icon';
        leftBtn.title = 'Move to Assigned';
        leftBtn.textContent = '←';
        leftBtn.onclick = function(e) {
            e.stopPropagation();
            moveCard(cardElement.dataset.cardId, 'assigned');
        };
        quickActions.appendChild(leftBtn);

        const rightBtn = document.createElement('button');
        rightBtn.className = 'btn-icon';
        rightBtn.title = 'Move to Complete';
        rightBtn.textContent = '→';
        rightBtn.onclick = function(e) {
            e.stopPropagation();
            moveCard(cardElement.dataset.cardId, 'complete');
        };
        quickActions.appendChild(rightBtn);

    } else if (columnId === 'complete') {
        const leftBtn = document.createElement('button');
        leftBtn.className = 'btn-icon';
        leftBtn.title = 'Move to In Progress';
        leftBtn.textContent = '←';
        leftBtn.onclick = function(e) {
            e.stopPropagation();
            moveCard(cardElement.dataset.cardId, 'in_progress');
        };
        quickActions.appendChild(leftBtn);
    }
}

// Update empty state visibility for all columns
function updateEmptyStates() {
    const columns = document.querySelectorAll('.cards-list');
    columns.forEach(column => {
        const cards = column.querySelectorAll('.card-item');
        const emptyState = column.querySelector('.empty-column');

        if (emptyState) {
            emptyState.style.display = cards.length === 0 ? 'block' : 'none';
        }
    });
}

// Toast Notification System
function showToast(message, showUndo = false) {
    // Remove existing toast
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `
        <span class="toast-message">${message}</span>
        ${showUndo ? '<button class="toast-undo" onclick="undoLastMove()">Undo</button>' : ''}
    `;
    
    document.body.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    // Auto-hide after 10 seconds (or 5 if no undo)
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, showUndo ? 10000 : 5000);
}

let draggedCard = null;

function handleDragStart(e) {
    draggedCard = this;
    this.classList.add('dragging');
    this.style.opacity = '0.5';
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
}

function handleDragEnd(e) {
    this.classList.remove('dragging');
    this.style.opacity = '1';
    
    // Remove all drag-over classes
    document.querySelectorAll('.cards-list').forEach(col => {
        col.classList.remove('drag-over');
    });
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDragEnter(e) {
    if (this.classList.contains('cards-list')) {
        this.classList.add('drag-over');
    }
}

function handleDragLeave(e) {
    // Only remove if actually leaving the element
    if (e.target === this) {
        this.classList.remove('drag-over');
    }
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
            // moveCard will handle the visual update now
            moveCard(cardId, newColumn);
        }

        // Reset draggedCard after move
        draggedCard = null;
    }

    return false;
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl+Z or Cmd+Z for undo
    if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault();
        undoLastMove();
    }
});

console.log('Enhanced Board.js loaded');