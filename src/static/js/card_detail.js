// Card Detail Page JavaScript

const CARD_ID = parseInt(window.location.pathname.split('/card/')[1]);

// Checklist Functions
function showAddChecklistItem() {
    document.getElementById('addChecklistForm').style.display = 'block';
    document.getElementById('newChecklistText').focus();
}

function cancelAddChecklistItem() {
    document.getElementById('addChecklistForm').style.display = 'none';
    document.getElementById('newChecklistText').value = '';
}

function addChecklistItem(parentId = null, level = 0) {
    const text = document.getElementById('newChecklistText').value.trim();
    if (!text) return;
    
    const formData = new FormData();
    formData.append('text', text);
    if (parentId) formData.append('parent_id', parentId);
    formData.append('level', level);
    
    fetch(`/card/${CARD_ID}/checklist/add`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            alert('Error: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error adding checklist item');
    });
}

function toggleChecklistItem(itemId) {
    fetch(`/checklist/${itemId}/toggle`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const text = document.getElementById(`checklist-text-${itemId}`);
            if (data.completed) {
                text.classList.add('completed');
            } else {
                text.classList.remove('completed');
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function editChecklistItemInline(itemId) {
    const textSpan = document.getElementById(`checklist-text-${itemId}`);
    const currentText = textSpan.textContent.trim();
    
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentText;
    input.className = 'checklist-edit-input';
    
    input.onblur = function() {
        saveChecklistEdit(itemId, input.value, textSpan);
    };
    
    input.onkeydown = function(e) {
        if (e.key === 'Enter') {
            saveChecklistEdit(itemId, input.value, textSpan);
        } else if (e.key === 'Escape') {
            textSpan.textContent = currentText;
            input.replaceWith(textSpan);
        }
    };
    
    textSpan.replaceWith(input);
    input.focus();
    input.select();
}

function saveChecklistEdit(itemId, newText, originalSpan) {
    if (!newText.trim()) {
        alert('Text cannot be empty');
        return;
    }
    
    const formData = new FormData();
    formData.append('text', newText);
    
    fetch(`/checklist/${itemId}/edit`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function deleteChecklistItem(itemId) {
    if (!confirm('Delete this checklist item?')) return;
    
    fetch(`/checklist/${itemId}/delete`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function indentChecklistItem(itemId, direction) {
    const formData = new FormData();
    formData.append('direction', direction);
    
    fetch(`/checklist/${itemId}/indent`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

// Comment Functions
function editComment(commentId) {
    const textDiv = document.getElementById(`comment-text-${commentId}`);
    const currentText = textDiv.textContent.trim();
    
    const textarea = document.createElement('textarea');
    textarea.value = currentText;
    textarea.className = 'comment-edit-textarea';
    textarea.rows = 3;
    
    const actions = document.createElement('div');
    actions.className = 'form-actions';
    actions.style.marginTop = '0.5rem';
    
    const saveBtn = document.createElement('button');
    saveBtn.textContent = 'Save';
    saveBtn.className = 'btn btn-sm btn-primary';
    saveBtn.onclick = function() {
        saveCommentEdit(commentId, textarea.value, textDiv);
    };
    
    const cancelBtn = document.createElement('button');
    cancelBtn.textContent = 'Cancel';
    cancelBtn.className = 'btn btn-sm btn-secondary';
    cancelBtn.onclick = function() {
        textDiv.textContent = currentText;
        textarea.remove();
        actions.remove();
    };
    
    actions.appendChild(saveBtn);
    actions.appendChild(cancelBtn);
    
    textDiv.textContent = '';
    textDiv.appendChild(textarea);
    textDiv.appendChild(actions);
    textarea.focus();
}

function saveCommentEdit(commentId, newText, originalDiv) {
    if (!newText.trim()) {
        alert('Comment cannot be empty');
        return;
    }
    
    const formData = new FormData();
    formData.append('text', newText);
    
    fetch(`/comment/${commentId}/edit`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error saving comment');
    });
}

// Bulk Add Checklist Items
function showBulkAddChecklist() {
    document.getElementById('bulkAddChecklistForm').style.display = 'block';
    document.getElementById('addChecklistForm').style.display = 'none';
    document.getElementById('bulkChecklistText').focus();
}

function cancelBulkAddChecklist() {
    document.getElementById('bulkAddChecklistForm').style.display = 'none';
    document.getElementById('bulkChecklistText').value = '';
}

async function addBulkChecklistItems() {
    const text = document.getElementById('bulkChecklistText').value.trim();
    if (!text) return;

    // Parse items — split by newlines, then by commas within each line
    const items = [];
    text.split('\n').forEach(line => {
        line = line.trim();
        if (!line) return;
        if (line.includes(',')) {
            line.split(',').map(s => s.trim()).filter(Boolean).forEach(s => items.push(s));
        } else {
            items.push(line);
        }
    });

    if (items.length === 0) {
        alert('No items found. Please enter at least one item.');
        return;
    }

    let successCount = 0;
    let errorCount = 0;

    for (const itemText of items) {
        const formData = new FormData();
        formData.append('text', itemText);
        formData.append('level', 0);

        try {
            const response = await fetch(`/card/${CARD_ID}/checklist/add`, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (data.success) { successCount++; } else { errorCount++; }
        } catch (error) {
            console.error('Error adding item:', error);
            errorCount++;
        }
    }

    if (errorCount > 0) {
        alert(`Added ${successCount} items. ${errorCount} failed.`);
    }
    window.location.reload();
}

// Checklist Drag and Drop
let draggedChecklistItem = null;

function handleChecklistDragStart(e) {
    draggedChecklistItem = e.currentTarget;
    e.currentTarget.style.opacity = '0.5';
    e.dataTransfer.effectAllowed = 'move';
}

function handleChecklistDragEnd(e) {
    e.currentTarget.style.opacity = '1';
    document.querySelectorAll('.checklist-item').forEach(item => {
        item.classList.remove('drag-over');
    });
}

function handleChecklistDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const target = e.currentTarget;
    if (target !== draggedChecklistItem) {
        target.classList.add('drag-over');
    }
    return false;
}

function handleChecklistDrop(e) {
    e.stopPropagation();
    const target = e.currentTarget;
    target.classList.remove('drag-over');

    if (!draggedChecklistItem || target === draggedChecklistItem) return false;

    const draggedLevel = parseInt(draggedChecklistItem.dataset.level);
    const targetLevel = parseInt(target.dataset.level);

    if (draggedLevel !== targetLevel) {
        alert('Can only reorder items at the same indentation level');
        return false;
    }

    const parent = target.parentNode;
    const rect = target.getBoundingClientRect();
    const midpoint = rect.top + (rect.height / 2);

    if (e.clientY < midpoint) {
        parent.insertBefore(draggedChecklistItem, target);
    } else {
        parent.insertBefore(draggedChecklistItem, target.nextSibling);
    }

    updateChecklistPositions();
    return false;
}

function updateChecklistPositions() {
    const positions = [];
    document.querySelectorAll('.checklist-item').forEach((item, index) => {
        positions.push({ id: parseInt(item.dataset.itemId), position: index });
    });

    fetch(`/card/${CARD_ID}/checklist/reorder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ positions: positions })
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            console.error('Failed to update positions');
            window.location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        window.location.reload();
    });
}

// Move to Board
function moveCardToBoard() {
    const boardId = document.getElementById('moveToBoardSelect').value;
    const column = document.getElementById('moveToColumnSelect').value;

    if (!boardId) {
        alert('Please select a board');
        return;
    }

    fetch(`/card/${CARD_ID}/move-to-board`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ board_id: parseInt(boardId), column: column })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.href = data.redirect;
        } else {
            alert('Error: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error moving card');
    });
}

console.log('Card detail page loaded');
